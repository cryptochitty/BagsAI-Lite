"""
Cache service: Redis if available, falls back to in-memory TTL cache.
"""
import time
import json
import logging
from typing import Any, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

# In-memory fallback store
_memory_cache: dict[str, tuple[Any, float]] = {}


class CacheService:
    def __init__(self):
        self._redis = None
        self._ttl = settings.CACHE_TTL
        self._try_connect_redis()

    def _try_connect_redis(self):
        if not settings.REDIS_URL:
            logger.info("No REDIS_URL configured, using in-memory cache")
            return
        try:
            import redis
            self._redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
            self._redis.ping()
            logger.info("Connected to Redis cache")
        except Exception as e:
            logger.warning(f"Redis unavailable ({e}), falling back to in-memory cache")
            self._redis = None

    def get(self, key: str) -> Optional[Any]:
        if self._redis:
            try:
                val = self._redis.get(key)
                if val:
                    return json.loads(val)
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")

        # In-memory fallback
        entry = _memory_cache.get(key)
        if entry:
            value, expiry = entry
            if time.time() < expiry:
                return value
            else:
                del _memory_cache[key]
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        ttl = ttl or self._ttl
        if self._redis:
            try:
                self._redis.setex(key, ttl, json.dumps(value, default=str))
                return
            except Exception as e:
                logger.warning(f"Redis set failed: {e}")

        _memory_cache[key] = (value, time.time() + ttl)

    def delete(self, key: str) -> None:
        if self._redis:
            try:
                self._redis.delete(key)
            except Exception:
                pass
        _memory_cache.pop(key, None)

    def flush(self) -> None:
        if self._redis:
            try:
                self._redis.flushdb()
            except Exception:
                pass
        _memory_cache.clear()


# Singleton
cache = CacheService()
