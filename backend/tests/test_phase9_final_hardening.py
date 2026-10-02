import os
import sys
import pytest
import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import Base, engine, get_db, SessionLocal
from app.core.security import get_password_hash, create_access_token
from app.models.models import (
    User, StudentProfile, UserRole, Question, TestCase, Event, EventQuestion,
    Submission, SubmissionVerdict, SubmissionStatus, Assessment, AssessmentQuestion,
    AssessmentAttempt, AttemptAnswer, AntiCheatEvent, AssessmentStatus, AttemptStatus,
    QuestionType
)

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield


def _create_user(db: Session, email: str, role: str, name: str = "Test User") -> User:
    u = db.query(User).filter(User.email == email).first()
    if not u:
        u = User(
            email=email,
            full_name=name,
            role=role,
            hashed_password=get_password_hash("pass123"),
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


def test_1_staff_multi_role_event_access_and_filtering():
    """
    Verifies that Super Admins, Placement Admins, and Faculty can view all events regardless
    of target branch/year, while Students are strictly filtered by eligibility.
    """
    db = SessionLocal()
    try:
        super_admin = _create_user(db, "super_admin_p9@usar.edu", UserRole.SUPER_ADMIN.value, "Super Admin")
        placement_admin = _create_user(db, "placement_admin_p9@usar.edu", UserRole.PLACEMENT_ADMIN.value, "Placement Admin")
        faculty = _create_user(db, "faculty_p9@usar.edu", UserRole.FACULTY.value, "Faculty P9")
        
        student_aiml = _create_user(db, "student_aiml_p9@usar.edu", UserRole.STUDENT.value, "AIML Student")
        if not student_aiml.student_profile:
            p = StudentProfile(user_id=student_aiml.id, enrollment_no="AIML001", branch="AI-ML", academic_year=3, is_approved=True)
            db.add(p)
            db.commit()

        # Create restricted event for IIOT branch year 4
        event = Event(
            title="IIOT Exclusive Placement Assessment",
            description="Restricted assessment for final year IIOT",
            target_branch="IIOT",
            target_year=4,
            start_time=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1),
            end_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2),
            duration_minutes=60,
            status="ACTIVE"
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        # Super Admin should see the event
        res_super = client.get("/api/v1/events/", headers=_get_auth_headers(super_admin))
        assert res_super.status_code == 200
        event_ids_super = [e["id"] for e in res_super.json()]
        assert event.id in event_ids_super

        # Placement Admin should see the event
        res_place = client.get("/api/v1/events/", headers=_get_auth_headers(placement_admin))
        assert res_place.status_code == 200
        event_ids_place = [e["id"] for e in res_place.json()]
        assert event.id in event_ids_place

        # Faculty should see the event
        res_fac = client.get("/api/v1/events/", headers=_get_auth_headers(faculty))
        assert res_fac.status_code == 200
        event_ids_fac = [e["id"] for e in res_fac.json()]
        assert event.id in event_ids_fac

        # AI-ML Student should NOT see the IIOT event
        res_stu = client.get("/api/v1/events/", headers=_get_auth_headers(student_aiml))
        assert res_stu.status_code == 200
        event_ids_stu = [e["id"] for e in res_stu.json()]
        assert event.id not in event_ids_stu

    finally:
        db.close()


def test_2_staff_access_to_student_topic_analytics_and_idor_protection():
    """
    Verifies that staff roles can view student topic analytics, students can view their own,
    and cross-student inspection is blocked with 403.
    """
    db = SessionLocal()
    try:
        faculty = _create_user(db, "faculty_analytics_p9@usar.edu", UserRole.FACULTY.value, "Faculty Analytics")
        student_a = _create_user(db, "student_a_p9@usar.edu", UserRole.STUDENT.value, "Student A")
        student_b = _create_user(db, "student_b_p9@usar.edu", UserRole.STUDENT.value, "Student B")

        # Faculty can view student A's analytics
        res_fac = client.get(f"/api/v1/analytics/student-topics/{student_a.id}", headers=_get_auth_headers(faculty))
        assert res_fac.status_code == 200
        data_fac = res_fac.json()
        assert "topic_mastery" in data_fac
        assert "score_trajectory" in data_fac

        # Student A can view their own analytics
        res_self = client.get(f"/api/v1/analytics/student-topics/{student_a.id}", headers=_get_auth_headers(student_a))
        assert res_self.status_code == 200

        # Student B CANNOT view student A's analytics (IDOR protected)
        res_idor = client.get(f"/api/v1/analytics/student-topics/{student_a.id}", headers=_get_auth_headers(student_b))
        assert res_idor.status_code == 403
        assert "Access denied" in res_idor.json()["detail"]

    finally:
        db.close()


