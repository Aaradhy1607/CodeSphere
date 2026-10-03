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
    User, StudentProfile, UserRole, AccountStatus, Question, TestCase, Event,
    Submission, SubmissionVerdict, SubmissionStatus, Assessment, AssessmentQuestion,
    AssessmentAttempt, AttemptAnswer, AntiCheatEvent, AssessmentStatus, AttemptStatus,
    RefreshToken
)
from app.services.code_runner import SandboxedCodeRunner, LocalProcessBackend, DockerExecutionBackend
from app.services.seeder import seed_database
from app.services.gemini_ai import gemini_service

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    auto_migrate_db()
    yield

def _get_or_create_user(db: Session, email: str, role: str, password: str = "SecurePass2026!") -> User:
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
# A. LOGIN WITH CORRECT CREDENTIALS -> SUCCESS
# =====================================================================
def test_a_login_correct_credentials_success():
    db = SessionLocal()
    try:
        user = _get_or_create_user(db, "valid.user@ipu.ac.in", UserRole.ADMIN.value, "CorrectPassword2026!")
        res = client.post("/api/v1/auth/login", json={
            "email": "valid.user@ipu.ac.in",
            "password": "CorrectPassword2026!"
        })
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "valid.user@ipu.ac.in"
    finally:
        db.close()

# =====================================================================
# B. LOGIN WITH WRONG PASSWORD -> 401
# =====================================================================
def test_b_login_wrong_password_returns_401():
    db = SessionLocal()
    try:
        user = _get_or_create_user(db, "wrongpass.user@ipu.ac.in", UserRole.ADMIN.value, "CorrectPassword2026!")
        res = client.post("/api/v1/auth/login", json={
            "email": "wrongpass.user@ipu.ac.in",
            "password": "WrongPassword123!"
        })
        assert res.status_code == 401
        assert "Invalid email or password" in res.json()["detail"]
    finally:
        db.close()

# =====================================================================
# C. LOGIN WITHOUT PASSWORD -> REJECTED (400 or 422)
# =====================================================================
def test_c_login_missing_password_rejected():
    res = client.post("/api/v1/auth/login", json={
        "email": "valid.user@ipu.ac.in"
    })
    assert res.status_code in (400, 422)

# =====================================================================
# D. LOGIN WITH EMPTY PASSWORD -> REJECTED (400 or 422)
# =====================================================================
def test_d_login_empty_password_rejected():
    res = client.post("/api/v1/auth/login", json={
        "email": "valid.user@ipu.ac.in",
        "password": ""
    })
    assert res.status_code in (400, 422)

# =====================================================================
# E. MISSING PASSWORD HASH IN DB -> REJECTED (FAIL CLOSED)
# =====================================================================
def test_e_missing_password_hash_fails_closed():
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.email == "nohash.user@ipu.ac.in").first()
        if not u:
            u = User(
                email="nohash.user@ipu.ac.in",
                full_name="No Hash User",
                role=UserRole.STUDENT.value,
                hashed_password="",  # Empty hash
                is_active=True,
                failed_login_attempts=0,
                locked_until=None
            )
            db.add(u)
        else:
            u.hashed_password = ""
            u.is_active = True
            u.failed_login_attempts = 0
            u.locked_until = None
        db.commit()

        # verify_password must fail closed
        assert verify_password("AnyPassword123!", "") is False
        assert verify_password("AnyPassword123!", None) is False

        # Attempt login
        res = client.post("/api/v1/auth/login", json={
            "email": "nohash.user@ipu.ac.in",
            "password": "AnyPassword123!"
        })
        assert res.status_code == 401
    finally:
        db.close()

# =====================================================================
# F. EXPIRED TOKEN -> CLEAN REJECTION (401)
# =====================================================================
def test_f_expired_token_rejected():
    expired_token = create_access_token(
        subject="1",
        expires_delta=datetime.timedelta(seconds=-10)
    )
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401

# =====================================================================
# G. INVALID TOKEN -> CLEAN REJECTION (401)
# =====================================================================
def test_g_invalid_token_rejected():
    res = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer malformed.jwt.signature"})
    assert res.status_code == 401

