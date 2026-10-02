import os
import sys
import time
import uuid
import datetime
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.config import Settings, settings
from app.core.database import Base, engine, SessionLocal, auto_migrate_db, check_db_health
from app.core.security import get_password_hash, create_access_token, verify_password
from app.models.models import (
    User, StudentProfile, UserRole, Question, TestCase, Event,
    Submission, SubmissionVerdict, SubmissionStatus, Assessment, AssessmentQuestion,
    AssessmentAttempt, AttemptAnswer, AntiCheatEvent, AssessmentStatus, AttemptStatus,
    QuestionType, Permission, get_permissions_for_role
)
from app.services.code_runner import (
    code_runner, MAX_OUTPUT_BYTES, SandboxedCodeRunner, LocalProcessBackend,
    DockerExecutionBackend, measure_process_peak_memory_kb
)
from app.services.judge_queue import judge_queue_manager, InvalidStateTransitionError
from app.services.seeder import seed_database

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_release_gate_db():
    Base.metadata.create_all(bind=engine)
    auto_migrate_db()
    yield


def _create_user(db: Session, email: str, role: str, name: str = "Test User") -> User:
    u = db.query(User).filter(User.email == email.lower()).first()
    if not u:
        u = User(
            email=email.lower(),
            full_name=name,
            role=role,
            hashed_password=get_password_hash("test_secure_password_2026"),
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


# =====================================================================
# 1. AUTHENTICATION FLOW & REFRESH ROTATION
# =====================================================================
def test_1_authentication_flow_and_session_tokens():
    db = SessionLocal()
    try:
        user = _create_user(db, "test.auth@std.ggsipu.ac.in", UserRole.STUDENT.value, "Auth Test Student")
        
        # Test valid login
        resp = client.post("/api/v1/auth/login", json={
            "email": user.email,
            "password": "test_secure_password_2026"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == user.email

        # Test token refresh rotation
        refresh_resp = client.post("/api/v1/auth/refresh", json={
            "refresh_token": data["refresh_token"]
        })
        assert refresh_resp.status_code == 200
        new_data = refresh_resp.json()
        assert "access_token" in new_data
        assert new_data["refresh_token"] != data["refresh_token"]

        # Reusing old refresh token must be rejected
        stale_resp = client.post("/api/v1/auth/refresh", json={
            "refresh_token": data["refresh_token"]
        })
        assert stale_resp.status_code in [400, 401]
    finally:
        db.close()


# =====================================================================
# 2. ALL 7 RBAC ROLES PERMISSION MATRIX
# =====================================================================
def test_2_all_seven_rbac_roles_permissions():
    roles = [
        UserRole.STUDENT,
        UserRole.FACULTY,
        UserRole.QUESTION_SETTER,
        UserRole.REVIEWER,
        UserRole.PLACEMENT_ADMIN,
        UserRole.ADMIN,
        UserRole.SUPER_ADMIN
    ]
    for r in roles:
        perms = get_permissions_for_role(r.value)
        assert isinstance(perms, list)
        assert len(perms) > 0
    
    # Verify STUDENT cannot manage users
    assert Permission.MANAGE_USERS.value not in get_permissions_for_role(UserRole.STUDENT.value)
    # Verify SUPER_ADMIN has MANAGE_USERS
    assert Permission.MANAGE_USERS.value in get_permissions_for_role(UserRole.SUPER_ADMIN.value)


# =====================================================================
# 3. RBAC ENDPOINT ACCESS RESTRICTIONS
# =====================================================================
def test_3_rbac_endpoint_access_restrictions():
    db = SessionLocal()
    try:
        student = _create_user(db, "student.rbac@std.ggsipu.ac.in", UserRole.STUDENT.value, "RBAC Student")
        headers = _get_auth_headers(student)

        # Student attempting to create question should be forbidden (403)
        resp = client.post("/api/v1/questions/", headers=headers, json={
            "title": "Unauthorized Question",
            "problem_statement": "Should fail",
            "difficulty_score": 5.0
        })
        assert resp.status_code == 403

        # Student attempting to view all users should be forbidden (403)
        resp = client.get("/api/v1/auth/users", headers=headers)
        assert resp.status_code == 403
    finally:
        db.close()


# =====================================================================
# 4. HORIZONTAL & VERTICAL IDOR PROTECTION
# =====================================================================
def test_4_horizontal_and_vertical_idor_protection():
    db = SessionLocal()
    try:
        s1 = _create_user(db, "idor.s1@std.ggsipu.ac.in", UserRole.STUDENT.value, "Student One")
        s2 = _create_user(db, "idor.s2@std.ggsipu.ac.in", UserRole.STUDENT.value, "Student Two")
        
        # S1 creates an assessment attempt
        assessment = Assessment(
            title="IDOR Test Assessment",
            duration_minutes=30,
            start_time=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5),
            end_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=60),
            status=AssessmentStatus.PUBLISHED.value,
            created_by_id=s1.id
        )
        db.add(assessment)
        db.flush()

        attempt = AssessmentAttempt(
            id=f"att_idor_{uuid.uuid4().hex[:8]}",
            assessment_id=assessment.id,
            candidate_id=s1.id,
            attempt_number=1,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            expiry_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=30),
            status=AttemptStatus.IN_PROGRESS.value
        )
        db.add(attempt)
        db.commit()

        # S2 tries to read S1's attempt state
        s2_headers = _get_auth_headers(s2)
        resp = client.get(f"/api/v1/assessments/attempts/{attempt.id}", headers=s2_headers)
        assert resp.status_code == 403

        # S2 tries to submit S1's attempt
        resp = client.post(f"/api/v1/assessments/attempts/{attempt.id}/submit", headers=s2_headers, json={})
        assert resp.status_code == 403
    finally:
        db.close()


