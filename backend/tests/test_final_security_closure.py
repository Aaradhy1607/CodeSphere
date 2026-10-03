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
# 2. EMPTY INITIAL_ADMIN_EMAIL FAILS VALIDATION
# =====================================================================
def test_2_empty_initial_admin_email_fails_validation():
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
# 3. WHITESPACE-ONLY INITIAL_ADMIN_EMAIL FAILS VALIDATION
# =====================================================================
def test_3_whitespace_initial_admin_email_fails_validation():
    s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a-very-long-production-grade-secret-key-32-chars-long",
        INITIAL_ADMIN_EMAIL="   \t\n  ",
        INITIAL_ADMIN_PASSWORD="a-very-strong-production-password-2026",
        DATABASE_URL="postgresql://user:pass@localhost:5432/db"
    )
    with pytest.raises(RuntimeError) as exc:
        s.validate_production_security()
    assert "INITIAL_ADMIN_EMAIL" in str(exc.value)

# =====================================================================
# 4. MISSING INITIAL_ADMIN_PASSWORD FAILS PRODUCTION VALIDATION
# =====================================================================
def test_4_missing_initial_admin_password_fails_production_validation():
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
# 5. WEAK/DEFAULT ADMIN PASSWORD FAILS PRODUCTION VALIDATION
# =====================================================================
def test_5_weak_admin_password_fails_production_validation():
    weak_passwords = ["admin123", "password", "123456", "admin", "codesphere", "short", "   "]
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
        assert "INITIAL_ADMIN_PASSWORD" in str(exc.value)

# =====================================================================
# 6. MISSING SECRET_KEY FAILS PRODUCTION VALIDATION
# =====================================================================
def test_6_missing_secret_key_fails_production_validation():
    invalid_keys = ["", "short-key", "codesphere-usar-super-secret-jwt-key-2026-production-ready", "admin123", "   "]
    for inv_k in invalid_keys:
        s = Settings(
            ENVIRONMENT="production",
            SECRET_KEY=inv_k,
            INITIAL_ADMIN_EMAIL="admin@ipu.ac.in",
            INITIAL_ADMIN_PASSWORD="a-very-strong-production-password-2026",
            DATABASE_URL="postgresql://user:pass@localhost:5432/db"
        )
        with pytest.raises(RuntimeError) as exc:
            s.validate_production_security()
        assert "SECRET_KEY" in str(exc.value)

# =====================================================================
# 7. EXISTING SUPER_ADMIN -> BOOTSTRAP IS STRICTLY IDEMPOTENT
# =====================================================================
def test_7_existing_super_admin_bootstrap_is_idempotent():
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
# 8. EXISTING SUPER_ADMIN PASSWORD REMAINS UNCHANGED AFTER REPEATED BOOTSTRAP
# =====================================================================
def test_8_existing_super_admin_password_remains_unchanged():
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

        # Admin updates their password in production
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
# 9. EXISTING SUPER_ADMIN EMAIL REMAINS UNCHANGED
# =====================================================================
def test_9_existing_super_admin_email_remains_unchanged():
    test_db_url = f"sqlite:///:memory:"
    t_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=t_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=t_engine)

    t_db = TestingSession()
    orig_env = settings.ENVIRONMENT
    orig_email = settings.INITIAL_ADMIN_EMAIL
    try:
        settings.ENVIRONMENT = "production"
        settings.INITIAL_ADMIN_EMAIL = "different.email@ipu.ac.in"

        sa = User(
            email="original.superadmin@ipu.ac.in",
            full_name="Original Super Admin",
            role=UserRole.SUPER_ADMIN.value,
            hashed_password=get_password_hash("existing_hash"),
            is_active=True
        )
        t_db.add(sa)
        t_db.commit()

        # Seed with different initial email in env
        seed_database(t_db)

        super_admins = t_db.query(User).filter(User.role == UserRole.SUPER_ADMIN.value).all()
        assert len(super_admins) == 1
        assert super_admins[0].email == "original.superadmin@ipu.ac.in"
    finally:
        settings.ENVIRONMENT = orig_env
        settings.INITIAL_ADMIN_EMAIL = orig_email
        t_db.close()

