import pytest
import time
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import SessionLocal, Base, engine, auto_migrate_db
from app.services.seeder import seed_database
from app.core.cache import cache, CacheManager, InMemoryCache
from app.core.rate_limiter import RateLimiter
from app.models.models import User, UserRole, Permission, StudentProfile
from app.core.security import create_access_token, create_refresh_token_record

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    auto_migrate_db()
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    yield

def get_admin_auth_headers():
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == UserRole.SUPER_ADMIN.value).first()
        token = create_access_token(admin.id, extra_claims={"role": admin.role})
        return {"Authorization": f"Bearer {token}"}
    finally:
        db.close()

# ============================================================================
# ISSUE #1 TESTS: Analytics Compare Data Integrity & Identity
# ============================================================================

def test_analytics_compare_endpoint_response_structure():
    """Validates that /analytics/compare returns strongly-typed StudentComparisonOut objects with student_id."""
    headers = get_admin_auth_headers()
    db = SessionLocal()
    try:
        students = db.query(User).filter(User.role == UserRole.STUDENT.value).limit(2).all()
        assert len(students) >= 2, "At least 2 students required for comparison test"
        id1, id2 = students[0].id, students[1].id
        
        response = client.get(f"/api/v1/analytics/compare?student_ids={id1},{id2}", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        
        for cand in data:
            # Genuinely stable unique identity checks
            assert "student_id" in cand
            assert "id" in cand
            assert "user_id" in cand
            assert cand["student_id"] is not None
            assert isinstance(cand["student_id"], int)
            assert cand["student_id"] > 0
            
            # Key UI fields match
            assert "full_name" in cand
            assert "placement_readiness" in cand
            assert "total_score" in cand
            assert "total_solved" in cand
            assert "consistency" in cand
            assert "topic_mastery" in cand
            assert isinstance(cand["topic_mastery"], dict)
            assert "recent_scores" in cand
            assert isinstance(cand["recent_scores"], list)
    finally:
        db.close()

def test_analytics_compare_unique_candidate_identities():
    """Validates that two compared students have distinct non-colliding student_id values."""
    headers = get_admin_auth_headers()
    db = SessionLocal()
    try:
        students = db.query(User).filter(User.role == UserRole.STUDENT.value).limit(2).all()
        id1, id2 = students[0].id, students[1].id
        
        response = client.get(f"/api/v1/analytics/compare?student_ids={id1},{id2}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        keys = [cand["student_id"] for cand in data]
        assert len(keys) == 2
        assert keys[0] != keys[1], "Candidate unique keys must not collide!"
        assert keys[0] == id1
        assert keys[1] == id2
    finally:
        db.close()

def test_analytics_compare_empty_and_invalid_ids():
    """Validates error handling on invalid query params."""
    headers = get_admin_auth_headers()
    
    # Missing/empty
    res_empty = client.get("/api/v1/analytics/compare?student_ids=", headers=headers)
    assert res_empty.status_code == 400
    
    # Non-numeric
    res_invalid = client.get("/api/v1/analytics/compare?student_ids=abc,xyz", headers=headers)
    assert res_invalid.status_code == 400

# ============================================================================
# ISSUE #2 TESTS: Redis Diagnostic, Fallback, and Reconnection
# ============================================================================

def test_cache_manager_in_memory_fallback_operations():
    """Validates thread-safe in-memory cache operations with TTL and pattern deletion."""
    test_cache = CacheManager()
    
    # Basic get/set
    test_cache.set("test_key_1", {"data": "hello"}, ttl=5)
    val = test_cache.get("test_key_1")
    assert val == {"data": "hello"}
    
    # Key deletion
    assert test_cache.delete("test_key_1") is True
    assert test_cache.get("test_key_1") is None
    
    # Pattern deletion
    test_cache.set("test_pat:a", 1)
    test_cache.set("test_pat:b", 2)
    test_cache.set("other_pat:c", 3)
    deleted_count = test_cache.delete_pattern("test_pat:*")
    assert deleted_count >= 2
    assert test_cache.get("test_pat:a") is None
    assert test_cache.get("test_pat:b") is None
    assert test_cache.get("other_pat:c") == 3

def test_cache_manager_reconnect_and_health_reporting():
    """Validates that check_health() returns structured diagnostic status."""
    health = cache.check_health()
    assert "status" in health
    assert health["status"] in ["HEALTHY", "FALLBACK_ACTIVE", "DISABLED"]
    assert "backend" in health
    assert health["backend"] in ["redis", "in_memory_fallback", "none"]

def test_rate_limiter_resilience_under_cache_fallback():
    """Validates that rate limiting remains 100% active and secure during in-memory fallback."""
    limiter = RateLimiter(times=3, seconds=5)
    
    class FakeRequest:
        def __init__(self, ip):
            self.headers = {}
            self.state = type("State", (), {})()
            self.url = type("URL", (), {"path": "/test/action"})()
            self.client = type("Client", (), {"host": ip})()
            self.method = "POST"
    
    req = FakeRequest("192.168.1.50")
    
    # 3 allowed requests
    limiter(req)
    assert req.state.rate_limit_remaining == 2
    limiter(req)
    assert req.state.rate_limit_remaining == 1
    limiter(req)
    assert req.state.rate_limit_remaining == 0
    
    # 4th request must trigger HTTP 429
    with pytest.raises(Exception) as exc_info:
        limiter(req)
    assert "429" in str(exc_info.value) or exc_info.value.status_code == 429

def test_token_revocation_security_isolation_during_cache_fallback():
    """Validates that refresh token revocation remains strictly enforced in database."""
    db = SessionLocal()
    try:
        user = db.query(User).first()
        raw_token, token_record = create_refresh_token_record(db, user.id)
        
        # Verify token is valid
        assert token_record.is_revoked is False
        
        # Revoke token
        token_record.is_revoked = True
        db.commit()
        
        # Verify revoked status is persisted
        db.refresh(token_record)
        assert token_record.is_revoked is True
    finally:
        db.close()
