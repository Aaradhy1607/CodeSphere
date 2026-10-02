import pytest
import datetime
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import Base, engine, SessionLocal
from app.core.security import create_access_token, get_password_hash
from app.models.models import (
    User, UserRole, AccountStatus, StudentProfile, Question, TestCase,
    Assessment, AssessmentQuestion, AssessmentAttempt, AttemptAnswer,
    AntiCheatEvent, AssessmentResult, AssessmentStatus, AttemptStatus,
    QuestionType, BloomsLevel, AntiCheatSeverity
)

client = TestClient(app)

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
    email = f"admin_phase5_{uuid.uuid4().hex[:6]}@usar.edu"
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            full_name="Assessment Admin",
            role=UserRole.ADMIN.value,
            status=AccountStatus.ACTIVE.value,
            hashed_password=get_password_hash("AdminPass123!"),
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

@pytest.fixture
def student_user(db: Session):
    email = f"student_phase5_{uuid.uuid4().hex[:6]}@usar.edu"
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            full_name="Student Candidate",
            role=UserRole.STUDENT.value,
            status=AccountStatus.ACTIVE.value,
            hashed_password=get_password_hash("StudentPass123!"),
            is_active=True
        )
        db.add(user)
        db.flush()

        profile = StudentProfile(
            user_id=user.id,
            enrollment_no=f"ENR{uuid.uuid4().hex[:6].upper()}",
            branch="AIML",
            academic_year=3,
            phone="9876543210",
            is_approved=True
        )
        db.add(profile)
        db.commit()
        db.refresh(user)
    return user

@pytest.fixture
def student_user_2(db: Session):
    email = f"student2_phase5_{uuid.uuid4().hex[:6]}@usar.edu"
    user = User(
        email=email,
        full_name="Student Two",
        role=UserRole.STUDENT.value,
        status=AccountStatus.ACTIVE.value,
        hashed_password=get_password_hash("Student2Pass123!"),
        is_active=True
    )
    db.add(user)
    db.flush()

    profile = StudentProfile(
        user_id=user.id,
        enrollment_no=f"ENR2_{uuid.uuid4().hex[:6].upper()}",
        branch="AIDS",
        academic_year=2,
        phone="9876543211",
        is_approved=True
    )
    db.add(profile)
    db.commit()
    db.refresh(user)
    return user

@pytest.fixture
def sample_questions(db: Session, admin_user: User):
    # 1. MCQ Question
    q_mcq = Question(
        title="Python Data Types MCQ",
        slug=f"mcq-py-types-{uuid.uuid4().hex[:6]}",
        problem_statement="What is the output of type([]) in Python?",
        question_type=QuestionType.MCQ.value,
        subject="Python",
        topic="Basics",
        marks=10,
        negative_marks=2.5,
        options=[
            {"id": "A", "text": "<class 'list'>", "is_correct": True},
            {"id": "B", "text": "<class 'dict'>", "is_correct": False},
            {"id": "C", "text": "<class 'set'>", "is_correct": False},
            {"id": "D", "text": "<class 'tuple'>", "is_correct": False},
        ],
        correct_answer="A",
        author_id=admin_user.id
    )
    db.add(q_mcq)

    # 2. Coding Question
    q_code = Question(
        title="Sum of Two Numbers Coding",
        slug=f"sum-two-numbers-{uuid.uuid4().hex[:6]}",
        problem_statement="Given two space-separated integers, print their sum.",
        input_format="Two space-separated integers a and b",
        output_format="A single integer representing the sum",
        constraints="-1000 <= a, b <= 1000",
        question_type=QuestionType.CODING.value,
        subject="Algorithms",
        topic="Basic Math",
        marks=20,
        author_id=admin_user.id
    )
    db.add(q_code)
    db.flush()

    # Test cases for coding question
    tc1 = TestCase(question_id=q_code.id, input_data="3 5\n", expected_output="8\n", is_hidden=False, points=10)
    tc2 = TestCase(question_id=q_code.id, input_data="10 -2\n", expected_output="8\n", is_hidden=True, points=10)
    db.add(tc1)
    db.add(tc2)

    # 3. Subjective Question
    q_subj = Question(
        title="System Architecture Subjective",
        slug=f"system-arch-{uuid.uuid4().hex[:6]}",
        problem_statement="Explain the difference between monolith and microservices architecture.",
        question_type=QuestionType.SUBJECTIVE.value,
        subject="System Design",
        topic="Architecture",
        marks=15,
        author_id=admin_user.id
    )
    db.add(q_subj)

    db.commit()
    return [q_mcq, q_code, q_subj]