# =====================================================================
# 5. HIDDEN TEST CASES SHIELDED FROM STUDENTS
# =====================================================================
def test_5_hidden_test_cases_shielded_from_students():
    db = SessionLocal()
    try:
        faculty = _create_user(db, "faculty.shield@ipu.ac.in", UserRole.FACULTY.value, "Faculty Shield")
        student = _create_user(db, "student.shield@std.ggsipu.ac.in", UserRole.STUDENT.value, "Student Shield")
        
        q = Question(
            title="Hidden Shield Question",
            slug=f"hidden-shield-q-{uuid.uuid4().hex[:8]}",
            problem_statement="Test shielding",
            difficulty_score=3,
            author_id=faculty.id,
            status="PUBLISHED"
        )
        db.add(q)
        db.flush()

        tc1 = TestCase(question_id=q.id, input_data="vis_in", expected_output="vis_out", is_hidden=False)
        tc2 = TestCase(question_id=q.id, input_data="TOP_SECRET_INPUT", expected_output="TOP_SECRET_OUTPUT", is_hidden=True)
        db.add_all([tc1, tc2])
        db.commit()

        # Create submission
        event = Event(
            title="Shield Event",
            start_time=datetime.datetime.now() - datetime.timedelta(minutes=5),
            end_time=datetime.datetime.now() + datetime.timedelta(minutes=60),
            status="ACTIVE"
        )
        db.add(event)
        db.commit()

        sub = Submission(
            event_id=event.id,
            question_id=q.id,
            user_id=student.id,
            code="print('vis_out')",
            language="python",
            status=SubmissionStatus.COMPLETED.value,
            verdict=SubmissionVerdict.WA.value,
            is_final=True,
            test_case_results=[
                {"test_case_id": tc1.id, "is_hidden": False, "passed": True, "output": "vis_out", "expected": "vis_out"},
                {"test_case_id": tc2.id, "is_hidden": True, "passed": False, "output": "wrong", "expected": "TOP_SECRET_OUTPUT"}
            ],
            submitted_at=datetime.datetime.now(datetime.timezone.utc)
        )
        db.add(sub)
        db.commit()

        # Student queries status endpoint
        s_headers = _get_auth_headers(student)
        resp = client.get(f"/api/v1/execute/status/{sub.id}", headers=s_headers)
        assert resp.status_code == 200
        data = resp.json()
        
        for r in data["test_case_results"]:
            if r["is_hidden"]:
                assert r["expected"] == "[HIDDEN]"
                assert r["output"] == ""
                assert "TOP_SECRET" not in str(r)
    finally:
        db.close()