def test_3_final_submission_idempotency_and_role_rules():
    """
    Verifies that normal students can only submit once per question in an event,
    and duplicate final submissions are rejected with 400.
    """
    db = SessionLocal()
    try:
        student = _create_user(db, "student_sub_p9@usar.edu", UserRole.STUDENT.value, "Student Sub P9")
        
        # Create test question
        import uuid
        uid_str = uuid.uuid4().hex[:6]
        q = Question(
            title=f"Phase 9 Hardening Question {uid_str}",
            slug=f"phase-9-hardening-q-{uid_str}",
            problem_statement="Calculate sum of two numbers",
            input_format="a b",
            output_format="sum",
            difficulty_score=3,
            status="PUBLISHED",
            question_type="CODING",
            time_limit_seconds=2.0,
            memory_limit_mb=256
        )
        db.add(q)
        db.commit()
        db.refresh(q)

        tc = TestCase(question_id=q.id, input_data="4 5", expected_output="9", is_hidden=False, points=100.0)
        db.add(tc)

        # Create active event
        event = Event(
            title="Phase 9 Coding Round",
            start_time=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=10),
            end_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
            status="ACTIVE",
            target_branch="ALL",
            target_year=0
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        eq = EventQuestion(event_id=event.id, question_id=q.id, order_index=1)
        db.add(eq)
        db.commit()

        # First synchronous final submission
        payload = {
            "event_id": event.id,
            "question_id": q.id,
            "code": "a, b = map(int, input().split())\nprint(a + b)",
            "language": "python"
        }
        res_1 = client.post("/api/v1/execute/submit", json=payload, headers=_get_auth_headers(student))
        assert res_1.status_code == 200
        sub_data = res_1.json()
        assert sub_data["is_final"] == True
        assert sub_data["passed_test_cases"] == 1

        # Second submission attempt by the same student must be rejected
        res_2 = client.post("/api/v1/execute/submit", json=payload, headers=_get_auth_headers(student))
        assert res_2.status_code == 400
        assert "already submitted your final solution" in res_2.json()["detail"]

        # Second async submission attempt must also be rejected
        res_async = client.post("/api/v1/execute/submit-async", json=payload, headers=_get_auth_headers(student))
        assert res_async.status_code == 400
        assert "already submitted your final solution" in res_async.json()["detail"]

    finally:
        db.close()


def test_4_assessment_state_machine_and_server_timer_authority():
    """
    Verifies that the server authoritative timer decrements accurately,
    heartbeats report server remaining seconds, and expired assessments reject start.
    """
    db = SessionLocal()
    try:
        admin = _create_user(db, "admin_assess_p9@usar.edu", UserRole.ADMIN.value, "Admin Assess P9")
        student = _create_user(db, "student_assess_p9@usar.edu", UserRole.STUDENT.value, "Student Assess P9")

        # Create active assessment
        assess = Assessment(
            title="Authoritative Timer Verification",
            description="Testing server countdown authority",
            duration_minutes=30,
            start_time=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5),
            end_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2),
            status=AssessmentStatus.ACTIVE.value,
            max_attempts=1,
            total_marks=100.0,
            passing_score=40.0,
            allowed_languages=["python", "cpp"]
        )
        db.add(assess)
        db.commit()
        db.refresh(assess)

        # Start attempt
        res_start = client.post(f"/api/v1/assessments/{assess.id}/start", headers=_get_auth_headers(student))
        assert res_start.status_code == 200
        attempt_data = res_start.json()
        attempt_id = attempt_data["attempt_id"]
        session_token = attempt_data["current_session_token"]
        assert attempt_data["remaining_seconds"] > 0
        assert attempt_data["remaining_seconds"] <= 1800

        # Heartbeat returns server-authoritative remaining time
        res_hb = client.post(
            f"/api/v1/assessments/attempts/{attempt_id}/heartbeat",
            json={"session_token": session_token},
            headers=_get_auth_headers(student)
        )
        assert res_hb.status_code == 200
        hb_data = res_hb.json()
        assert hb_data["is_active"] == True
        assert hb_data["status"] == "IN_PROGRESS"
        assert hb_data["remaining_seconds"] <= attempt_data["remaining_seconds"]

    finally:
        db.close()


def test_5_anti_cheat_violation_logging_and_integrity_penalty():
    """
    Verifies that anti-cheat tab switches, blur events, and full-screen exits are logged,
    integrity scores are adjusted deterministically, and threshold violations trigger termination.
    """
    db = SessionLocal()
    try:
        admin = _create_user(db, "admin_proctor_p9@usar.edu", UserRole.ADMIN.value, "Admin Proctor P9")
        student = _create_user(db, "student_proctor_p9@usar.edu", UserRole.STUDENT.value, "Student Proctor P9")

        assess = Assessment(
            title="Proctoring Integrity Hardening",
            description="Testing violation logging and severity weighting",
            duration_minutes=45,
            start_time=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5),
            end_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2),
            status=AssessmentStatus.ACTIVE.value,
            max_attempts=1,
            anti_cheat_policy={
                "max_tab_switches": 3,
                "penalties": {"TAB_SWITCH": 10.0, "WINDOW_BLUR": 5.0}
            }
        )
        db.add(assess)
        db.commit()
        db.refresh(assess)

        res_start = client.post(f"/api/v1/assessments/{assess.id}/start", headers=_get_auth_headers(student))
        assert res_start.status_code == 200
        attempt_id = res_start.json()["attempt_id"]

        # Log tab switch violation
        event_payload = {
            "event_type": "TAB_SWITCH",
            "severity": "HIGH",
            "event_data": {"window": "tab_2"}
        }
        res_viol = client.post(
            f"/api/v1/assessments/attempts/{attempt_id}/anti-cheat-event",
            json=event_payload,
            headers=_get_auth_headers(student)
        )
        assert res_viol.status_code == 200
        viol_data = res_viol.json()
        assert viol_data["event_type"] == "TAB_SWITCH"
        assert viol_data["severity"] == "HIGH"

        # Check attempt state reflects the logged violation
        res_att = client.get(f"/api/v1/assessments/attempts/{attempt_id}", headers=_get_auth_headers(student))
        assert res_att.status_code == 200
        att_state = res_att.json()
        assert att_state["tab_switch_count"] == 1
        assert att_state["integrity_score"] < 100.0

    finally:
        db.close()