# =====================================================================
# 1. ASSESSMENT CRUD & LIFECYCLE TESTS
# =====================================================================

def test_assessment_crud_and_lifecycle(admin_user: User, sample_questions: list):
    admin_token = create_access_token(str(admin_user.id), extra_claims={"role": admin_user.role})
    headers = {"Authorization": f"Bearer {admin_token}"}

    now = datetime.datetime.now(datetime.timezone.utc)
    start_t = now - datetime.timedelta(minutes=5)
    end_t = now + datetime.timedelta(hours=2)

    payload = {
        "title": "USAR Diagnostic Coding & Aptitude Test",
        "description": "Comprehensive placement evaluation round",
        "instructions": "No external aids allowed. Fullscreen required.",
        "duration_minutes": 90,
        "start_time": start_t.isoformat(),
        "end_time": end_t.isoformat(),
        "max_attempts": 1,
        "passing_score": 60.0,
        "total_marks": 45.0,
        "negative_marking": True,
        "negative_mark_rate": 0.25,
        "randomize_questions": True,
        "randomize_options": True,
        "allowed_languages": ["python", "cpp", "c", "java"],
        "candidate_assignment": {"type": "ALL", "targets": []},
        "anti_cheat_policy": {"max_tab_switches": 3, "action": "WARN", "require_fullscreen": True},
        "show_results_immediately": True,
        "allow_review": True,
        "questions": [
            {"question_id": sample_questions[0].id, "section_name": "MCQ", "order_index": 1, "marks": 10.0, "negative_marks": 2.5},
            {"question_id": sample_questions[1].id, "section_name": "Coding", "order_index": 2, "marks": 20.0, "negative_marks": 0.0},
            {"question_id": sample_questions[2].id, "section_name": "Subjective", "order_index": 3, "marks": 15.0, "negative_marks": 0.0},
        ]
    }

    # Create Assessment
    res = client.post("/api/v1/assessments/", json=payload, headers=headers)
    assert res.status_code == 200, res.text
    created = res.json()
    assert created["title"] == payload["title"]
    assert created["total_questions"] == 3
    assessment_id = created["id"]

    # Publish Assessment
    res_pub = client.post(f"/api/v1/assessments/{assessment_id}/publish", headers=headers)
    assert res_pub.status_code == 200
    assert "published" in res_pub.json()["message"].lower()

    # Get Assessment
    res_get = client.get(f"/api/v1/assessments/{assessment_id}", headers=headers)
    assert res_get.status_code == 200
    detail = res_get.json()
    assert len(detail["questions"]) == 3
    assert detail["status"] == AssessmentStatus.ACTIVE.value

    # Update Assessment
    res_up = client.put(f"/api/v1/assessments/{assessment_id}", json={"duration_minutes": 100}, headers=headers)
    assert res_up.status_code == 200

# =====================================================================
# 2. STUDENT EXAM ATTEMPT & ZERO-LEAKAGE VERIFICATION
# =====================================================================

