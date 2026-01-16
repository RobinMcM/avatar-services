"""
Avatar Service Worker - Processes TTS and lip-sync jobs from the queue.
"""
import os
import sys
import json
import time
import signal
import traceback
from typing import Optional

import redis
import structlog

from tts import synthesize_speech
from lipsync import extract_mouth_cues, generate_eye_events
from capture_processor import process_capture_job

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Environment configuration
VALKEY_HOST = os.getenv("VALKEY_HOST", "localhost")
VALKEY_PORT = int(os.getenv("VALKEY_PORT", "6379"))
DATA_DIR = os.getenv("DATA_DIR", "/data")
PIPER_MODEL = os.getenv("PIPER_MODEL", "/opt/piper/voices/en_US-lessac-medium.onnx")

# Queue keys
JOB_QUEUE_KEY = "avatar:jobs"
CAPTURE_JOB_QUEUE_KEY = "avatar:capture:jobs"
RESULT_KEY_PREFIX = "avatar:result:"
CACHE_KEY_PREFIX = "avatar:cache:"

# TTLs
RESULT_TTL_SECONDS = 3600  # 1 hour
CACHE_TTL_SECONDS = 86400 * 7  # 7 days

# Worker state
running = True


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global running
    logger.info("shutdown_signal_received", signal=signum)
    running = False


def get_voice_model_path(voice_id: str) -> str:
    """Get the full path to a voice model."""
    voices_dir = os.path.dirname(PIPER_MODEL)
    model_path = os.path.join(voices_dir, f"{voice_id}.onnx")
    
    if os.path.exists(model_path):
        return model_path
    
    # Fall back to default model
    logger.warning("voice_not_found", voice_id=voice_id, using_default=PIPER_MODEL)
    return PIPER_MODEL


def process_job(job_data: dict, redis_client: redis.Redis) -> dict:
    """
    Process a single render job.
    
    Args:
        job_data: Job data from the queue
        redis_client: Redis client for storing results
    
    Returns:
        Result dictionary
    """
    render_id = job_data["render_id"]
    cache_key = job_data["cache_key"]
    text = job_data["text"]
    voice_id = job_data["voice_id"]
    speed = job_data.get("speed", 1.0)
    audio_base_url = job_data.get("audio_base_url", "http://localhost:8080/audio")
    
    start_time = time.time()
    logger.info("processing_job", render_id=render_id, text_length=len(text))
    
    # Update status to processing
    update_result_status(redis_client, render_id, "processing")
    
    try:
        # Step 1: Synthesize speech
        voice_model = get_voice_model_path(voice_id)
        tts_result = synthesize_speech(
            text=text,
            output_filename=render_id,
            voice_model=voice_model,
            speed=speed,
        )
        
        audio_filename = tts_result["output_filename"]
        audio_path = tts_result["output_path"]
        duration_ms = tts_result["duration_ms"]
        
        # Step 2: Extract mouth cues
        # For OGG files, we need to convert back to WAV for Rhubarb
        # (Rhubarb only supports WAV format)
        if audio_path.endswith('.ogg'):
            import subprocess
            wav_temp = audio_path.replace('.ogg', '_temp.wav')
            subprocess.run([
                'ffmpeg', '-y', '-i', audio_path, wav_temp
            ], capture_output=True, timeout=30)
            mouth_cues = extract_mouth_cues(wav_temp, text=text)
            os.remove(wav_temp)
        else:
            mouth_cues = extract_mouth_cues(audio_path, text=text)
        
        # Step 3: Generate eye events
        eye_events = generate_eye_events(duration_ms, text)
        
        # Build audio URL
        audio_url = f"{audio_base_url}/{audio_filename}"
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # Build result
        result = {
            "render_id": render_id,
            "status": "completed",
            "audio_url": audio_url,
            "duration_ms": duration_ms,
            "mouth_cues": mouth_cues,
            "eye_events": eye_events,
            "cached": False,
            "error": None,
            "processing_time_ms": processing_time_ms,
        }
        
        logger.info(
            "job_completed",
            render_id=render_id,
            duration_ms=duration_ms,
            mouth_cue_count=len(mouth_cues),
            eye_event_count=len(eye_events),
            processing_time_ms=processing_time_ms,
        )
        
        return result
    
    except Exception as e:
        logger.error(
            "job_failed",
            render_id=render_id,
            error=str(e),
            traceback=traceback.format_exc(),
        )
        
        return {
            "render_id": render_id,
            "status": "failed",
            "audio_url": None,
            "duration_ms": None,
            "mouth_cues": None,
            "eye_events": None,
            "cached": False,
            "error": str(e),
            "processing_time_ms": int((time.time() - start_time) * 1000),
        }


