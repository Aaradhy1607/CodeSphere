from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_password_hash, verify_password
from app.main import app
from app.models.models import AccountStatus, Base, StudentProfile, User, UserRole


def test_student_login_by_id_and_email_persists_password_and_session_flow(tmp_path, caplog):
    password = "Persistent-Student-Password-42!"
    db_url = f"sqlite:///{tmp_path / 'student-auth.db'}"
    test_engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    test_session_factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine
    )

    def override_get_db():
        db = test_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with test_session_factory() as db:
            student = User(
                email="student.auth@std.ggsipu.ac.in",
                full_name="Student Auth Test",
                role=UserRole.STUDENT.value,
                status=AccountStatus.ACTIVE.value,
                hashed_password=get_password_hash(password),
                is_active=True
            )
            db.add(student)
            db.flush()
            db.add(StudentProfile(
                user_id=student.id,
                enrollment_no="ENR-TEST-2042",
                branch="AIML",
                academic_year=3,
                is_approved=True
            ))
            db.commit()

        client = TestClient(app)
        login_res = client.post(
            f"{settings.API_V1_STR}/auth/login",
            json={"email": " enr-test-2042 ", "password": password}
        )
        assert login_res.status_code == 200
        login_data = login_res.json()
        assert login_data["user"]["email"] == "student.auth@std.ggsipu.ac.in"
        assert login_data["user"]["role"] == UserRole.STUDENT.value
        assert "hashed_password" not in login_data["user"]
        assert password not in login_res.text

        wrong_password_res = client.post(
            f"{settings.API_V1_STR}/auth/login",
            json={"email": "ENR-TEST-2042", "password": "Wrong-Password"}
        )
        assert wrong_password_res.status_code == 401

        refresh_res = client.post(
            f"{settings.API_V1_STR}/auth/refresh",
            json={"refresh_token": login_data["refresh_token"]}
        )
        assert refresh_res.status_code == 200
        refreshed_data = refresh_res.json()

        logout_res = client.post(
            f"{settings.API_V1_STR}/auth/logout",
            json={"refresh_token": refreshed_data["refresh_token"]},
            headers={"Authorization": f"Bearer {refreshed_data['access_token']}"}
        )
        assert logout_res.status_code == 200
        revoked_refresh_res = client.post(
            f"{settings.API_V1_STR}/auth/refresh",
            json={"refresh_token": refreshed_data["refresh_token"]}
        )
        assert revoked_refresh_res.status_code == 401

        email_login_res = client.post(
            f"{settings.API_V1_STR}/auth/login",
            json={
                "email": "STUDENT.AUTH@STD.GGSIPU.AC.IN",
                "password": password
            }
        )
        assert email_login_res.status_code == 200
        assert password not in caplog.text
    finally:
        app.dependency_overrides.pop(get_db, None)
        test_engine.dispose()

    restarted_engine = create_engine(db_url, connect_args={"check_same_thread": False})
    try:
        with sessionmaker(bind=restarted_engine)() as restarted_db:
            persisted_student = restarted_db.query(User).filter(
                User.email == "student.auth@std.ggsipu.ac.in"
            ).one()
            assert verify_password(password, persisted_student.hashed_password)
    finally:
        restarted_engine.dispose()