def test_student_attempt_start_and_zero_leakage(student_user: User, admin_user: User, sample_questions: list):
    admin_token = create_access_token(str(admin_user.id), extra_claims={"role": admin_user.role})
    student_token = create_access_token(str(student_user.id), extra_claims={"role": student_user.role})

    now = datetime.datetime.now(datetime.timezone.utc)
    res_a = client.post("/api/v1/assessments/", json={
        "title": "Placement Aptitude Test",
        "duration_minutes": 60,
        "start_time": (now - datetime.timedelta(minutes=5)).isoformat(),
        "end_time": (now + datetime.timedelta(hours=2)).isoformat(),
        "randomize_questions": True,
        "randomize_options": True,
        "questions": [
            {"question_id": sample_questions[0].id, "marks": 10.0},
            {"question_id": sample_questions[1].id, "marks": 20.0},
        ]
    }, headers={"Authorization": f"Bearer {admin_token}"})
    a_id = res_a.json()["id"]
    client.post(f"/api/v1/assessments/{a_id}/publish", headers={"Authorization": f"Bearer {admin_token}"})

    # Student starts attempt
    res_start = client.post(f"/api/v1/assessments/{a_id}/start", json={}, headers={"Authorization": f"Bearer {student_token}"})
    assert res_start.status_code == 200, res_start.text
    state = res_start.json()
    assert state["status"] == AttemptStatus.IN_PROGRESS.value
    assert state["remaining_seconds"] > 0
    assert len(state["questions"]) == 2
    attempt_id = state["attempt_id"]

    # ZERO LEAKAGE AUDIT: Initial question payload must NOT contain correct answers or hidden test cases!
    for q in state["questions"]:
        assert "correct_answer" not in q or q.get("correct_answer") is None
        assert "reference_solutions" not in q or not q.get("reference_solutions")
        for tc in q.get("visible_test_cases", []):
            assert not tc.get("is_hidden", False)
        for opt in q.get("options", []):
            assert "is_correct" not in opt

    # Resume attempt check: refreshing returns identical state and valid remaining timer
    res_resume = client.get(f"/api/v1/assessments/attempts/{attempt_id}/state", headers={"Authorization": f"Bearer {student_token}"})
    assert res_resume.status_code == 200
    resumed = res_resume.json()
    assert resumed["attempt_id"] == attempt_id
    assert resumed["status"] == AttemptStatus.IN_PROGRESS.value

# =====================================================================
# 3. AUTOSAVE, HEARTBEAT & MULTI-SESSION PROTECTION
# =====================================================================

def test_autosave_heartbeat_and_multi_session(student_user: User, admin_user: User, sample_questions: list):
    admin_token = create_access_token(str(admin_user.id), extra_claims={"role": admin_user.role})
    student_token = create_access_token(str(student_user.id), extra_claims={"role": student_user.role})

    now = datetime.datetime.now(datetime.timezone.utc)
    res_a = client.post("/api/v1/assessments/", json={
        "title": "Autosave & Session Test",
        "duration_minutes": 30,
        "start_time": (now - datetime.timedelta(minutes=1)).isoformat(),
        "end_time": (now + datetime.timedelta(hours=1)).isoformat(),
        "questions": [
            {"question_id": sample_questions[0].id, "marks": 10.0},
        ]
    }, headers={"Authorization": f"Bearer {admin_token}"})
    a_id = res_a.json()["id"]
    client.post(f"/api/v1/assessments/{a_id}/publish", headers={"Authorization": f"Bearer {admin_token}"})

    res_start = client.post(f"/api/v1/assessments/{a_id}/start", json={}, headers={"Authorization": f"Bearer {student_token}"})
    attempt_id = res_start.json()["attempt_id"]
    session_token = res_start.json()["session_token"]

    # 1. Autosave answer
    res_save = client.post(f"/api/v1/assessments/attempts/{attempt_id}/answers", json={
        "question_id": sample_questions[0].id,
        "answer_data": {"selected_option": "A"},
        "is_flagged": True
    }, headers={"Authorization": f"Bearer {student_token}"})
    assert res_save.status_code == 200
    save_body = res_save.json()
    assert save_body["success"] is True
    assert save_body["is_flagged"] is True

    # Verify answer was persisted
    res_state = client.get(f"/api/v1/assessments/attempts/{attempt_id}/state", headers={"Authorization": f"Bearer {student_token}"})
    assert sample_questions[0].id in res_state.json()["answered_question_ids"]
    assert sample_questions[0].id in res_state.json()["flagged_question_ids"]

    # 2. Heartbeat valid
    res_hb = client.post(f"/api/v1/assessments/attempts/{attempt_id}/heartbeat", json={
        "session_token": session_token
    }, headers={"Authorization": f"Bearer {student_token}"})
    assert res_hb.status_code == 200
    assert res_hb.json()["valid"] is True

    # 3. Multi-session anomaly: candidate opens another tab with stale token
    res_hb_stale = client.post(f"/api/v1/assessments/attempts/{attempt_id}/heartbeat", json={
        "session_token": "stale_token_from_old_tab"
    }, headers={"Authorization": f"Bearer {student_token}"})
    assert res_hb_stale.status_code == 200
    assert res_hb_stale.json()["valid"] is False
    assert res_hb_stale.json()["terminated"] is True

