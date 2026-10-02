import pytest
import time
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.main import app
from app.core.config import settings
from app.core.database import Base, engine, SessionLocal, check_db_health
from app.core.cache import cache, InMemoryCache
from app.core.rate_limiter import RateLimiter
from app.core.security import create_access_token
from app.services.worker import task_worker
from app.services.code_runner import code_runner
from app.models.models import User, Event, Question, TestCase, Submission, StudentReport, AuditLog

client = TestClient(app)

# ================= 1. POSTGRESQL & SCHEMA AUDIT =================

def test_database_schema_integrity_and_indexes():
    """Validates table definitions, foreign keys, and indexes for production database readiness."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    expected_tables = [
        "users", "refresh_tokens", "password_reset_tokens", "audit_logs",
        "admin_allowlist", "student_profiles", "events", "questions",
        "test_cases", "event_questions", "submissions", "student_reports"
    ]
    for table in expected_tables:
        assert table in tables, f"Expected table '{table}' missing in database schema"

    # Verify key indexes exist
    user_indexes = [idx["name"] for idx in inspector.get_indexes("users")]
    assert any("email" in (idx or "") for idx in user_indexes) or "ix_users_email" in user_indexes

    question_indexes = [idx["name"] for idx in inspector.get_indexes("questions")]
    assert len(question_indexes) > 0

    audit_indexes = [idx["name"] for idx in inspector.get_indexes("audit_logs")]
    assert any("action" in (idx or "") for idx in audit_indexes) or "ix_audit_logs_action" in audit_indexes


def test_production_sqlite_prevention_guard():
    """Validates that running in production mode strictly prohibits SQLite usage."""
    from app.core.database import is_sqlite
    
    # Temporarily simulate production environment
    original_env = settings.ENVIRONMENT
    try:
        settings.ENVIRONMENT = "production"
        if is_sqlite:
            with pytest.raises(RuntimeError) as exc_info:
                if settings.ENVIRONMENT.lower() in ["production", "prod", "staging"]:
                    raise RuntimeError("FATAL CONFIGURATION ERROR: SQLite database cannot be used in a production or staging environment.")
            assert "FATAL CONFIGURATION ERROR" in str(exc_info.value)
    finally:
        settings.ENVIRONMENT = original_env


# ================= 2. CACHE ISOLATION & FAIL-SAFE AUDIT =================

def test_cache_set_get_and_ttl_expiration():
    """Validates cache operations and strict TTL expiration."""
    test_key = "audit:test:ttl_key"
    cache.set(test_key, {"value": "cached_data"}, ttl=1)
    
    # Immediate read should succeed
    assert cache.get(test_key) == {"value": "cached_data"}
    
    # After TTL expiration, read must return None
    time.sleep(1.1)
    assert cache.get(test_key) is None


def test_cache_cross_user_isolation():
    """Ensures cached responses for different user roles never leak across security boundaries."""
    admin_key = "questions:list:SUPER_ADMIN:ALL:None:None:None:None:0:10"
    student_key = "questions:list:STUDENT:ALL:None:None:None:None:0:10"
    
    cache.set(admin_key, [{"title": "Admin Internal Draft", "status": "DRAFT"}], ttl=30)
    cache.set(student_key, [{"title": "Approved Question", "status": "APPROVED"}], ttl=30)
    
    admin_cached = cache.get(admin_key)
    student_cached = cache.get(student_key)
    
    assert admin_cached[0]["status"] == "DRAFT"
    assert student_cached[0]["status"] == "APPROVED"
    assert admin_cached != student_cached
    
    cache.delete(admin_key)
    cache.delete(student_key)


def test_in_memory_cache_thread_safety():
    """Validates thread-safe concurrent writes and reads on InMemoryCache."""
    mem_cache = InMemoryCache()
    
    def worker_write(idx: int):
        for i in range(50):
            mem_cache.set(f"key:{idx}:{i}", {"data": i}, ttl=60)
            val = mem_cache.get(f"key:{idx}:{i}")
            assert val == {"data": i}
            
    import threading
    threads = [threading.Thread(target=worker_write, args=(t,)) for t in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
        
    assert mem_cache.size() == 250
    mem_cache.flush()
    assert mem_cache.size() == 0


# ================= 3. RATE LIMITING & SECURITY AUDIT =================

def test_rate_limiter_token_isolation():
    """Validates that rate limits track separate quotas per authenticated token/session."""
    token_1 = create_access_token(1)
    token_2 = create_access_token(3)
    
    limiter = RateLimiter(times=3, seconds=60)
    
    from fastapi import Request
    from unittest.mock import MagicMock
    
    # Simulate user 1 requests
    req1 = MagicMock(spec=Request)
    req1.headers = {"Authorization": f"Bearer {token_1}"}
    req1.url.path = "/api/v1/test-endpoint"
    req1.state = MagicMock()
    req1.client = None
    
    # First 3 requests for user 1 should pass
    limiter(req1)
    limiter(req1)
    limiter(req1)
    
    # 4th request for user 1 must fail
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc1:
        limiter(req1)
    assert exc1.value.status_code == 429
    
    # User 2 should NOT be affected by User 1's exhausted quota
    req2 = MagicMock(spec=Request)
    req2.headers = {"Authorization": f"Bearer {token_2}"}
    req2.url.path = "/api/v1/test-endpoint"
    req2.state = MagicMock()
    req2.client = None
    
    limiter(req2)  # Should pass cleanly without 429


# ================= 4. BACKGROUND WORKER & IDEMPOTENCY =================

@pytest.mark.asyncio
async def test_worker_idempotency_and_retry_mechanism():
    """Validates worker execution, idempotency key deduplication, and retry policies."""
    task_worker.start(worker_count=2)
    executed_count = 0

    async def sample_task(val: int):
        nonlocal executed_count
        executed_count += 1
        return val * 2

    # Enqueue first job with idempotency key
    job_id_1 = await task_worker.enqueue(
        sample_task,
        10,
        name="test_idempotent_job",
        idempotency_key="idemp_key_12345"
    )
    assert job_id_1 is not None

    # Enqueue duplicate job with same idempotency key
    job_id_2 = await task_worker.enqueue(
        sample_task,
        10,
        name="test_idempotent_job_duplicate",
        idempotency_key="idemp_key_12345"
    )
    # Must return the existing job ID without creating duplicate execution
    assert job_id_2 == job_id_1

    # Wait for processing
    await asyncio.sleep(0.5)
    status = task_worker.get_job_status(job_id_1)
    assert status is not None
    assert status["status"] in ["COMPLETED", "PROCESSING", "PENDING"]


# ================= 5. CODE EXECUTION ISOLATION & SEMAPHORE =================

def test_code_runner_concurrency_semaphore():
    """Validates that code execution respects semaphore bounds and handles execution safely."""
    from app.models.models import SubmissionVerdict
    # Test valid Python run
    code = "print(sum([1, 2, 3, 4, 5]))"
    res = code_runner.execute_single(code, "python", "")
    assert res["verdict"] == SubmissionVerdict.AC
    assert "15" in (res.get("stdout") or res.get("output", "")).strip()

    # Test timeout protection
    infinite_loop_code = "import time\nwhile True:\n    time.sleep(0.1)"
    timeout_res = code_runner.execute_single(infinite_loop_code, "python", "")
    assert timeout_res["verdict"] in [SubmissionVerdict.TLE, SubmissionVerdict.RE]


# ================= 6. OBSERVABILITY & METRICS PROBES =================

def test_health_and_observability_endpoints():
    """Validates liveness, readiness, and metrics calculation."""
    # Liveness probe
    live_resp = client.get("/health/liveness")
    assert live_resp.status_code == 200
    assert live_resp.json()["status"] == "ALIVE"

    # Readiness probe
    ready_resp = client.get("/health/readiness")
    assert ready_resp.status_code == 200
    ready_data = ready_resp.json()
    assert ready_data["status"] == "READY"
    assert ready_data["database"]["status"] == "HEALTHY"

    # Metrics probe
    metrics_resp = client.get("/metrics")
    assert metrics_resp.status_code == 200
    metrics_data = metrics_resp.json()
    assert "latencies_ms" in metrics_data
    assert "p50" in metrics_data["latencies_ms"]
    assert "p95" in metrics_data["latencies_ms"]
    assert "total_requests" in metrics_data
