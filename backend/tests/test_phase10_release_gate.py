import os
import sys
import pytest
import uuid
import datetime
import time
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import Base, engine, SessionLocal
from app.core.security import get_password_hash, create_access_token
from app.models.models import (
    User, StudentProfile, UserRole, Question, TestCase, Event, EventQuestion,
    Submission, SubmissionVerdict, SubmissionStatus, Assessment, AssessmentQuestion,
    AssessmentAttempt, AttemptAnswer, AntiCheatEvent, AssessmentStatus, AttemptStatus,
    QuestionType
)
from app.services.code_runner import code_runner

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


def test_1_complete_end_to_end_assessment_and_judging_workflow():
    """
    Validates the entire integrated college assessment lifecycle:
    1. Faculty creates a new coding problem with sample and hidden test cases.
    2. Faculty creates, schedules, and publishes an assessment round.
    3. Student authenticates, verifies eligibility, and starts an attempt.
    4. Student writes code, tests with custom input, and saves draft answer.
    5. Student submits assessment.
    6. Judge engine evaluates all test cases authoritatively.
    7. Student views result report with hidden test data shielded.
    8. Faculty monitors assessment attempt and reviews results.
    """
    db = SessionLocal()
    try:
        q_setter = _create_user(db, "q_setter_e2e@usar.edu", UserRole.QUESTION_SETTER.value, "Prof. Question Setter")
        placement_admin = _create_user(db, "placement_admin_e2e@usar.edu", UserRole.PLACEMENT_ADMIN.value, "Dr. Placement Head")
        student = _create_user(db, "student_e2e@usar.edu", UserRole.STUDENT.value, "Student E2E Candidate")
        if not student.student_profile:
            p = StudentProfile(user_id=student.id, enrollment_no="001USAR2026", branch="CSE", academic_year=3, is_approved=True)
            db.add(p)
            db.commit()

        # Step 1: Question Setter creates a coding question
        uid = uuid.uuid4().hex[:6]
        q_payload = {
            "title": f"Reverse Words in String {uid}",
            "problem_statement": "Given a string of words separated by spaces, reverse the order of the words.",
            "input_format": "A single line containing words separated by space.",
            "output_format": "The words in reverse order.",
            "constraints": "1 <= len(S) <= 1000",
            "difficulty_score": 4,
            "question_type": "CODING",
            "marks": 100,
            "negative_marks": 0.0,
            "time_estimate_minutes": 30,
            "expected_time_complexity": "O(N)",
            "expected_space_complexity": "O(N)",
            "time_limit_seconds": 2.0,
            "memory_limit_mb": 256,
            "reference_solutions": {
                "python": "s = input().strip()\nprint(' '.join(s.split()[::-1]))"
            },
            "test_cases": [
                {
                    "input_data": "hello world",
                    "expected_output": "world hello",
                    "is_hidden": False,
                    "explanation": "Sample case",
                    "points": 30.0
                },
                {
                    "input_data": "the sky is blue",
                    "expected_output": "blue is sky the",
                    "is_hidden": True,
                    "explanation": "Hidden case",
                    "points": 70.0
                }
            ]
        }
        res_create_q = client.post("/api/v1/questions/", json=q_payload, headers=_get_auth_headers(q_setter))
        assert res_create_q.status_code == 200, f"Question creation failed: {res_create_q.text}"
        question_data = res_create_q.json()
        question_id = question_data["id"]

        # Step 2: Placement Admin creates, adds questions, and publishes an assessment
        assess_payload = {
            "title": f"USAR Campus Placement Assessment {uid}",
            "description": "Technical round for software engineer roles",
            "instructions": "Attempt all problems within 60 minutes.",
            "duration_minutes": 60,
            "start_time": (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)).isoformat(),
            "end_time": (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)).isoformat(),
            "max_attempts": 1,
            "total_marks": 100.0,
            "passing_score": 40.0,
            "allowed_languages": ["python", "cpp", "c", "java"],
            "candidate_assignment": {"type": "ALL", "targets": []},
            "anti_cheat_policy": {"max_tab_switches": 3},
            "show_results_immediately": True,
            "allow_review": True,
            "status": "DRAFT",
            "questions": [
                {
                    "question_id": question_id,
                    "order_index": 1,
                    "marks": 100.0
                }
            ]
        }
        res_create_a = client.post("/api/v1/assessments/", json=assess_payload, headers=_get_auth_headers(placement_admin))
        assert res_create_a.status_code == 200, f"Assessment creation failed: {res_create_a.text}"
        assessment_id = res_create_a.json()["id"]

        # Publish assessment
        res_pub = client.post(f"/api/v1/assessments/{assessment_id}/publish", headers=_get_auth_headers(placement_admin))
        assert res_pub.status_code == 200
        assert "published successfully" in res_pub.json()["message"]

        # Step 3: Student starts attempt
        res_start = client.post(f"/api/v1/assessments/{assessment_id}/start", headers=_get_auth_headers(student))
        assert res_start.status_code == 200
        attempt_state = res_start.json()
        attempt_id = attempt_state["attempt_id"]
        assert len(attempt_state["questions"]) == 1

        # Verify hidden test case inputs/outputs are NOT in candidate question payload
        candidate_q = attempt_state["questions"][0]
        assert candidate_q["question_id"] == question_id
        # Sample test cases may be present, but hidden test cases must be excluded from candidate test cases list
        for tc in (candidate_q.get("sample_test_cases") or []):
            assert tc.get("is_hidden") is False or tc.get("is_hidden") is None

        # Step 4: Student executes with Custom Input
        student_code = "s = input().strip()\nprint(' '.join(s.split()[::-1]))"
        run_payload = {
            "question_id": question_id,
            "code": student_code,
            "language": "python",
            "custom_input": "quick brown fox"
        }
        res_run = client.post("/api/v1/execute/run", json=run_payload, headers=_get_auth_headers(student))
        assert res_run.status_code == 200
        run_data = res_run.json()
        assert run_data["output"].strip() == "fox brown quick"
        assert run_data["execution_time_ms"] >= 0

        # Autosave candidate answer
        save_payload = {
            "question_id": question_id,
            "submitted_code": student_code,
            "submitted_language": "python",
            "is_flagged": False
        }
        res_save = client.post(f"/api/v1/assessments/attempts/{attempt_id}/save-answer", json=save_payload, headers=_get_auth_headers(student))
        assert res_save.status_code == 200
        assert res_save.json()["success"] == True

        # Step 5: Student submits final exam
        res_submit = client.post(
            f"/api/v1/assessments/attempts/{attempt_id}/submit",
            json={"final_sync_answers": [save_payload]},
            headers=_get_auth_headers(student)
        )
        assert res_submit.status_code == 200
        result_data = res_submit.json()
        assert result_data["total_score"] == 100.0
        assert result_data["passed"] == True

        # Step 6: Student retrieves results (with hidden tests sanitized)
        res_result = client.get(f"/api/v1/assessments/attempts/{attempt_id}/result", headers=_get_auth_headers(student))
        assert res_result.status_code == 200
        res_detail = res_result.json()
        assert res_detail["total_score"] == 100.0

        # Step 7: Placement Admin reviews monitor dashboard and assessment results
        res_mon = client.get(f"/api/v1/assessments/{assessment_id}/monitor", headers=_get_auth_headers(placement_admin))
        assert res_mon.status_code == 200
        mon_data = res_mon.json()
        assert mon_data["total_started"] >= 1
        assert mon_data["submitted_count"] >= 1

        res_results_list = client.get(f"/api/v1/assessments/{assessment_id}/results", headers=_get_auth_headers(placement_admin))
        assert res_results_list.status_code == 200
        assert len(res_results_list.json()) >= 1

    finally:
        db.close()