# =====================================================================
# 10. EXISTING NORMAL USER WITH INITIAL_ADMIN_EMAIL IS NOT PROMOTED (FAILS SAFELY)
# =====================================================================
def test_10_existing_normal_user_is_not_silently_promoted():
    test_db_url = f"sqlite:///:memory:"
    t_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=t_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=t_engine)

    t_db = TestingSession()
    orig_env = settings.ENVIRONMENT
    orig_email = settings.INITIAL_ADMIN_EMAIL
    try:
        settings.ENVIRONMENT = "production"
        settings.INITIAL_ADMIN_EMAIL = "target.user@ipu.ac.in"

        # Pre-existing user with non-privileged role
        normal_u = User(
            email="target.user@ipu.ac.in",
            full_name="Normal User",
            role="GUEST",
            hashed_password=get_password_hash("guestpass"),
            is_active=True
        )
        t_db.add(normal_u)
        t_db.commit()

        # Seeder must fail closed rather than promoting this user to SUPER_ADMIN
        with pytest.raises(RuntimeError) as exc:
            seed_database(t_db)
        assert "Automatic promotion to SUPER_ADMIN is blocked" in str(exc.value)

        # Verify user role is still un-escalated
        t_db.refresh(normal_u)
        assert normal_u.role == "GUEST"
    finally:
        settings.ENVIRONMENT = orig_env
        settings.INITIAL_ADMIN_EMAIL = orig_email
        t_db.close()

# =====================================================================
# 11. EXISTING FACULTY WITH INITIAL_ADMIN_EMAIL CANNOT BECOME SUPER_ADMIN
# =====================================================================
def test_11_existing_faculty_cannot_become_super_admin():
    test_db_url = f"sqlite:///:memory:"
    t_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=t_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=t_engine)

    t_db = TestingSession()
    orig_env = settings.ENVIRONMENT
    orig_email = settings.INITIAL_ADMIN_EMAIL
    try:
        settings.ENVIRONMENT = "production"
        settings.INITIAL_ADMIN_EMAIL = "faculty.member@ipu.ac.in"

        faculty_u = User(
            email="faculty.member@ipu.ac.in",
            full_name="Prof. Member",
            role=UserRole.FACULTY.value,
            hashed_password=get_password_hash("facultypass"),
            is_active=True
        )
        t_db.add(faculty_u)
        t_db.commit()

        with pytest.raises(RuntimeError) as exc:
            seed_database(t_db)
        assert "FACULTY" in str(exc.value)

        t_db.refresh(faculty_u)
        assert faculty_u.role == UserRole.FACULTY.value
    finally:
        settings.ENVIRONMENT = orig_env
        settings.INITIAL_ADMIN_EMAIL = orig_email
        t_db.close()

# =====================================================================
# 12. EXISTING STUDENT WITH INITIAL_ADMIN_EMAIL CANNOT BECOME SUPER_ADMIN
# =====================================================================
def test_12_existing_student_cannot_become_super_admin():
    test_db_url = f"sqlite:///:memory:"
    t_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=t_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=t_engine)

    t_db = TestingSession()
    orig_env = settings.ENVIRONMENT
    orig_email = settings.INITIAL_ADMIN_EMAIL
    try:
        settings.ENVIRONMENT = "production"
        settings.INITIAL_ADMIN_EMAIL = "student.member@std.ggsipu.ac.in"

        student_u = User(
            email="student.member@std.ggsipu.ac.in",
            full_name="Student Member",
            role=UserRole.STUDENT.value,
            hashed_password=get_password_hash("studentpass"),
            is_active=True
        )
        t_db.add(student_u)
        t_db.commit()

        with pytest.raises(RuntimeError) as exc:
            seed_database(t_db)
        assert "STUDENT" in str(exc.value)

        t_db.refresh(student_u)
        assert student_u.role == UserRole.STUDENT.value
    finally:
        settings.ENVIRONMENT = orig_env
        settings.INITIAL_ADMIN_EMAIL = orig_email
        t_db.close()

