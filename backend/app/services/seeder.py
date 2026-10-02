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

    # 1. INITIAL SUPER ADMIN BOOTSTRAP (Idempotent single-admin creation)
    initial_admin_email = settings.INITIAL_ADMIN_EMAIL.strip().lower()

    # Check if ANY Super Admin already exists in the database
    existing_super_admin = db.query(User).filter(User.role == UserRole.SUPER_ADMIN.value).first()

    if not existing_super_admin:
        # Check if the user exists with a different role
        existing_user = db.query(User).filter(User.email == initial_admin_email).first()
        if existing_user:
            existing_user.role = UserRole.SUPER_ADMIN.value
            existing_user.status = AccountStatus.ACTIVE.value
            existing_user.is_active = True
        else:
            initial_admin = User(
                email=initial_admin_email,
                full_name=settings.INITIAL_ADMIN_NAME,
                role=UserRole.SUPER_ADMIN.value,
                status=AccountStatus.ACTIVE.value,
                hashed_password=get_password_hash(settings.INITIAL_ADMIN_PASSWORD),
                avatar_url="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150",
                is_active=True
            )
            db.add(initial_admin)

        # Ensure allowlist entry exists for bootstrap admin
        admin_allowlist_entry = db.query(AdminAllowlist).filter(AdminAllowlist.email == initial_admin_email).first()
        if not admin_allowlist_entry:
            db.add(AdminAllowlist(
                email=initial_admin_email,
                name=settings.INITIAL_ADMIN_NAME,
                assigned_role=UserRole.SUPER_ADMIN.value,
                added_by="SYSTEM_BOOTSTRAP",
                is_active=True
            ))
        else:
            admin_allowlist_entry.assigned_role = UserRole.SUPER_ADMIN.value
        db.flush()

    # In production, stop here. Do NOT seed universal demo staff or student credentials.
    if is_prod or not settings.SEED_DEMO_DATA:
        db.commit()
        print(f"[CodeSphere Seeder] Production initialization complete. Primary administrator: {initial_admin_email}")
        return

    # 2. DEVELOPMENT-ONLY DEMO ACCOUNTS & STAFF ALLOWLIST
    dev_staff_password = settings.SEED_STAFF_PASSWORD
    dev_student_password = settings.SEED_STUDENT_PASSWORD

    staff_allowlist = [
        {"email": "admin@ipu.ac.in", "name": "Placement Cell Operations Admin", "role": UserRole.ADMIN.value},
        {"email": "tnp.officer@ipu.ac.in", "name": "USAR Placement Head", "role": UserRole.PLACEMENT_ADMIN.value},
        {"email": "faculty.sharma@ipu.ac.in", "name": "Prof. Rajesh Sharma (Faculty Advisor)", "role": UserRole.FACULTY.value},
        {"email": "setter.ai@ipu.ac.in", "name": "Dr. Neha Verma (Question Setter)", "role": UserRole.QUESTION_SETTER.value},
        {"email": "reviewer.cs@ipu.ac.in", "name": "Dr. Vikram Mehta (Curriculum Reviewer)", "role": UserRole.REVIEWER.value},
    ]
    for entry in staff_allowlist:
        existing = db.query(AdminAllowlist).filter(AdminAllowlist.email == entry["email"]).first()
        if not existing:
            db.add(AdminAllowlist(
                email=entry["email"],
                name=entry["name"],
                assigned_role=entry["role"],
                added_by="SYSTEM_BOOTSTRAP",
                is_active=True
            ))
        else:
            existing.assigned_role = entry["role"]
    db.flush()

    users_to_seed = [
        {
            "email": "admin@ipu.ac.in",
            "full_name": "Placement Operations Admin",
            "role": UserRole.ADMIN.value,
            "password": dev_staff_password,
            "avatar_url": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150"
        },
        {
            "email": "tnp.officer@ipu.ac.in",
            "full_name": "USAR Placement Coordinator",
            "role": UserRole.PLACEMENT_ADMIN.value,
            "password": dev_staff_password,
            "avatar_url": "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150"
        },
        {
            "email": "faculty.sharma@ipu.ac.in",
            "full_name": "Prof. Rajesh Sharma",
            "role": UserRole.FACULTY.value,
            "password": dev_staff_password,
            "avatar_url": "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=150"
        },
        {
            "email": "setter.ai@ipu.ac.in",
            "full_name": "Dr. Neha Verma",
            "role": UserRole.QUESTION_SETTER.value,
            "password": dev_staff_password,
            "avatar_url": "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=150"
        },
        {
            "email": "reviewer.cs@ipu.ac.in",
            "full_name": "Dr. Vikram Mehta",
            "role": UserRole.REVIEWER.value,
            "password": dev_staff_password,
            "avatar_url": "https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?w=150"
        },
        {
            "email": "aarav.patel@std.ggsipu.ac.in",
            "full_name": "Aarav Patel",
            "role": UserRole.STUDENT.value,
            "password": dev_student_password,
            "avatar_url": "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=150",
            "profile": {
                "enrollment_no": "001USAR2023",
                "branch": "AIML",
                "academic_year": 3
            }
        },
        {
            "email": "diya.sharma@std.ggsipu.ac.in",
            "full_name": "Diya Sharma",
            "role": UserRole.STUDENT.value,
            "password": dev_student_password,
            "avatar_url": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=150",
            "profile": {
                "enrollment_no": "002USAR2022",
                "branch": "AR",
                "academic_year": 4
            }
        }
    ]

    for u_data in users_to_seed:
        existing_u = db.query(User).filter(User.email == u_data["email"]).first()
        if not existing_u:
            new_u = User(
                email=u_data["email"],
                full_name=u_data["full_name"],
                role=u_data["role"],
                status=AccountStatus.ACTIVE.value,
                hashed_password=get_password_hash(u_data["password"]),
                avatar_url=u_data["avatar_url"],
                is_active=True
            )
            db.add(new_u)
            db.flush()

            if "profile" in u_data and u_data["profile"]:
                p_info = u_data["profile"]
                profile = StudentProfile(
                    user_id=new_u.id,
                    enrollment_no=p_info["enrollment_no"],
                    branch=p_info["branch"],
                    academic_year=p_info["academic_year"],
                    is_approved=True
                )
                db.add(profile)
        else:
            existing_u.role = u_data["role"]
            existing_u.status = AccountStatus.ACTIVE.value
            existing_u.is_active = True
    
    db.commit()
    print("[CodeSphere] Development database seeded with test accounts.")
