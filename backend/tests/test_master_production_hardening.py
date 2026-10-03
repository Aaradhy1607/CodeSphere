import os
import pytest
import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.main import app
from app.core.config import Settings, settings
from app.core.database import Base, engine, SessionLocal, auto_migrate_db
from app.core.security import get_password_hash, create_access_token, verify_password
from app.models.models import (
    User, StudentProfile, UserRole, AccountStatus, Question, TestCase,
    Submission, SubmissionVerdict, SubmissionStatus, RefreshToken
)
from app.services.adaptive_learning import adaptive_learning_engine
from app.services.problem_quality import problem_quality_engine
from app.services.duplicate_detector import duplicate_detector
from app.services.test_case_quality import test_case_quality_validator

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    auto_migrate_db()
    yield

def _get_or_create_user(db: Session, email: str, role: str, password: str = "MasterPass2026!") -> User:
    u = db.query(User).filter(User.email == email.lower()).first()
    if not u:
        u = User(
            email=email.lower(),
            full_name=email.split("@")[0].title(),
            role=role,
            hashed_password=get_password_hash(password),
            is_active=True,
            failed_login_attempts=0,
            locked_until=None
        )
        db.add(u)
        db.commit()
        db.refresh(u)
    else:
        u.role = role
        u.hashed_password = get_password_hash(password)
        u.is_active = True
        u.failed_login_attempts = 0
        u.locked_until = None
        db.commit()
        db.refresh(u)
    return u

# =====================================================================
# 1. CORS SECURITY TESTS
# =====================================================================

def test_cors_approved_origin_allowed():
    """Approved frontend origin receives allow-origin header and credentials flag."""
    res = client.options("/api/v1/auth/me", headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET"
    })
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert res.headers.get("access-control-allow-credentials") == "true"

def test_cors_unapproved_origin_rejected():
    """Unapproved origin is not reflected in access-control-allow-origin."""
    res = client.options("/api/v1/auth/me", headers={
        "Origin": "http://malicious-attacker.com",
        "Access-Control-Request-Method": "GET"
    })
    # CORSMiddleware does not return allow-origin header for untrusted origins
    allow_origin = res.headers.get("access-control-allow-origin")
    assert allow_origin != "http://malicious-attacker.com"
    assert allow_origin != "*"

def test_cors_wildcard_rejected_in_production():
    """Production configuration with wildcard CORS origin fails fast."""
    s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a" * 32,
        INITIAL_ADMIN_EMAIL="admin@ipu.ac.in",
        INITIAL_ADMIN_PASSWORD="StrongPassword123!",
        DATABASE_URL="postgresql://user:pass@localhost:5432/db",
        CORS_ORIGINS="http://localhost:3000,*"
    )
    with pytest.raises(RuntimeError) as exc:
        s.validate_production_security()
    assert "Wildcard '*' CORS origin is strictly forbidden in production" in str(exc.value)

def test_cors_empty_origins_rejected_in_production():
    """Production configuration without explicit CORS origins fails fast."""
    s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a" * 32,
        INITIAL_ADMIN_EMAIL="admin@ipu.ac.in",
        INITIAL_ADMIN_PASSWORD="StrongPassword123!",
        DATABASE_URL="postgresql://user:pass@localhost:5432/db",
        CORS_ORIGINS=""
    )
    with pytest.raises(RuntimeError) as exc:
        s.validate_production_security()
    assert "Explicit CORS_ORIGINS must be configured for production" in str(exc.value)

# =====================================================================
# 2. PRODUCTION CONFIGURATION FAIL-CLOSED TESTS
# =====================================================================

def test_prod_config_missing_secret_key_fails_closed():
    s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="",
        INITIAL_ADMIN_EMAIL="admin@ipu.ac.in",
        INITIAL_ADMIN_PASSWORD="StrongPassword123!",
        DATABASE_URL="postgresql://user:pass@localhost:5432/db",
        CORS_ORIGINS="https://codesphere.ipu.ac.in"
    )
    with pytest.raises(RuntimeError) as exc:
        s.validate_production_security()
    assert "SECRET_KEY" in str(exc.value)

def test_prod_config_weak_secret_key_fails_closed():
    s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="short-secret-key",
        INITIAL_ADMIN_EMAIL="admin@ipu.ac.in",
        INITIAL_ADMIN_PASSWORD="StrongPassword123!",
        DATABASE_URL="postgresql://user:pass@localhost:5432/db",
        CORS_ORIGINS="https://codesphere.ipu.ac.in"
    )
    with pytest.raises(RuntimeError) as exc:
        s.validate_production_security()
    assert "SECRET_KEY" in str(exc.value)

