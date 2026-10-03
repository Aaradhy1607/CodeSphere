import os
import time
import pytest
from app.core.config import settings
from app.core.cache import cache, CacheManager, InMemoryCache
from app.core.rate_limiter import RateLimiter

def test_cache_manager_basic_operations():
    """Verify set, get, TTL, and delete operations on cache manager."""
    test_key = "test:codesphere:key"
    test_val = {"status": "ok", "timestamp": time.time()}

    # Set key
    success = cache.set(test_key, test_val, ttl=30)
    assert success is True

    # Get key
    fetched = cache.get(test_key)
    assert fetched is not None
    assert fetched["status"] == "ok"

    # Delete key
    deleted = cache.delete(test_key)
    assert deleted is True

    # Confirm key gone
    assert cache.get(test_key) is None

def test_cache_pattern_deletion():
    """Verify pattern matching deletion in cache."""
    cache.set("user:session:1", "active", ttl=60)
    cache.set("user:session:2", "active", ttl=60)
    cache.set("system:config:1", "enabled", ttl=60)

    # Delete all user session patterns
    deleted_count = cache.delete_pattern("user:session:*")
    assert deleted_count >= 2

    assert cache.get("user:session:1") is None
    assert cache.get("user:session:2") is None
    assert cache.get("system:config:1") == "enabled"

    cache.delete("system:config:1")

def test_rate_limiter_token_bucket_integration():
    """Verify rate limiter allows within threshold and rejects overflow."""
    from unittest.mock import MagicMock
    from fastapi import HTTPException
    
    limiter = RateLimiter(times=5, seconds=10)
    mock_request = MagicMock()
    mock_request.headers = {}
    mock_request.client.host = "192.168.1.100"
    mock_request.url.path = "/test/api"
    mock_request.state = MagicMock()

    # Clear any previous rate limit key
    cache.delete("rate_limit:/test/api:ip:192.168.1.100")

    # Consume allowed tokens
    for _ in range(5):
        limiter(mock_request)

    # 6th attempt must raise HTTPException with 429
    with pytest.raises(HTTPException) as exc_info:
        limiter(mock_request)
    assert exc_info.value.status_code == 429

def test_in_memory_cache_thread_safety():
    """Verify thread-safe fallback cache behavior."""
    mem_cache = InMemoryCache()
    import threading

    def worker(idx):
        for i in range(50):
            mem_cache.set(f"thread:{idx}:{i}", f"val_{i}", ttl=10)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert mem_cache.size() == 250
    assert mem_cache.get("thread:0:0") == "val_0"
