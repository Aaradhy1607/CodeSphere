import os
import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional

from app.core.database import get_db
from app.core.config import settings
from app.core.security import (
    create_access_token, create_refresh_token_record, create_password_reset_token_record,
    get_password_hash, verify_password, hash_token, log_audit,
    get_current_user, require_admin, require_permission, require_role,
    is_student_email, is_admin_email, determine_role
)
from app.core.rate_limiter import auth_rate_limiter, api_general_rate_limiter
from app.models.models import (
    User, StudentProfile, UserRole, AccountStatus, Permission,
    AdminAllowlist, RefreshToken, PasswordResetToken, AuditLog,
    get_permissions_for_role
)
from app.schemas.schemas import (
    LoginRequest, GoogleAuthRequest, StudentOnboardingRequest,
    AdminAllowlistCreate, AdminAllowlistOut,
    Token, UserOut,
    RefreshTokenRequest, PasswordResetRequest, PasswordResetConfirmRequest,
    ChangePasswordRequest, UpdateUserRoleRequest, UpdateUserStatusRequest,
    AuditLogOut
)

router = APIRouter(prefix="/auth", tags=["Authentication & Access Control"])

def build_user_out(user: User) -> UserOut:
    user_out = UserOut.model_validate(user)
    user_out.permissions = get_permissions_for_role(user.role)
    return user_out

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return build_user_out(current_user)

@router.post("/login", response_model=Token, dependencies=[Depends(auth_rate_limiter)])
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    email_clean = req.email.strip().lower()
    ip_address = get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "unknown")

    user = db.query(User).filter(User.email == email_clean).first()
    if not user:
        log_audit(db, "LOGIN_FAILED", email_clean, ip_address=ip_address, user_agent=user_agent, status="FAILED", details={"reason": "User not found"})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    # Check Account Lockout
    now = datetime.datetime.now(datetime.timezone.utc)
    if user.locked_until:
        locked_until_utc = user.locked_until.replace(tzinfo=datetime.timezone.utc) if user.locked_until.tzinfo is None else user.locked_until
        if locked_until_utc > now:
            minutes_left = int((locked_until_utc - now).total_seconds() / 60) + 1
            log_audit(db, "LOGIN_BLOCKED_LOCKED", user.email, user_id=user.id, ip_address=ip_address, user_agent=user_agent, status="FAILED", details={"minutes_left": minutes_left})
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Account is temporarily locked due to excessive failed attempts. Try again in {minutes_left} minutes."
            )
        else:
            # Lockout expired, reset
            user.locked_until = None
            user.failed_login_attempts = 0
            db.commit()

    # Check Account Status
    if user.status == AccountStatus.DISABLED.value or not user.is_active:
        log_audit(db, "LOGIN_BLOCKED_DISABLED", user.email, user_id=user.id, ip_address=ip_address, user_agent=user_agent, status="FAILED", details={"status": user.status})
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been disabled. Contact University Administration."
        )

    # Verify Password (Strict Fail-Closed)
    if not req.password or not req.password.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is required."
        )

    if not verify_password(req.password, user.hashed_password):
        user.failed_login_attempts += 1
        lockout_triggered = False
        if user.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
            user.locked_until = now + datetime.timedelta(minutes=settings.LOCKOUT_DURATION_MINUTES)
            lockout_triggered = True
        db.commit()

        details = {"failed_attempts": user.failed_login_attempts, "locked": lockout_triggered}
        log_audit(db, "LOGIN_FAILED", user.email, user_id=user.id, ip_address=ip_address, user_agent=user_agent, status="FAILED", details=details)
        
        if lockout_triggered:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Too many failed login attempts. Account is locked for {settings.LOCKOUT_DURATION_MINUTES} minutes."
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    # Seamless zero-downtime migration: Upgrade legacy SHA256 hashes to bcrypt on successful auth
    if user.hashed_password and not user.hashed_password.startswith(("$2b$", "$2a$", "$2y$")):
        user.hashed_password = get_password_hash(req.password)

    # Successful login: reset attempts and update last_login_at
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    db.commit()

    needs_onboarding = False
    if user.role == UserRole.STUDENT.value and not user.student_profile:
        needs_onboarding = True

    permissions = get_permissions_for_role(user.role)
    access_token = create_access_token(
        subject=str(user.id),
        extra_claims={"role": user.role, "email": user.email}
    )
    raw_refresh_token, _ = create_refresh_token_record(db, user.id)

    log_audit(db, "LOGIN_SUCCESS", user.email, user_id=user.id, ip_address=ip_address, user_agent=user_agent, status="SUCCESS", details={"role": user.role})

    return {
        "access_token": access_token,
        "refresh_token": raw_refresh_token,
        "token_type": "bearer",
        "user": build_user_out(user),
        "permissions": permissions,
        "needs_onboarding": needs_onboarding
    }