# =====================================================================
# 4. ANTI-CHEATING EVENTS & INTEGRITY AUDIT TRAIL
# =====================================================================

def test_anti_cheating_event_logging_and_policy(student_user: User, admin_user: User, sample_questions: list):
    admin_token = create_access_token(str(admin_user.id), extra_claims={"role": admin_user.role})
    student_token = create_access_token(str(student_user.id), extra_claims={"role": student_user.role})

    now = datetime.datetime.now(datetime.timezone.utc)
    res_a = client.post("/api/v1/assessments/", json={
        "title": "Strict Proctoring Assessment",
        "duration_minutes": 45,
        "start_time": (now - datetime.timedelta(minutes=1)).isoformat(),
        "end_time": (now + datetime.timedelta(hours=1)).isoformat(),
        "anti_cheat_policy": {"max_tab_switches": 2, "action": "TERMINATE"},
        "questions": [{"question_id": sample_questions[0].id, "marks": 10.0}]
    }, headers={"Authorization": f"Bearer {admin_token}"})
    a_id = res_a.json()["id"]
    client.post(f"/api/v1/assessments/{a_id}/publish", headers={"Authorization": f"Bearer {admin_token}"})

    res_start = client.post(f"/api/v1/assessments/{a_id}/start", json={}, headers={"Authorization": f"Bearer {student_token}"})
    attempt_id = res_start.json()["attempt_id"]

    # Log tab switch event 1 (LOW severity)
    res_ev1 = client.post(f"/api/v1/assessments/attempts/{attempt_id}/events", json={
        "event_type": "TAB_BLUR",
        "severity": "LOW",
        "metadata_json": {"blur_duration_ms": 1200}
    }, headers={"Authorization": f"Bearer {student_token}"})
    assert res_ev1.status_code == 200
    assert res_ev1.json()["event_type"] == "TAB_BLUR"

    # Log copy/paste event (HIGH severity)
    res_ev2 = client.post(f"/api/v1/assessments/attempts/{attempt_id}/events", json={
        "event_type": "PASTE",
        "severity": "HIGH",
        "metadata_json": {"pasted_length": 50}
    }, headers={"Authorization": f"Bearer {student_token}"})
    assert res_ev2.status_code == 200

    # Check that integrity score decayed
    res_state = client.get(f"/api/v1/assessments/attempts/{attempt_id}/state", headers={"Authorization": f"Bearer {student_token}"})
    assert res_state.json()["integrity_score"] < 100.0

    # Trigger second tab blur which hits policy threshold (max_tab_switches=2 -> TERMINATE)
    res_ev3 = client.post(f"/api/v1/assessments/attempts/{attempt_id}/events", json={
        "event_type": "TAB_BLUR",
        "severity": "LOW"
    }, headers={"Authorization": f"Bearer {student_token}"})
    assert res_ev3.status_code == 200

    # Attempt state should now be TERMINATED
    res_state_after = client.get(f"/api/v1/assessments/attempts/{attempt_id}/state", headers={"Authorization": f"Bearer {student_token}"})
    assert res_state_after.json()["status"] == AttemptStatus.TERMINATED.value

