import pytest
import datetime
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import Base, engine, SessionLocal, auto_migrate_db
from app.core.security import create_access_token, get_password_hash
from app.models.models import (
    User, UserRole, AccountStatus, Question, TestCase, QuestionType,
    SubmissionVerdict, SubmissionStatus, Event, EventStatus, Submission,
    StudentProfile, Permission
)

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    auto_migrate_db()
    yield

@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def create_test_student(db: Session, email_prefix: str = "student") -> tuple[User, str]:
    uid = str(uuid.uuid4())[:8]
    email = f"{email_prefix}_{uid}@college.edu"
    user = User(
        email=email,
        hashed_password=get_password_hash("Student@123"),
        full_name=f"Student {uid}",
        role=UserRole.STUDENT.value,
        status=AccountStatus.ACTIVE.value,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    profile = StudentProfile(
        user_id=user.id,
        enrollment_no=f"ENR_{uid}",
        branch="AIML",
        academic_year=3
    )
    db.add(profile)
    db.commit()

    token = create_access_token(subject=user.id, extra_claims={"role": user.role, "email": user.email})
    return user, token


def create_test_question(db: Session, title: str = "Two Sum Problem") -> Question:
    q = Question(
        title=title,
        slug=f"{title.lower().replace(' ', '-')}-{str(uuid.uuid4())[:6]}",
        problem_statement="Given two numbers A and B, print their sum.",
        input_format="Two space-separated integers A and B.",
        output_format="A single integer representing A + B.",
        constraints="1 <= A, B <= 10^9",
        question_type=QuestionType.CODING.value,
        difficulty_score=2,
        time_limit_seconds=2.0,
        memory_limit_mb=256,
        status="PUBLISHED",
        is_ai_generated=False
    )
    db.add(q)
    db.commit()
    db.refresh(q)

    # 1 visible test case
    tc_vis = TestCase(
        question_id=q.id,
        input_data="3 4\n",
        expected_output="7",
        is_hidden=False,
        points=10
    )
    # 1 hidden test case
    tc_hid = TestCase(
        question_id=q.id,
        input_data="100 200\n",
        expected_output="300",
        is_hidden=True,
        points=90
    )
    db.add_all([tc_vis, tc_hid])
    db.commit()
    return q


def create_test_event(db: Session, question: Question) -> Event:
    now = datetime.datetime.now()
    event = Event(
        title=f"CP Contest {str(uuid.uuid4())[:6]}",
        target_branch="ALL",
        target_year=0,
        start_time=now - datetime.timedelta(hours=1),
        end_time=now + datetime.timedelta(hours=2),
        duration_minutes=120,
        status=EventStatus.ACTIVE.value,
        is_leaderboard_visible=True,
        allow_branch_questions=False,
        are_solutions_released=False,
        are_results_released=False
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


# =====================================================================
# 1. RUN CODE UX: VISIBLE CASES & CUSTOM INPUT
# =====================================================================

def test_run_code_visible_test_cases_only(db_session):
    student, token = create_test_student(db_session, "runner_stu")
    q = create_test_question(db_session, "Addition Solver")

    correct_py = "import sys\ndata = sys.stdin.read().split()\nif data: print(int(data[0]) + int(data[1]))\n"

    # Run visible test cases
    res = client.post(
        "/api/v1/execute/run",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "question_id": q.id,
            "code": correct_py,
            "language": "python"
        }
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["verdict"] == "Accepted"
    assert data["passed"] is True
    assert data["execution_time_ms"] >= 0.0
    # Visible sample results must have exactly 1 visible case
    assert len(data["sample_results"]) == 1
    assert data["sample_results"][0]["is_hidden"] is False
    assert data["sample_results"][0]["output"].strip() == "7"


def test_run_code_with_custom_input(db_session):
    student, token = create_test_student(db_session, "custom_in_stu")
    q = create_test_question(db_session, "Custom In Question")

    correct_py = "import sys\ndata = sys.stdin.read().split()\nif data: print(int(data[0]) * int(data[1]))\n"

    res = client.post(
        "/api/v1/execute/run",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "question_id": q.id,
            "code": correct_py,
            "language": "python",
            "custom_input": "9 8\n"
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["output"].strip() == "72"


# =====================================================================
# 2. ASYNC SUBMIT & STATE MACHINE STATUS POLLING
# =====================================================================

def test_async_submit_and_status_polling_shielded(db_session):
    student, token = create_test_student(db_session, "async_stu")
    q = create_test_question(db_session, "Async Judge Question")
    event = create_test_event(db_session, q)

    correct_py = "import sys\ndata = sys.stdin.read().split()\nif data: print(int(data[0]) + int(data[1]))\n"

    # Submit Async
    submit_res = client.post(
        "/api/v1/execute/submit-async",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "event_id": event.id,
            "question_id": q.id,
            "code": correct_py,
            "language": "python"
        }
    )
    assert submit_res.status_code == 200, submit_res.text
    sub_data = submit_res.json()
    submission_id = sub_data["submission_id"]
    assert submission_id > 0
    assert sub_data["status"] in ["QUEUED", "COMPILING", "RUNNING", "EVALUATING", "COMPLETED"]

    # Poll status endpoint
    status_res = client.get(
        f"/api/v1/execute/status/{submission_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert status_res.status_code == 200
    st_data = status_res.json()
    assert st_data["submission_id"] == submission_id

    # Verify Hidden Test Shielding: hidden test inputs/expected outputs must NEVER leak
    for tc in st_data.get("test_case_results", []):
        if tc["is_hidden"]:
            assert tc["expected"] == "[HIDDEN]"
            assert tc["output"] == ""


# =====================================================================
# 3. AUTHORIZATION ISOLATION: STUDENT CANNOT VIEW OTHERS' SUBMISSIONS
# =====================================================================

def test_submission_status_authorization_isolation(db_session):
    student_a, token_a = create_test_student(db_session, "stu_a")
    student_b, token_b = create_test_student(db_session, "stu_b")
    q = create_test_question(db_session, "Auth Iso Question")
    event = create_test_event(db_session, q)

    # Student A submits
    sub_a = client.post(
        "/api/v1/execute/submit-async",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "event_id": event.id,
            "question_id": q.id,
            "code": "print('A')",
            "language": "python"
        }
    ).json()

    # Student B attempts to query Student A's submission status
    forbidden_res = client.get(
        f"/api/v1/execute/status/{sub_a['submission_id']}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert forbidden_res.status_code == 403
    assert "Access denied" in forbidden_res.json()["detail"]


# =====================================================================
# 4. STUDENT SUBMISSION HISTORY & HEURISTICS
# =====================================================================

def test_student_submission_history_endpoint(db_session):
    student, token = create_test_student(db_session, "hist_stu")
    q = create_test_question(db_session, "History Question")
    event = create_test_event(db_session, q)

    # Submit solution via sync submit
    sync_res = client.post(
        "/api/v1/execute/submit",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "event_id": event.id,
            "question_id": q.id,
            "code": "import sys\ndata = sys.stdin.read().split()\nif data: print(int(data[0]) + int(data[1]))\n",
            "language": "python"
        }
    )
    assert sync_res.status_code == 200

    # Query history
    hist_res = client.get(
        f"/api/v1/execute/my-submission-history/{q.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert hist_res.status_code == 200
    h_data = hist_res.json()
    assert h_data["question_id"] == q.id
    assert h_data["total_submissions"] >= 1
    assert len(h_data["history"]) >= 1
    assert h_data["history"][0]["language"] == "python"
    assert h_data["history"][0]["verdict"] == "Accepted"