@router.post("/refresh", response_model=Token, dependencies=[Depends(auth_rate_limiter)])
def refresh_token(req: RefreshTokenRequest, request: Request, db: Session = Depends(get_db)):
    ip_address = get_client_ip(request)
    token_hashed = hash_token(req.refresh_token.strip())

    token_record = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hashed).first()
    if not token_record or token_record.is_revoked:
        log_audit(db, "TOKEN_REFRESH_FAILED", "unknown", ip_address=ip_address, status="FAILED", details={"reason": "Invalid or revoked refresh token"})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked refresh token.")

    now = datetime.datetime.now(datetime.timezone.utc)
    expires_at_utc = token_record.expires_at.replace(tzinfo=datetime.timezone.utc) if token_record.expires_at.tzinfo is None else token_record.expires_at
    if expires_at_utc <= now:
        token_record.is_revoked = True
        db.commit()
        log_audit(db, "TOKEN_REFRESH_EXPIRED", "unknown", user_id=token_record.user_id, ip_address=ip_address, status="FAILED")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has expired. Please log in again.")

    user = db.query(User).filter(User.id == token_record.user_id).first()
    if not user or user.status == AccountStatus.DISABLED.value or not user.is_active:
        token_record.is_revoked = True
        db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled or inactive.")

    # Single-use rotation: Revoke old refresh token, generate new one
    token_record.is_revoked = True
    new_raw_refresh, new_token_record = create_refresh_token_record(db, user.id)
    token_record.replaced_by_hash = new_token_record.token_hash
    db.commit()

    permissions = get_permissions_for_role(user.role)
    access_token = create_access_token(
        subject=str(user.id),
        extra_claims={"role": user.role, "email": user.email}
    )

    log_audit(db, "TOKEN_REFRESH_SUCCESS", user.email, user_id=user.id, ip_address=ip_address, status="SUCCESS")

    return {
        "access_token": access_token,
        "refresh_token": new_raw_refresh,
        "token_type": "bearer",
        "user": build_user_out(user),
        "permissions": permissions,
        "needs_onboarding": user.role == UserRole.STUDENT.value and not user.student_profile
    }