# =====================================================================
# 5. MULTI-TYPE EVALUATION & RESULTS ENGINE
# =====================================================================

def test_multitype_evaluation_mcq_coding_subjective(student_user: User, admin_user: User, sample_questions: list):
    admin_token = create_access_token(str(admin_user.id), extra_claims={"role": admin_user.role})
    student_token = create_access_token(str(student_user.id), extra_claims={"role": student_user.role})

    now = datetime.datetime.now(datetime.timezone.utc)
    res_a = client.post("/api/v1/assessments/", json={
        "title": "Comprehensive Evaluation Round",
        "duration_minutes": 60,
        "start_time": (now - datetime.timedelta(minutes=2)).isoformat(),
        "end_time": (now + datetime.timedelta(hours=2)).isoformat(),
        "passing_score": 50.0,
        "show_results_immediately": True,
        "allow_review": True,
        "questions": [
            {"question_id": sample_questions[0].id, "section_name": "MCQ", "marks": 10.0, "negative_marks": 2.5},
            {"question_id": sample_questions[1].id, "section_name": "Coding", "marks": 20.0, "negative_marks": 0.0},
            {"question_id": sample_questions[2].id, "section_name": "Subjective", "marks": 15.0, "negative_marks": 0.0},
        ]
    }, headers={"Authorization": f"Bearer {admin_token}"})
    a_id = res_a.json()["id"]
    client.post(f"/api/v1/assessments/{a_id}/publish", headers={"Authorization": f"Bearer {admin_token}"})

    res_start = client.post(f"/api/v1/assessments/{a_id}/start", json={}, headers={"Authorization": f"Bearer {student_token}"})
    attempt_id = res_start.json()["attempt_id"]
    mcq_q = next(q for q in res_start.json()["questions"] if q["question_id"] == sample_questions[0].id)
    correct_opt_id = next(opt["id"] for opt in mcq_q["options"] if "<class 'list'>" in opt["text"])

    # 1. Answer MCQ correctly with the randomized option ID displayed to candidate
    client.post(f"/api/v1/assessments/attempts/{attempt_id}/answers", json={
        "question_id": sample_questions[0].id,
        "answer_data": {"selected_option": correct_opt_id}
    }, headers={"Authorization": f"Bearer {student_token}"})

    # 2. Answer Coding correctly
    code_python = "import sys\nline = sys.stdin.read().split()\nif line:\n    print(int(line[0]) + int(line[1]))\n"
    client.post(f"/api/v1/assessments/attempts/{attempt_id}/answers", json={
        "question_id": sample_questions[1].id,
        "answer_data": {"code": code_python, "language": "python"}
    }, headers={"Authorization": f"Bearer {student_token}"})

    # 3. Answer Subjective
    client.post(f"/api/v1/assessments/attempts/{attempt_id}/answers", json={
        "question_id": sample_questions[2].id,
        "answer_data": {"subjective_text": "Monolith is a single deployable unit whereas microservices are decoupled."}
    }, headers={"Authorization": f"Bearer {student_token}"})

    # Submit assessment
    res_sub = client.post(f"/api/v1/assessments/attempts/{attempt_id}/submit", json={}, headers={"Authorization": f"Bearer {student_token}"})
    assert res_sub.status_code == 200, res_sub.text
    result = res_sub.json()

    # MCQ (10) + Coding (20, passes both test cases) = 30 points
    assert result["total_score"] >= 30.0
    assert result["attempted_count"] == 3
    assert result["correct_count"] >= 2
    assert result["passed"] is True
    assert "section_breakdown" in result
    assert "difficulty_breakdown" in result
    assert len(result["question_breakdown"]) == 3

# =====================================================================
# 6. IDOR & SECURITY AUTHORIZATION CHECKS
# =====================================================================