# =====================================================================
# 13. EXISTING ADMIN WITH INITIAL_ADMIN_EMAIL IS NOT SILENTLY OVERWRITTEN
# =====================================================================
def test_13_existing_admin_cannot_be_silently_converted():
    test_db_url = f"sqlite:///:memory:"
    t_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=t_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=t_engine)

    t_db = TestingSession()
    orig_env = settings.ENVIRONMENT
    orig_email = settings.INITIAL_ADMIN_EMAIL
    try:
        settings.ENVIRONMENT = "production"
        settings.INITIAL_ADMIN_EMAIL = "admin.operations@ipu.ac.in"

        admin_u = User(
            email="admin.operations@ipu.ac.in",
            full_name="Ops Admin",
            role=UserRole.ADMIN.value,
            hashed_password=get_password_hash("adminpass"),
            is_active=True
        )
        t_db.add(admin_u)
        t_db.commit()

        with pytest.raises(RuntimeError) as exc:
            seed_database(t_db)
        assert "ADMIN" in str(exc.value)

        t_db.refresh(admin_u)
        assert admin_u.role == UserRole.ADMIN.value
    finally:
        settings.ENVIRONMENT = orig_env
        settings.INITIAL_ADMIN_EMAIL = orig_email
        t_db.close()

# =====================================================================
# 14. NO SUPER_ADMIN + NO CONFLICT -> EXACTLY ONE SUPER_ADMIN CREATED
# =====================================================================
def test_14_clean_bootstrap_creates_exactly_one_super_admin():
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
        settings.INITIAL_ADMIN_EMAIL = "new.superadmin@ipu.ac.in"
        settings.INITIAL_ADMIN_PASSWORD = "StrongProdPassword2026!"

        seed_database(t_db)

        super_admins = t_db.query(User).filter(User.role == UserRole.SUPER_ADMIN.value).all()
        assert len(super_admins) == 1
        assert super_admins[0].email == "new.superadmin@ipu.ac.in"
        assert super_admins[0].is_active is True
    finally:
        settings.ENVIRONMENT = orig_env
        settings.INITIAL_ADMIN_EMAIL = orig_email
        settings.INITIAL_ADMIN_PASSWORD = orig_pass
        t_db.close()

# =====================================================================
# 15. RUNNING BOOTSTRAP MULTIPLE TIMES KEEPS EXACTLY ONE SUPER_ADMIN
# =====================================================================
def test_15_repeated_bootstrap_maintains_single_super_admin():
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
        settings.INITIAL_ADMIN_EMAIL = "repeated.superadmin@ipu.ac.in"
        settings.INITIAL_ADMIN_PASSWORD = "StrongProdPassword2026!"

        for _ in range(5):
            seed_database(t_db)

        super_admins = t_db.query(User).filter(User.role == UserRole.SUPER_ADMIN.value).all()
        assert len(super_admins) == 1
        assert super_admins[0].email == "repeated.superadmin@ipu.ac.in"
    finally:
        settings.ENVIRONMENT = orig_env
        settings.INITIAL_ADMIN_EMAIL = orig_email
        settings.INITIAL_ADMIN_PASSWORD = orig_pass
        t_db.close()

