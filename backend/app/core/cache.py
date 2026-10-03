import json
import time
import logging
from typing import Any, Optional, Callable, Dict
from functools import wraps
import threading
import redis
from app.core.config import settings

logger = logging.getLogger("codesphere.cache")

class InMemoryCache:
    """Thread-safe in-memory cache with TTL support for fallback when Redis is unavailable."""
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            if entry["expires_at"] and time.time() > entry["expires_at"]:
                del self._store[key]
                return None
            return entry["value"]

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        expires_at = (time.time() + ttl) if ttl else None
        with self._lock:
            self._store[key] = {
                "value": value,
                "expires_at": expires_at
            }
        return True

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def delete_pattern(self, pattern: str) -> int:
        import fnmatch
        with self._lock:
            keys_to_del = [k for k in self._store.keys() if fnmatch.fnmatch(k, pattern)]
            for k in keys_to_del:
                del self._store[k]
            return len(keys_to_del)

    def flush(self):
        with self._lock:
            self._store.clear()

    def size(self) -> int:
        now = time.time()
        with self._lock:
            expired = [k for k, v in self._store.items() if v["expires_at"] and now > v["expires_at"]]
            for k in expired:
                del self._store[k]
            return len(self._store)


class CacheManager:
    RECONNECT_COOLDOWN_SECONDS = 15.0

    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.in_memory_fallback = InMemoryCache()
        self.is_redis_available = False
        self._last_connect_attempt: float = 0.0
        self._reconnect_lock = threading.Lock()
        self._init_redis()

    def _init_redis(self):
        if not settings.CACHE_ENABLED:
            logger.info("Caching is disabled via configuration.")
            return

        self._last_connect_attempt = time.time()
        try:
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=0.75,
                socket_connect_timeout=0.75,
                retry_on_timeout=False,
                max_connections=50
            )
            # Test connection ping
            self.redis_client.ping()
            self.is_redis_available = True
            logger.info(f"[REDIS CONNECTED] Successfully connected to Redis backend at {settings.REDIS_URL}.")
        except Exception as e:
            self.is_redis_available = False
            logger.warning(
                f"[REDIS UNAVAILABLE — FALLBACK ACTIVE] Redis unreachable at {settings.REDIS_URL} ({e}). "
                "Thread-safe in-memory cache activated."
            )

    def _try_reconnect(self) -> bool:
        """
        Non-blocking, rate-limited reconnection check to recover Redis connectivity when restored.
        """
        if not settings.CACHE_ENABLED:
            return False
        
        now = time.time()
        if now - self._last_connect_attempt < self.RECONNECT_COOLDOWN_SECONDS:
            return False

        with self._reconnect_lock:
            if now - self._last_connect_attempt < self.RECONNECT_COOLDOWN_SECONDS:
                return False
            self._last_connect_attempt = now

            try:
                if not self.redis_client:
                    self.redis_client = redis.from_url(
                        settings.REDIS_URL,
                        decode_responses=True,
                        socket_timeout=0.75,
                        socket_connect_timeout=0.75,
                        retry_on_timeout=False,
                        max_connections=50
                    )
                self.redis_client.ping()
                if not self.is_redis_available:
                    self.is_redis_available = True
                    logger.info(f"[REDIS RECONNECTED] Connection to Redis at {settings.REDIS_URL} re-established. Resuming distributed cache.")
                return True
            except Exception:
                self.is_redis_available = False
                return False

    def get(self, key: str) -> Optional[Any]:
        if not settings.CACHE_ENABLED:
            return None
        full_key = f"{settings.CACHE_PREFIX}{key}"
        
        if not self.is_redis_available:
            self._try_reconnect()

        if self.is_redis_available and self.redis_client:
            try:
                data = self.redis_client.get(full_key)
                if data:
                    return json.loads(data)
                return None
            except Exception as e:
                logger.warning(f"Redis GET failed for key {key}: {e}. Switching to in-memory fallback.")
                self.is_redis_available = False
                self._last_connect_attempt = time.time()

        return self.in_memory_fallback.get(full_key)

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        if not settings.CACHE_ENABLED:
            return False
        full_key = f"{settings.CACHE_PREFIX}{key}"
        expiry = ttl or settings.CACHE_DEFAULT_TTL

        if not self.is_redis_available:
            self._try_reconnect()

        if self.is_redis_available and self.redis_client:
            try:
                serialized = json.dumps(value, default=str)
                self.redis_client.set(full_key, serialized, ex=expiry)
                return True
            except Exception as e:
                logger.warning(f"Redis SET failed for key {key}: {e}. Switching to in-memory fallback.")
                self.is_redis_available = False
                self._last_connect_attempt = time.time()

        return self.in_memory_fallback.set(full_key, value, expiry)

    def delete(self, key: str) -> bool:
        full_key = f"{settings.CACHE_PREFIX}{key}"
        deleted = False
        if self.is_redis_available and self.redis_client:
            try:
                res = self.redis_client.delete(full_key)
                deleted = bool(res > 0)
                self.in_memory_fallback.delete(full_key)
                return deleted
            except Exception as e:
                logger.warning(f"Redis DELETE failed for key {key}: {e}")
                self.is_redis_available = False
        return self.in_memory_fallback.delete(full_key)

    def delete_pattern(self, pattern: str) -> int:
        full_pattern = f"{settings.CACHE_PREFIX}{pattern}"
        count = 0
        if self.is_redis_available and self.redis_client:
            try:
                keys = self.redis_client.keys(full_pattern)
                if keys:
                    count = self.redis_client.delete(*keys)
                self.in_memory_fallback.delete_pattern(full_pattern)
                return count
            except Exception as e:
                logger.warning(f"Redis delete_pattern failed for {pattern}: {e}")
                self.is_redis_available = False
        return self.in_memory_fallback.delete_pattern(full_pattern)

    def check_health(self) -> dict:
        if not settings.CACHE_ENABLED:
            return {"status": "DISABLED", "backend": "none"}
        
        # Check or attempt reconnect
        if not self.is_redis_available:
            self._try_reconnect()

        if self.is_redis_available and self.redis_client:
            try:
                start = time.time()
                self.redis_client.ping()
                latency_ms = (time.time() - start) * 1000.0
                info = self.redis_client.info(section="memory")
                return {
                    "status": "HEALTHY",
                    "backend": "redis",
                    "latency_ms": round(latency_ms, 2),
                    "used_memory_human": info.get("used_memory_human", "N/A"),
                }
            except Exception as e:
                self.is_redis_available = False
                return {
                    "status": "FALLBACK_ACTIVE",
                    "backend": "in_memory_fallback",
                    "error": str(e),
                    "memory_items": self.in_memory_fallback.size()
                }
        return {
            "status": "FALLBACK_ACTIVE",
            "backend": "in_memory_fallback",
            "memory_items": self.in_memory_fallback.size()
        }

cache = CacheManager()

def cached(ttl: int = 60, prefix: str = "", key_builder: Optional[Callable] = None):
    """
    Decorator to cache endpoint or function outputs.
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not settings.CACHE_ENABLED:
                return func(*args, **kwargs)

            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                args_str = ":".join(str(a) for a in args if not hasattr(a, "__dict__"))
                kwargs_str = ":".join(f"{k}={v}" for k, v in sorted(kwargs.items()) if not hasattr(v, "__dict__"))
                cache_key = f"{prefix}:{func.__name__}:{args_str}:{kwargs_str}"

            cached_val = cache.get(cache_key)
            if cached_val is not None:
                return cached_val

            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl=ttl)
            return result
        return wrapper
    return decorator

# Granular invalidation helpers
def invalidate_questions_cache():
    cache.delete_pattern("questions:*")
    cache.delete_pattern("events:*")

def invalidate_events_cache():
    cache.delete_pattern("events:*")
    cache.delete_pattern("leaderboards:*")

def invalidate_leaderboards_cache():
    cache.delete_pattern("leaderboards:*")
    cache.delete_pattern("analytics:*")

def invalidate_analytics_cache():
    cache.delete_pattern("analytics:*")
    cache.delete_pattern("reports:*")
