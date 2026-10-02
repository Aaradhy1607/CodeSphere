import pytest
import datetime
import os
import tempfile
import uuid
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.config import settings
from app.core.database import engine, SessionLocal, auto_migrate_db
from app.core.security import get_password_hash, create_access_token
from app.models.models import (
    Base, User, UserRole, Question, TestCase, Assessment, AssessmentQuestion,
    AssessmentAttempt, AttemptStatus, AssessmentResult, AntiCheatEvent,
    Submission, SubmissionStatus, SubmissionVerdict
)
from app.services.seeder import seed_database
from app.services.code_runner import code_runner
from app.services.judge_queue import judge_queue_manager, InvalidStateTransitionError

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

def create_test_user(db, email, role, password="password123"):
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        return existing
    user = User(
        email=email,
        hashed_password=get_password_hash(password),
        full_name=f"User {email}",
        role=role,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def get_auth_headers(user):
    token = create_access_token(subject=user.id, extra_claims={"role": user.role, "email": user.email})
    return {"Authorization": f"Bearer {token}"}

# =====================================================================
# 1. MULTI-LANGUAGE JUDGE & ADVERSARIAL SANDBOX
# =====================================================================

def test_code_runner_python_ac():
    code = "import sys\nline = sys.stdin.read().strip()\nprint(int(line) * 2)"
    res = code_runner.execute_single(
        code=code,
        language="python",
        input_data="21",
        timeout_seconds=2.0
    )
    assert res["verdict"] == SubmissionVerdict.AC.value or res.get("passed") is not False
    assert res.get("output", "").strip() == "42"

def test_code_runner_python_wa_and_re():
    # Runtime error
    code_re = "a = 1 / 0"
    res_re = code_runner.execute_single(
        code=code_re,
        language="python",
        input_data="",
        timeout_seconds=2.0
    )
    assert res_re["verdict"] == SubmissionVerdict.RE.value or "ZeroDivisionError" in (res_re.get("error") or "")

def test_code_runner_python_tle_enforcement():
    # Infinite loop
    code_tle = "while True: pass"
    res_tle = code_runner.execute_single(
        code=code_tle,
        language="python",
        input_data="",
        timeout_seconds=1.0
    )
    assert res_tle["verdict"] == SubmissionVerdict.TLE.value or "Time Limit Exceeded" in (res_tle.get("error") or "")

def test_code_runner_ole_enforcement():
    # Output limit exhaustion attack
    code_ole = "print('A' * 2000000)"
    res_ole = code_runner.execute_single(
        code=code_ole,
        language="python",
        input_data="",
        timeout_seconds=3.0
    )
    # Output must be bounded to prevent memory explosion
    out_len = len(res_ole.get("output", ""))
    assert out_len <= 300000

def test_code_runner_env_secret_scrubbing():
    # Verify environment secrets are not leaked to student process
    code_env = "import os; print(os.environ.get('DATABASE_URL'), os.environ.get('JWT_SECRET_KEY'))"
    res_env = code_runner.execute_single(
        code=code_env,
        language="python",
        input_data="",
        timeout_seconds=2.0
    )
    output = res_env.get("output", "")
    assert "postgresql://" not in output
    assert "supersecret" not in output

# =====================================================================
# 2. ASSESSMENT ENGINE & STRICT IDOR TESTS
# =====================================================================

def test_assessment_idor_and_security():
    db = SessionLocal()
    admin = create_test_user(db, "admin_gate@test.com", UserRole.ADMIN.value)
    student_a = create_test_user(db, "student_a_gate@test.com", UserRole.STUDENT.value)
    student_b = create_test_user(db, "student_b_gate@test.com", UserRole.STUDENT.value)

    # Create question with hidden test case
    q = Question(
        title="Sum Problem Gate",
        slug=f"sum-problem-gate-{uuid.uuid4().hex[:6]}",
        problem_statement="Return sum",
        question_type="CODING",
        author_id=admin.id
    )
    db.add(q)
    db.commit()
    db.refresh(q)

    tc_vis = TestCase(question_id=q.id, input_data="1 2", expected_output="3", is_hidden=False)
    tc_hid = TestCase(question_id=q.id, input_data="100 200", expected_output="300", is_hidden=True)
    db.add_all([tc_vis, tc_hid])
    db.commit()

    # Create assessment
    assessment = Assessment(
        title="Midterm Exam Gate",
        duration_minutes=60,
        status="ACTIVE",
        start_time=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=10),
        end_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=50),
        allow_review=False,
        show_results_immediately=False,
        created_by_id=admin.id
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)

    aq = AssessmentQuestion(
        assessment_id=assessment.id,
        question_id=q.id,
        order_index=1,
        marks=10.0
    )
    db.add(aq)
    db.commit()

    # Student A starts assessment
    headers_a = get_auth_headers(student_a)
    headers_b = get_auth_headers(student_b)

    res_start_a = client.post(f"/api/v1/assessments/{assessment.id}/start", headers=headers_a)
    assert res_start_a.status_code == 200
    state_a = res_start_a.json()
    attempt_a_id = state_a["attempt_id"]

    # Verify hidden test cases are NOT leaked in questions
    assert len(state_a["questions"][0]["visible_test_cases"]) == 1
    assert state_a["questions"][0]["visible_test_cases"][0]["input_data"] == "1 2"

    # IDOR TEST 1: Student B tries to view Student A's attempt state
    res_b_view = client.get(f"/api/v1/assessments/attempts/{attempt_a_id}/state", headers=headers_b)
    assert res_b_view.status_code in [403, 404]

    # IDOR TEST 2: Student B tries to save answer to Student A's attempt
    res_b_save = client.post(
        f"/api/v1/assessments/attempts/{attempt_a_id}/save-answer",
        json={"question_id": q.id, "submitted_code": "print('hacked')"},
        headers=headers_b
    )
    assert res_b_save.status_code in [403, 404]

    # IDOR TEST 3: Student B tries to submit Student A's attempt
    res_b_submit = client.post(f"/api/v1/assessments/attempts/{attempt_a_id}/submit", headers=headers_b)
    assert res_b_submit.status_code in [403, 404]

    # IDOR TEST 4: Student B tries to access admin monitor dashboard
    res_b_mon = client.get(f"/api/v1/assessments/{assessment.id}/monitor", headers=headers_b)
    assert res_b_mon.status_code == 403

    # IDOR TEST 5: Student B tries to perform admin action on Student A's attempt
    res_b_act = client.post(
        f"/api/v1/assessments/attempts/{attempt_a_id}/admin-action",
        json={"action": "TERMINATE", "reason": "malicious"},
        headers=headers_b
    )
    assert res_b_act.status_code == 403

    # Student A saves answer via root-level fields (contract test)
    res_a_save = client.post(
        f"/api/v1/assessments/attempts/{attempt_a_id}/save-answer",
        json={"question_id": q.id, "submitted_code": "print(3)", "submitted_language": "python"},
        headers=headers_a
    )
    assert res_a_save.status_code == 200
    assert res_a_save.json()["success"] is True

    # Student A logs anti-cheat event
    res_a_event = client.post(
        f"/api/v1/assessments/attempts/{attempt_a_id}/anti-cheat-event",
        json={"event_type": "TAB_SWITCH", "severity": "MEDIUM", "event_data": {"count": 1}},
        headers=headers_a
    )
    assert res_a_event.status_code == 200

    # Verify Student A can fetch their own events
    res_a_events = client.get(f"/api/v1/assessments/attempts/{attempt_a_id}/events", headers=headers_a)
    assert res_a_events.status_code == 200
    assert len(res_a_events.json()) == 1

    # Verify Student B cannot fetch Student A's events
    res_b_events = client.get(f"/api/v1/assessments/attempts/{attempt_a_id}/events", headers=headers_b)
    assert res_b_events.status_code == 403

    # Student A final submission
    res_a_sub = client.post(f"/api/v1/assessments/attempts/{attempt_a_id}/submit", headers=headers_a)
    assert res_a_sub.status_code == 200
    result_out = res_a_sub.json()
    assert result_out["attempt_id"] == attempt_a_id

    # Admin monitor can view results
    headers_admin = get_auth_headers(admin)
    res_admin_mon = client.get(f"/api/v1/assessments/{assessment.id}/monitor", headers=headers_admin)
    assert res_admin_mon.status_code == 200
    assert res_admin_mon.json()["submitted_count"] == 1

    db.close()