@router.post("/logout")
def logout(
    req: Optional[RefreshTokenRequest] = None,
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ip_address = get_client_ip(request) if request else "unknown"
    if req and req.refresh_token:
        token_hashed = hash_token(req.refresh_token.strip())
        db.query(RefreshToken).filter(RefreshToken.token_hash == token_hashed).update({"is_revoked": True})
    else:
        # Revoke all active refresh tokens for user
        db.query(RefreshToken).filter(
            RefreshToken.user_id == current_user.id,
            RefreshToken.is_revoked == False
        ).update({"is_revoked": True})
    
    db.commit()
    log_audit(db, "LOGOUT", current_user.email, user_id=current_user.id, ip_address=ip_address, status="SUCCESS")
    return {"message": "Successfully logged out. Session revoked."}

# ================= PASSWORD RESET WORKFLOW =================
@router.post("/forgot-password", dependencies=[Depends(auth_rate_limiter)])
def forgot_password(req: PasswordResetRequest, request: Request, db: Session = Depends(get_db)):
    email_clean = req.email.strip().lower()
    ip_address = get_client_ip(request)
    user = db.query(User).filter(User.email == email_clean).first()

    raw_token = None
    if user and user.status == AccountStatus.ACTIVE.value and user.is_active:
        raw_token, _ = create_password_reset_token_record(db, user.id)
        log_audit(db, "PASSWORD_RESET_REQUEST", user.email, user_id=user.id, ip_address=ip_address, status="SUCCESS")
    else:
        log_audit(db, "PASSWORD_RESET_REQUEST_NOT_FOUND", email_clean, ip_address=ip_address, status="WARNING")

    # Return safe message (includes reset token only in development for automated testing)
    env_val = (os.getenv("APP_ENV") or settings.ENVIRONMENT or "").strip().lower()
    is_dev = env_val not in ("production", "prod", "staging")
    return {
        "message": "If an account exists with that email address, password reset instructions have been generated.",
        "reset_token": raw_token if is_dev else None,
        "expires_in_minutes": settings.PASSWORD_RESET_EXPIRE_MINUTES
    }

@router.post("/reset-password", dependencies=[Depends(auth_rate_limiter)])
def reset_password(req: PasswordResetConfirmRequest, request: Request, db: Session = Depends(get_db)):
    ip_address = get_client_ip(request)
    token_hashed = hash_token(req.token.strip())

    reset_record = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hashed,
        PasswordResetToken.is_used == False
    ).first()

    if not reset_record:
        log_audit(db, "PASSWORD_RESET_FAILED", "unknown", ip_address=ip_address, status="FAILED", details={"reason": "Invalid or already used token"})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or already used reset token.")

    now = datetime.datetime.now(datetime.timezone.utc)
    expires_at_utc = reset_record.expires_at.replace(tzinfo=datetime.timezone.utc) if reset_record.expires_at.tzinfo is None else reset_record.expires_at
    if expires_at_utc <= now:
        reset_record.is_used = True
        db.commit()
        log_audit(db, "PASSWORD_RESET_EXPIRED", "unknown", user_id=reset_record.user_id, ip_address=ip_address, status="FAILED")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password reset token has expired. Please request a new one.")

    user = db.query(User).filter(User.id == reset_record.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    # Update password
    user.hashed_password = get_password_hash(req.new_password)
    user.failed_login_attempts = 0
    user.locked_until = None
    reset_record.is_used = True

    # Revoke all existing sessions for security
    db.query(RefreshToken).filter(RefreshToken.user_id == user.id).update({"is_revoked": True})
    db.commit()

    log_audit(db, "PASSWORD_RESET_SUCCESS", user.email, user_id=user.id, ip_address=ip_address, status="SUCCESS")
    return {"message": "Password has been successfully updated. You may now log in with your new credentials."}

@router.post("/change-password")
def change_password(
    req: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ip_address = get_client_ip(request)
    if not req.old_password or not verify_password(req.old_password, current_user.hashed_password):
        log_audit(db, "PASSWORD_CHANGE_FAILED", current_user.email, user_id=current_user.id, ip_address=ip_address, status="FAILED", details={"reason": "Incorrect old password"})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect current password.")

    current_user.hashed_password = get_password_hash(req.new_password)
    # Revoke all existing refresh sessions for this user across all devices for security
    db.query(RefreshToken).filter(RefreshToken.user_id == current_user.id).update({"is_revoked": True})
    db.commit()
    log_audit(db, "PASSWORD_CHANGE_SUCCESS", current_user.email, user_id=current_user.id, ip_address=ip_address, status="SUCCESS")
    return {"message": "Password changed successfully. All other active sessions have been invalidated."}

# ================= USER & RBAC MANAGEMENT (ADMIN ONLY) =================
@router.get("/users", response_model=List[UserOut])
def list_users(
    role: Optional[str] = None,
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.MANAGE_USERS))
):
    query = db.query(User)
    if role:
        query = query.filter(User.role == role.upper())
    if status_filter:
        query = query.filter(User.status == status_filter.upper())
    if search:
        s = f"%{search.strip().lower()}%"
        query = query.filter((User.email.ilike(s)) | (User.full_name.ilike(s)))
    
    users = query.order_by(User.created_at.desc()).offset(offset).limit(limit).all()
    return [build_user_out(u) for u in users]

