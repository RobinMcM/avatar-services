"""
Text-to-Speech module using Piper TTS.
"""
import os
import subprocess
import tempfile
from typing import Optional
import structlog

logger = structlog.get_logger()

# Piper configuration
PIPER_BINARY = os.getenv("PIPER_BINARY", "piper")
PIPER_MODEL = os.getenv("PIPER_MODEL", "/opt/piper/voices/en_US-lessac-medium.onnx")
DATA_DIR = os.getenv("DATA_DIR", "/data")
AUDIO_DIR = os.path.join(DATA_DIR, "audio")


def ensure_audio_dir():
    """Ensure the audio directory exists."""
    os.makedirs(AUDIO_DIR, exist_ok=True)


def synthesize_speech(
    text: str,
    output_filename: str,
    voice_model: Optional[str] = None,
    speed: float = 1.0,
) -> dict:
    """
    Synthesize speech from text using Piper TTS.
    
    Args:
        text: The text to synthesize
        output_filename: Base filename for output (without extension)
        voice_model: Path to voice model, uses default if not specified
        speed: Speech speed multiplier (0.5 to 2.0)
    
    Returns:
        Dictionary with output_path, duration_ms, and format
    """
    ensure_audio_dir()
    
    model_path = voice_model or PIPER_MODEL
    
    # Output paths - generate WAV first, then convert to OGG
    wav_path = os.path.join(AUDIO_DIR, f"{output_filename}.wav")
    ogg_path = os.path.join(AUDIO_DIR, f"{output_filename}.ogg")
    
    logger.info(
        "synthesizing_speech",
        text_length=len(text),
        voice_model=model_path,
        speed=speed,
    )
    
    try:
        # Calculate length scale (inverse of speed for Piper)
        length_scale = 1.0 / speed
        
        # Run Piper TTS
        cmd = [
            PIPER_BINARY,
            "--model", model_path,
            "--output_file", wav_path,
            "--length_scale", str(length_scale),
        ]
        
        process = subprocess.run(
            cmd,
            input=text,
            capture_output=True,
            text=True,
            timeout=120,
        )
        
        if process.returncode != 0:
            logger.error("piper_failed", stderr=process.stderr, returncode=process.returncode)
            raise RuntimeError(f"Piper TTS failed: {process.stderr}")
        
        # Verify WAV was created
        if not os.path.exists(wav_path):
            raise RuntimeError("Piper did not create output file")
        
        # Get WAV duration using ffprobe
        duration_ms = get_audio_duration_ms(wav_path)
        
        # Convert to OGG/Opus for smaller file size
        convert_success = convert_to_ogg(wav_path, ogg_path)
        
        if convert_success and os.path.exists(ogg_path):
            # Use OGG file
            os.remove(wav_path)  # Clean up WAV
            final_path = ogg_path
            audio_format = "ogg"
            final_filename = f"{output_filename}.ogg"
        else:
            # Fall back to WAV
            final_path = wav_path
            audio_format = "wav"
            final_filename = f"{output_filename}.wav"
        
        file_size = os.path.getsize(final_path)
        
        logger.info(
            "speech_synthesized",
            output_path=final_path,
            duration_ms=duration_ms,
            format=audio_format,
            file_size_bytes=file_size,
        )
        
        return {
            "output_path": final_path,
            "output_filename": final_filename,
            "duration_ms": duration_ms,
            "format": audio_format,
            "file_size_bytes": file_size,
        }
    
    except subprocess.TimeoutExpired:
        logger.error("piper_timeout")
        raise RuntimeError("Piper TTS timed out")
    except Exception as e:
        logger.error("synthesis_failed", error=str(e))
        # Clean up partial files
        for path in [wav_path, ogg_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass
        raise


def get_audio_duration_ms(audio_path: str) -> int:
    """Get audio duration in milliseconds using ffprobe."""
    try:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            duration_seconds = float(result.stdout.strip())
            return int(duration_seconds * 1000)
    except Exception as e:
        logger.warning("ffprobe_failed", error=str(e))
    
    # Fallback: estimate from file size (rough approximation for 22050Hz 16-bit mono)
    file_size = os.path.getsize(audio_path)
    estimated_duration = (file_size - 44) / (22050 * 2)  # Subtract header, 22050 Hz, 2 bytes/sample
    return max(int(estimated_duration * 1000), 100)


def convert_to_ogg(wav_path: str, ogg_path: str) -> bool:
    """Convert WAV to OGG/Opus using ffmpeg."""
    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-i", wav_path,
            "-c:a", "libopus",
            "-b:a", "48k",
            "-vbr", "on",
            "-compression_level", "10",
            ogg_path,
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        return result.returncode == 0
    except Exception as e:
        logger.warning("ogg_conversion_failed", error=str(e))
        return False


def get_available_voices() -> list[dict]:
    """List available voice models."""
    voices_dir = os.path.dirname(PIPER_MODEL)
    voices = []
    
    if os.path.exists(voices_dir):
        for filename in os.listdir(voices_dir):
            if filename.endswith(".onnx"):
                voice_id = filename.replace(".onnx", "")
                voices.append({
                    "voice_id": voice_id,
                    "path": os.path.join(voices_dir, filename),
                })
    
    return voices
