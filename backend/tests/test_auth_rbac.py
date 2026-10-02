import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.config import settings
from app.core.database import engine, SessionLocal, auto_migrate_db
from app.core.security import (
    get_password_hash, verify_password, create_access_token, 
    create_refresh_token_record, create_password_reset_token_record,
    hash_token, log_audit, determine_role
)
from app.models.models import (
    Base, User, UserRole, AccountStatus, Permission, ROLE_PERMISSIONS,
    get_permissions_for_role, RefreshToken, PasswordResetToken, AuditLog
)
from app.services.seeder import seed_database

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

def get_auth_headers(email: str, password: str = "Admin@123") -> dict:
    """Helper to log in and return authorization Bearer header"""
    res = client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={"email": email, "password": password}
    )
    if res.status_code == 200:
        token = res.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    return {}

# -------------------------------------------------------------
# 1. PASSWORD SECURITY & HASHING TESTS
# -------------------------------------------------------------
def test_bcrypt_password_hashing():
    pwd = "SecureUniversityPassword2026!"
    hashed = get_password_hash(pwd)
    assert hashed.startswith("$2b$")
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False

def test_legacy_hash_compatibility():
    # Legacy SHA-256 fallback compatibility
    import hashlib
    salt = "codesphere_salt_usar_2026"
    pwd = "legacy_password"
    legacy_hash = hashlib.sha256(f"{salt}{pwd}".encode("utf-8")).hexdigest()
    assert verify_password(pwd, legacy_hash) is True
    assert verify_password("wrong", legacy_hash) is False

# -------------------------------------------------------------
# 2. AUTHENTICATION & LOGIN TESTS
# -------------------------------------------------------------
def test_valid_login_super_admin():
    res = client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={"email": settings.INITIAL_ADMIN_EMAIL, "password": settings.INITIAL_ADMIN_PASSWORD}
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == settings.INITIAL_ADMIN_EMAIL.lower()
    assert data["user"]["role"] == UserRole.SUPER_ADMIN.value
    assert Permission.MANAGE_ROLES.value in data["user"]["permissions"]

def test_invalid_login_credentials():
    res = client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={"email": "nonexistent.user@ipu.ac.in", "password": "WrongPassword123"}
    )
    assert res.status_code == 401
    assert "Invalid email or password" in res.json()["detail"]

def test_brute_force_lockout():
    email = "test.brute@std.ggsipu.ac.in"
    db = SessionLocal()
    try:
        # Create a test student
        student = db.query(User).filter(User.email == email).first()
        if not student:
            student = User(
                email=email,
                full_name="Brute Test Student",
                role=UserRole.STUDENT.value,
                hashed_password=get_password_hash("Student@123"),
                status=AccountStatus.ACTIVE.value,
                is_active=True
            )
            db.add(student)
            db.commit()
    finally:
        db.close()

    # Fail login 5 times
    for attempt in range(1, 6):
        res = client.post(
            f"{settings.API_V1_STR}/auth/login",
            json={"email": email, "password": "WrongPassword!"}
        )
        assert res.status_code in [401, 403]
    
    # 6th attempt should be blocked with 403 Account Locked
    res = client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={"email": email, "password": "Student@123"}
    )
    assert res.status_code == 403
    assert "temporarily locked" in res.json()["detail"]

def test_disabled_account_cannot_login():
    email = "disabled.user@std.ggsipu.ac.in"
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                email=email,
                full_name="Disabled User",
                role=UserRole.STUDENT.value,
                hashed_password=get_password_hash("Disabled@123"),
                status=AccountStatus.DISABLED.value,
                is_active=False
            )
            db.add(user)
            db.commit()
    finally:
        db.close()

    res = client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={"email": email, "password": "Disabled@123"}
    )
    assert res.status_code == 403
    assert "disabled" in res.json()["detail"].lower()

# -------------------------------------------------------------
# 3. REFRESH TOKEN ROTATION & REVOCATION
# -------------------------------------------------------------
def test_refresh_token_flow_and_rotation():
    # 1. Login to get tokens
    res = client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={"email": settings.INITIAL_ADMIN_EMAIL, "password": settings.INITIAL_ADMIN_PASSWORD}
    )
    assert res.status_code == 200
    refresh_token = res.json()["refresh_token"]

    # 2. Use refresh token to obtain new access and refresh tokens
    refresh_res = client.post(
        f"{settings.API_V1_STR}/auth/refresh",
        json={"refresh_token": refresh_token}
    )
    assert refresh_res.status_code == 200
    new_data = refresh_res.json()
    new_access_token = new_data["access_token"]
    new_refresh_token = new_data["refresh_token"]
    assert new_refresh_token != refresh_token

    # 3. Old refresh token must now be revoked (single-use rotation)
    reuse_res = client.post(
        f"{settings.API_V1_STR}/auth/refresh",
        json={"refresh_token": refresh_token}
    )
    assert reuse_res.status_code == 401
    assert "revoked" in reuse_res.json()["detail"].lower()