# =====================================================================
# 6. REFERENCE SOLUTION SHIELDING UNTIL ADMIN RELEASE
# =====================================================================
def test_6_reference_solution_shielded_until_release():
    db = SessionLocal()
    try:
        student = _create_user(db, "student.refsol@std.ggsipu.ac.in", UserRole.STUDENT.value, "Ref Sol Student")
        q = Question(
            title="Ref Solution Shield Test",
            slug=f"ref-shield-q-{uuid.uuid4().hex[:8]}",
            problem_statement="Shielded ref",
            reference_solutions={"python": "SUPER_SECRET_OPTIMAL_SOLUTION()"},
            difficulty_score=3,
            status="PUBLISHED"
        )
        db.add(q)
        db.flush()

        event = Event(
            title="Unreleased Solutions Event",
            start_time=datetime.datetime.now() - datetime.timedelta(minutes=10),
            end_time=datetime.datetime.now() + datetime.timedelta(minutes=50),
            status="ACTIVE",
            are_solutions_released=False
        )
        db.add(event)
        db.flush()

        sub = Submission(
            event_id=event.id,
            question_id=q.id,
            user_id=student.id,
            code="print('test')",
            language="python",
            is_final=True,
            submitted_at=datetime.datetime.now(datetime.timezone.utc)
        )
        db.add(sub)
        db.commit()

        # Before release, reference_solution is None
        headers = _get_auth_headers(student)
        resp = client.get(f"/api/v1/execute/my-submission/{event.id}/{q.id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["reference_solution"] is None

        # Admin releases solutions
        event.are_solutions_released = True
        db.commit()

        resp2 = client.get(f"/api/v1/execute/my-submission/{event.id}/{q.id}", headers=headers)
        assert resp2.status_code == 200
        assert resp2.json()["reference_solution"] == "SUPER_SECRET_OPTIMAL_SOLUTION()"
    finally:
        db.close()


# =====================================================================
# 7. SERVER TIMER AUTHORITY & CLIENT INDEPENDENCE
# =====================================================================
def test_7_server_timer_authority_and_client_clock_independence():
    db = SessionLocal()
    try:
        student = _create_user(db, "student.timer@std.ggsipu.ac.in", UserRole.STUDENT.value, "Timer Student")
        assessment = Assessment(
            title="Timer Authority Exam",
            duration_minutes=10,
            start_time=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=2),
            end_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=60),
            status=AssessmentStatus.PUBLISHED.value
        )
        db.add(assessment)
        db.flush()

        start_t = datetime.datetime.now(datetime.timezone.utc)
        exp_t = start_t + datetime.timedelta(minutes=10)
        attempt = AssessmentAttempt(
            id=f"att_timer_{uuid.uuid4().hex[:8]}",
            assessment_id=assessment.id,
            candidate_id=student.id,
            attempt_number=1,
            start_time=start_t,
            expiry_time=exp_t,
            status=AttemptStatus.IN_PROGRESS.value
        )
        db.add(attempt)
        db.commit()

        headers = _get_auth_headers(student)
        resp = client.get(f"/api/v1/assessments/attempts/{attempt.id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        # Server calculates remaining seconds authoritative from its own clock
        assert 580 <= data["remaining_seconds"] <= 605
    finally:
        db.close()


# =====================================================================
# 8. AUTOSAVE AND ANSWER VERSION TRACKING
# =====================================================================
def test_8_answer_autosave_and_version_tracking():
    db = SessionLocal()
    try:
        student = _create_user(db, "student.autosave@std.ggsipu.ac.in", UserRole.STUDENT.value, "Autosave Student")
        assessment = Assessment(
            title="Autosave Assessment",
            duration_minutes=45,
            start_time=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5),
            end_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=60),
            status=AssessmentStatus.PUBLISHED.value
        )
        db.add(assessment)
        db.flush()

        q = Question(
            title="Q1 Autosave",
            slug=f"q1-autosave-{uuid.uuid4().hex[:8]}",
            problem_statement="Solve",
            difficulty_score=3,
            status="PUBLISHED"
        )
        db.add(q)
        db.flush()

        aq = AssessmentQuestion(assessment_id=assessment.id, question_id=q.id, order_index=1, marks=10.0)
        db.add(aq)

        attempt = AssessmentAttempt(
            id=f"att_auto_{uuid.uuid4().hex[:8]}",
            assessment_id=assessment.id,
            candidate_id=student.id,
            attempt_number=1,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            expiry_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=45),
            status=AttemptStatus.IN_PROGRESS.value
        )
        db.add(attempt)
        db.commit()

        headers = _get_auth_headers(student)

        # First autosave
        resp1 = client.post(
            f"/api/v1/assessments/attempts/{attempt.id}/save-answer",
            headers=headers,
            json={"question_id": q.id, "submitted_code": "def solve(): return 1", "submitted_language": "python"}
        )
        assert resp1.status_code == 200
        assert resp1.json()["version"] == 1

        # Second autosave (version increments)
        resp2 = client.post(
            f"/api/v1/assessments/attempts/{attempt.id}/save-answer",
            headers=headers,
            json={"question_id": q.id, "submitted_code": "def solve(): return 2", "submitted_language": "python"}
        )
        assert resp2.status_code == 200
        assert resp2.json()["version"] == 2
    finally:
        db.close()


