"""
Lip sync extraction module using Rhubarb Lip Sync.
"""
import os
import json
import random
import subprocess
import tempfile
import re
from typing import Optional
import structlog

logger = structlog.get_logger()

# Rhubarb configuration
RHUBARB_BINARY = os.getenv("RHUBARB_BINARY", "rhubarb")

# Rhubarb viseme to simple viseme mapping
# Rhubarb outputs: A, B, C, D, E, F, G, H, X (rest)
# We map to a simplified set that works well for 2D avatar sprites
VISEME_MAP = {
    "A": "AA",    # Jaw open (ah, uh)
    "B": "EE",    # Closed mouth narrow (b, m, p)
    "C": "EE",    # Open mouth narrow (eh, ae)
    "D": "AA",    # Open mouth wide (ai, ay)
    "E": "OH",    # Rounded lips (oh, ow)
    "F": "OO",    # Tight rounded (oo, w)
    "G": "FF",    # Upper teeth on lower lip (f, v)
    "H": "TH",    # Tongue between teeth (l, th)
    "X": "REST",  # Rest/silence
}

# All visemes used in our system
VISEME_SET = ["REST", "AA", "EE", "OH", "OO", "FF", "TH"]


def extract_mouth_cues(
    audio_path: str,
    text: Optional[str] = None,
    dialog_file: Optional[str] = None,
) -> list[dict]:
    """
    Extract mouth animation cues from audio using Rhubarb Lip Sync.
    
    Args:
        audio_path: Path to the audio file
        text: Optional transcript text for better accuracy
        dialog_file: Optional path to dialog file
    
    Returns:
        List of mouth cue dictionaries with t_ms, viseme, and weight
    """
    logger.info("extracting_mouth_cues", audio_path=audio_path)
    
    # Build command
    cmd = [
        RHUBARB_BINARY,
        "-f", "json",
        "-r", "phonetic",  # Use phonetic recognizer (no dialog needed)
    ]
    
    # If text is provided, create a temporary dialog file
    temp_dialog = None
    if text:
        try:
            temp_dialog = tempfile.NamedTemporaryFile(
                mode='w', suffix='.txt', delete=False
            )
            temp_dialog.write(text)
            temp_dialog.close()
            cmd.extend(["-d", temp_dialog.name])
        except Exception as e:
            logger.warning("dialog_file_creation_failed", error=str(e))
    elif dialog_file:
        cmd.extend(["-d", dialog_file])
    
    cmd.append(audio_path)
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        
        if result.returncode != 0:
            logger.error(
                "rhubarb_failed",
                stderr=result.stderr,
                returncode=result.returncode,
            )
            raise RuntimeError(f"Rhubarb failed: {result.stderr}")
        
        # Parse JSON output
        rhubarb_data = json.loads(result.stdout)
        mouth_cues = parse_rhubarb_output(rhubarb_data)
        
        logger.info("mouth_cues_extracted", cue_count=len(mouth_cues))
        return mouth_cues
    
    except subprocess.TimeoutExpired:
        logger.error("rhubarb_timeout")
        raise RuntimeError("Rhubarb lip sync timed out")
    except json.JSONDecodeError as e:
        logger.error("rhubarb_json_parse_error", error=str(e))
        raise RuntimeError(f"Failed to parse Rhubarb output: {e}")
    finally:
        # Clean up temporary dialog file
        if temp_dialog and os.path.exists(temp_dialog.name):
            try:
                os.remove(temp_dialog.name)
            except:
                pass


def parse_rhubarb_output(rhubarb_data: dict) -> list[dict]:
    """
    Parse Rhubarb JSON output into our mouth cue format.
    
    Rhubarb output format:
    {
        "metadata": {...},
        "mouthCues": [
            {"start": 0.0, "end": 0.5, "value": "X"},
            {"start": 0.5, "end": 0.8, "value": "A"},
            ...
        ]
    }
    """
    mouth_cues = []
    raw_cues = rhubarb_data.get("mouthCues", [])
    
    for cue in raw_cues:
        start_ms = int(cue["start"] * 1000)
        end_ms = int(cue["end"] * 1000)
        rhubarb_viseme = cue["value"]
        
        # Map to our viseme set
        viseme = VISEME_MAP.get(rhubarb_viseme, "REST")
        
        # Calculate weight based on duration (longer = more emphasis)
        duration_ms = end_ms - start_ms
        weight = min(1.0, 0.5 + (duration_ms / 500))  # Scale weight by duration
        
        mouth_cues.append({
            "t_ms": start_ms,
            "viseme": viseme,
            "weight": round(weight, 2),
        })
        
        # Add end cue if there's a gap to next cue (for smooth interpolation)
        # This helps with transitions back to rest position
    
    return mouth_cues


def generate_eye_events(
    duration_ms: int,
    text: str,
) -> list[dict]:
    """
    Generate eye animation events (blinks and saccades).
    
    Blinks occur:
    - Every 3-6 seconds naturally
    - At punctuation marks (periods, commas, etc.)
    
    Saccades (eye movements) occur:
    - Subtly every 1-3 seconds
    """
    events = []
    
    # Natural blinks every 3-6 seconds
    current_time = random.randint(500, 1500)  # Start after a small delay
    while current_time < duration_ms - 200:
        events.append({
            "t_ms": current_time,
            "event_type": "blink",
            "duration_ms": random.randint(100, 200),
            "direction": None,
        })
        # Next blink in 3-6 seconds
        current_time += random.randint(3000, 6000)
    
    # Punctuation-aware blinks
    punctuation_pattern = r'[.!?,;:]'
    matches = list(re.finditer(punctuation_pattern, text))
    
    if matches and duration_ms > 0:
        # Estimate timing based on text position
        text_len = len(text)
        for match in matches:
            # Calculate approximate time based on character position
            char_pos = match.start()
            approx_time_ms = int((char_pos / text_len) * duration_ms)
            
            # Add slight delay after punctuation
            blink_time = approx_time_ms + random.randint(100, 300)
            
            if blink_time < duration_ms - 200:
                # Avoid duplicate blinks (within 500ms of existing)
                is_duplicate = any(
                    abs(e["t_ms"] - blink_time) < 500 
                    for e in events if e["event_type"] == "blink"
                )
                if not is_duplicate:
                    events.append({
                        "t_ms": blink_time,
                        "event_type": "blink",
                        "duration_ms": random.randint(120, 180),
                        "direction": None,
                    })
    
    # Subtle saccades (eye movements)
    saccade_time = random.randint(1000, 2000)
    saccade_directions = ["left", "right", "up", "down", "center"]
    
    while saccade_time < duration_ms - 300:
        events.append({
            "t_ms": saccade_time,
            "event_type": "saccade",
            "duration_ms": random.randint(200, 400),
            "direction": random.choice(saccade_directions),
        })
        # Next saccade in 1-3 seconds
        saccade_time += random.randint(1000, 3000)
    
    # Sort by time
    events.sort(key=lambda e: e["t_ms"])
    
    logger.info(
        "eye_events_generated",
        blink_count=len([e for e in events if e["event_type"] == "blink"]),
        saccade_count=len([e for e in events if e["event_type"] == "saccade"]),
    )
    
    return events


def get_viseme_set() -> list[str]:
    """Return the set of visemes used by this system."""
    return VISEME_SET.copy()