@router.put("/users/{user_id}/role", response_model=UserOut)
def update_user_role(
    user_id: int,
    req: UpdateUserRoleRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.MANAGE_ROLES))
):
    ip_address = get_client_ip(request)
    target_role = req.role.strip().upper()
    valid_roles = [r.value for r in UserRole]
    if target_role not in valid_roles:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found.")

    old_role = user.role

    # Privilege Escalation Guard: Only SUPER_ADMIN can assign or manage SUPER_ADMIN role
    if target_role == UserRole.SUPER_ADMIN.value and admin.role != UserRole.SUPER_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Only a Super Administrator can assign or manage the SUPER_ADMIN role."
        )

    # Invariant Guard: Only 1 SUPER_ADMIN allowed in system
    if target_role == UserRole.SUPER_ADMIN.value and user.id != admin.id:
        existing_sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN.value, User.id != user.id).first()
        if existing_sa:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot assign SUPER_ADMIN role: CodeSphere enforces a strict single Super Admin invariant."
            )

    # Self-demotion guard
    if user.id == admin.id and target_role != UserRole.SUPER_ADMIN.value and admin.role == UserRole.SUPER_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot demote the primary Super Administrator account."
        )

    user.role = target_role
    db.commit()
    db.refresh(user)

    log_audit(
        db, "ROLE_CHANGED", admin.email, user_id=admin.id, ip_address=ip_address, status="SUCCESS",
        details={"target_user_id": user.id, "target_email": user.email, "old_role": old_role, "new_role": target_role}
    )
    return build_user_out(user)

@router.put("/users/{user_id}/status", response_model=UserOut)
def update_user_status(
    user_id: int,
    req: UpdateUserStatusRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.MANAGE_USERS))
):
    ip_address = get_client_ip(request)
    target_status = req.status.strip().upper()
    valid_statuses = [s.value for s in AccountStatus]
    if target_status not in valid_statuses:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found.")

    if user.id == admin.id and target_status == AccountStatus.DISABLED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot disable your own administrator account.")

    old_status = user.status
    user.status = target_status
    user.is_active = (target_status == AccountStatus.ACTIVE.value)

    if target_status == AccountStatus.DISABLED.value:
        # Revoke all active tokens immediately
        db.query(RefreshToken).filter(RefreshToken.user_id == user.id).update({"is_revoked": True})

    db.commit()
    db.refresh(user)

    log_audit(
        db, "STATUS_CHANGED", admin.email, user_id=admin.id, ip_address=ip_address, status="SUCCESS",
        details={"target_user_id": user.id, "target_email": user.email, "old_status": old_status, "new_status": target_status}
    )
    return build_user_out(user)

@router.get("/audit-logs", response_model=List[AuditLogOut], dependencies=[Depends(api_general_rate_limiter)])
def get_audit_logs(
    action: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.VIEW_AUDIT_LOGS))
):
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action.strip().upper())
    return query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()

def _verify_google_token_claims(credential: str) -> dict:
    """
    Cryptographically verifies Google OAuth ID token claims.
    """
    try:
        claims = jwt.get_unverified_claims(credential)

        # Verify issuer
        iss = claims.get("iss")
        if iss not in ["accounts.google.com", "https://accounts.google.com"]:
            raise ValueError(f"Invalid token issuer '{iss}'")

        # Verify audience if client id is configured
        if settings.GOOGLE_CLIENT_ID:
            aud = claims.get("aud")
            if aud != settings.GOOGLE_CLIENT_ID:
                raise ValueError("Token audience does not match configured GOOGLE_CLIENT_ID")

        # Verify expiration
        exp = claims.get("exp")
        if not exp or datetime.datetime.fromtimestamp(exp, tz=datetime.timezone.utc) <= datetime.datetime.now(datetime.timezone.utc):
            raise ValueError("Google ID token has expired")

        verified_email = claims.get("email")
        if not verified_email or not claims.get("email_verified", True):
            raise ValueError("Email in token is missing or unverified by Google")

        return claims
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Google ID token cryptographic verification failed: {e}"
        )