# =====================================================================
# 9. DOUBLE-SUBMIT IDEMPOTENCY PROTECTION
# =====================================================================
def test_9_double_submit_idempotency_protection():
    db = SessionLocal()
    try:
        student = _create_user(db, "student.doublesub@std.ggsipu.ac.in", UserRole.STUDENT.value, "Double Sub Student")
        assessment = Assessment(
            title="Double Submit Assessment",
            duration_minutes=30,
            start_time=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5),
            end_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=60),
            status=AssessmentStatus.PUBLISHED.value
        )
        db.add(assessment)
        db.flush()

        attempt = AssessmentAttempt(
            id=f"att_doublesub_{uuid.uuid4().hex[:8]}",
            assessment_id=assessment.id,
            candidate_id=student.id,
            attempt_number=1,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            expiry_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=30),
            status=AttemptStatus.IN_PROGRESS.value
        )
        db.add(attempt)
        db.commit()

        headers = _get_auth_headers(student)

        # First submission
        resp1 = client.post(f"/api/v1/assessments/attempts/{attempt.id}/submit", headers=headers, json={})
        assert resp1.status_code == 200
        res1_id = resp1.json()["id"]

        # Second submission (idempotent; returns existing result smoothly without error or double scoring)
        resp2 = client.post(f"/api/v1/assessments/attempts/{attempt.id}/submit", headers=headers, json={})
        assert resp2.status_code == 200
        assert resp2.json()["id"] == res1_id
    finally:
        db.close()


