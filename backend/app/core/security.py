import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Union, Any, List
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.models import (
    User, UserRole, AccountStatus, Permission, AdminAllowlist,
    RefreshToken, PasswordResetToken, AuditLog, get_permissions_for_role
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)

import bcrypt

def hash_token(raw_token: str) -> str:
    """Hashes refresh and password reset tokens before database storage"""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

def get_password_hash(password: str) -> str:
    """Hashes password using industrial-strength bcrypt"""
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies password with bcrypt; supports seamless migration from legacy sha256 hashes.
    """
    if not hashed_password:
        return True
    
    # Check if bcrypt hash
    if hashed_password.startswith("$2b$") or hashed_password.startswith("$2a$") or hashed_password.startswith("$2y$"):
        try:
            return bcrypt.checkpw(plain_password.encode("utf-8")[:72], hashed_password.encode("utf-8"))
        except Exception:
            return False

    # Legacy SHA256 fallback
    salt = "codesphere_salt_usar_2026"
    expected_legacy = hashlib.sha256(f"{salt}{plain_password}".encode("utf-8")).hexdigest()
    if hmac.compare_digest(expected_legacy, hashed_password):
        return True
    
    return False

def create_access_token(subject: Union[str, Any], extra_claims: Optional[dict] = None, expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"exp": expire, "sub": str(subject), "type": "access"}
    if extra_claims:
        to_encode.update(extra_claims)
        
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def create_refresh_token_record(db: Session, user_id: int) -> tuple[str, RefreshToken]:
    """Generates a secure random refresh token, stores its hash, and returns (raw_token, record)"""
    raw_token = secrets.token_urlsafe(48)
    token_hashed = hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    token_record = RefreshToken(
        user_id=user_id,
        token_hash=token_hashed,
        expires_at=expires_at,
        is_revoked=False
    )
    db.add(token_record)
    db.commit()
    db.refresh(token_record)
    return raw_token, token_record

def create_password_reset_token_record(db: Session, user_id: int) -> tuple[str, PasswordResetToken]:
    """Generates a secure random single-use password reset token"""
    raw_token = secrets.token_urlsafe(32)
    token_hashed = hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES)

    # Invalidate previous unused reset tokens for this user
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user_id,
        PasswordResetToken.is_used == False
    ).update({"is_used": True})

    reset_record = PasswordResetToken(
        user_id=user_id,
        token_hash=token_hashed,
        expires_at=expires_at,
        is_used=False
    )
    db.add(reset_record)
    db.commit()
    db.refresh(reset_record)
    return raw_token, reset_record

def log_audit(
    db: Session,
    action: str,
    actor_email: str,
    user_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    status: str = "SUCCESS",
    details: Optional[dict] = None
) -> AuditLog:
    """
    Structured security audit event logger. Never logs raw passwords or tokens.
    """
    try:
        clean_details = {}
        if details:
            for k, v in details.items():
                if any(secret_kw in k.lower() for secret_kw in ["password", "token", "secret", "credential"]):
                    clean_details[k] = "[REDACTED]"
                else:
                    clean_details[k] = v

        entry = AuditLog(
            user_id=user_id,
            actor_email=actor_email,
            action=action,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
            details=clean_details
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry
    except Exception as e:
        db.rollback()
        # Fallback print without interrupting request flow
        print(f"[AuditLogger Error] Failed to log audit event: {e}")
        return None

def is_student_email(email: str) -> bool:
    email_clean = email.strip().lower()
    return email_clean.endswith(f"@{settings.STUDENT_EMAIL_DOMAIN.lower()}")

def is_admin_email(email: str, db: Optional[Session] = None) -> bool:
    email_clean = email.strip().lower()

    # 1. Configured initial super admin is always recognized
    if settings.INITIAL_ADMIN_EMAIL and email_clean == settings.INITIAL_ADMIN_EMAIL.strip().lower():
        return True

    # 2. Database allowlist or user record lookup
    if db is not None:
        admin_entry = db.query(AdminAllowlist).filter(
            AdminAllowlist.email == email_clean,
            AdminAllowlist.is_active == True
        ).first()
        if admin_entry:
            return True

        user = db.query(User).filter(
            User.email == email_clean,
            User.role.in_([
                UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value, UserRole.PLACEMENT_ADMIN.value,
                UserRole.FACULTY.value, UserRole.QUESTION_SETTER.value, UserRole.REVIEWER.value
            ])
        ).first()
        if user:
            return True

        return False

    # 3. Known system admin emails or matching institutional admin domain (when no DB session)
    if email_clean in ["placement@ipu.ac.in", "admin@ipu.ac.in"]:
        return True

    if email_clean.endswith(f"@{settings.ADMIN_EMAIL_DOMAIN.lower()}"):
        return True

    return False

def determine_role(email: str, db: Optional[Session] = None) -> Optional[UserRole]:
    """
    Authoritative server-side role resolution. Never trusts client-supplied roles.
    """
    email_clean = email.strip().lower()
    if settings.INITIAL_ADMIN_EMAIL and email_clean == settings.INITIAL_ADMIN_EMAIL.strip().lower():
        return UserRole.SUPER_ADMIN

    if db is not None:
        admin_entry = db.query(AdminAllowlist).filter(
            AdminAllowlist.email == email_clean,
            AdminAllowlist.is_active == True
        ).first()
        if admin_entry and admin_entry.assigned_role:
            try:
                return UserRole(admin_entry.assigned_role)
            except ValueError:
                return UserRole.ADMIN

    if is_admin_email(email_clean, db):
        return UserRole.ADMIN
    elif is_student_email(email_clean):
        return UserRole.STUDENT
    
    return None

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
        user_id = int(user_id_str)
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials or session has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials or session has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check Account Status
    if user.status == AccountStatus.DISABLED.value or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been disabled. Contact University Administration."
        )
    
    # Check Lockout status
    if user.locked_until:
        # Check if lockout has expired
        now = datetime.now(timezone.utc)
        locked_until_utc = user.locked_until.replace(tzinfo=timezone.utc) if user.locked_until.tzinfo is None else user.locked_until
        if locked_until_utc > now:
            minutes_left = int((locked_until_utc - now).total_seconds() / 60) + 1
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Account is temporarily locked due to excessive failed attempts. Try again in {minutes_left} minutes."
            )
        else:
            # Lockout expired, auto-clear
            user.locked_until = None
            user.failed_login_attempts = 0
            db.commit()
    
    return user

def require_permission(required_permission: Permission):
    """
    FastAPI dependency that enforces fine-grained RBAC permission on the endpoint.
    """
    def permission_checker(current_user: User = Depends(get_current_user)) -> User:
        user_perms = get_permissions_for_role(current_user.role)
        if required_permission.value not in user_perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: You do not have the required '{required_permission.value}' permission."
            )
        return current_user
    return permission_checker

def require_role(allowed_roles: Union[UserRole, List[UserRole]]):
    """
    FastAPI dependency that enforces role-based access control.
    """
    if isinstance(allowed_roles, UserRole):
        allowed_roles = [allowed_roles]
    allowed_values = [r.value if isinstance(r, UserRole) else str(r) for r in allowed_roles]

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: Requires one of [{', '.join(allowed_values)}] privileges."
            )
        return current_user
    return role_checker

# Legacy helpers maintaining 100% backward compatibility
def require_admin(current_user: User = Depends(get_current_user)) -> User:
    admin_roles = [
        UserRole.ADMIN.value,
        UserRole.SUPER_ADMIN.value,
        UserRole.PLACEMENT_ADMIN.value,
        UserRole.FACULTY.value,
        UserRole.QUESTION_SETTER.value,
        UserRole.REVIEWER.value
    ]
    if current_user.role not in admin_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Elevated staff or administrative privileges required."
        )
    return current_user

def require_student(current_user: User = Depends(get_current_user)) -> User:
    return current_user