# =====================================================================
# 16. NO PLAINTEXT ADMIN PASSWORD APPEARS IN DATABASE
# =====================================================================
def test_16_no_plaintext_admin_password_in_db():
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
        raw_pw = "SuperSecretUnstoredPassword123!"
        settings.INITIAL_ADMIN_EMAIL = "plaintext.check@ipu.ac.in"
        settings.INITIAL_ADMIN_PASSWORD = raw_pw

        seed_database(t_db)

        admin = t_db.query(User).filter(User.email == "plaintext.check@ipu.ac.in").first()
        assert admin is not None
        assert admin.hashed_password != raw_pw
        assert raw_pw not in admin.hashed_password
        assert verify_password(raw_pw, admin.hashed_password)
    finally:
        settings.ENVIRONMENT = orig_env
        settings.INITIAL_ADMIN_EMAIL = orig_email
        settings.INITIAL_ADMIN_PASSWORD = orig_pass
        t_db.close()

# =====================================================================
# 17. NO PASSWORD OR SECRET IS EMITTED IN VALIDATION/BOOTSTRAP ERROR MESSAGES
# =====================================================================
def test_17_no_password_or_secret_emitted_in_errors():
    secret_pass = "MySuperSecretPasswordNeverLeak123!"
    s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="short",
        INITIAL_ADMIN_EMAIL="admin@ipu.ac.in",
        INITIAL_ADMIN_PASSWORD=secret_pass,
        DATABASE_URL="postgresql://user:pass@localhost:5432/db"
    )
    with pytest.raises(RuntimeError) as exc:
        s.validate_production_security()
    error_msg = str(exc.value)
    assert secret_pass not in error_msg
    assert "short" not in error_msg

# =====================================================================
# 18. BOOTSTRAP FAILURE ROLLS BACK CLEANLY
# =====================================================================
def test_18_bootstrap_failure_rolls_back_cleanly():
    test_db_url = f"sqlite:///:memory:"
    t_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=t_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=t_engine)

    t_db = TestingSession()
    orig_env = settings.ENVIRONMENT
    orig_email = settings.INITIAL_ADMIN_EMAIL
    try:
        settings.ENVIRONMENT = "production"
        settings.INITIAL_ADMIN_EMAIL = "conflict@ipu.ac.in"

        # Pre-seed conflicting student
        st = User(
            email="conflict@ipu.ac.in",
            full_name="Conflict User",
            role=UserRole.STUDENT.value,
            hashed_password=get_password_hash("pass"),
            is_active=True
        )
        t_db.add(st)
        t_db.commit()

        with pytest.raises(RuntimeError):
            seed_database(t_db)

        # No partially created Super Admin or orphaned records
        sa_count = t_db.query(User).filter(User.role == UserRole.SUPER_ADMIN.value).count()
        assert sa_count == 0
    finally:
        settings.ENVIRONMENT = orig_env
        settings.INITIAL_ADMIN_EMAIL = orig_email
        t_db.close()

# =====================================================================
# 19. EXISTING PRODUCTION DEMO-DATA PROHIBITION REMAINS INTACT
# =====================================================================
def test_19_existing_production_demo_data_prohibition():
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
        settings.INITIAL_ADMIN_EMAIL = "prod.clean@ipu.ac.in"
        settings.INITIAL_ADMIN_PASSWORD = "StrongProdPassword2026!"
        settings.SEED_DEMO_DATA = False

        seed_database(t_db)

        users = t_db.query(User).all()
        # In production, exactly 1 Super Admin user must be created
        assert len(users) == 1
        assert users[0].email == "prod.clean@ipu.ac.in"
        assert users[0].role == UserRole.SUPER_ADMIN.value

        # No demo students or mock users seeded
        students = t_db.query(User).filter(User.role == UserRole.STUDENT.value).all()
        assert len(students) == 0
    finally:
        settings.ENVIRONMENT = orig_env
        settings.INITIAL_ADMIN_EMAIL = orig_email
        settings.INITIAL_ADMIN_PASSWORD = orig_pass
        settings.SEED_DEMO_DATA = orig_seed
        t_db.close()

