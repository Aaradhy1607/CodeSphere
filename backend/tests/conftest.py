import pytest
from app.core.database import SessionLocal, Base, engine, auto_migrate_db
from app.models.models import User, AdminAllowlist, UserRole, AccountStatus
from app.core.security import get_password_hash

@pytest.fixture(scope="session", autouse=True)
def setup_test_suite_fixtures():
    Base.metadata.create_all(bind=engine)
    auto_migrate_db()
    db = SessionLocal()
    try:
        # 1. Staff Allowlist for test assertions
        staff_allowlist = [
            {"email": "placement@ipu.ac.in", "name": "Placement Cell Operations Admin", "role": UserRole.ADMIN.value},
            {"email": "admin@ipu.ac.in", "name": "Placement Cell Operations Admin", "role": UserRole.ADMIN.value},
            {"email": "usar.tnp@ipu.ac.in", "name": "USAR Placement Head", "role": UserRole.ADMIN.value},
            {"email": "tnp.officer@ipu.ac.in", "name": "USAR Placement Coordinator", "role": UserRole.PLACEMENT_ADMIN.value},
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
                    added_by="TEST_SUITE",
                    is_active=True
                ))
            else:
                existing.assigned_role = entry["role"]

        # 2. Test Users required across unit and integration tests
        test_users = [
            {
                "email": "placement@ipu.ac.in",
                "full_name": "Placement Operations Admin",
                "role": UserRole.ADMIN.value,
                "password": "admin123"
            },
            {
                "email": "admin@ipu.ac.in",
                "full_name": "Placement Operations Admin",
                "role": UserRole.ADMIN.value,
                "password": "Admin@123"
            },
            {
                "email": "usar.tnp@ipu.ac.in",
                "full_name": "USAR Placement Head",
                "role": UserRole.ADMIN.value,
                "password": "Admin@123"
            },
            {
                "email": "setter.ai@ipu.ac.in",
                "full_name": "Dr. Neha Verma",
                "role": UserRole.QUESTION_SETTER.value,
                "password": "setter123"
            },
            {
                "email": "reviewer.cs@ipu.ac.in",
                "full_name": "Dr. Vikram Mehta",
                "role": UserRole.REVIEWER.value,
                "password": "reviewer123"
            },
            {
                "email": "aarav.patel@std.ggsipu.ac.in",
                "full_name": "Aarav Patel",
                "role": UserRole.STUDENT.value,
                "password": "student123"
            }
        ]
        for u in test_users:
            existing_user = db.query(User).filter(User.email == u["email"]).first()
            if not existing_user:
                db.add(User(
                    email=u["email"],
                    full_name=u["full_name"],
                    role=u["role"],
                    status=AccountStatus.ACTIVE.value,
                    hashed_password=get_password_hash(u["password"]),
                    is_active=True
                ))
        db.commit()
    finally:
        db.close()
    yield