def test_assessment_idor_and_security_guards(student_user: User, student_user_2: User, admin_user: User, sample_questions: list):
    admin_token = create_access_token(str(admin_user.id), extra_claims={"role": admin_user.role})
    student1_token = create_access_token(str(student_user.id), extra_claims={"role": student_user.role})
    student2_token = create_access_token(str(student_user_2.id), extra_claims={"role": student_user_2.role})

    now = datetime.datetime.now(datetime.timezone.utc)
    res_a = client.post("/api/v1/assessments/", json={
        "title": "IDOR Security Assessment",
        "duration_minutes": 30,
        "start_time": (now - datetime.timedelta(minutes=1)).isoformat(),
        "end_time": (now + datetime.timedelta(hours=1)).isoformat(),
        "questions": [{"question_id": sample_questions[0].id, "marks": 10.0}]
    }, headers={"Authorization": f"Bearer {admin_token}"})
    a_id = res_a.json()["id"]
    client.post(f"/api/v1/assessments/{a_id}/publish", headers={"Authorization": f"Bearer {admin_token}"})

    # Student 1 starts attempt
    res_start1 = client.post(f"/api/v1/assessments/{a_id}/start", json={}, headers={"Authorization": f"Bearer {student1_token}"})
    attempt_id1 = res_start1.json()["attempt_id"]

    # Student 2 tries to access Student 1's attempt state -> Expect 403 Forbidden
    res_idor_get = client.get(f"/api/v1/assessments/attempts/{attempt_id1}/state", headers={"Authorization": f"Bearer {student2_token}"})
    assert res_idor_get.status_code == 403

    # Student 2 tries to save answer on Student 1's attempt -> Expect 403 Forbidden
    res_idor_save = client.post(f"/api/v1/assessments/attempts/{attempt_id1}/answers", json={
        "question_id": sample_questions[0].id,
        "answer_data": {"selected_option": "B"}
    }, headers={"Authorization": f"Bearer {student2_token}"})
    assert res_idor_save.status_code == 403

    # Student 2 tries to submit Student 1's attempt -> Expect 403 Forbidden
    res_idor_sub = client.post(f"/api/v1/assessments/attempts/{attempt_id1}/submit", json={}, headers={"Authorization": f"Bearer {student2_token}"})
    assert res_idor_sub.status_code == 403

    # Student 1 cannot create assessments -> Expect 403 Forbidden
    res_create_student = client.post("/api/v1/assessments/", json={"title": "Unauthorized"}, headers={"Authorization": f"Bearer {student1_token}"})
    assert res_create_student.status_code == 403

# =====================================================================
# 7. REAL-TIME MONITORING & PROCTOR ACTIONS
# =====================================================================

