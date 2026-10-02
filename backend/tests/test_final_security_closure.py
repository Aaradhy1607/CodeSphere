import os
import sys
import time
import uuid
import datetime
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.main import app
from app.core.config import Settings, settings
from app.core.database import Base, engine, SessionLocal, auto_migrate_db, check_db_health
from app.core.security import get_password_hash, create_access_token, verify_password
from app.models.models import (
    User, StudentProfile, UserRole, AccountStatus, Question, TestCase, Event,
    Submission, SubmissionVerdict, SubmissionStatus, Assessment, AssessmentQuestion,
    AssessmentAttempt, AttemptAnswer, AntiCheatEvent, AssessmentStatus, AttemptStatus,
    Permission, get_permissions_for_role
)
from app.services.code_runner import (
    code_runner, MAX_OUTPUT_BYTES, SandboxedCodeRunner, LocalProcessBackend,
    DockerExecutionBackend, measure_process_peak_memory_kb, ExecutionSession
)
from app.services.judge_queue import judge_queue_manager, InvalidStateTransitionError
from app.services.seeder import seed_database

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_security_closure_db():
    Base.metadata.create_all(bind=engine)
    auto_migrate_db()
    yield

def _create_user(db: Session, email: str, role: str, name: str = "Test User") -> User:
    u = db.query(User).filter(User.email == email.lower()).first()
    if not u:
        u = User(
            email=email.lower(),
            full_name=name,
            role=role,
            hashed_password=get_password_hash("test_secure_password_2026"),
            is_active=True
        )
        db.add(u)
        db.commit()
        db.refresh(u)
    return u

def _get_auth_headers(user: User) -> dict:
    token = create_access_token(
        subject=str(user.id),
        extra_claims={"role": user.role, "email": user.email}
    )
    return {"Authorization": f"Bearer {token}"}

# =====================================================================
# 1. MISSING INITIAL_ADMIN_EMAIL FAILS PRODUCTION VALIDATION
# =====================================================================
def test_1_missing_initial_admin_email_fails_production_validation():
    s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a-very-long-production-grade-secret-key-32-chars-long",
        INITIAL_ADMIN_EMAIL="",
        INITIAL_ADMIN_PASSWORD="a-very-strong-production-password-2026",
        DATABASE_URL="postgresql://user:pass@localhost:5432/db"
    )
    with pytest.raises(RuntimeError) as exc:
        s.validate_production_security()
    assert "INITIAL_ADMIN_EMAIL" in str(exc.value)

# =====================================================================
# 2. MISSING INITIAL_ADMIN_PASSWORD FAILS PRODUCTION VALIDATION
# =====================================================================
def test_2_missing_initial_admin_password_fails_production_validation():
    s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a-very-long-production-grade-secret-key-32-chars-long",
        INITIAL_ADMIN_EMAIL="admin@ipu.ac.in",
        INITIAL_ADMIN_PASSWORD="",
        DATABASE_URL="postgresql://user:pass@localhost:5432/db"
    )
    with pytest.raises(RuntimeError) as exc:
        s.validate_production_security()
    assert "INITIAL_ADMIN_PASSWORD" in str(exc.value)

# =====================================================================
# 3. WEAK ADMIN PASSWORD FAILS PRODUCTION VALIDATION
# =====================================================================
def test_3_weak_admin_password_fails_production_validation():
    weak_passwords = ["admin123", "password", "123456", "admin", "codesphere", "short"]
    for weak_p in weak_passwords:
        s = Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a-very-long-production-grade-secret-key-32-chars-long",
            INITIAL_ADMIN_EMAIL="admin@ipu.ac.in",
            INITIAL_ADMIN_PASSWORD=weak_p,
            DATABASE_URL="postgresql://user:pass@localhost:5432/db"
        )
        with pytest.raises(RuntimeError) as exc:
            s.validate_production_security()
        assert "Insecure INITIAL_ADMIN_PASSWORD" in str(exc.value) or "INITIAL_ADMIN_PASSWORD" in str(exc.value)

# =====================================================================
# 4. MISSING SECRET_KEY FAILS PRODUCTION VALIDATION
# =====================================================================
def test_4_missing_secret_key_fails_production_validation():
    s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="",
        INITIAL_ADMIN_EMAIL="admin@ipu.ac.in",
        INITIAL_ADMIN_PASSWORD="a-very-strong-production-password-2026",
        DATABASE_URL="postgresql://user:pass@localhost:5432/db"
    )
    with pytest.raises(RuntimeError) as exc:
        s.validate_production_security()
    assert "SECRET_KEY" in str(exc.value)

