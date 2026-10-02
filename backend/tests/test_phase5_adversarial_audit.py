import datetime
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import Base, engine, SessionLocal
from app.models.models import (
    User, UserRole, AccountStatus, Question, QuestionType, TestCase, Assessment,
    AssessmentQuestion, AssessmentAttempt, AttemptAnswer, AntiCheatEvent,
    AssessmentResult, AssessmentStatus, AttemptStatus, AntiCheatEventType,
    AntiCheatSeverity, StudentProfile
)
from app.core.security import get_password_hash, create_access_token
from app.services.code_runner import code_runner
from app.services.evaluation_engine import evaluation_engine
from app.services.assessment_service import assessment_service

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield

@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def admin_user(db: Session):
    email = f"adv_admin_{uuid.uuid4().hex[:6]}@codesphere.edu"
    user = User(
        email=email,
        hashed_password=get_password_hash("AdminPass123!"),
        full_name="Adversarial Admin",
        role=UserRole.ADMIN.value,
        status=AccountStatus.ACTIVE.value,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@pytest.fixture
def student_alice(db: Session):
    email = f"alice_{uuid.uuid4().hex[:6]}@codesphere.edu"
    user = User(
        email=email,
        hashed_password=get_password_hash("AlicePass123!"),
        full_name="Alice Candidate",
        role=UserRole.STUDENT.value,
        status=AccountStatus.ACTIVE.value,
        is_active=True
    )
    db.add(user)
    db.flush()
    profile = StudentProfile(
        user_id=user.id,
        enrollment_no=f"ENR_A_{uuid.uuid4().hex[:6].upper()}",
        branch="AIML",
        academic_year=3,
        phone="9876543201",
        is_approved=True
    )
    db.add(profile)
    db.commit()
    db.refresh(user)
    return user

@pytest.fixture
def student_bob(db: Session):
    email = f"bob_{uuid.uuid4().hex[:6]}@codesphere.edu"
    user = User(
        email=email,
        hashed_password=get_password_hash("BobPass123!"),
        full_name="Bob Candidate",
        role=UserRole.STUDENT.value,
        status=AccountStatus.ACTIVE.value,
        is_active=True
    )
    db.add(user)
    db.flush()
    profile = StudentProfile(
        user_id=user.id,
        enrollment_no=f"ENR_B_{uuid.uuid4().hex[:6].upper()}",
        branch="AIDS",
        academic_year=3,
        phone="9876543202",
        is_approved=True
    )
    db.add(profile)
    db.commit()
    db.refresh(user)
    return user

@pytest.fixture
def sample_questions(db: Session, admin_user: User):
    # 1. MCQ Single
    q1 = Question(
        title="Python Data Types",
        slug=f"py-immut-adv-{uuid.uuid4().hex[:6]}",
        problem_statement="Which data type is immutable in Python?",
        question_type=QuestionType.MCQ.value,
        options=[
            {"id": "A", "text": "List"},
            {"id": "B", "text": "Tuple"},
            {"id": "C", "text": "Dictionary"},
            {"id": "D", "text": "Set"}
        ],
        correct_answer="B",
        explanation="Tuples cannot be modified after creation.",
        author_id=admin_user.id,
        marks=10.0,
        status="PUBLISHED"
    )

    # 2. Multi-Select Question
    q2 = Question(
        title="Primitive Types in Java",
        slug=f"java-prim-adv-{uuid.uuid4().hex[:6]}",
        problem_statement="Select all primitive types in Java.",
        question_type=QuestionType.MCQ.value,
        options=[
            {"id": "A", "text": "int"},
            {"id": "B", "text": "boolean"},
            {"id": "C", "text": "String"},
            {"id": "D", "text": "float"}
        ],
        correct_answer='["A", "B", "D"]',
        explanation="String is an object, not a primitive in Java.",
        author_id=admin_user.id,
        marks=10.0,
        status="PUBLISHED"
    )

    # 3. Coding Question with Hidden and Visible test cases
    q3 = Question(
        title="Double Integer",
        slug=f"double-int-adv-{uuid.uuid4().hex[:6]}",
        problem_statement="Given integer X, print 2*X.",
        question_type=QuestionType.CODING.value,
        author_id=admin_user.id,
        marks=20.0,
        status="PUBLISHED"
    )
    db.add_all([q1, q2, q3])
    db.commit()
    db.refresh(q1)
    db.refresh(q2)
    db.refresh(q3)

    tc1 = TestCase(question_id=q3.id, input_data="5\n", expected_output="10\n", is_hidden=False, points=5.0)
    tc2 = TestCase(question_id=q3.id, input_data="100\n", expected_output="200\n", is_hidden=True, points=15.0)
    db.add_all([tc1, tc2])
    db.commit()

    return [q1, q2, q3]

# =====================================================================
# 1. SECURITY & RBAC ADVERSARIAL TESTS (PART A)
# =====================================================================

def test_student_forbidden_admin_endpoints(student_alice: User, admin_user: User, sample_questions: list):
    student_token = create_access_token(str(student_alice.id), extra_claims={"role": student_alice.role})
    admin_token = create_access_token(str(admin_user.id), extra_claims={"role": admin_user.role})

    now = datetime.datetime.now(datetime.timezone.utc)
    # Student cannot create assessment
    res = client.post("/api/v1/assessments/", json={
        "title": "Hacker Exam",
        "duration_minutes": 30,
        "start_time": now.isoformat(),
        "end_time": (now + datetime.timedelta(hours=2)).isoformat(),
        "questions": [{"question_id": sample_questions[0].id, "marks": 10.0}]
    }, headers={"Authorization": f"Bearer {student_token}"})
    assert res.status_code == 403

    # Admin creates valid assessment
    res_a = client.post("/api/v1/assessments/", json={
        "title": "Staff Assessment 101",
        "duration_minutes": 30,
        "start_time": now.isoformat(),
        "end_time": (now + datetime.timedelta(hours=2)).isoformat(),
        "questions": [{"question_id": sample_questions[0].id, "marks": 10.0}]
    }, headers={"Authorization": f"Bearer {admin_token}"})
    assert res_a.status_code == 200, res_a.text
    a_id = res_a.json()["id"]

    # Student cannot publish
    res_pub = client.post(f"/api/v1/assessments/{a_id}/publish", headers={"Authorization": f"Bearer {student_token}"})
    assert res_pub.status_code == 403

    # Student cannot edit
    res_edit = client.put(f"/api/v1/assessments/{a_id}", json={"title": "Hacked Title"}, headers={"Authorization": f"Bearer {student_token}"})
    assert res_edit.status_code == 403

    # Student cannot delete
    res_del = client.delete(f"/api/v1/assessments/{a_id}", headers={"Authorization": f"Bearer {student_token}"})
    assert res_del.status_code == 403

    # Student cannot access monitor dashboard
    res_mon = client.get(f"/api/v1/assessments/{a_id}/monitor", headers={"Authorization": f"Bearer {student_token}"})
    assert res_mon.status_code == 403

    # Student cannot access cohort results
    res_res = client.get(f"/api/v1/assessments/{a_id}/results", headers={"Authorization": f"Bearer {student_token}"})
    assert res_res.status_code == 403

def test_cross_student_idor_prevention(student_alice: User, student_bob: User, admin_user: User, sample_questions: list):
    admin_token = create_access_token(str(admin_user.id), extra_claims={"role": admin_user.role})
    alice_token = create_access_token(str(student_alice.id), extra_claims={"role": student_alice.role})
    bob_token = create_access_token(str(student_bob.id), extra_claims={"role": student_bob.role})

    now = datetime.datetime.now(datetime.timezone.utc)
    res_a = client.post("/api/v1/assessments/", json={
        "title": "Cross-Student Test",
        "duration_minutes": 30,
        "start_time": (now - datetime.timedelta(minutes=1)).isoformat(),
        "end_time": (now + datetime.timedelta(hours=2)).isoformat(),
        "questions": [{"question_id": sample_questions[0].id, "marks": 10.0}]
    }, headers={"Authorization": f"Bearer {admin_token}"})
    a_id = res_a.json()["id"]
    client.post(f"/api/v1/assessments/{a_id}/publish", headers={"Authorization": f"Bearer {admin_token}"})

    # Alice starts attempt
    res_alice_start = client.post(f"/api/v1/assessments/{a_id}/start", json={}, headers={"Authorization": f"Bearer {alice_token}"})
    alice_att_id = res_alice_start.json()["attempt_id"]

    # Bob attempts to read Alice's state
    res_bob_peek = client.get(f"/api/v1/assessments/attempts/{alice_att_id}/state", headers={"Authorization": f"Bearer {bob_token}"})
    assert res_bob_peek.status_code == 403

    # Bob attempts to save an answer on Alice's attempt
    res_bob_save = client.post(f"/api/v1/assessments/attempts/{alice_att_id}/answers", json={
        "question_id": sample_questions[0].id,
        "answer_data": {"selected_options": ["A"]}
    }, headers={"Authorization": f"Bearer {bob_token}"})
    assert res_bob_save.status_code == 403

    # Bob attempts to submit Alice's attempt
    res_bob_submit = client.post(f"/api/v1/assessments/attempts/{alice_att_id}/submit", json={}, headers={"Authorization": f"Bearer {bob_token}"})
    assert res_bob_submit.status_code == 403

    # Bob attempts to trigger proctor override on Alice's attempt
    res_bob_action = client.post(f"/api/v1/assessments/attempts/{alice_att_id}/action", json={
        "action": "EXTEND_TIME",
        "reason": "Unauthorized extension",
        "extra_minutes": 30
    }, headers={"Authorization": f"Bearer {bob_token}"})
    assert res_bob_action.status_code == 403

# =====================================================================
# 2. ZERO DATA LEAKAGE AUDIT (PART B)
# =====================================================================

def test_zero_data_leakage_in_student_payloads(student_alice: User, admin_user: User, sample_questions: list):
    admin_token = create_access_token(str(admin_user.id), extra_claims={"role": admin_user.role})
    alice_token = create_access_token(str(student_alice.id), extra_claims={"role": student_alice.role})

    now = datetime.datetime.now(datetime.timezone.utc)
    res_a = client.post("/api/v1/assessments/", json={
        "title": "Strict Leakage Check Exam",
        "duration_minutes": 45,
        "allow_review": False,
        "show_results_immediately": False,
        "start_time": (now - datetime.timedelta(minutes=1)).isoformat(),
        "end_time": (now + datetime.timedelta(hours=2)).isoformat(),
        "questions": [
            {"question_id": sample_questions[0].id, "marks": 10.0},
            {"question_id": sample_questions[2].id, "marks": 20.0}
        ]
    }, headers={"Authorization": f"Bearer {admin_token}"})
    a_id = res_a.json()["id"]
    client.post(f"/api/v1/assessments/{a_id}/publish", headers={"Authorization": f"Bearer {admin_token}"})

    # 1. Inspect GET /assessments/{id}
    res_get = client.get(f"/api/v1/assessments/{a_id}", headers={"Authorization": f"Bearer {alice_token}"})
    data_get = res_get.json()
    for q in data_get["questions"]:
        assert "correct_answer" not in q
        assert "explanation" not in q
        assert "reference_solutions" not in q
        # Ensure hidden test case is not in visible_test_cases
        if "visible_test_cases" in q:
            for tc in q["visible_test_cases"]:
                assert tc.get("is_hidden") is not True

    # 2. Inspect POST /assessments/{id}/start
    res_start = client.post(f"/api/v1/assessments/{a_id}/start", json={}, headers={"Authorization": f"Bearer {alice_token}"})
    start_data = res_start.json()
    for q in start_data["questions"]:
        assert "correct_answer" not in q
        assert "explanation" not in q
        assert "reference_solutions" not in q
        if "visible_test_cases" in q:
            for tc in q["visible_test_cases"]:
                assert tc.get("is_hidden") is not True

    # 3. Inspect Submit response when review is disabled
    att_id = start_data["attempt_id"]
    res_submit = client.post(f"/api/v1/assessments/attempts/{att_id}/submit", json={}, headers={"Authorization": f"Bearer {alice_token}"})
    submit_data = res_submit.json()
    for q in submit_data.get("question_breakdown", []):
        assert "correct_answer" not in q
        assert "explanation" not in q

# =====================================================================
# 3. CODE RUNNER ENVIRONMENT ISOLATION & HOST PROTECTION (PART I)
# =====================================================================

def test_code_runner_environment_isolation():
    code = """
import os
print("SECRET_KEY=" + str(os.environ.get("SECRET_KEY")))
print("DATABASE_URL=" + str(os.environ.get("DATABASE_URL")))
"""
    res = code_runner.execute_single(code, "python", "")
    assert res["verdict"].value in ["Accepted", "Wrong Answer"]
    assert "SECRET_KEY=None" in res["output"]
    assert "DATABASE_URL=None" in res["output"]

def test_code_runner_infinite_loop_timeout():
    code = """
import time
time.sleep(10)
"""
    old_to = code_runner.timeout_seconds
    try:
        code_runner.timeout_seconds = 2.0
        res = code_runner.execute_single(code, "python", "")
        assert res["verdict"].value == "Time Limit Exceeded"
    finally:
        code_runner.timeout_seconds = old_to

# =====================================================================
# 4. MULTI-SELECT SCORING MODES & INTEGRITY SCORE CLAMPING (PART H & G)
# =====================================================================

def test_multiselect_scoring_correct_and_partial(sample_questions: list):
    q_msq = sample_questions[1]
    # 1. Full Match: 3/3 -> 10.0 Marks
    score, verdict, details = evaluation_engine.evaluate_multiselect(
        question=q_msq,
        answer_data={"selected_options": ["A", "B", "D"]},
        marks=10.0,
        negative_marks=2.0
    )
    assert score == 10.0
    assert verdict == "CORRECT"

    # 2. Partial Match (2 of 3 correct): 2/3 * 10 = 6.67
    score, verdict, details = evaluation_engine.evaluate_multiselect(
        question=q_msq,
        answer_data={"selected_options": ["A", "B"]},
        marks=10.0,
        negative_marks=2.0
    )
    assert 6.6 <= score <= 6.7
    assert verdict == "PARTIAL"

    # 3. Wrong Option Added (A, B + C where C is wrong): (2 - 1) / 3 * 10 = 3.33
    score, verdict, details = evaluation_engine.evaluate_multiselect(
        question=q_msq,
        answer_data={"selected_options": ["A", "B", "C"]},
        marks=10.0,
        negative_marks=2.0
    )
    assert 3.3 <= score <= 3.4

    # 4. Only Wrong Option Added: negative deduction
    score, verdict, details = evaluation_engine.evaluate_multiselect(
        question=q_msq,
        answer_data={"selected_options": ["C"]},
        marks=10.0,
        negative_marks=2.0
    )
    assert score == -2.0
    assert verdict == "INCORRECT"

def test_anti_cheat_score_clamping_and_termination(student_alice: User, admin_user: User, sample_questions: list):
    admin_token = create_access_token(str(admin_user.id), extra_claims={"role": admin_user.role})
    alice_token = create_access_token(str(student_alice.id), extra_claims={"role": student_alice.role})

    now = datetime.datetime.now(datetime.timezone.utc)
    res_a = client.post("/api/v1/assessments/", json={
        "title": "Anti-Cheat Clamping Test",
        "duration_minutes": 20,
        "anti_cheat_policy": {
            "max_tab_switches": 3,
            "action": "TERMINATE"
        },
        "start_time": (now - datetime.timedelta(minutes=1)).isoformat(),
        "end_time": (now + datetime.timedelta(hours=1)).isoformat(),
        "questions": [{"question_id": sample_questions[0].id, "marks": 10.0}]
    }, headers={"Authorization": f"Bearer {admin_token}"})
    assert res_a.status_code == 200, res_a.text
    a_id = res_a.json()["id"]
    client.post(f"/api/v1/assessments/{a_id}/publish", headers={"Authorization": f"Bearer {admin_token}"})

    res_start = client.post(f"/api/v1/assessments/{a_id}/start", json={}, headers={"Authorization": f"Bearer {alice_token}"})
    att_id = res_start.json()["attempt_id"]

    # Send 10 violation events — verify score does not drop below 0
    for i in range(10):
        client.post(f"/api/v1/assessments/attempts/{att_id}/events", json={
            "event_type": "TAB_BLUR",
            "severity": "HIGH",
            "metadata_json": {"switch_index": i}
        }, headers={"Authorization": f"Bearer {alice_token}"})

    res_state = client.get(f"/api/v1/assessments/attempts/{att_id}/state", headers={"Authorization": f"Bearer {alice_token}"})
    state_data = res_state.json()
    assert state_data["integrity_score"] >= 0
    assert state_data["status"] == AttemptStatus.TERMINATED.value

    # Terminated candidate cannot submit answers
    res_save_after = client.post(f"/api/v1/assessments/attempts/{att_id}/answers", json={
        "question_id": sample_questions[0].id,
        "answer_data": {"selected_options": ["B"]}
    }, headers={"Authorization": f"Bearer {alice_token}"})
    assert res_save_after.status_code == 400
    assert "terminated" in res_save_after.json()["detail"].lower()