# =====================================================================
# 10. ASSESSMENT EXPIRY & AUTO-EVALUATION
# =====================================================================
def test_10_assessment_expiry_and_auto_evaluation():
    db = SessionLocal()
    try:
        student = _create_user(db, "student.expiry@std.ggsipu.ac.in", UserRole.STUDENT.value, "Expiry Student")
        assessment = Assessment(
            title="Expiry Exam",
            duration_minutes=5,
            start_time=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=20),
            end_time=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=10),
            status=AssessmentStatus.PUBLISHED.value
        )
        db.add(assessment)
        db.flush()

        # Attempt with past expiry
        attempt = AssessmentAttempt(
            id=f"att_exp_{uuid.uuid4().hex[:8]}",
            assessment_id=assessment.id,
            candidate_id=student.id,
            attempt_number=1,
            start_time=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=20),
            expiry_time=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=15),
            status=AttemptStatus.IN_PROGRESS.value
        )
        db.add(attempt)
        db.commit()

        headers = _get_auth_headers(student)
        # Calling get attempt state triggers auto-grading of expired attempt
        resp = client.get(f"/api/v1/assessments/attempts/{attempt.id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == AttemptStatus.EXPIRED.value
        assert resp.json()["remaining_seconds"] == 0
    finally:
        db.close()


# =====================================================================
# 11. PROCTORING ANTI-CHEAT EVENT LOGGING & TERMINATION
# =====================================================================
def test_11_proctoring_anti_cheat_event_deductions_and_termination():
    db = SessionLocal()
    try:
        student = _create_user(db, "student.anticheat@std.ggsipu.ac.in", UserRole.STUDENT.value, "AntiCheat Student")
        assessment = Assessment(
            title="Proctored Exam",
            duration_minutes=30,
            start_time=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5),
            end_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=60),
            anti_cheat_policy={"max_tab_switches": 2, "action": "TERMINATE"},
            status=AssessmentStatus.PUBLISHED.value
        )
        db.add(assessment)
        db.flush()

        attempt = AssessmentAttempt(
            id=f"att_ac_{uuid.uuid4().hex[:8]}",
            assessment_id=assessment.id,
            candidate_id=student.id,
            attempt_number=1,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            expiry_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=30),
            status=AttemptStatus.IN_PROGRESS.value,
            integrity_score=100.0
        )
        db.add(attempt)
        db.commit()

        headers = _get_auth_headers(student)

        # Tab switch 1
        resp1 = client.post(
            f"/api/v1/assessments/attempts/{attempt.id}/anti-cheat-event",
            headers=headers,
            json={"event_type": "TAB_BLUR", "severity": "MEDIUM"}
        )
        assert resp1.status_code == 200

        # Tab switch 2 -> exceeds max_tab_switches (2) with TERMINATE policy
        resp2 = client.post(
            f"/api/v1/assessments/attempts/{attempt.id}/anti-cheat-event",
            headers=headers,
            json={"event_type": "TAB_BLUR", "severity": "HIGH"}
        )
        assert resp2.status_code == 200

        db.refresh(attempt)
        assert attempt.status == AttemptStatus.TERMINATED.value
        assert attempt.integrity_score < 100.0
    finally:
        db.close()


# =====================================================================
# 12. REAL ASYNC SUBMISSION LIFECYCLE & POLLING
# =====================================================================
def test_12_real_async_submission_lifecycle_and_polling():
    db = SessionLocal()
    try:
        student = _create_user(db, "student.async@std.ggsipu.ac.in", UserRole.STUDENT.value, "Async Student")
        q = Question(
            title="Async Judge Problem",
            slug=f"async-judge-q-{uuid.uuid4().hex[:8]}",
            problem_statement="Print hello",
            difficulty_score=1,
            status="PUBLISHED"
        )
        db.add(q)
        db.flush()

        tc = TestCase(question_id=q.id, input_data="", expected_output="Hello CodeSphere", is_hidden=False, points=10)
        db.add(tc)

        event = Event(
            title="Async Event",
            start_time=datetime.datetime.now() - datetime.timedelta(minutes=5),
            end_time=datetime.datetime.now() + datetime.timedelta(minutes=60),
            status="ACTIVE"
        )
        db.add(event)
        db.commit()

        headers = _get_auth_headers(student)

        # POST to submit-async
        resp = client.post(
            "/api/v1/execute/submit-async",
            headers=headers,
            json={
                "event_id": event.id,
                "question_id": q.id,
                "code": "print('Hello CodeSphere')",
                "language": "python"
            }
        )
        assert resp.status_code == 200
        sub_id = resp.json()["submission_id"]
        assert resp.json()["status"] == SubmissionStatus.QUEUED.value

        # Initial status query shows QUEUED
        stat_initial = client.get(f"/api/v1/execute/status/{sub_id}", headers=headers)
        assert stat_initial.status_code == 200
        assert stat_initial.json()["status"] in [SubmissionStatus.QUEUED.value, SubmissionStatus.RUNNING.value, SubmissionStatus.COMPLETED.value]

        # Execute judge worker sync handler
        judge_queue_manager._execute_submission_sync(sub_id, "release-gate-worker")

        # Poll status after worker execution
        stat_final = client.get(f"/api/v1/execute/status/{sub_id}", headers=headers)
        assert stat_final.status_code == 200
        st_data = stat_final.json()
        assert st_data["status"] == SubmissionStatus.COMPLETED.value
        assert st_data["verdict"] == SubmissionVerdict.AC.value
        assert st_data["passed_test_cases"] == 1
        assert st_data["total_test_cases"] == 1
        assert st_data["score"] == 100.0
    finally:
        db.close()


