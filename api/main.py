"""
Avatar Service API - FastAPI application.
Provides endpoints for synchronous and asynchronous avatar rendering.
"""
import os
import time
import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from models import (
    RenderRequest,
    RenderResponse,
    AsyncRenderResponse,
    HealthResponse,
    ErrorResponse,
    RenderStatus,
)
from valkey import (
    init_valkey,
    close_valkey,
    get_valkey_client,
    ValkeyClient,
)

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
AUDIO_BASE_URL = os.getenv("AUDIO_BASE_URL", "http://localhost:8080/audio")
SYNC_TIMEOUT_SECONDS = int(os.getenv("SYNC_TIMEOUT_SECONDS", "60"))
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "10"))

# Simple concurrency limiter
_active_requests = 0
_request_lock = asyncio.Lock()


async def check_concurrency_limit():
    """Check if we're under the concurrency limit."""
    global _active_requests
    async with _request_lock:
        if _active_requests >= MAX_CONCURRENT_REQUESTS:
            return False
        _active_requests += 1
        return True


async def release_concurrency_slot():
    """Release a concurrency slot."""
    global _active_requests
    async with _request_lock:
        _active_requests = max(0, _active_requests - 1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("starting_avatar_api", valkey_host=VALKEY_HOST, valkey_port=VALKEY_PORT)
    await init_valkey(VALKEY_HOST, VALKEY_PORT)
    yield
    # Shutdown
    logger.info("shutting_down_avatar_api")
    await close_valkey()


# Create FastAPI app
app = FastAPI(
    title="Avatar Service API",
    description="API for generating TTS audio and lip-sync animation data for 2D avatars",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include capture studio router
from capture import router as capture_router
app.include_router(capture_router)


# Dependency to get Valkey client
async def get_valkey() -> ValkeyClient:
    return get_valkey_client()


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check(valkey: ValkeyClient = Depends(get_valkey)):
    """Health check endpoint."""
    try:
        is_healthy = await valkey.is_healthy()
        queue_length = await valkey.get_queue_length() if is_healthy else 0
        return HealthResponse(
            status="healthy" if is_healthy else "unhealthy",
            valkey_connected=is_healthy,
            pending_jobs=queue_length,
        )
    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        return HealthResponse(status="unhealthy", valkey_connected=False, pending_jobs=0)


@app.post(
    "/v1/avatar/render",
    response_model=RenderResponse,
    responses={
        429: {"model": ErrorResponse, "description": "Too many requests"},
        504: {"model": ErrorResponse, "description": "Render timeout"},
    },
    tags=["Render"],
)
async def render_sync(
    request: RenderRequest,
    valkey: ValkeyClient = Depends(get_valkey),
):
    """
    Synchronous render endpoint.
    Waits for the worker to complete rendering before returning.
    """
    start_time = time.time()
    
    # Check concurrency limit
    if not await check_concurrency_limit():
        raise HTTPException(
            status_code=429,
            detail="Too many concurrent requests. Please try again later.",
        )
    
    try:
        # Generate cache key and check cache
        cache_key = valkey.generate_cache_key(
            request.voice_id, request.speed, request.text
        )
        
        cached_result = await valkey.get_cached_result(cache_key)
        if cached_result:
            logger.info("serving_cached_result", cache_key=cache_key)
            cached_result["cached"] = True
            return RenderResponse(**cached_result)
        
        # Generate render ID and enqueue job
        render_id = valkey.generate_render_id(
            request.voice_id, request.speed, request.text
        )
        
        job_data = {
            "render_id": render_id,
            "cache_key": cache_key,
            "text": request.text,
            "voice_id": request.voice_id,
            "speed": request.speed,
            "audio_base_url": AUDIO_BASE_URL,
        }
        
        await valkey.enqueue_job(job_data)
        logger.info("job_enqueued_sync", render_id=render_id)
        
        # Wait for result
        result = await valkey.wait_for_result(render_id, timeout_seconds=SYNC_TIMEOUT_SECONDS)
        
        if result is None:
            logger.warning("render_timeout", render_id=render_id)
            raise HTTPException(
                status_code=504,
                detail=f"Render timed out after {SYNC_TIMEOUT_SECONDS} seconds",
            )
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        result["processing_time_ms"] = processing_time_ms
        result["cached"] = False
        
        logger.info(
            "render_completed",
            render_id=render_id,
            processing_time_ms=processing_time_ms,
        )
        
        return RenderResponse(**result)
    
    finally:
        await release_concurrency_slot()


@app.post(
    "/v1/avatar/render_async",
    response_model=AsyncRenderResponse,
    responses={
        429: {"model": ErrorResponse, "description": "Too many requests"},
    },
    tags=["Render"],
)
async def render_async(
    request: RenderRequest,
    http_request: Request,
    valkey: ValkeyClient = Depends(get_valkey),
):
    """
    Asynchronous render endpoint.
    Returns immediately with a render_id for polling.
    """
    # Generate cache key and check cache
    cache_key = valkey.generate_cache_key(
        request.voice_id, request.speed, request.text
    )
    
    cached_result = await valkey.get_cached_result(cache_key)
    if cached_result:
        logger.info("serving_cached_result_async", cache_key=cache_key)
        # Return the cached result's render_id for immediate retrieval
        render_id = cached_result.get("render_id", cache_key.split(":")[-1])
        # Store result for polling
        await valkey.set_result(render_id, cached_result)
        
        base_url = str(http_request.base_url).rstrip("/")
        return AsyncRenderResponse(
            render_id=render_id,
            status=RenderStatus.COMPLETED,
            poll_url=f"{base_url}/v1/avatar/render/{render_id}",
        )
    
    # Generate render ID and enqueue job
    render_id = valkey.generate_render_id(
        request.voice_id, request.speed, request.text
    )
    
    job_data = {
        "render_id": render_id,
        "cache_key": cache_key,
        "text": request.text,
        "voice_id": request.voice_id,
        "speed": request.speed,
        "audio_base_url": AUDIO_BASE_URL,
    }
    
    # Store initial pending status
    await valkey.set_result(render_id, {
        "render_id": render_id,
        "status": RenderStatus.PENDING.value,
    })
    
    await valkey.enqueue_job(job_data)
    logger.info("job_enqueued_async", render_id=render_id)
    
    base_url = str(http_request.base_url).rstrip("/")
    return AsyncRenderResponse(
        render_id=render_id,
        status=RenderStatus.PENDING,
        poll_url=f"{base_url}/v1/avatar/render/{render_id}",
    )


@app.get(
    "/v1/avatar/render/{render_id}",
    response_model=RenderResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Render not found"},
    },
    tags=["Render"],
)
async def get_render_status(
    render_id: str,
    valkey: ValkeyClient = Depends(get_valkey),
):
    """
    Get the status/result of an async render job.
    Poll this endpoint until status is 'completed' or 'failed'.
    """
    result = await valkey.get_result(render_id)
    
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Render {render_id} not found",
        )
    
    return RenderResponse(**result)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error("unhandled_exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