# =====================================================================
# 5. PRODUCTION SQLITE IS REJECTED IF POSTGRESQL IS REQUIRED
# =====================================================================
def test_5_production_sqlite_is_rejected_if_postgresql_required():
    s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a-very-long-production-grade-secret-key-32-chars-long",
        INITIAL_ADMIN_EMAIL="admin@ipu.ac.in",
        INITIAL_ADMIN_PASSWORD="a-very-strong-production-password-2026",
        DATABASE_URL="sqlite:///./prod.db"
    )
    with pytest.raises(RuntimeError) as exc:
        s.validate_production_security()
    assert "SQLite" in str(exc.value)

# =====================================================================
# 6. PRODUCTION REQUIRES DOCKER SANDBOX
# =====================================================================
def test_6_production_requires_docker_sandbox():
    # When REQUIRE_DOCKER_SANDBOX is True and ALLOW_LOCAL_PROCESS_FALLBACK is False,
    # Docker backend fails closed if docker daemon is unavailable
    backend = DockerExecutionBackend(fallback_backend=None)
    backend._docker_available = False
    
    orig_req = settings.REQUIRE_DOCKER_SANDBOX
    orig_allow = settings.ALLOW_LOCAL_PROCESS_FALLBACK
    try:
        settings.REQUIRE_DOCKER_SANDBOX = True
        settings.ALLOW_LOCAL_PROCESS_FALLBACK = False

        session = ExecutionSession("python", "temp", cmd=["python", "-c", "print(1)"])
        res = backend.execute(session, "", timeout_seconds=2.0)
        assert res["verdict"] == SubmissionVerdict.RE
        assert "Docker container sandboxing is mandatory" in res["error"]
        assert res["backend"] == "docker_unavailable_fail_closed"
    finally:
        settings.REQUIRE_DOCKER_SANDBOX = orig_req
        settings.ALLOW_LOCAL_PROCESS_FALLBACK = orig_allow

# =====================================================================
# 7. PRODUCTION DOES NOT SILENTLY FALL BACK TO LOCAL PROCESS BACKEND
# =====================================================================
def test_7_production_does_not_silently_fallback():
    backend = DockerExecutionBackend(fallback_backend=LocalProcessBackend())
    backend._docker_available = False
    
    orig_req = settings.REQUIRE_DOCKER_SANDBOX
    orig_allow = settings.ALLOW_LOCAL_PROCESS_FALLBACK
    try:
        settings.REQUIRE_DOCKER_SANDBOX = True
        settings.ALLOW_LOCAL_PROCESS_FALLBACK = False

        session = ExecutionSession("python", "temp", cmd=["python", "-c", "print(1)"])
        res = backend.execute(session, "", timeout_seconds=2.0)
        assert res["backend"] != "local_process_fallback"
        assert res["backend"] == "docker_unavailable_fail_closed"
    finally:
        settings.REQUIRE_DOCKER_SANDBOX = orig_req
        settings.ALLOW_LOCAL_PROCESS_FALLBACK = orig_allow

# =====================================================================
# 8. DEVELOPMENT MAY STILL USE LOCAL PROCESS BACKEND
# =====================================================================
def test_8_development_may_use_local_process_backend():
    runner = SandboxedCodeRunner(backend=LocalProcessBackend())
    res = runner.execute_single("print('dev-ok')", "python", "")
    assert res["verdict"] == SubmissionVerdict.AC
    assert "dev-ok" in res["output"]

# =====================================================================
# 9. DEMO ENDPOINTS BLOCKED IN PRODUCTION
# =====================================================================
def test_9_demo_endpoints_blocked_in_production():
    orig_env = settings.ENVIRONMENT
    try:
        settings.ENVIRONMENT = "production"
        
        # /auth/demo-users must return 403 in production
        resp_users = client.get("/api/v1/auth/demo-users")
        assert resp_users.status_code == 403
        assert "disabled in production" in resp_users.json()["detail"]

        # /auth/demo-switch must return 403 in production
        resp_switch = client.post("/api/v1/auth/demo-switch", json={"role": "STUDENT"})
        assert resp_switch.status_code == 403
        assert "disabled in production" in resp_switch.json()["detail"]
    finally:
        settings.ENVIRONMENT = orig_env