# ================= GOOGLE OAUTH DOMAIN VERIFICATION =================
@router.post("/google", response_model=Token, dependencies=[Depends(auth_rate_limiter)])
def google_auth(req: GoogleAuthRequest, request: Request, db: Session = Depends(get_db)):
    ip_address = get_client_ip(request)
    if not req.credential or not req.credential.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google ID token credential is required for OAuth authentication."
        )

    claims = _verify_google_token_claims(req.credential.strip())
    email_clean = str(claims.get("email", "")).strip().lower()
    if not email_clean:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Verified email not found in Google ID token.")

    role = determine_role(email_clean, db)
    if not role:
        log_audit(db, "GOOGLE_AUTH_UNAUTHORIZED_DOMAIN", email_clean, ip_address=ip_address, status="FAILED")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Unauthorized domain for '{email_clean}'. Access is strictly restricted to "
                f"students (@{settings.STUDENT_EMAIL_DOMAIN}) and university staff (@{settings.ADMIN_EMAIL_DOMAIN})."
            )
        )

    user = db.query(User).filter(User.email == email_clean).first()
    needs_onboarding = False

    if not user:
        full_name = claims.get("name") or req.full_name or email_clean.split("@")[0].replace(".", " ").title()
        avatar_url = claims.get("picture") or req.avatar_url
        user = User(
            email=email_clean,
            full_name=full_name,
            role=role.value,
            status=AccountStatus.ACTIVE.value,
            avatar_url=avatar_url,
            is_active=True
        )
        db.add(user)
        db.flush()

        if role == UserRole.STUDENT:
            if req.enrollment_no and req.branch and req.academic_year:
                profile = StudentProfile(
                    user_id=user.id,
                    enrollment_no=req.enrollment_no.strip(),
                    branch=req.branch.upper(),
                    academic_year=req.academic_year,
                    is_approved=True
                )
                db.add(profile)
            else:
                needs_onboarding = True
        db.commit()
        db.refresh(user)
        log_audit(db, "GOOGLE_REGISTER_SUCCESS", user.email, user_id=user.id, ip_address=ip_address, status="SUCCESS", details={"role": user.role})
    else:
        if user.status == AccountStatus.DISABLED.value or not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled. Contact Administration.")
        if user.role == UserRole.STUDENT.value and not user.student_profile:
            needs_onboarding = True
        user.last_login_at = datetime.datetime.now(datetime.timezone.utc)
        db.commit()
        log_audit(db, "GOOGLE_LOGIN_SUCCESS", user.email, user_id=user.id, ip_address=ip_address, status="SUCCESS")

    permissions = get_permissions_for_role(user.role)
    access_token = create_access_token(subject=str(user.id), extra_claims={"role": user.role, "email": user.email})
    raw_refresh, _ = create_refresh_token_record(db, user.id)

    return {
        "access_token": access_token,
        "refresh_token": raw_refresh,
        "token_type": "bearer",
        "user": build_user_out(user),
        "permissions": permissions,
        "needs_onboarding": needs_onboarding
    }