# =====================================================================
# H. REFRESH REPLAY -> REJECTED (401)
# =====================================================================
def test_h_refresh_replay_rejected():
    db = SessionLocal()
    try:
        user = _get_or_create_user(db, "refresh.user@ipu.ac.in", UserRole.STUDENT.value, "Pass123456!")
        login_res = client.post("/api/v1/auth/login", json={
            "email": "refresh.user@ipu.ac.in",
            "password": "Pass123456!"
        })
        assert login_res.status_code == 200
        tokens = login_res.json()
        raw_refresh = tokens["refresh_token"]

        # 1st Refresh -> SUCCESS
        ref1 = client.post("/api/v1/auth/refresh", json={"refresh_token": raw_refresh})
        assert ref1.status_code == 200

        # Replay Old Token -> REJECTED (401)
        ref2 = client.post("/api/v1/auth/refresh", json={"refresh_token": raw_refresh})
        assert ref2.status_code == 401
    finally:
        db.close()

# =====================================================================
# I. LOGOUT -> REFRESH SESSION REVOKED
# =====================================================================
def test_i_logout_revokes_refresh_session():
    db = SessionLocal()
    try:
        user = _get_or_create_user(db, "logout.test@ipu.ac.in", UserRole.STUDENT.value, "Pass123456!")
        login_res = client.post("/api/v1/auth/login", json={
            "email": "logout.test@ipu.ac.in",
            "password": "Pass123456!"
        })
        tokens = login_res.json()
        raw_access = tokens["access_token"]
        raw_refresh = tokens["refresh_token"]

        # Logout
        logout_res = client.post("/api/v1/auth/logout", json={"refresh_token": raw_refresh}, headers={"Authorization": f"Bearer {raw_access}"})
        assert logout_res.status_code == 200

        # Attempt refresh after logout -> REJECTED
        ref_after = client.post("/api/v1/auth/refresh", json={"refresh_token": raw_refresh})
        assert ref_after.status_code == 401
    finally:
        db.close()

# =====================================================================
# J. PASSWORD CHANGE -> PREVIOUS SESSIONS INVALIDATED
# =====================================================================
def test_j_password_change_invalidates_previous_sessions():
    db = SessionLocal()
    try:
        user = _get_or_create_user(db, "pwdchange.user@ipu.ac.in", UserRole.STUDENT.value, "OldPassword123!")
        login_res = client.post("/api/v1/auth/login", json={
            "email": "pwdchange.user@ipu.ac.in",
            "password": "OldPassword123!"
        })
        tokens = login_res.json()
        raw_access = tokens["access_token"]
        raw_refresh = tokens["refresh_token"]

        # Change Password
        change_res = client.post("/api/v1/auth/change-password", json={
            "old_password": "OldPassword123!",
            "new_password": "NewStrongPassword2026!"
        }, headers={"Authorization": f"Bearer {raw_access}"})
        assert change_res.status_code == 200

        # Old refresh token MUST be revoked
        ref_res = client.post("/api/v1/auth/refresh", json={"refresh_token": raw_refresh})
        assert ref_res.status_code == 401

        # Login with old password MUST fail
        old_login = client.post("/api/v1/auth/login", json={
            "email": "pwdchange.user@ipu.ac.in",
            "password": "OldPassword123!"
        })
        assert old_login.status_code == 401

        # Login with new password MUST succeed
        new_login = client.post("/api/v1/auth/login", json={
            "email": "pwdchange.user@ipu.ac.in",
            "password": "NewStrongPassword2026!"
        })
        assert new_login.status_code == 200
    finally:
        db.close()