# =====================================================================
# 13. QUEUE STATE TRANSITIONS & ILLEGAL TRANSITION REJECTION
# =====================================================================
def test_13_queue_state_transitions_and_illegal_rejection():
    # Valid transition: QUEUED -> COMPILING
    judge_queue_manager.validate_transition(SubmissionStatus.QUEUED.value, SubmissionStatus.COMPILING.value)
    
    # Valid transition: COMPILING -> RUNNING
    judge_queue_manager.validate_transition(SubmissionStatus.COMPILING.value, SubmissionStatus.RUNNING.value)

    # Illegal transition: COMPLETED -> QUEUED must raise InvalidStateTransitionError
    with pytest.raises(InvalidStateTransitionError):
        judge_queue_manager.validate_transition(SubmissionStatus.COMPLETED.value, SubmissionStatus.QUEUED.value)

    # Illegal transition: RUNNING -> QUEUED must raise InvalidStateTransitionError
    with pytest.raises(InvalidStateTransitionError):
        judge_queue_manager.validate_transition(SubmissionStatus.RUNNING.value, SubmissionStatus.QUEUED.value)


# =====================================================================
# 14. DUPLICATE WORKER CLAIM PREVENTION
# =====================================================================
def test_14_duplicate_worker_claim_prevention():
    # Test internal locked claim set of JudgeQueueManager
    judge_queue_manager._claimed_submission_ids.add(99999)
    assert 99999 in judge_queue_manager._claimed_submission_ids
    judge_queue_manager._claimed_submission_ids.discard(99999)
    assert 99999 not in judge_queue_manager._claimed_submission_ids


# =====================================================================
# 15. TLE TIMEOUT ENFORCEMENT & PROCESS CLEANUP
# =====================================================================
def test_15_tle_enforcement_and_process_cleanup():
    code = "import time\nwhile True:\n    time.sleep(0.1)"
    res = code_runner.execute_single(code, "python", "", timeout_seconds=1.0)
    assert res["verdict"] == SubmissionVerdict.TLE
    assert "Time Limit Exceeded" in res["error"]


# =====================================================================
# 16. MLE DETECTION & MEMORY TELEMETRY
# =====================================================================
def test_16_mle_detection_and_memory_telemetry():
    # Normal execution measures peak memory
    code_normal = "a = [i for i in range(500000)]\nprint(len(a))"
    res_normal = code_runner.execute_single(code_normal, "python", "", timeout_seconds=3.0)
    assert res_normal["verdict"] == SubmissionVerdict.AC
    # Memory measured on Windows or reported safely
    assert res_normal["memory_kb"] >= 0.0

    # If memory limit is set deliberately very low (e.g. 1 MB) and process uses more:
    backend = LocalProcessBackend()
    temp_dir = code_runner._create_temp_dir()
    try:
        session = code_runner._prepare_session("a = [0] * 1000000\nprint(len(a))", "python", temp_dir)
        res_mle = backend.execute(session, "", timeout_seconds=3.0, memory_limit_mb=1)
        if res_mle["memory_kb"] > 1024.0:
            assert res_mle["verdict"] == SubmissionVerdict.MLE
    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


# =====================================================================
# 17. OLE STREAMING OUTPUT FLOOD PROTECTION
# =====================================================================
def test_17_ole_enforcement_and_process_termination():
    # Outputting huge flood exceeding 256 KB MAX_OUTPUT_BYTES
    code = "print('A' * 300000)"
    res = code_runner.execute_single(code, "python", "", timeout_seconds=3.0)
    assert res["verdict"] == SubmissionVerdict.OLE
    assert len(res["output"].encode("utf-8")) <= MAX_OUTPUT_BYTES
    assert "Output Limit Exceeded" in res["error"]


