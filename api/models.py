"""
Pydantic models for the Avatar Service API.
"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class RenderStatus(str, Enum):
    """Status of a render job."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class VoiceId(str, Enum):
    """Available voice options."""
    EN_US_LESSAC = "en_US-lessac-medium"
    EN_US_AMY = "en_US-amy-medium"
    EN_US_RYAN = "en_US-ryan-medium"
    EN_GB_ALAN = "en_GB-alan-medium"


class MouthCue(BaseModel):
    """A single mouth animation cue."""
    t_ms: int = Field(..., description="Timestamp in milliseconds")
    viseme: str = Field(..., description="Viseme identifier (A-X or rest)")
    weight: float = Field(default=1.0, ge=0.0, le=1.0, description="Animation weight")


class EyeEvent(BaseModel):
    """An eye animation event (blink or saccade)."""
    t_ms: int = Field(..., description="Timestamp in milliseconds")
    event_type: str = Field(..., description="Event type: blink, saccade")
    duration_ms: int = Field(default=150, description="Event duration in milliseconds")
    direction: Optional[str] = Field(default=None, description="Saccade direction if applicable")


class RenderRequest(BaseModel):
    """Request to render avatar animation from text."""
    text: str = Field(..., min_length=1, max_length=5000, description="Text to synthesize")
    voice_id: str = Field(default="en_US-lessac-medium", description="Voice model identifier")
    speed: float = Field(default=1.0, ge=0.5, le=2.0, description="Speech speed multiplier")
    
    @field_validator('text')
    @classmethod
    def clean_text(cls, v: str) -> str:
        """Clean and validate input text."""
        v = v.strip()
        if not v:
            raise ValueError("Text cannot be empty")
        return v


class RenderResponse(BaseModel):
    """Response containing rendered avatar animation data."""
    render_id: str = Field(..., description="Unique render identifier")
    status: RenderStatus = Field(..., description="Current render status")
    audio_url: Optional[str] = Field(default=None, description="URL to audio file")
    duration_ms: Optional[int] = Field(default=None, description="Audio duration in milliseconds")
    mouth_cues: Optional[list[MouthCue]] = Field(default=None, description="Mouth animation cues")
    eye_events: Optional[list[EyeEvent]] = Field(default=None, description="Eye animation events")
    cached: bool = Field(default=False, description="Whether result was served from cache")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    processing_time_ms: Optional[int] = Field(default=None, description="Processing time in ms")


class AsyncRenderResponse(BaseModel):
    """Response for async render request."""
    render_id: str = Field(..., description="Unique render identifier for polling")
    status: RenderStatus = Field(default=RenderStatus.PENDING, description="Initial status")
    poll_url: str = Field(..., description="URL to poll for results")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(default="healthy")
    valkey_connected: bool = Field(default=False)
    pending_jobs: int = Field(default=0)


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(default=None, description="Detailed error info")


# Capture Studio Models

class CaptureUploadResponse(BaseModel):
    """Response from capture video upload."""
    capture_id: str = Field(..., description="Unique capture identifier")
    filename: str = Field(..., description="Uploaded filename")
    size_bytes: int = Field(..., description="File size in bytes")


class CaptureProcessRequest(BaseModel):
    """Request to process a captured video."""
    capture_id: str = Field(..., description="Capture ID from upload")
    avatar_id: str = Field(..., description="Avatar identifier")


class CaptureProcessResponse(BaseModel):
    """Response from starting capture processing."""
    job_id: str = Field(..., description="Processing job identifier")
    status: str = Field(default="queued", description="Initial job status")


class CaptureJobStatus(BaseModel):
    """Status of a capture processing job."""
    job_id: str = Field(..., description="Job identifier")
    status: str = Field(..., description="Job status: queued, processing, completed, failed")
    progress: Optional[int] = Field(None, description="Progress percentage (0-100)")
    avatar_id: Optional[str] = Field(None, description="Avatar ID being generated")
    manifest_url: Optional[str] = Field(None, description="URL to generated manifest.json")
    zip_url: Optional[str] = Field(None, description="URL to download avatar pack ZIP")
    error: Optional[str] = Field(None, description="Error message if failed")
    logs: Optional[list] = Field(None, description="Processing logs")