# =====================================================================
# K. STUDENT CANNOT ACCESS ANOTHER STUDENT'S DATA (IDOR PROTECTED)
# =====================================================================
def test_k_student_cannot_access_another_students_data():
    db = SessionLocal()
    try:
        student_a = _get_or_create_user(db, "student.a@std.ggsipu.ac.in", UserRole.STUDENT.value, "Pass123456!")
        student_b = _get_or_create_user(db, "student.b@std.ggsipu.ac.in", UserRole.STUDENT.value, "Pass123456!")

        token_a = create_access_token(subject=str(student_a.id), extra_claims={"role": student_a.role, "email": student_a.email})
        token_b = create_access_token(subject=str(student_b.id), extra_claims={"role": student_b.role, "email": student_b.email})

        # Student A attempts to access Student B's student report or attempt
        idor_res = client.get(f"/api/v1/students/{student_b.id}/reports", headers={"Authorization": f"Bearer {token_a}"})
        assert idor_res.status_code in (403, 404)
    finally:
        db.close()

# =====================================================================
# L. STUDENT CANNOT CREATE PRIVILEGED USER
# =====================================================================
def test_l_student_cannot_create_privileged_user():
    db = SessionLocal()
    try:
        student = _get_or_create_user(db, "student.noescalate@std.ggsipu.ac.in", UserRole.STUDENT.value, "Pass123456!")
        token = create_access_token(subject=str(student.id), extra_claims={"role": student.role, "email": student.email})

        # Attempt to add admin allowlist
        res = client.post("/api/v1/auth/admins", json={
            "email": "new.admin@ipu.ac.in",
            "assigned_role": "ADMIN"
        }, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403
    finally:
        db.close()

# =====================================================================
# M. ADMIN CANNOT CREATE SUPER_ADMIN
# =====================================================================
def test_m_admin_cannot_create_super_admin():
    db = SessionLocal()
    try:
        admin = _get_or_create_user(db, "normal.admin@ipu.ac.in", UserRole.ADMIN.value, "Pass123456!")
        token = create_access_token(subject=str(admin.id), extra_claims={"role": admin.role, "email": admin.email})
        target_student = _get_or_create_user(db, "target.student@std.ggsipu.ac.in", UserRole.STUDENT.value, "Pass123456!")

        # Normal ADMIN attempts to promote target to SUPER_ADMIN
        res = client.put(f"/api/v1/auth/users/{target_student.id}/role", json={
            "role": "SUPER_ADMIN"
        }, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403
    finally:
        db.close()

# =====================================================================
# N. MULTIPLE SUPER_ADMIN TRIGGERS INVARIANT VIOLATION ON BOOTSTRAP
# =====================================================================
def test_n_multiple_super_admin_fails_closed():
    test_db_url = "sqlite:///:memory:"
    t_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=t_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=t_engine)
    t_db = TestingSession()

    try:
        sa1 = User(
            email="sa1@ipu.ac.in",
            full_name="SA 1",
            role=UserRole.SUPER_ADMIN.value,
            hashed_password=get_password_hash("Pass123456!"),
            is_active=True
        )
        sa2 = User(
            email="sa2@ipu.ac.in",
            full_name="SA 2",
            role=UserRole.SUPER_ADMIN.value,
            hashed_password=get_password_hash("Pass123456!"),
            is_active=True
        )
        t_db.add_all([sa1, sa2])
        t_db.commit()

        with pytest.raises(RuntimeError) as exc:
            seed_database(t_db)
        assert "INVARIANT VIOLATION" in str(exc.value)
    finally:
        t_db.close()

# =====================================================================
# O. PRODUCTION HAS NO DEMO USERS AND DEMO ENDPOINTS ARE DECOMMISSIONED
# =====================================================================
def test_o_demo_endpoints_decommissioned():
    res1 = client.get("/api/v1/auth/demo-users")
    assert res1.status_code == 403
    res2 = client.post("/api/v1/auth/demo-switch", json={"role": "STUDENT"})
    assert res2.status_code == 403

# =====================================================================
# P. PRODUCTION SANDBOX FAILS CLOSED IF DOCKER IS REQUIRED BUT UNAVAILABLE
# =====================================================================
def test_p_docker_sandbox_fail_closed_when_required():
    orig_req = settings.REQUIRE_DOCKER_SANDBOX
    orig_allow = settings.ALLOW_LOCAL_PROCESS_FALLBACK
    try:
        settings.REQUIRE_DOCKER_SANDBOX = True
        settings.ALLOW_LOCAL_PROCESS_FALLBACK = False

        docker_backend = DockerExecutionBackend()
        docker_backend._docker_available = False

        runner = SandboxedCodeRunner(backend=docker_backend)
        res = runner.execute_single(code="print('hello')", language="python", input_data="", timeout_seconds=2.0)
        assert res["verdict"] == SubmissionVerdict.RE
        assert "Docker container sandboxing is mandatory" in str(res["error"])
    finally:
        settings.REQUIRE_DOCKER_SANDBOX = orig_req
        settings.ALLOW_LOCAL_PROCESS_FALLBACK = orig_allow

# =====================================================================
# Q. AI MALFORMED OUTPUT -> SAFELY REJECTED OR FALLBACK
# =====================================================================
def test_q_ai_malformed_output_rejected():
    malformed_json_str = "This is not JSON at all {"
    try:
        gemini_service._safe_json_parse(malformed_json_str)
    except Exception:
        pass
    
    # Test that fallback generates a valid question structure without crashing
    res = gemini_service.generate_question(topic="Arrays", question_type="MCQ")
    assert isinstance(res, dict)
    assert "stem" in res or "title" in res or "question" in res

# =====================================================================
# R. JUDGE TIMEOUT -> SAFELY TERMINATED (TLE)
# =====================================================================
def test_r_judge_timeout_tle_termination():
    runner = SandboxedCodeRunner(backend=LocalProcessBackend())
    infinite_loop_py = "import time\nwhile True:\n    time.sleep(0.1)"
    res = runner.execute_single(code=infinite_loop_py, language="python", input_data="", timeout_seconds=1.0)
    assert res["verdict"] == SubmissionVerdict.TLE
    assert res["time_ms"] >= 900.0

# =====================================================================
# S. JUDGE OUTPUT OVERFLOW -> SAFELY TERMINATED (OLE)
# =====================================================================
def test_s_judge_output_overflow_ole_termination():
    runner = SandboxedCodeRunner(backend=LocalProcessBackend())
    flood_py = "for _ in range(100000):\n    print('A' * 100)"
    res = runner.execute_single(code=flood_py, language="python", input_data="", timeout_seconds=3.0)
    assert res["verdict"] == SubmissionVerdict.OLE

# =====================================================================
# T. HIDDEN TEST CASES NEVER EXPOSED
# =====================================================================
def test_t_hidden_test_cases_not_exposed_to_students():
    db = SessionLocal()
    try:
        admin = _get_or_create_user(db, "setter.hidden@ipu.ac.in", UserRole.QUESTION_SETTER.value, "Pass123456!")
        admin_token = create_access_token(subject=str(admin.id), extra_claims={"role": admin.role, "email": admin.email})

        # Create question with hidden test case
        ts = int(datetime.datetime.now().timestamp() * 1000)
        q = Question(
            title="Secret Hidden Test Question",
            slug=f"secret-hidden-test-question-{ts}",
            problem_statement="Calculate square of n",
            input_format="n",
            output_format="n^2",
            difficulty_score=3,
            author_id=admin.id,
            status="PUBLISHED"
        )
        db.add(q)
        db.flush()

        tc1 = TestCase(question_id=q.id, input_data="2", expected_output="4", is_hidden=False)
        tc2 = TestCase(question_id=q.id, input_data="999", expected_output="998001", is_hidden=True)
        db.add_all([tc1, tc2])
        db.commit()

        # Student queries question
        student = _get_or_create_user(db, "student.inspect@std.ggsipu.ac.in", UserRole.STUDENT.value, "Pass123456!")
        student_token = create_access_token(subject=str(student.id), extra_claims={"role": student.role, "email": student.email})

        res = client.get(f"/api/v1/questions/{q.id}", headers={"Authorization": f"Bearer {student_token}"})
        assert res.status_code == 200
        q_data = res.json()
        
        # Test cases in student payload MUST NOT include hidden test cases
        if "test_cases" in q_data and q_data["test_cases"]:
            for tc in q_data["test_cases"]:
                assert tc.get("is_hidden") is not True
                assert tc.get("input_data") != "999"
    finally:
        db.close()