def test_prod_config_missing_admin_email_fails_closed():
    s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a" * 32,
        INITIAL_ADMIN_EMAIL="",
        INITIAL_ADMIN_PASSWORD="StrongPassword123!",
        DATABASE_URL="postgresql://user:pass@localhost:5432/db",
        CORS_ORIGINS="https://codesphere.ipu.ac.in"
    )
    with pytest.raises(RuntimeError) as exc:
        s.validate_production_security()
    assert "INITIAL_ADMIN_EMAIL" in str(exc.value)

def test_prod_config_weak_admin_password_fails_closed():
    s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a" * 32,
        INITIAL_ADMIN_EMAIL="admin@ipu.ac.in",
        INITIAL_ADMIN_PASSWORD="admin123",
        DATABASE_URL="postgresql://user:pass@localhost:5432/db",
        CORS_ORIGINS="https://codesphere.ipu.ac.in"
    )
    with pytest.raises(RuntimeError) as exc:
        s.validate_production_security()
    assert "Insecure INITIAL_ADMIN_PASSWORD" in str(exc.value)

def test_prod_config_sqlite_fails_closed():
    s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a" * 32,
        INITIAL_ADMIN_EMAIL="admin@ipu.ac.in",
        INITIAL_ADMIN_PASSWORD="StrongPassword123!",
        DATABASE_URL="sqlite:///./codesphere.db",
        CORS_ORIGINS="https://codesphere.ipu.ac.in"
    )
    with pytest.raises(RuntimeError) as exc:
        s.validate_production_security()
    assert "SQLite database cannot be used in a production" in str(exc.value)

# =====================================================================
# 3. AI QUESTION QUALITY LOOP TESTS
# =====================================================================

def test_ai_problem_quality_scorer_complete_evaluation():
    complete_tcs = [
        {"id": 1, "input_data": "5\n1 2 3 4 5", "expected_output": "15", "is_hidden": False, "category": "NORMAL"},
        {"id": 2, "input_data": "3\n10 20 30", "expected_output": "60", "is_hidden": False, "category": "NORMAL"},
        {"id": 3, "input_data": "1\n0", "expected_output": "0", "is_hidden": True, "category": "MINIMUM"},
        {"id": 4, "input_data": "2\n-5 5", "expected_output": "0", "is_hidden": True, "category": "BOUNDARY"},
        {"id": 5, "input_data": "100\n" + "1 " * 100, "expected_output": "100", "is_hidden": True, "category": "PERFORMANCE"},
        {"id": 6, "input_data": "4\n1000000000 1000000000", "expected_output": "2000000000", "is_hidden": True, "category": "OVERFLOW"},
    ]
    eval_result = problem_quality_engine.evaluate_problem(
        title="Sum of Array Elements",
        problem_statement="Given an array of integers, compute and return the total sum of all elements.",
        input_format="First line contains N. Second line contains N integers.",
        output_format="Print a single integer representing the sum.",
        constraints="1 <= N <= 10^5, -10^9 <= A[i] <= 10^9",
        examples=[{"input": "3\n1 2 3", "output": "6", "explanation": "1+2+3=6"}],
        difficulty_score=3,
        expected_time_complexity="O(N)",
        expected_space_complexity="O(1)",
        time_limit_seconds=2.0,
        memory_limit_mb=256,
        reference_solutions={
            "python": "import sys\ninput = sys.stdin.read\ndef solve():\n    data = input().split()\n    if data: print(sum(map(int, data[1:])))\nsolve()",
            "cpp": "#include <iostream>\nusing namespace std;\nint main() { int n; if(cin >> n){ long long s=0, x; while(n--){ cin>>x; s+=x; } cout<<s<<endl; } return 0; }"
        },
        test_cases=complete_tcs,
        question_type="CODING"
    )
    assert eval_result["quality_score"] >= 80.0
    assert eval_result["is_ready_for_review"] is True
    assert len(eval_result["errors"]) == 0

def test_ai_duplicate_detector_exact_and_semantic():
    stmt1 = "Given an array of integers, return the maximum subarray sum in O(N) time."
    stmt2 = "Given an array of integers, return the maximum subarray sum in O(N) time."
    stmt3 = "Given a list of positive numbers, find all distinct prime numbers smaller than N."
    
    dup_res = duplicate_detector.compare_statements(stmt1, stmt2)
    assert dup_res["is_duplicate"] is True
    assert dup_res["similarity_score"] >= 0.88
    
    diff_res = duplicate_detector.compare_statements(stmt1, stmt3)
    assert diff_res["is_duplicate"] is False
    assert diff_res["similarity_score"] < 0.50

def test_ai_test_case_quality_analysis():
    tc_list = [
        {"input_data": "5\n1 2 3 4 5", "expected_output": "15", "is_hidden": False},
        {"input_data": "0\n", "expected_output": "0", "is_hidden": True},
        {"input_data": "1\n-10", "expected_output": "-10", "is_hidden": True}
    ]
    analysis = test_case_quality_validator.validate_test_suite(tc_list)
    assert analysis["total_count"] == 3
    assert analysis["hidden_count"] == 2
    assert analysis["visible_count"] == 1
    assert "categories_present" in analysis