def update_result_status(redis_client: redis.Redis, render_id: str, status: str):
    """Update the status of a render job."""
    key = f"{RESULT_KEY_PREFIX}{render_id}"
    current = redis_client.get(key)
    if current:
        data = json.loads(current)
        data["status"] = status
        redis_client.setex(key, RESULT_TTL_SECONDS, json.dumps(data))


def store_result(redis_client: redis.Redis, result: dict, cache_key: str):
    """Store the render result and cache it."""
    render_id = result["render_id"]
    
    # Store result
    result_key = f"{RESULT_KEY_PREFIX}{render_id}"
    redis_client.setex(result_key, RESULT_TTL_SECONDS, json.dumps(result))
    
    # Cache if successful
    if result["status"] == "completed":
        redis_client.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(result))
        logger.debug("result_cached", cache_key=cache_key)
    
    # Notify waiters
    notify_key = f"avatar:notify:{render_id}"
    redis_client.lpush(notify_key, "ready")
    redis_client.expire(notify_key, 60)


def run_worker():
    """Main worker loop."""
    global running
    
    # Set up signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    logger.info(
        "worker_starting",
        valkey_host=VALKEY_HOST,
        valkey_port=VALKEY_PORT,
    )
    
    # Connect to Valkey
    redis_client = redis.Redis(
        host=VALKEY_HOST,
        port=VALKEY_PORT,
        decode_responses=True,
    )
    
    # Test connection
    try:
        redis_client.ping()
        logger.info("connected_to_valkey")
    except redis.ConnectionError as e:
        logger.error("valkey_connection_failed", error=str(e))
        sys.exit(1)
    
    # Main processing loop
    while running:
        try:
            # Check both queues (render and capture)
            result = redis_client.brpop([JOB_QUEUE_KEY, CAPTURE_JOB_QUEUE_KEY], timeout=5)
            
            if result is None:
                # Timeout, no jobs available
                continue
            
            queue_key, job_json = result
            job_data = json.loads(job_json)
            
            # Determine job type
            job_type = job_data.get('type', 'render')
            
            if job_type == 'capture_processing':
                # Handle capture processing job
                logger.info("processing_capture_job", job_id=job_data.get('job_id'))
                capture_result = process_capture_job(job_data, redis_client)
                
                # Update final status
                job_id = job_data['job_id']
                status_key = f"avatar:capture:status:{job_id}"
                status_data = json.loads(redis_client.get(status_key) or '{}')
                status_data.update(capture_result)
                redis_client.set(status_key, json.dumps(status_data), ex=3600)
                
            else:
                # Handle render job
                render_id = job_data["render_id"]
                
                # Check if result already exists (avoid reprocessing)
                existing = redis_client.get(f"{RESULT_KEY_PREFIX}{render_id}")
                if existing:
                    existing_data = json.loads(existing)
                    if existing_data.get("status") in ["completed", "failed"]:
                        logger.info("skipping_already_processed", render_id=render_id)
                        continue
                
                # Process the job
                result = process_job(job_data, redis_client)
                
                # Store result and cache
                store_result(redis_client, result, job_data["cache_key"])
        
        except redis.ConnectionError as e:
            logger.error("valkey_connection_error", error=str(e))
            time.sleep(5)  # Wait before reconnecting
            try:
                redis_client.ping()
            except:
                redis_client = redis.Redis(
                    host=VALKEY_HOST,
                    port=VALKEY_PORT,
                    decode_responses=True,
                )
        
        except Exception as e:
            logger.error("worker_error", error=str(e), traceback=traceback.format_exc())
            time.sleep(1)
    
    logger.info("worker_stopped")
    redis_client.close()


if __name__ == "__main__":
    run_worker()