def test_realtime_monitoring_and_proctor_actions(student_user: User, admin_user: User, sample_questions: list):
    admin_token = create_access_token(str(admin_user.id), extra_claims={"role": admin_user.role})
    student_token = create_access_token(str(student_user.id), extra_claims={"role": student_user.role})

    now = datetime.datetime.now(datetime.timezone.utc)
    res_a = client.post("/api/v1/assessments/", json={
        "title": "Live Monitoring Round",
        "duration_minutes": 20,
        "start_time": (now - datetime.timedelta(minutes=1)).isoformat(),
        "end_time": (now + datetime.timedelta(hours=1)).isoformat(),
        "questions": [{"question_id": sample_questions[0].id, "marks": 10.0}]
    }, headers={"Authorization": f"Bearer {admin_token}"})
    a_id = res_a.json()["id"]
    client.post(f"/api/v1/assessments/{a_id}/publish", headers={"Authorization": f"Bearer {admin_token}"})

    res_start = client.post(f"/api/v1/assessments/{a_id}/start", json={}, headers={"Authorization": f"Bearer {student_token}"})
    attempt_id = res_start.json()["attempt_id"]

    # Admin checks monitor dashboard
    res_mon = client.get(f"/api/v1/assessments/{a_id}/monitor", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_mon.status_code == 200
    mon_data = res_mon.json()
    assert mon_data["active_now"] >= 1
    assert len(mon_data["candidates"]) >= 1

    # Proctor extends time (+15 mins)
    res_ext = client.post(f"/api/v1/assessments/attempts/{attempt_id}/action", json={
        "action": "EXTEND_TIME",
        "extend_minutes": 15
    }, headers={"Authorization": f"Bearer {admin_token}"})
    assert res_ext.status_code == 200
    assert "extended" in res_ext.json()["message"].lower()

    # Proctor force submits attempt
    res_force = client.post(f"/api/v1/assessments/attempts/{attempt_id}/action", json={
        "action": "FORCE_SUBMIT",
        "reason": "Test conclusion"
    }, headers={"Authorization": f"Bearer {admin_token}"})
    assert res_force.status_code == 200
    assert res_force.json()["new_status"] == AttemptStatus.SUBMITTED.value

# =====================================================================
# 8. EXPIRY & AUTO-SUBMISSION ON EXPIRED SESSIONS
# =====================================================================

def test_assessment_expiry_and_auto_submission(student_user: User, admin_user: User, sample_questions: list, db: Session):
    admin_token = create_access_token(str(admin_user.id), extra_claims={"role": admin_user.role})
    student_token = create_access_token(str(student_user.id), extra_claims={"role": student_user.role})

    now = datetime.datetime.now(datetime.timezone.utc)
    res_a = client.post("/api/v1/assessments/", json={
        "title": "Short Duration Expiry Assessment",
        "duration_minutes": 1,
        "start_time": (now - datetime.timedelta(minutes=10)).isoformat(),
        "end_time": (now + datetime.timedelta(hours=1)).isoformat(),
        "questions": [{"question_id": sample_questions[0].id, "marks": 10.0}]
    }, headers={"Authorization": f"Bearer {admin_token}"})
    a_id = res_a.json()["id"]
    client.post(f"/api/v1/assessments/{a_id}/publish", headers={"Authorization": f"Bearer {admin_token}"})

    res_start = client.post(f"/api/v1/assessments/{a_id}/start", json={}, headers={"Authorization": f"Bearer {student_token}"})
    attempt_id = res_start.json()["attempt_id"]

    # Save an answer
    client.post(f"/api/v1/assessments/attempts/{attempt_id}/answers", json={
        "question_id": sample_questions[0].id,
        "answer_data": {"selected_option": "A"}
    }, headers={"Authorization": f"Bearer {student_token}"})

    # Simulate time passing by manually modifying expiry_time in db
    att = db.query(AssessmentAttempt).filter(AssessmentAttempt.id == attempt_id).first()
    att.expiry_time = now - datetime.timedelta(seconds=20)
    db.commit()

    # Heartbeat detects expired attempt and returns valid=False
    res_hb = client.post(f"/api/v1/assessments/attempts/{attempt_id}/heartbeat", json={
        "session_token": att.session_token
    }, headers={"Authorization": f"Bearer {student_token}"})
    assert res_hb.status_code == 200
    assert res_hb.json()["valid"] is False
    assert res_hb.json()["terminated"] is True

    # State endpoint auto-evaluates and marks EXPIRED
    res_state = client.get(f"/api/v1/assessments/attempts/{attempt_id}/state", headers={"Authorization": f"Bearer {student_token}"})
    assert res_state.json()["status"] == AttemptStatus.EXPIRED.value
    assert res_state.json()["remaining_seconds"] == 0

    # Submitting after expiry still succeeds idempotently and returns the graded result
    res_sub = client.post(f"/api/v1/assessments/attempts/{attempt_id}/submit", json={}, headers={"Authorization": f"Bearer {student_token}"})
    assert res_sub.status_code == 200
    assert "total_score" in res_sub.json()

# =====================================================================
# 9. MULTIPLE-SELECT / MSQ QUESTION EVALUATION
# =====================================================================

def test_multiselect_scoring_modes(student_user: User, admin_user: User, db: Session):
    admin_token = create_access_token(str(admin_user.id), extra_claims={"role": admin_user.role})
    student_token = create_access_token(str(student_user.id), extra_claims={"role": student_user.role})

    # Create MSQ question with multiple correct options (A and C)
    q_msq = Question(
        title="Python Mutable Objects MSQ",
        slug=f"msq-py-mutable-{uuid.uuid4().hex[:6]}",
        problem_statement="Select all mutable data types in Python.",
        question_type="MULTIPLE_SELECT",
        subject="Python",
        marks=10,
        negative_marks=2.0,
        options=[
            {"id": "A", "text": "List", "is_correct": True},
            {"id": "B", "text": "Tuple", "is_correct": False},
            {"id": "C", "text": "Dictionary", "is_correct": True},
            {"id": "D", "text": "String", "is_correct": False},
        ],
        author_id=admin_user.id
    )
    db.add(q_msq)
    db.commit()

    now = datetime.datetime.now(datetime.timezone.utc)
    res_a = client.post("/api/v1/assessments/", json={
        "title": "MSQ Evaluation Assessment",
        "duration_minutes": 30,
        "start_time": (now - datetime.timedelta(minutes=1)).isoformat(),
        "end_time": (now + datetime.timedelta(hours=1)).isoformat(),
        "randomize_options": False, # Fixed option keys for direct test assertions
        "show_results_immediately": True,
        "allow_review": True,
        "questions": [{"question_id": q_msq.id, "marks": 10.0, "negative_marks": 2.0}]
    }, headers={"Authorization": f"Bearer {admin_token}"})
    a_id = res_a.json()["id"]
    client.post(f"/api/v1/assessments/{a_id}/publish", headers={"Authorization": f"Bearer {admin_token}"})

    res_start = client.post(f"/api/v1/assessments/{a_id}/start", json={}, headers={"Authorization": f"Bearer {student_token}"})
    attempt_id = res_start.json()["attempt_id"]

    # Select A and C (100% correct)
    client.post(f"/api/v1/assessments/attempts/{attempt_id}/answers", json={
        "question_id": q_msq.id,
        "answer_data": {"selected_options": ["A", "C"]}
    }, headers={"Authorization": f"Bearer {student_token}"})

    res_sub = client.post(f"/api/v1/assessments/attempts/{attempt_id}/submit", json={}, headers={"Authorization": f"Bearer {student_token}"})
    assert res_sub.status_code == 200
    assert res_sub.json()["total_score"] == 10.0
    assert res_sub.json()["passed"] is True

# =====================================================================
# 10. MAX ATTEMPTS EXHAUSTION
# =====================================================================

def test_max_attempts_exhaustion(student_user: User, admin_user: User, sample_questions: list):
    admin_token = create_access_token(str(admin_user.id), extra_claims={"role": admin_user.role})
    student_token = create_access_token(str(student_user.id), extra_claims={"role": student_user.role})

    now = datetime.datetime.now(datetime.timezone.utc)
    res_a = client.post("/api/v1/assessments/", json={
        "title": "Single Attempt Only Assessment",
        "duration_minutes": 15,
        "max_attempts": 1,
        "start_time": (now - datetime.timedelta(minutes=1)).isoformat(),
        "end_time": (now + datetime.timedelta(hours=1)).isoformat(),
        "questions": [{"question_id": sample_questions[0].id, "marks": 10.0}]
    }, headers={"Authorization": f"Bearer {admin_token}"})
    a_id = res_a.json()["id"]
    client.post(f"/api/v1/assessments/{a_id}/publish", headers={"Authorization": f"Bearer {admin_token}"})

    # Attempt 1: Start and submit
    res_start1 = client.post(f"/api/v1/assessments/{a_id}/start", json={}, headers={"Authorization": f"Bearer {student_token}"})
    att_id1 = res_start1.json()["attempt_id"]
    client.post(f"/api/v1/assessments/attempts/{att_id1}/submit", json={}, headers={"Authorization": f"Bearer {student_token}"})

    # Attempt 2: Should be rejected with HTTP 400 (max attempt reached)
    res_start2 = client.post(f"/api/v1/assessments/{a_id}/start", json={}, headers={"Authorization": f"Bearer {student_token}"})
    assert res_start2.status_code == 400
    assert "maximum attempt limit" in res_start2.json()["detail"].lower()