# =====================================================================
# 4. ADAPTIVE LEARNING FEEDBACK LOOP TESTS
# =====================================================================

def test_adaptive_learning_cold_start():
    db = SessionLocal()
    try:
        user = _get_or_create_user(db, "adaptive.cold@std.ggsipu.ac.in", UserRole.STUDENT.value)
        rec = adaptive_learning_engine.get_student_adaptive_recommendation(user.id, db)
        assert rec["has_sufficient_history"] is False
        assert rec["learning_path_mode"] == "FOUNDATIONAL_BUILDER"
        assert rec["recommended_difficulty_score"] == 3.0
        assert "Arrays" in rec["recommended_topics"]
    finally:
        db.close()

def test_adaptive_learning_weak_performance():
    db = SessionLocal()
    try:
        from app.models.models import Event
        user = _get_or_create_user(db, "adaptive.weak@std.ggsipu.ac.in", UserRole.STUDENT.value)
        ts = int(datetime.datetime.now().timestamp() * 1000)
        
        evt = Event(
            title=f"Adaptive Weak Event {ts}",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            end_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)
        )
        db.add(evt)
        db.flush()

        q = Question(
            title=f"Adaptive Weak Test Q {ts}",
            slug=f"adaptive-weak-test-q-{ts}",
            problem_statement="Test statement",
            difficulty_score=5,
            topic="Dynamic Programming",
            author_id=user.id,
            status="PUBLISHED"
        )
        db.add(q)
        db.flush()

        for _ in range(4):
            s = Submission(
                event_id=evt.id,
                user_id=user.id,
                question_id=q.id,
                language="python",
                code="pass",
                status=SubmissionStatus.COMPLETED.value,
                verdict=SubmissionVerdict.WA.value,
                is_final=True,
                score=0.0
            )
            db.add(s)
        db.commit()

        rec = adaptive_learning_engine.get_student_adaptive_recommendation(user.id, db)
        assert rec["has_sufficient_history"] is True
        assert rec["overall_accuracy"] < 40.0
        assert rec["learning_path_mode"] == "CONCEPT_REINFORCEMENT"
        assert rec["recommended_difficulty_score"] <= 3.5
    finally:
        db.close()

def test_adaptive_learning_strong_performance():
    db = SessionLocal()
    try:
        from app.models.models import Event
        user = _get_or_create_user(db, "adaptive.strong@std.ggsipu.ac.in", UserRole.STUDENT.value)
        ts = int(datetime.datetime.now().timestamp() * 1000)
        
        evt = Event(
            title=f"Adaptive Strong Event {ts}",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            end_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)
        )
        db.add(evt)
        db.flush()

        q = Question(
            title=f"Adaptive Strong Test Q {ts}",
            slug=f"adaptive-strong-test-q-{ts}",
            problem_statement="Test statement",
            difficulty_score=5,
            topic="Binary Trees",
            author_id=user.id,
            status="PUBLISHED"
        )
        db.add(q)
        db.flush()

        # Create 5 accepted submissions
        for _ in range(5):
            s = Submission(
                event_id=evt.id,
                user_id=user.id,
                question_id=q.id,
                language="python",
                code="print('ok')",
                status=SubmissionStatus.COMPLETED.value,
                verdict=SubmissionVerdict.AC.value,
                is_final=True,
                score=100.0
            )
            db.add(s)
        db.commit()

        rec = adaptive_learning_engine.get_student_adaptive_recommendation(user.id, db)
        assert rec["has_sufficient_history"] is True
        assert rec["overall_accuracy"] >= 80.0
        assert rec["learning_path_mode"] == "ADVANCED_CHALLENGE"
        assert rec["recommended_difficulty_score"] >= 7.0
    finally:
        db.close()

def test_adaptive_recommendations_endpoint_idor_protection():
    db = SessionLocal()
    try:
        student_a = _get_or_create_user(db, "adaptive.idor.a@std.ggsipu.ac.in", UserRole.STUDENT.value)
        student_b = _get_or_create_user(db, "adaptive.idor.b@std.ggsipu.ac.in", UserRole.STUDENT.value)

        token_a = create_access_token(subject=str(student_a.id), extra_claims={"role": student_a.role, "email": student_a.email})
        
        # Student A attempts to view Student B's adaptive recommendations
        res = client.get(f"/api/v1/students/{student_b.id}/adaptive-recommendations", headers={"Authorization": f"Bearer {token_a}"})
        assert res.status_code == 403

        # Student A views own recommendations -> 200 OK
        own_res = client.get(f"/api/v1/students/{student_a.id}/adaptive-recommendations", headers={"Authorization": f"Bearer {token_a}"})
        assert own_res.status_code == 200
        data = own_res.json()
        assert "recommended_difficulty_score" in data
        assert "learning_path_mode" in data
    finally:
        db.close()