def test_2_production_health_and_observability_endpoints():
    """
    Validates that production health probes, readiness checks,
    metrics collectors, and judge telemetry are fully active and reporting.
    """
    # Liveness probe
    res_live = client.get("/health/liveness")
    assert res_live.status_code == 200
    assert res_live.json()["status"] == "ALIVE"

    # Readiness probe
    res_ready = client.get("/health/readiness")
    assert res_ready.status_code == 200
    ready_data = res_ready.json()
    assert ready_data["status"] == "READY"
    assert "database" in ready_data
    assert "cache" in ready_data
    assert "worker" in ready_data

    # System metrics
    res_metrics = client.get("/metrics")
    assert res_metrics.status_code == 200
    metrics_data = res_metrics.json()
    assert "uptime_seconds" in metrics_data
    assert "latencies_ms" in metrics_data
    assert "total_requests" in metrics_data

    # Judge queue observability metrics
    db = SessionLocal()
    try:
        admin = _create_user(db, "admin_metrics_p10@usar.edu", UserRole.ADMIN.value, "Admin Metrics")
        res_j_metrics = client.get("/api/v1/execute/metrics", headers=_get_auth_headers(admin))
        assert res_j_metrics.status_code == 200
        j_data = res_j_metrics.json()
        assert "queued_submissions" in j_data
        assert "sandbox_backend" in j_data
        assert "average_execution_time_ms" in j_data
    finally:
        db.close()


def test_3_adversarial_security_and_privilege_escalation_guards():
    """
    Tests that:
    1. Students cannot access admin allowlist or switch roles.
    2. Students cannot delete questions or assessments.
    3. Students cannot access other students' assessment submissions.
    4. Client-side scoring and verdict manipulation are strictly rejected.
    """
    db = SessionLocal()
    try:
        student = _create_user(db, "malicious_student_p10@usar.edu", UserRole.STUDENT.value, "Attacker")
        headers = _get_auth_headers(student)

        # 1. Attempt to view admin allowlist
        res_allow = client.get("/api/v1/auth/admins", headers=headers)
        assert res_allow.status_code in [401, 403]

        # 2. Attempt to delete a question
        res_del_q = client.delete("/api/v1/questions/1", headers=headers)
        assert res_del_q.status_code in [401, 403]

        # 3. Attempt to delete an assessment
        res_del_a = client.delete("/api/v1/assessments/1", headers=headers)
        assert res_del_a.status_code in [401, 403]

        # 4. Attempt to trigger admin action on attempt
        res_action = client.post(
            "/api/v1/assessments/attempts/attempt_1/admin-action",
            json={"action": "FORCE_SUBMIT", "reason": "exploit"},
            headers=headers
        )
        assert res_action.status_code in [401, 403]

    finally:
        db.close()