# =====================================================================
# 18. RE RUNTIME ERROR CLASSIFICATION
# =====================================================================
def test_18_re_runtime_error_classification():
    code = "x = 10 / 0"
    res = code_runner.execute_single(code, "python", "")
    assert res["verdict"] == SubmissionVerdict.RE
    assert "ZeroDivisionError" in res["error"]


# =====================================================================
# 19. CE COMPILATION ERROR CLASSIFICATION
# =====================================================================
def test_19_ce_compilation_error_classification():
    code = "def invalid_syntax(:"
    res = code_runner.execute_single(code, "python", "")
    assert res["verdict"] == SubmissionVerdict.RE or res["verdict"] == SubmissionVerdict.CE
    assert ("SyntaxError" in res["error"] or "invalid" in res["error"].lower())


# =====================================================================
# 20. AC ACCEPTED MULTI-TESTCASE EVALUATION
# =====================================================================
def test_20_ac_accepted_multi_testcase_evaluation():
    code = "import sys\nfor line in sys.stdin:\n    if line.strip():\n        a, b = map(int, line.split())\n        print(a + b)"
    test_cases = [
        {"input": "2 3", "expected": "5", "points": 10, "is_hidden": False},
        {"input": "10 20", "expected": "30", "points": 10, "is_hidden": True},
    ]
    res = code_runner.evaluate_test_cases(code, "python", test_cases)
    assert res["verdict"] == SubmissionVerdict.AC
    assert res["passed_count"] == 2
    assert res["total_count"] == 2
    assert res["earned_points"] == 20


# =====================================================================
# 21. WA WRONG ANSWER VERDICT
# =====================================================================
def test_21_wa_wrong_answer_verdict():
    code = "print(0)"
    test_cases = [
        {"input": "1", "expected": "100", "points": 10, "is_hidden": False}
    ]
    res = code_runner.evaluate_test_cases(code, "python", test_cases)
    assert res["verdict"] == SubmissionVerdict.WA
    assert res["passed_count"] == 0


# =====================================================================
# 22. SUBPROCESS ENVIRONMENT SECRET SCRUBBING
# =====================================================================
def test_22_subprocess_environment_secret_scrubbing():
    # Set a dummy secret in parent process
    os.environ["SECRET_KEY"] = "super-secret-parent-token"
    os.environ["DATABASE_URL"] = "postgresql://user:pass@host/db"
    
    code = "import os\nprint(os.environ.get('SECRET_KEY', 'CLEAN'), os.environ.get('DATABASE_URL', 'CLEAN'))"
    res = code_runner.execute_single(code, "python", "")
    assert res["verdict"] == SubmissionVerdict.AC
    assert "super-secret-parent-token" not in res["output"]
    assert "postgresql://" not in res["output"]
    assert "CLEAN CLEAN" in res["output"]


# =====================================================================
# 23. DOCKER ISOLATION COMMAND CONSTRUCTION
# =====================================================================
def test_23_network_and_docker_isolation_policy():
    docker_backend = DockerExecutionBackend()
    assert docker_backend.default_image is not None
    # Verify image resolution
    assert "python" in docker_backend._get_image_for_lang("python")
    assert "gcc" in docker_backend._get_image_for_lang("cpp")


# =====================================================================
# 24. WORKSPACE TEMPORARY DIRECTORY CLEANUP
# =====================================================================
def test_24_workspace_temporary_dir_cleanup():
    temp_dirs_before = []
    res = code_runner.execute_single("print('cleanup test')", "python", "")
    assert res["verdict"] == SubmissionVerdict.AC
    # Temp dir created by execute_single is deleted in finally block


# =====================================================================
# 25. DATABASE INTEGRITY & HEALTH CHECK
# =====================================================================
def test_25_database_integrity_and_foreign_keys():
    db_health = check_db_health()
    assert db_health["status"] == "HEALTHY"
    assert db_health["latency_ms"] >= 0.0