# =====================================================================
# 20. EXISTING RBAC / IDOR / PRIVILEGE SECURITY TESTS PASS
# =====================================================================
def test_20_students_cannot_create_privileged_users_or_escalate():
    db = SessionLocal()
    try:
        student = _create_user(db, "student.rbac.check@std.ggsipu.ac.in", UserRole.STUDENT.value, "RBAC Check Student")
        headers = _get_auth_headers(student)

        # 1. Attempt to add admin to allowlist
        resp1 = client.post(
            "/api/v1/auth/admins",
            headers=headers,
            json={"email": "hacker@ipu.ac.in", "name": "Hacker", "assigned_role": "ADMIN"}
        )
        assert resp1.status_code == 403

        # 2. Attempt role escalation
        resp2 = client.put(
            f"/api/v1/auth/users/{student.id}/role",
            headers=headers,
            json={"role": "SUPER_ADMIN"}
        )
        assert resp2.status_code == 403

        # 3. IDOR check against another student
        other_student = _create_user(db, "other.student@std.ggsipu.ac.in", UserRole.STUDENT.value, "Other Student")
        resp3 = client.get(f"/api/v1/students/{other_student.id}/history", headers=headers)
        assert resp3.status_code == 403
    finally:
        db.close()

# =====================================================================
# 21. INVARIANT VIOLATION ON MULTIPLE SUPER_ADMIN RECORDS
# =====================================================================
def test_21_multiple_super_admins_trigger_invariant_violation():
    test_db_url = f"sqlite:///:memory:"
    t_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=t_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=t_engine)

    t_db = TestingSession()
    orig_env = settings.ENVIRONMENT
    try:
        settings.ENVIRONMENT = "production"
        sa1 = User(
            email="sa1@ipu.ac.in",
            full_name="SA 1",
            role=UserRole.SUPER_ADMIN.value,
            hashed_password=get_password_hash("pass1"),
            is_active=True
        )
        sa2 = User(
            email="sa2@ipu.ac.in",
            full_name="SA 2",
            role=UserRole.SUPER_ADMIN.value,
            hashed_password=get_password_hash("pass2"),
            is_active=True
        )
        t_db.add(sa1)
        t_db.add(sa2)
        t_db.commit()

        with pytest.raises(RuntimeError) as exc:
            seed_database(t_db)
        assert "Multiple SUPER_ADMIN records" in str(exc.value)
    finally:
        settings.ENVIRONMENT = orig_env
        t_db.close()

# =====================================================================
# 22. SUBMITTED CODE CANNOT READ HOST SECRETS
# =====================================================================
def test_22_submitted_code_cannot_read_host_secrets():
    os.environ["SECRET_KEY"] = "super-secret-host-key-never-leak"
    os.environ["DATABASE_URL"] = "postgresql://secret_user:secret_pass@dbhost:5432/secretdb"
    code = "import os\nprint(os.environ.get('SECRET_KEY', 'NOT_FOUND_SEC'))\nprint(os.environ.get('DATABASE_URL', 'NOT_FOUND_DB'))"
    res = code_runner.execute_single(code, "python", "")
    assert res["verdict"] == SubmissionVerdict.AC
    assert "super-secret-host-key" not in res["output"]
    assert "secret_pass" not in res["output"]
    assert "NOT_FOUND_SEC" in res["output"]
    assert "NOT_FOUND_DB" in res["output"]

# =====================================================================
# 23. OUTPUT FLOODING REMAINS BLOCKED
# =====================================================================
def test_23_output_flooding_remains_blocked():
    code = "while True:\n    print('A' * 10000)"
    res = code_runner.execute_single(code, "python", "", timeout_seconds=3.0)
    assert res["verdict"] in [SubmissionVerdict.OLE, SubmissionVerdict.TLE]
    if res["verdict"] == SubmissionVerdict.OLE:
        assert len(res["output"].encode("utf-8")) <= MAX_OUTPUT_BYTES + 4096

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
        admin = _create_user(db, "admin.closure.test@ipu.ac.in", UserRole.ADMIN.value, "Admin Closure Test")
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
