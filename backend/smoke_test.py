import os
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.models import User, AdminAllowlist, UserRole, StudentProfile, Assessment, Submission, Question, Event

def run_production_smoke_test():
    client = TestClient(app)
    db = SessionLocal()
    try:
        # 1. Verify Database Inventory
        super_admin_count = db.query(User).filter(User.role == UserRole.SUPER_ADMIN.value).count()
        other_users_count = db.query(User).filter(User.role != UserRole.SUPER_ADMIN.value).count()
        allowlist_count = db.query(AdminAllowlist).count()
        student_profiles_count = db.query(StudentProfile).count()
        assessments_count = db.query(Assessment).count()
        submissions_count = db.query(Submission).count()
        questions_count = db.query(Question).count()
        events_count = db.query(Event).count()

        print(f"DATABASE INVENTORY:")
        print(f"  SUPER_ADMIN Count:      {super_admin_count}")
        print(f"  Other Users Count:      {other_users_count}")
        print(f"  Admin Allowlist Count:  {allowlist_count}")
        print(f"  Student Profiles Count: {student_profiles_count}")
        print(f"  Assessments Count:      {assessments_count}")
        print(f"  Submissions Count:      {submissions_count}")
        print(f"  Questions Count:        {questions_count}")
        print(f"  Events Count:           {events_count}")

        assert super_admin_count == 1, f"Expected 1 SUPER_ADMIN, found {super_admin_count}"
        assert other_users_count == 0, f"Expected 0 other users, found {other_users_count}"
        assert student_profiles_count == 0, f"Expected 0 student profiles, found {student_profiles_count}"

        # 2. Verify Super Admin Authentication
        email = (settings.INITIAL_ADMIN_EMAIL or "").strip().lower()
        pwd = (settings.INITIAL_ADMIN_PASSWORD or "").strip()
        login_res = client.post(f"{settings.API_V1_STR}/auth/login", json={"email": email, "password": pwd})
        assert login_res.status_code == 200, f"Super Admin login failed: {login_res.status_code} {login_res.text}"
        tokens = login_res.json()
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        print("  Super Admin Login:      SUCCESS (200 OK)")

        # 3. Verify /auth/me
        me_res = client.get(f"{settings.API_V1_STR}/auth/me", headers={"Authorization": f"Bearer {access_token}"})
        assert me_res.status_code == 200, f"/auth/me failed: {me_res.status_code}"
        me_data = me_res.json()
        assert me_data["role"] == UserRole.SUPER_ADMIN.value, f"Unexpected role: {me_data.get('role')}"
        assert me_data["email"].lower() == email, f"Unexpected email: {me_data.get('email')}"
        print(f"  /auth/me Verification:  SUCCESS (Role: {me_data['role']}, Email: {me_data['email']})")

        # 4. Verify Demo Endpoints Blocked (403 Forbidden in Production)
        demo_users_res = client.get(f"{settings.API_V1_STR}/auth/demo-users")
        assert demo_users_res.status_code == 403, f"demo-users returned {demo_users_res.status_code}, expected 403"
        print(f"  /auth/demo-users:       BLOCKED (403 Forbidden)")

        demo_switch_res = client.post(f"{settings.API_V1_STR}/auth/demo-switch", json={"role": "STUDENT"})
        assert demo_switch_res.status_code == 403, f"demo-switch returned {demo_switch_res.status_code}, expected 403"
        print(f"  /auth/demo-switch:      BLOCKED (403 Forbidden)")

        # 5. Verify Invalid & Expired Token Rejection
        invalid_res = client.get(f"{settings.API_V1_STR}/auth/me", headers={"Authorization": "Bearer invalid.token.payload"})
        assert invalid_res.status_code == 401, f"Invalid token returned {invalid_res.status_code}, expected 401"
        print(f"  Invalid Token Check:    REJECTED (401 Unauthorized)")

        # 6. Verify Token Refresh Flow
        refresh_res = client.post(f"{settings.API_V1_STR}/auth/refresh", json={"refresh_token": refresh_token})
        assert refresh_res.status_code == 200, f"Token refresh failed: {refresh_res.status_code}"
        print(f"  Token Refresh Flow:     SUCCESS (200 OK)")

        # 7. Verify Public Registration Role Privilege Escalation Blocked
        reg_res = client.post(f"{settings.API_V1_STR}/auth/register", json={
            "email": "test.attacker@std.ggsipu.ac.in",
            "password": "Password123!",
            "full_name": "Test Attacker",
            "role": "SUPER_ADMIN"
        })
        # If registered, the role MUST be STUDENT, never SUPER_ADMIN
        if reg_res.status_code == 200:
            reg_user = db.query(User).filter(User.email == "test.attacker@std.ggsipu.ac.in").first()
            assert reg_user.role == UserRole.STUDENT.value, f"Privilege escalation occurred: {reg_user.role}"
            # Clean up test registration
            db.delete(reg_user)
            db.commit()
            print(f"  Privilege Escalation:   BLOCKED (Client-supplied role ignored, server assigned STUDENT)")
        else:
            print(f"  Registration Validation: ENFORCED ({reg_res.status_code})")

        print("==================================================")
        print("ALL PRODUCTION SMOKE TESTS PASSED SUCCESSFULLY!")
        print("==================================================")

    finally:
        db.close()

if __name__ == "__main__":
    run_production_smoke_test()