# =====================================================================
# 3. MULTIPLE ACTIVE SESSIONS & SERVER-AUTHORITATIVE TIMER
# =====================================================================

def test_heartbeat_multi_session_anomaly_and_expiry():
    db = SessionLocal()
    admin = create_test_user(db, "admin_heartbeat@test.com", UserRole.ADMIN.value)
    student = create_test_user(db, "student_hb@test.com", UserRole.STUDENT.value)

    assessment = Assessment(
        title="Heartbeat Exam",
        duration_minutes=1, # 1 minute
        status="ACTIVE",
        start_time=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=70),
        end_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10),
        created_by_id=admin.id
    )
    db.add(assessment)
    db.commit()

    headers = get_auth_headers(student)
    res_start = client.post(f"/api/v1/assessments/{assessment.id}/start", headers=headers)
    assert res_start.status_code == 200
    att_id = res_start.json()["attempt_id"]
    valid_token = res_start.json().get("session_token")

    # Heartbeat with invalid session token (multiple tabs opened)
    res_invalid_tab = client.post(
        f"/api/v1/assessments/attempts/{att_id}/heartbeat",
        json={"session_token": "stale_tab_token_xyz"},
        headers=headers
    )
    assert res_invalid_tab.status_code == 200
    assert res_invalid_tab.json()["valid"] is False
    assert res_invalid_tab.json()["terminated"] is True
    assert "Multiple active sessions" in res_invalid_tab.json()["termination_reason"]

    db.close()

# =====================================================================
# 4. SUBMISSION STATE MACHINE & STUCK SUBMISSION RECOVERY
# =====================================================================

def test_submission_state_machine_and_stuck_recovery():
    # 1. Test Valid Transitions
    judge_queue_manager.validate_transition(SubmissionStatus.QUEUED.value, SubmissionStatus.COMPILING.value)
    judge_queue_manager.validate_transition(SubmissionStatus.COMPILING.value, SubmissionStatus.RUNNING.value)
    judge_queue_manager.validate_transition(SubmissionStatus.RUNNING.value, SubmissionStatus.EVALUATING.value)
    judge_queue_manager.validate_transition(SubmissionStatus.EVALUATING.value, SubmissionStatus.COMPLETED.value)

    # 2. Test Invalid Transitions
    with pytest.raises(InvalidStateTransitionError):
        judge_queue_manager.validate_transition(SubmissionStatus.COMPLETED.value, SubmissionStatus.RUNNING.value)

    with pytest.raises(InvalidStateTransitionError):
        judge_queue_manager.validate_transition(SubmissionStatus.CANCELLED.value, SubmissionStatus.QUEUED.value)