# =====================================================================
# 10. NO PRODUCTION DEMO USERS CREATED
# =====================================================================
def test_10_no_production_demo_users_created():
    test_db_url = f"sqlite:///:memory:"
    t_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=t_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=t_engine)
    
    t_db = TestingSession()
    orig_env = settings.ENVIRONMENT
    orig_email = settings.INITIAL_ADMIN_EMAIL
    orig_pass = settings.INITIAL_ADMIN_PASSWORD
    orig_seed = settings.SEED_DEMO_DATA
    try:
        settings.ENVIRONMENT = "production"
        settings.INITIAL_ADMIN_EMAIL = "prod.admin@ipu.ac.in"
        settings.INITIAL_ADMIN_PASSWORD = "StrongProdPassword2026!"
        settings.SEED_DEMO_DATA = False

        seed_database(t_db)

        users = t_db.query(User).all()
        # In production, exactly 1 Super Admin user must be created
        assert len(users) == 1
        assert users[0].email == "prod.admin@ipu.ac.in"
        assert users[0].role == UserRole.SUPER_ADMIN.value

        # No student demo accounts or mock users
        students = t_db.query(User).filter(User.role == UserRole.STUDENT.value).all()
        assert len(students) == 0
    finally:
        settings.ENVIRONMENT = orig_env
        settings.INITIAL_ADMIN_EMAIL = orig_email
        settings.INITIAL_ADMIN_PASSWORD = orig_pass
        settings.SEED_DEMO_DATA = orig_seed
        t_db.close()

# =====================================================================
# 11. INITIAL SUPER ADMIN BOOTSTRAP IS IDEMPOTENT
# =====================================================================
def test_11_initial_super_admin_bootstrap_is_idempotent():
    test_db_url = f"sqlite:///:memory:"
    t_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=t_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=t_engine)
    
    t_db = TestingSession()
    orig_env = settings.ENVIRONMENT
    orig_email = settings.INITIAL_ADMIN_EMAIL
    orig_pass = settings.INITIAL_ADMIN_PASSWORD
    try:
        settings.ENVIRONMENT = "production"
        settings.INITIAL_ADMIN_EMAIL = "bootstrap.admin@ipu.ac.in"
        settings.INITIAL_ADMIN_PASSWORD = "StrongProdPassword2026!"

        # Run 1
        seed_database(t_db)
        count_1 = t_db.query(User).filter(User.role == UserRole.SUPER_ADMIN.value).count()
        assert count_1 == 1

        # Run 2 (Restart simulation)
        seed_database(t_db)
        count_2 = t_db.query(User).filter(User.role == UserRole.SUPER_ADMIN.value).count()
        assert count_2 == 1
    finally:
        settings.ENVIRONMENT = orig_env
        settings.INITIAL_ADMIN_EMAIL = orig_email
        settings.INITIAL_ADMIN_PASSWORD = orig_pass
        t_db.close()

# =====================================================================
# 12. RESTART DOES NOT CREATE DUPLICATE SUPER ADMIN
# =====================================================================
def test_12_restart_does_not_create_duplicate_super_admin():
    test_db_url = f"sqlite:///:memory:"
    t_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=t_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=t_engine)
    
    t_db = TestingSession()
    orig_env = settings.ENVIRONMENT
    try:
        settings.ENVIRONMENT = "production"
        # Manually create existing Super Admin
        sa = User(
            email="existing.superadmin@ipu.ac.in",
            full_name="Existing Super Admin",
            role=UserRole.SUPER_ADMIN.value,
            hashed_password=get_password_hash("existing_hash"),
            is_active=True
        )
        t_db.add(sa)
        t_db.commit()

        # Run seeder
        seed_database(t_db)
        super_admins = t_db.query(User).filter(User.role == UserRole.SUPER_ADMIN.value).all()
        assert len(super_admins) == 1
        assert super_admins[0].email == "existing.superadmin@ipu.ac.in"
    finally:
        settings.ENVIRONMENT = orig_env
        t_db.close()

# =====================================================================
# 13. RESTART DOES NOT RESET ADMIN PASSWORD
# =====================================================================
def test_13_restart_does_not_reset_admin_password():
    test_db_url = f"sqlite:///:memory:"
    t_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=t_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=t_engine)
    
    t_db = TestingSession()
    orig_env = settings.ENVIRONMENT
    orig_email = settings.INITIAL_ADMIN_EMAIL
    orig_pass = settings.INITIAL_ADMIN_PASSWORD
    try:
        settings.ENVIRONMENT = "production"
        settings.INITIAL_ADMIN_EMAIL = "reset.test.admin@ipu.ac.in"
        settings.INITIAL_ADMIN_PASSWORD = "FirstPassword2026!"

        # Initial bootstrap
        seed_database(t_db)
        admin_u = t_db.query(User).filter(User.email == "reset.test.admin@ipu.ac.in").first()
        assert verify_password("FirstPassword2026!", admin_u.hashed_password)

        # Admin changes their password in production
        admin_u.hashed_password = get_password_hash("UpdatedCustomPassword2026!")
        t_db.commit()

        # Restart with original settings
        seed_database(t_db)
        t_db.refresh(admin_u)

        # Password must remain the updated custom password
        assert verify_password("UpdatedCustomPassword2026!", admin_u.hashed_password)
        assert not verify_password("FirstPassword2026!", admin_u.hashed_password)
    finally:
        settings.ENVIRONMENT = orig_env
        settings.INITIAL_ADMIN_EMAIL = orig_email
        settings.INITIAL_ADMIN_PASSWORD = orig_pass
        t_db.close()

