import time
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.core.cache import cache, InMemoryCache
from app.core.rate_limiter import RateLimiter
from app.core.database import check_db_health
from app.services.worker import task_worker

client = TestClient(app)

def test_health_liveness():
    resp = client.get("/health/liveness")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ALIVE"
    assert "uptime_seconds" in data
    assert "timestamp" in data

def test_health_readiness():
    resp = client.get("/health/readiness")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "READY"
    assert "database" in data
    assert "cache" in data
    assert "worker" in data
    assert data["database"]["status"] == "HEALTHY"

def test_observability_middleware_headers():
    resp = client.get("/health/liveness", headers={"X-Request-ID": "test-req-12345"})
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID") == "test-req-12345"
    assert "X-Process-Time-Ms" in resp.headers

def test_metrics_endpoint():
    resp = client.get("/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "uptime_seconds" in data
    assert "total_requests" in data
    assert "latencies_ms" in data
    assert "database_pool" in data
    assert "cache_backend" in data

def test_cache_operations():
    # Test setting and getting
    cache.set("test_key_1", {"msg": "hello_world"}, ttl=5)
    val = cache.get("test_key_1")
    assert val == {"msg": "hello_world"}

    # Test pattern deletion
    cache.set("users:1", "alice", ttl=10)
    cache.set("users:2", "bob", ttl=10)
    count = cache.delete_pattern("users:*")
    assert count >= 2
    assert cache.get("users:1") is None
    assert cache.get("users:2") is None

def test_in_memory_cache_ttl():
    mem = InMemoryCache()
    mem.set("exp_key", "active", ttl=1)
    assert mem.get("exp_key") == "active"
    time.sleep(1.1)
    assert mem.get("exp_key") is None

def test_rate_limiter_throttling():
    limiter = RateLimiter(times=3, seconds=5)
    from fastapi import Request
    from unittest.mock import Mock

    mock_req = Mock(spec=Request)
    mock_req.state = Mock()
    mock_req.url.path = "/test-rate"
    mock_req.client.host = "192.168.1.100"
    mock_req.headers = {}

    # 1st call -> OK
    limiter(mock_req)
    # 2nd call -> OK
    limiter(mock_req)
    # 3rd call -> OK
    limiter(mock_req)
    # 4th call -> HTTPException 429
    with pytest.raises(Exception) as excinfo:
        limiter(mock_req)
    assert "429" in str(excinfo.value) or "Rate limit" in str(excinfo.value)

@pytest.mark.asyncio
async def test_background_worker_enqueue_and_idempotency():
    executed = []

    def sample_task(val: int):
        executed.append(val)
        return val * 2

    job_id1 = await task_worker.enqueue(sample_task, 42, idempotency_key="idemp-key-1")
    assert job_id1 is not None

    # Idempotent enqueue should return same job_id
    job_id2 = await task_worker.enqueue(sample_task, 42, idempotency_key="idemp-key-1")
    assert job_id1 == job_id2

    stats = task_worker.get_stats()
    assert stats["total_jobs"] >= 1
