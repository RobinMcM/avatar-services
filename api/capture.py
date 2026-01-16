"""
Capture Studio API endpoints.
Handles video upload and processing for avatar pack generation.
"""
import os
import uuid
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
import structlog

from models import (
    CaptureUploadResponse,
    CaptureProcessRequest,
    CaptureProcessResponse,
    CaptureJobStatus
)
from valkey import get_valkey_client

logger = structlog.get_logger()

# Configuration
DATA_DIR = os.getenv("DATA_DIR", "/data")
CAPTURES_DIR = os.path.join(DATA_DIR, "captures")
AVATARS_DIR = os.path.join(DATA_DIR, "avatars")

# Valkey keys
CAPTURE_JOB_QUEUE_KEY = "avatar:capture:jobs"
CAPTURE_JOB_STATUS_PREFIX = "avatar:capture:status:"

# Ensure directories exist
os.makedirs(CAPTURES_DIR, exist_ok=True)
os.makedirs(AVATARS_DIR, exist_ok=True)

# Create router
router = APIRouter(prefix="/v1/capture", tags=["capture"])


@router.post("/upload", response_model=CaptureUploadResponse)
async def upload_capture(
    video: UploadFile = File(..., description="Recorded video file"),
    avatar_id: str = Form(..., description="Avatar identifier")
):
    """
    Upload a captured video for processing.
    
    Returns a capture_id to use for processing.
    """
    try:
        # Validate avatar_id
        if not avatar_id.replace('_', '').isalnum():
            raise HTTPException(status_code=400, detail="Avatar ID must be alphanumeric with underscores only")
        
        # Generate capture ID
        capture_id = str(uuid.uuid4())
        
        # Save uploaded file
        file_path = os.path.join(CAPTURES_DIR, f"{capture_id}.webm")
        
        # Read and save file
        file_size = 0
        with open(file_path, 'wb') as f:
            while chunk := await video.read(8192):
                f.write(chunk)
                file_size += len(chunk)
        
        # Validate file size
        min_size = 100 * 1024  # 100KB minimum
        max_size = 500 * 1024 * 1024  # 500MB maximum
        
        if file_size < min_size:
            os.remove(file_path)
            raise HTTPException(status_code=400, detail=f"File too small ({file_size} bytes). Minimum {min_size} bytes.")
        
        if file_size > max_size:
            os.remove(file_path)
            raise HTTPException(status_code=400, detail=f"File too large ({file_size} bytes). Maximum {max_size} bytes.")
        
        logger.info(
            "capture_uploaded",
            capture_id=capture_id,
            avatar_id=avatar_id,
            file_size=file_size,
            filename=video.filename
        )
        
        return CaptureUploadResponse(
            capture_id=capture_id,
            filename=video.filename or f"{capture_id}.webm",
            size_bytes=file_size
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("upload_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/process", response_model=CaptureProcessResponse)
async def process_capture(request: CaptureProcessRequest):
    """
    Start processing a captured video into an avatar pack.
    
    Returns a job_id to poll for status.
    """
    try:
        # Validate capture exists
        capture_path = os.path.join(CAPTURES_DIR, f"{request.capture_id}.webm")
        if not os.path.exists(capture_path):
            raise HTTPException(status_code=404, detail="Capture not found")
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Create job payload
        job_data = {
            'job_id': job_id,
            'capture_id': request.capture_id,
            'avatar_id': request.avatar_id,
            'capture_path': capture_path,
            'avatars_dir': AVATARS_DIR,
            'type': 'capture_processing'
        }
        
        # Store initial status
        valkey_client = get_valkey_client()
        status_key = f"{CAPTURE_JOB_STATUS_PREFIX}{job_id}"
        
        initial_status = {
            'job_id': job_id,
            'status': 'queued',
            'progress': 0,
            'avatar_id': request.avatar_id,
            'logs': ['Job queued']
        }
        
        await valkey_client.set_json(status_key, initial_status, ttl=3600)
        
        # Queue job
        await valkey_client.push_job(CAPTURE_JOB_QUEUE_KEY, job_data)
        
        logger.info(
            "capture_job_queued",
            job_id=job_id,
            capture_id=request.capture_id,
            avatar_id=request.avatar_id
        )
        
        return CaptureProcessResponse(
            job_id=job_id,
            status="queued"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("process_start_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start processing: {str(e)}")


@router.get("/jobs/{job_id}", response_model=CaptureJobStatus)
async def get_job_status(job_id: str):
    """
    Get the status of a capture processing job.
    """
    try:
        valkey_client = get_valkey_client()
        status_key = f"{CAPTURE_JOB_STATUS_PREFIX}{job_id}"
        
        # Get status from Valkey
        status_data = await valkey_client.get_json(status_key)
        
        if not status_data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return CaptureJobStatus(**status_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("status_fetch_failed", job_id=job_id, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch status: {str(e)}")