def test_logout_revokes_tokens():
    res = client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={"email": settings.INITIAL_ADMIN_EMAIL, "password": settings.INITIAL_ADMIN_PASSWORD}
    )
    assert res.status_code == 200
    access_token = res.json()["access_token"]
    refresh_token = res.json()["refresh_token"]

    headers = {"Authorization": f"Bearer {access_token}"}
    logout_res = client.post(
        f"{settings.API_V1_STR}/auth/logout",
        json={"refresh_token": refresh_token},
        headers=headers
    )
    assert logout_res.status_code == 200
    assert "message" in logout_res.json()

    # Refresh token should now be revoked
    refresh_res = client.post(
        f"{settings.API_V1_STR}/auth/refresh",
        json={"refresh_token": refresh_token}
    )
    assert refresh_res.status_code == 401

# -------------------------------------------------------------
# 4. PASSWORD RESET WORKFLOW
# -------------------------------------------------------------
def test_password_reset_workflow():
    db = SessionLocal()
    test_email = "reset.test@std.ggsipu.ac.in"
    try:
        user = db.query(User).filter(User.email == test_email).first()
        if not user:
            user = User(
                email=test_email,
                full_name="Reset Test",
                role=UserRole.STUDENT.value,
                hashed_password=get_password_hash("OldPassword@123"),
                status=AccountStatus.ACTIVE.value
            )
            db.add(user)
            db.commit()
    finally:
        db.close()

    # 1. Request password reset
    req_res = client.post(
        f"{settings.API_V1_STR}/auth/forgot-password",
        json={"email": test_email}
    )
    assert req_res.status_code == 200
    assert "password reset" in req_res.json()["message"].lower()

    # Retrieve the token created in DB for testing
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == test_email).first()
        reset_entry = db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.is_used == False
        ).order_by(PasswordResetToken.id.desc()).first()
        assert reset_entry is not None
        # Generate verified test token
        raw_token, _ = create_password_reset_token_record(db, user.id)
    finally:
        db.close()

    # 2. Confirm password reset
    confirm_res = client.post(
        f"{settings.API_V1_STR}/auth/reset-password",
        json={
            "token": raw_token,
            "new_password": "NewSecurePassword@2026"
        }
    )
    assert confirm_res.status_code == 200
    assert "successfully" in confirm_res.json()["message"].lower()

    # 3. Token cannot be reused
    reuse_res = client.post(
        f"{settings.API_V1_STR}/auth/reset-password",
        json={
            "token": raw_token,
            "new_password": "AnotherPassword@2026"
        }
    )
    assert reuse_res.status_code == 400
    assert "already used" in reuse_res.json()["detail"].lower() or "invalid" in reuse_res.json()["detail"].lower()

    # 4. Login with new password must succeed
    login_res = client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={"email": test_email, "password": "NewSecurePassword@2026"}
    )
    assert login_res.status_code == 200

# -------------------------------------------------------------
# 5. ROLE-BASED ACCESS CONTROL (RBAC) & PERMISSION ENFORCEMENT
# -------------------------------------------------------------
def test_rbac_roles_and_permissions_mapping():
    # Verify complete 7 roles
    all_roles = [
        UserRole.STUDENT, UserRole.FACULTY, UserRole.QUESTION_SETTER,
        UserRole.REVIEWER, UserRole.PLACEMENT_ADMIN, UserRole.ADMIN, UserRole.SUPER_ADMIN
    ]
    for r in all_roles:
        perms = get_permissions_for_role(r.value)
        assert isinstance(perms, list)
        assert len(perms) > 0

    # Student has SUBMIT_CODE, but NOT MANAGE_USERS or CREATE_QUESTION
    student_perms = get_permissions_for_role(UserRole.STUDENT.value)
    assert Permission.SUBMIT_CODE.value in student_perms
    assert Permission.MANAGE_USERS.value not in student_perms
    assert Permission.CREATE_QUESTION.value not in student_perms

    # Question Setter can CREATE_QUESTION but cannot MANAGE_USERS
    qs_perms = get_permissions_for_role(UserRole.QUESTION_SETTER.value)
    assert Permission.CREATE_QUESTION.value in qs_perms
    assert Permission.MANAGE_USERS.value not in qs_perms

    # Super Admin has all permissions
    sa_perms = get_permissions_for_role(UserRole.SUPER_ADMIN.value)
    assert Permission.MANAGE_ROLES.value in sa_perms
    assert Permission.MANAGE_SYSTEM_SETTINGS.value in sa_perms
    assert Permission.VIEW_AUDIT_LOGS.value in sa_perms