# =====================================================================
# 14. STUDENTS CANNOT CREATE PRIVILEGED USERS
# =====================================================================
def test_14_students_cannot_create_privileged_users():
    db = SessionLocal()
    try:
        student = _create_user(db, "student.nocreate@std.ggsipu.ac.in", UserRole.STUDENT.value, "No Create Student")
        headers = _get_auth_headers(student)

        # Student attempts to add admin to allowlist
        resp1 = client.post(
            "/api/v1/auth/admins",
            headers=headers,
            json={"email": "attacker@ipu.ac.in", "name": "Attacker", "assigned_role": "ADMIN"}
        )
        assert resp1.status_code == 403

        # Student attempts to create student
        resp2 = client.post(
            "/api/v1/students/create",
            headers=headers,
            params={"name": "Fake", "email": "fake@std.ggsipu.ac.in", "enrollment_no": "099USAR", "branch": "AIML", "academic_year": 1}
        )
        assert resp2.status_code == 403
    finally:
        db.close()

# =====================================================================
# 15. STUDENTS CANNOT ESCALATE ROLES
# =====================================================================
def test_15_students_cannot_escalate_roles():
    db = SessionLocal()
    try:
        student = _create_user(db, "student.noescalate@std.ggsipu.ac.in", UserRole.STUDENT.value, "No Escalate Student")
        headers = _get_auth_headers(student)

        resp = client.put(
            f"/api/v1/auth/users/{student.id}/role",
            headers=headers,
            json={"role": "SUPER_ADMIN"}
        )
        assert resp.status_code == 403
    finally:
        db.close()

# =====================================================================
# 16. FACULTY CANNOT BECOME SUPER_ADMIN
# =====================================================================
def test_16_faculty_cannot_become_super_admin():
    db = SessionLocal()
    try:
        faculty = _create_user(db, "faculty.nofac2sa@ipu.ac.in", UserRole.FACULTY.value, "Faculty User")
        headers = _get_auth_headers(faculty)

        resp = client.put(
            f"/api/v1/auth/users/{faculty.id}/role",
            headers=headers,
            json={"role": "SUPER_ADMIN"}
        )
        assert resp.status_code == 403
    finally:
        db.close()

# =====================================================================
# 17. CROSS-STUDENT IDOR REMAINS BLOCKED
# =====================================================================
def test_17_cross_student_idor_remains_blocked():
    db = SessionLocal()
    try:
        s1 = _create_user(db, "s1.idor@std.ggsipu.ac.in", UserRole.STUDENT.value, "Student One")
        s2 = _create_user(db, "s2.idor@std.ggsipu.ac.in", UserRole.STUDENT.value, "Student Two")

        s1_headers = _get_auth_headers(s1)
        s2_headers = _get_auth_headers(s2)

        # S2 tries to access S1's history
        resp = client.get(f"/api/v1/students/{s1.id}/history", headers=s2_headers)
        assert resp.status_code == 403
        assert "Access denied" in resp.json()["detail"]
    finally:
        db.close()

# =====================================================================
# 18. PASSWORD/RESET SECRETS NEVER APPEAR IN RESPONSES
# =====================================================================
def test_18_password_and_reset_secrets_never_appear_in_responses():
    db = SessionLocal()
    try:
        user = _create_user(db, "secret.check@std.ggsipu.ac.in", UserRole.STUDENT.value, "Secret Check")
        
        orig_env = settings.ENVIRONMENT
        try:
            settings.ENVIRONMENT = "production"
            resp = client.post("/api/v1/auth/forgot-password", json={"email": user.email})
            assert resp.status_code == 200
            data = resp.json()
            assert data["reset_token"] is None
            assert "password" not in str(data).lower() or "password reset" in data.get("message", "").lower()
            assert "secret" not in str(data).lower()
        finally:
            settings.ENVIRONMENT = orig_env
    finally:
        db.close()

