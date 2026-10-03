import os
import datetime
from sqlalchemy.orm import Session
from app.models.models import (
    User, AdminAllowlist, UserRole, AccountStatus, StudentProfile
)
from app.core.config import settings
from app.core.security import get_password_hash

def seed_database(db: Session):
    env_val = (os.getenv("APP_ENV") or settings.ENVIRONMENT or "").strip().lower()
    is_prod = env_val in ("production", "prod", "staging")

    initial_admin_email = (settings.INITIAL_ADMIN_EMAIL or "").strip().lower()
    initial_admin_password = (settings.INITIAL_ADMIN_PASSWORD or "").strip()

    # Fail closed in production if required variables are missing
    if is_prod and (not initial_admin_email or not initial_admin_password):
        raise RuntimeError("FATAL BOOTSTRAP ERROR: INITIAL_ADMIN_EMAIL and INITIAL_ADMIN_PASSWORD must be configured in production.")

    # In dev/test, fallback if empty
    if not initial_admin_email:
        initial_admin_email = "placement@ipu.ac.in"
    if not initial_admin_password:
        initial_admin_password = "admin123"

    try:
        # 1. INITIAL SUPER ADMIN BOOTSTRAP (Idempotent single-admin creation)
        existing_super_admins = db.query(User).filter(User.role == UserRole.SUPER_ADMIN.value).all()

        # CASE D: Multiple SUPER_ADMIN records exist -> Invariant violation
        if len(existing_super_admins) > 1:
            raise RuntimeError(
                f"FATAL INVARIANT VIOLATION: Multiple SUPER_ADMIN records ({len(existing_super_admins)}) "
                "detected in the database. Manual administrative remediation is required."
            )

        # CASE A: Exactly one SUPER_ADMIN already exists -> Strictly idempotent
        if len(existing_super_admins) == 1:
            # Do NOT modify password, email, or role. Do NOT create another.
            pass
        else:
            # CASE B or C: No SUPER_ADMIN exists in database
            existing_user = db.query(User).filter(User.email == initial_admin_email).first()

            # CASE C: Existing non-SUPER_ADMIN account matches INITIAL_ADMIN_EMAIL -> Block promotion
            if existing_user is not None:
                raise RuntimeError(
                    f"FATAL BOOTSTRAP ERROR: An existing account with role '{existing_user.role}' "
                    f"already exists with email '{initial_admin_email}'. Automatic promotion to SUPER_ADMIN "
                    "is blocked for security. Manual identity resolution is required."
                )

            # CASE B: No SUPER_ADMIN exists AND INITIAL_ADMIN_EMAIL does not exist -> Create exactly one
            initial_admin = User(
                email=initial_admin_email,
                full_name=settings.INITIAL_ADMIN_NAME or "System Super Administrator",
                role=UserRole.SUPER_ADMIN.value,
                status=AccountStatus.ACTIVE.value,
                hashed_password=get_password_hash(initial_admin_password),
                avatar_url="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150",
                is_active=True
            )
            db.add(initial_admin)

            # Ensure allowlist entry exists for bootstrap admin transactionally
            admin_allowlist_entry = db.query(AdminAllowlist).filter(AdminAllowlist.email == initial_admin_email).first()
            if not admin_allowlist_entry:
                db.add(AdminAllowlist(
                    email=initial_admin_email,
                    name=settings.INITIAL_ADMIN_NAME or "System Super Administrator",
                    assigned_role=UserRole.SUPER_ADMIN.value,
                    added_by="SYSTEM_BOOTSTRAP",
                    is_active=True
                ))
            else:
                admin_allowlist_entry.assigned_role = UserRole.SUPER_ADMIN.value

            db.flush()

        # Invariant check and bootstrap complete. Transactionally commit.
        db.commit()
    except Exception:
        db.rollback()
        raise