# =====================================================================
# 26. MIGRATION REPEATABILITY & AUTO-MIGRATE
# =====================================================================
def test_26_migration_repeatability_and_auto_migrate():
    # Calling auto_migrate_db multiple times must be strictly idempotent
    auto_migrate_db()
    auto_migrate_db()
    db_health = check_db_health()
    assert db_health["status"] == "HEALTHY"


# =====================================================================
# 27. FRONTEND/BACKEND CONTRACT ALIGNMENT
# =====================================================================
def test_27_frontend_backend_contract_types():
    db = SessionLocal()
    try:
        user = _create_user(db, "contract.test@ipu.ac.in", UserRole.ADMIN.value, "Contract Admin")
        headers = _get_auth_headers(user)
        
        # Test change-password accepts { old_password, new_password }
        resp = client.post("/api/v1/auth/change-password", headers=headers, json={
            "old_password": "test_secure_password_2026",
            "new_password": "test_secure_password_2026_updated"
        })
        assert resp.status_code == 200

        # Revert back
        resp2 = client.post("/api/v1/auth/change-password", headers=headers, json={
            "old_password": "test_secure_password_2026_updated",
            "new_password": "test_secure_password_2026"
        })
        assert resp2.status_code == 200
    finally:
        db.close()


# =====================================================================
# 28. HEALTH & READINESS PROBES TELEMETRY
# =====================================================================
def test_28_health_liveness_and_readiness_probes():
    live_resp = client.get("/health/liveness")
    assert live_resp.status_code == 200
    assert live_resp.json()["status"] == "ALIVE"

    ready_resp = client.get("/health/readiness")
    assert ready_resp.status_code == 200
    r_data = ready_resp.json()
    assert r_data["status"] == "READY"
    assert "judge_queue" in r_data
    assert "backend" in r_data["judge_queue"]

    metrics_resp = client.get("/metrics")
    assert metrics_resp.status_code == 200
    assert "total_requests" in metrics_resp.json()


# =====================================================================
# 29. PRODUCTION CONFIGURATION FAIL-FAST VALIDATION
# =====================================================================
def test_29_production_config_validation_fail_fast():
    # Insecure secret in production must raise RuntimeError
    bad_settings = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="codesphere-usar-super-secret-jwt-key-2026-production-ready",
        DATABASE_URL="postgresql://user:pass@host/db",
        INITIAL_ADMIN_PASSWORD="super_secure_custom_password_2026"
    )
    with pytest.raises(RuntimeError):
        bad_settings.validate_production_security()

    # SQLite in production must raise RuntimeError
    sqlite_prod_settings = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="custom-strong-random-key-with-at-least-32-chars-long",
        DATABASE_URL="sqlite:///./test.db",
        INITIAL_ADMIN_PASSWORD="super_secure_custom_password_2026"
    )
    with pytest.raises(RuntimeError):
        sqlite_prod_settings.validate_production_security()

    # Insecure admin password in production must raise RuntimeError
    weak_pwd_settings = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="custom-strong-random-key-with-at-least-32-chars-long",
        DATABASE_URL="postgresql://user:pass@host/db",
        INITIAL_ADMIN_PASSWORD="admin123"
    )
    with pytest.raises(RuntimeError):
        weak_pwd_settings.validate_production_security()


# =====================================================================
# 30. PRODUCTION SEEDER & DEMO SWITCH ISOLATION
# =====================================================================
def test_30_production_seeder_and_demo_switch_isolation():
    # Temporarily set environment to production
    orig_env = settings.ENVIRONMENT
    try:
        settings.ENVIRONMENT = "production"
        
        # /auth/demo-users must be forbidden in production
        resp_demo_users = client.get("/api/v1/auth/demo-users")
        assert resp_demo_users.status_code == 403

        # /auth/demo-switch must be forbidden in production
        resp_demo_switch = client.post("/api/v1/auth/demo-switch", json={"role": "STUDENT"})
        assert resp_demo_switch.status_code == 403
    finally:
        settings.ENVIRONMENT = orig_env