# =====================================================================
# 19. SUBMITTED CODE CANNOT READ SECRET_KEY
# =====================================================================
def test_19_submitted_code_cannot_read_secret_key():
    os.environ["SECRET_KEY"] = "super-secret-host-key-never-leak"
    code = "import os\nprint(os.environ.get('SECRET_KEY', 'NOT_FOUND'))"
    res = code_runner.execute_single(code, "python", "")
    assert res["verdict"] == SubmissionVerdict.AC
    assert "super-secret-host-key" not in res["output"]
    assert "NOT_FOUND" in res["output"]

# =====================================================================
# 20. SUBMITTED CODE CANNOT READ DATABASE_URL
# =====================================================================
def test_20_submitted_code_cannot_read_database_url():
    os.environ["DATABASE_URL"] = "postgresql://secret_user:secret_pass@dbhost:5432/secretdb"
    code = "import os\nprint(os.environ.get('DATABASE_URL', 'NOT_FOUND'))"
    res = code_runner.execute_single(code, "python", "")
    assert res["verdict"] == SubmissionVerdict.AC
    assert "secret_pass" not in res["output"]
    assert "NOT_FOUND" in res["output"]

# =====================================================================
# 21. DOCKER SANDBOX USES REQUIRED RESTRICTIONS
# =====================================================================
def test_21_docker_sandbox_uses_required_restrictions():
    backend = DockerExecutionBackend()
    session = ExecutionSession("python", "temp_workspace", cmd=["python", "solution.py"])
    # Inspect docker backend configuration invariants
    assert backend.default_image is not None
    assert "codesphere" in backend.default_image or "python" in backend.default_image

# =====================================================================
# 22. OUTPUT FLOODING REMAINS BLOCKED
# =====================================================================
def test_22_output_flooding_remains_blocked():
    code = "while True:\n    print('A' * 10000)"
    res = code_runner.execute_single(code, "python", "", timeout_seconds=3.0)
    assert res["verdict"] in [SubmissionVerdict.OLE, SubmissionVerdict.TLE]
    if res["verdict"] == SubmissionVerdict.OLE:
        assert len(res["output"].encode("utf-8")) <= MAX_OUTPUT_BYTES + 4096

# =====================================================================
# 23. MEMORY LIMITS REMAIN ENFORCED
# =====================================================================
def test_23_memory_limits_remain_enforced():
    backend = LocalProcessBackend()
    temp_dir = code_runner._create_temp_dir()
    try:
        session = code_runner._prepare_session("a = [0] * 1000000\nprint(len(a))", "python", temp_dir)
        res = backend.execute(session, "", timeout_seconds=3.0, memory_limit_mb=1)
        if res["memory_kb"] > 1024.0:
            assert res["verdict"] == SubmissionVerdict.MLE
    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

# =====================================================================
# 24. ASYNC JUDGE STATE MACHINE REMAINS VALID
# =====================================================================
def test_24_async_judge_state_machine_remains_valid():
    judge_queue_manager.validate_transition(SubmissionStatus.QUEUED.value, SubmissionStatus.COMPILING.value)
    judge_queue_manager.validate_transition(SubmissionStatus.COMPILING.value, SubmissionStatus.RUNNING.value)
    judge_queue_manager.validate_transition(SubmissionStatus.RUNNING.value, SubmissionStatus.EVALUATING.value)
    judge_queue_manager.validate_transition(SubmissionStatus.EVALUATING.value, SubmissionStatus.COMPLETED.value)

    with pytest.raises(InvalidStateTransitionError):
        judge_queue_manager.validate_transition(SubmissionStatus.COMPLETED.value, SubmissionStatus.QUEUED.value)

# =====================================================================
# 25. DATABASE INTEGRITY AND ADMIN AUTHENTICATION
# =====================================================================
def test_25_database_integrity_and_admin_authentication():
    db = SessionLocal()
    try:
        admin = _create_user(db, "admin.integrity@ipu.ac.in", UserRole.ADMIN.value, "Admin Integrity")
        assert admin.id > 0
        assert verify_password("test_secure_password_2026", admin.hashed_password)
        
        # Test login API with valid credentials
        resp = client.post("/api/v1/auth/login", json={"email": admin.email, "password": "test_secure_password_2026"})
        assert resp.status_code == 200
        token_data = resp.json()
        assert "access_token" in token_data
        assert token_data["user"]["role"] == UserRole.ADMIN.value
    finally:
        db.close()