def test_unauthenticated_request_rejected():
    res = client.get(f"{settings.API_V1_STR}/auth/users")
    assert res.status_code == 401

def test_student_cannot_access_admin_api():
    # Login as student
    student_headers = get_auth_headers("aarav.patel@std.ggsipu.ac.in", "student123")
    assert "Authorization" in student_headers

    # Try to access admin user management API
    res = client.get(f"{settings.API_V1_STR}/auth/users", headers=student_headers)
    assert res.status_code == 403
    assert "Forbidden" in res.json()["detail"]

    # Try to create a question
    q_res = client.post(
        f"{settings.API_V1_STR}/questions",
        json={
            "title": "Unauthorized Question",
            "problem_statement": "Desc",
            "input_format": "Int",
            "output_format": "Int",
            "constraints": "1 <= N <= 10",
            "difficulty_score": 1,
            "test_cases": [{"input_data": "1", "expected_output": "1", "points": 10, "is_hidden": False}]
        },
        headers=student_headers
    )
    assert q_res.status_code == 403

def test_question_setter_can_create_question_but_not_manage_users():
    qs_headers = get_auth_headers("setter.ai@ipu.ac.in", "setter123")
    assert "Authorization" in qs_headers

    # Attempt to create question -> ALLOW
    q_res = client.post(
        f"{settings.API_V1_STR}/questions",
        json={
            "title": "RBAC Test Question",
            "problem_statement": "A test question for question setters",
            "input_format": "Single integer n",
            "output_format": "Single integer 2*n",
            "constraints": "1 <= n <= 100",
            "difficulty_score": 2,
            "test_cases": [{"input_data": "10", "expected_output": "20", "points": 10, "is_hidden": False}]
        },
        headers=qs_headers
    )
    assert q_res.status_code in [200, 201]

    # Attempt to view audit logs -> DENY (403)
    audit_res = client.get(f"{settings.API_V1_STR}/auth/audit-logs", headers=qs_headers)
    assert audit_res.status_code == 403

def test_admin_can_manage_roles_and_view_audit_logs():
    admin_headers = get_auth_headers(settings.INITIAL_ADMIN_EMAIL, settings.INITIAL_ADMIN_PASSWORD)
    assert "Authorization" in admin_headers

    # Get users list
    users_res = client.get(f"{settings.API_V1_STR}/auth/users", headers=admin_headers)
    assert users_res.status_code == 200
    users = users_res.json()
    assert len(users) > 0

    # Get audit logs
    logs_res = client.get(f"{settings.API_V1_STR}/auth/audit-logs", headers=admin_headers)
    assert logs_res.status_code == 200
    logs = logs_res.json()
    assert isinstance(logs, list)

def test_role_change_and_status_update():
    admin_headers = get_auth_headers(settings.INITIAL_ADMIN_EMAIL, settings.INITIAL_ADMIN_PASSWORD)
    db = SessionLocal()
    target_email = "target.rbac@std.ggsipu.ac.in"
    try:
        user = db.query(User).filter(User.email == target_email).first()
        if not user:
            user = User(
                email=target_email,
                full_name="Target User",
                role=UserRole.STUDENT.value,
                hashed_password=get_password_hash("Target@123"),
                status=AccountStatus.ACTIVE.value
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        target_id = user.id
    finally:
        db.close()

    # Update role to FACULTY
    role_res = client.put(
        f"{settings.API_V1_STR}/auth/users/{target_id}/role",
        json={"role": UserRole.FACULTY.value},
        headers=admin_headers
    )
    assert role_res.status_code == 200
    assert role_res.json()["role"] == UserRole.FACULTY.value

    # Update status to DISABLED
    status_res = client.put(
        f"{settings.API_V1_STR}/auth/users/{target_id}/status",
        json={"status": AccountStatus.DISABLED.value},
        headers=admin_headers
    )
    assert status_res.status_code == 200
    assert status_res.json()["status"] == AccountStatus.DISABLED.value

def test_audit_logs_redact_sensitive_data():
    db = SessionLocal()
    try:
        entry = log_audit(
            db=db,
            action="TEST_ACTION",
            actor_email="admin@ipu.ac.in",
            details={
                "password": "SecretPassword123",
                "refresh_token": "secret_token_value",
                "safe_info": "safe_value"
            }
        )
        assert entry is not None
        assert entry.details["password"] == "[REDACTED]"
        assert entry.details["refresh_token"] == "[REDACTED]"
        assert entry.details["safe_info"] == "safe_value"
    finally:
        db.close()
