"""
Valkey (Redis-compatible) connection and job queue utilities.
"""
import json
import hashlib
from typing import Optional, Any
from contextlib import asynccontextmanager

import redis.asyncio as redis
import structlog

logger = structlog.get_logger()

# Queue and cache key prefixes
JOB_QUEUE_KEY = "avatar:jobs"
RESULT_KEY_PREFIX = "avatar:result:"
CACHE_KEY_PREFIX = "avatar:cache:"
PROCESSING_KEY_PREFIX = "avatar:processing:"

# TTLs
RESULT_TTL_SECONDS = 3600  # 1 hour
CACHE_TTL_SECONDS = 86400 * 7  # 7 days
PROCESSING_TTL_SECONDS = 120  # 2 minutes


class ValkeyClient:
    """Async Valkey/Redis client wrapper."""
    
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self._pool: Optional[redis.ConnectionPool] = None
        self._client: Optional[redis.Redis] = None
    
    async def connect(self) -> None:
        """Establish connection to Valkey."""
        self._pool = redis.ConnectionPool(
            host=self.host,
            port=self.port,
            decode_responses=True,
            max_connections=20
        )
        self._client = redis.Redis(connection_pool=self._pool)
        # Test connection
        await self._client.ping()
        logger.info("connected_to_valkey", host=self.host, port=self.port)
    
    async def disconnect(self) -> None:
        """Close connection to Valkey."""
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()
        logger.info("disconnected_from_valkey")
    
    @property
    def client(self) -> redis.Redis:
        """Get the Redis client instance."""
        if not self._client:
            raise RuntimeError("Valkey client not connected")
        return self._client
    
    @staticmethod
    def generate_cache_key(voice_id: str, speed: float, text: str) -> str:
        """Generate a cache key from render parameters."""
        content = f"{voice_id}:{speed:.2f}:{text}"
        hash_digest = hashlib.sha256(content.encode()).hexdigest()[:16]
        return f"{CACHE_KEY_PREFIX}{hash_digest}"
    
    @staticmethod
    def generate_render_id(voice_id: str, speed: float, text: str) -> str:
        """Generate a unique render ID."""
        import time
        content = f"{voice_id}:{speed:.2f}:{text}:{time.time_ns()}"
        return hashlib.sha256(content.encode()).hexdigest()[:24]
    
    async def get_cached_result(self, cache_key: str) -> Optional[dict]:
        """Get a cached render result."""
        data = await self.client.get(cache_key)
        if data:
            logger.debug("cache_hit", cache_key=cache_key)
            return json.loads(data)
        logger.debug("cache_miss", cache_key=cache_key)
        return None
    
    async def set_cached_result(self, cache_key: str, result: dict) -> None:
        """Cache a render result."""
        await self.client.setex(
            cache_key,
            CACHE_TTL_SECONDS,
            json.dumps(result)
        )
        logger.debug("cache_set", cache_key=cache_key)
    
    async def enqueue_job(self, job_data: dict) -> None:
        """Add a job to the processing queue."""
        await self.client.lpush(JOB_QUEUE_KEY, json.dumps(job_data))
        logger.info("job_enqueued", render_id=job_data.get("render_id"))
    
    async def set_result(self, render_id: str, result: dict) -> None:
        """Store a render result."""
        key = f"{RESULT_KEY_PREFIX}{render_id}"
        await self.client.setex(key, RESULT_TTL_SECONDS, json.dumps(result))
        logger.debug("result_stored", render_id=render_id)
    
    async def get_result(self, render_id: str) -> Optional[dict]:
        """Get a render result by ID."""
        key = f"{RESULT_KEY_PREFIX}{render_id}"
        data = await self.client.get(key)
        if data:
            return json.loads(data)
        return None
    
    async def wait_for_result(self, render_id: str, timeout_seconds: int = 60) -> Optional[dict]:
        """Wait for a render result with blocking."""
        key = f"{RESULT_KEY_PREFIX}{render_id}"
        
        # Use BRPOP on a notification channel for the specific render
        notify_key = f"avatar:notify:{render_id}"
        
        # First check if result already exists
        result = await self.get_result(render_id)
        if result:
            return result
        
        # Wait for notification
        try:
            notification = await self.client.brpop(notify_key, timeout=timeout_seconds)
            if notification:
                return await self.get_result(render_id)
        except Exception as e:
            logger.error("wait_for_result_error", error=str(e))
        
        return None
    
    async def notify_result_ready(self, render_id: str) -> None:
        """Notify that a render result is ready."""
        notify_key = f"avatar:notify:{render_id}"
        await self.client.lpush(notify_key, "ready")
        await self.client.expire(notify_key, 60)  # Clean up after 60s
    
    async def set_processing(self, render_id: str) -> bool:
        """Mark a render as being processed. Returns True if set, False if already processing."""
        key = f"{PROCESSING_KEY_PREFIX}{render_id}"
        result = await self.client.set(key, "1", ex=PROCESSING_TTL_SECONDS, nx=True)
        return result is not None
    
    async def clear_processing(self, render_id: str) -> None:
        """Clear the processing flag for a render."""
        key = f"{PROCESSING_KEY_PREFIX}{render_id}"
        await self.client.delete(key)
    
    async def get_queue_length(self) -> int:
        """Get the current job queue length."""
        return await self.client.llen(JOB_QUEUE_KEY)
    
    async def is_healthy(self) -> bool:
        """Check if Valkey connection is healthy."""
        try:
            await self.client.ping()
            return True
        except Exception:
            return False
    
    async def set_json(self, key: str, data: dict, ttl: Optional[int] = None) -> None:
        """Store JSON data in Valkey."""
        import json as json_module
        await self._client.set(key, json_module.dumps(data), ex=ttl)
    
    async def get_json(self, key: str) -> Optional[dict]:
        """Retrieve JSON data from Valkey."""
        import json as json_module
        data = await self._client.get(key)
        if data:
            return json_module.loads(data)
        return None
    
    async def push_job(self, queue_key: str, job_data: dict) -> None:
        """Push a job to a queue."""
        import json as json_module
        await self._client.rpush(queue_key, json_module.dumps(job_data))


# Singleton instance
_valkey_client: Optional[ValkeyClient] = None


def get_valkey_client() -> ValkeyClient:
    """Get the global Valkey client instance."""
    global _valkey_client
    if _valkey_client is None:
        raise RuntimeError("Valkey client not initialized")
    return _valkey_client


async def init_valkey(host: str, port: int) -> ValkeyClient:
    """Initialize the global Valkey client."""
    global _valkey_client
    _valkey_client = ValkeyClient(host, port)
    await _valkey_client.connect()
    return _valkey_client


async def close_valkey() -> None:
    """Close the global Valkey client."""
    global _valkey_client
    if _valkey_client:
        await _valkey_client.disconnect()
        _valkey_client = None