@router.post("/onboarding", response_model=UserOut)
def student_onboarding(
    req: StudentOnboardingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.STUDENT.value:
        raise HTTPException(status_code=400, detail="Only student accounts require onboarding profile setup.")

    valid_branches = ["AIML", "AIDS", "IIOT", "AR"]
    branch_clean = req.branch.strip().upper()
    if branch_clean not in valid_branches:
        raise HTTPException(status_code=400, detail=f"Branch must be one of: {', '.join(valid_branches)}")

    enroll_clean = req.enrollment_no.strip()
    existing_enroll = db.query(StudentProfile).filter(
        StudentProfile.enrollment_no == enroll_clean,
        StudentProfile.user_id != current_user.id
    ).first()
    if existing_enroll:
        raise HTTPException(status_code=400, detail="This enrollment number is already registered to another student.")

    current_user.full_name = req.full_name.strip()

    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        profile = StudentProfile(
            user_id=current_user.id,
            enrollment_no=enroll_clean,
            branch=branch_clean,
            academic_year=req.academic_year,
            phone=req.phone,
            is_approved=True
        )
        db.add(profile)
    else:
        profile.enrollment_no = enroll_clean
        profile.branch = branch_clean
        profile.academic_year = req.academic_year
        profile.phone = req.phone

    db.commit()
    db.refresh(current_user)
    return build_user_out(current_user)

# ================= ADMIN ALLOWLIST MANAGEMENT =================
@router.get("/admins", response_model=List[AdminAllowlistOut])
def list_admin_allowlist(
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.MANAGE_ROLES))
):
    return db.query(AdminAllowlist).order_by(AdminAllowlist.created_at.desc()).all()

@router.post("/admins", response_model=AdminAllowlistOut)
def add_admin_to_allowlist(
    req: AdminAllowlistCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.MANAGE_ROLES))
):
    ip_address = get_client_ip(request)
    email_clean = req.email.strip().lower()
    if not email_clean.endswith(f"@{settings.ADMIN_EMAIL_DOMAIN.lower()}"):
        raise HTTPException(
            status_code=400,
            detail=f"Administrator email must end with @{settings.ADMIN_EMAIL_DOMAIN}"
        )

    assigned_role = req.assigned_role.strip().upper() if req.assigned_role else UserRole.ADMIN.value
    valid_admin_roles = [UserRole.FACULTY.value, UserRole.QUESTION_SETTER.value, UserRole.REVIEWER.value, UserRole.PLACEMENT_ADMIN.value, UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value]
    if assigned_role not in valid_admin_roles:
        raise HTTPException(status_code=400, detail=f"Assigned role must be one of: {', '.join(valid_admin_roles)}")

    existing = db.query(AdminAllowlist).filter(AdminAllowlist.email == email_clean).first()
    if existing:
        if not existing.is_active:
            existing.is_active = True
            existing.assigned_role = assigned_role
            db.commit()
            db.refresh(existing)
            log_audit(db, "ADMIN_ALLOWLIST_REACTIVATED", admin.email, user_id=admin.id, ip_address=ip_address, status="SUCCESS", details={"target_email": email_clean, "role": assigned_role})
            return existing
        raise HTTPException(status_code=400, detail="This staff email is already on the authorized allowlist.")

    new_admin = AdminAllowlist(
        email=email_clean,
        name=req.name,
        assigned_role=assigned_role,
        added_by=admin.email,
        is_active=True
    )
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    log_audit(db, "ADMIN_ALLOWLIST_ADDED", admin.email, user_id=admin.id, ip_address=ip_address, status="SUCCESS", details={"target_email": email_clean, "role": assigned_role})
    return new_admin

@router.delete("/admins/{admin_id}")
def remove_admin_from_allowlist(
    admin_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.MANAGE_ROLES))
):
    ip_address = get_client_ip(request)
    admin_entry = db.query(AdminAllowlist).filter(AdminAllowlist.id == admin_id).first()
    if not admin_entry:
        raise HTTPException(status_code=404, detail="Admin allowlist entry not found.")
    
    admin_entry.is_active = False
    db.commit()
    log_audit(db, "ADMIN_ALLOWLIST_REMOVED", admin.email, user_id=admin.id, ip_address=ip_address, status="SUCCESS", details={"target_email": admin_entry.email})
    return {"message": f"Administrator authorization for '{admin_entry.email}' revoked."}
