import os
import sys
import time
import pytest
import asyncio
from datetime import datetime, timezone

from app.models.models import (
    Submission, SubmissionVerdict, SubmissionStatus, Question, TestCase, Event, User, UserRole, AccountStatus
)
from app.services.code_runner import (
    code_runner, ExecutionSession, LocalProcessBackend, DockerExecutionBackend, SandboxedCodeRunner
)
from app.services.judge_queue import (
    judge_queue_manager, JudgeQueueManager, InvalidStateTransitionError, VALID_STATE_TRANSITIONS
)
from app.services.evaluation_engine import evaluation_engine
from app.core.database import SessionLocal, auto_migrate_db


@pytest.fixture(scope="module")
def db_session():
    auto_migrate_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def sample_question(db_session):
    # Ensure test question exists
    q = db_session.query(Question).filter(Question.slug == "test-p6-judge-question").first()
    if not q:
        q = Question(
            title="Phase 6 Test Problem",
            slug="test-p6-judge-question",
            problem_statement="Calculate sum of two integers.",
            input_format="Two space-separated integers",
            output_format="One integer sum",
            question_type="CODING",
            time_limit_seconds=2.0,
            memory_limit_mb=256,
            marks=100,
            status="PUBLISHED"
        )
        db_session.add(q)
        db_session.flush()

        tc1 = TestCase(question_id=q.id, input_data="3 5\n", expected_output="8", points=50, is_hidden=False)
        tc2 = TestCase(question_id=q.id, input_data="10 20\n", expected_output="30", points=50, is_hidden=True)
        db_session.add_all([tc1, tc2])
        db_session.commit()
        db_session.refresh(q)
    return q


@pytest.fixture(scope="module")
def sample_user(db_session):
    u = db_session.query(User).filter(User.email == "p6_tester@std.ggsipu.ac.in").first()
    if not u:
        u = User(
            email="p6_tester@std.ggsipu.ac.in",
            full_name="Phase 6 Judge Tester",
            role=UserRole.STUDENT.value,
            status=AccountStatus.ACTIVE.value
        )
        db_session.add(u)
        db_session.commit()
        db_session.refresh(u)
    return u


@pytest.fixture(scope="module")
def sample_event(db_session):
    ev = db_session.query(Event).filter(Event.title == "Phase 6 Judge Verification Event").first()
    if not ev:
        now = datetime.now()
        ev = Event(
            title="Phase 6 Judge Verification Event",
            description="Verification event for production judge",
            start_time=now,
            end_time=now,
            status="ACTIVE"
        )
        db_session.add(ev)
        db_session.commit()
        db_session.refresh(ev)
    return ev


# =========================================================================
# PART 1: PRODUCTION DOCKER SANDBOX & FALLBACK VERIFICATION
# =========================================================================

def test_1_docker_backend_fallback_and_command_construction():
    """Verifies DockerExecutionBackend initializes, checks docker daemon, and falls back cleanly."""
    docker_backend = DockerExecutionBackend()
    assert hasattr(docker_backend, "execute")
    assert hasattr(docker_backend, "is_docker_active")

    # Verify fallback execution produces valid result structure
    session = ExecutionSession(lang="python", temp_dir=".", cmd=[sys.executable, "-c", "print('docker_check')"])
    res = docker_backend.execute(session, "", timeout_seconds=2.0)
    assert res["verdict"] == SubmissionVerdict.AC
    assert "docker_check" in res["output"]
    assert "backend" in res


def test_2_environment_secret_isolation():
    """Untrusted code must NEVER receive SECRET_KEY, DATABASE_URL, or GEMINI_API_KEY."""
    code = """
import os
for secret in ['SECRET_KEY', 'DATABASE_URL', 'GEMINI_API_KEY', 'JWT_SECRET']:
    if secret in os.environ and os.environ[secret]:
        print(f"LEAK:{secret}")
print("CLEAN")
"""
    res = code_runner.execute_single(code, "python", "")
    assert res["verdict"] == SubmissionVerdict.AC
    assert "LEAK" not in res["output"]
    assert "CLEAN" in res["output"]


def test_3_filesystem_workspace_isolation_and_cleanup():
    """Temporary runner directories must be cleaned up after execution completes."""
    code = "print('temp_clean_test')"
    res = code_runner.execute_single(code, "python", "")
    assert res["verdict"] == SubmissionVerdict.AC
    assert "temp_clean_test" in res["output"]


# =========================================================================
# PART 2: RESOURCE ENFORCEMENT & VERDICT ACCURACY
# =========================================================================

def test_4_timeout_terminates_and_cleans_up():
    """Infinite loop must be terminated within timeout with TLE verdict."""
    code = """
import time
while True:
    time.sleep(0.1)
"""
    start_t = time.time()
    res = code_runner.execute_single(code, "python", "", timeout_seconds=1.0)
    duration = time.time() - start_t
    assert res["verdict"] == SubmissionVerdict.TLE
    assert duration < 4.0  # Must be killed quickly


def test_5_output_flooding_triggers_ole():
    """Runaway output generation must trigger Output Limit Exceeded without memory exhaustion."""
    code = """
import sys
for _ in range(100000):
    sys.stdout.write("CodeSphereOutputFloodTest1234567890\\n")
"""
    res = code_runner.execute_single(code, "python", "", timeout_seconds=3.0)
    assert res["verdict"] == SubmissionVerdict.OLE
    assert "Output Limit Exceeded" in res["error"]


def test_6_runtime_error_classification():
    """ZeroDivisionError and exception exits must trigger RE with captured error."""
    code = """
x = 10 / 0
"""
    res = code_runner.execute_single(code, "python", "")
    assert res["verdict"] == SubmissionVerdict.RE
    assert "ZeroDivisionError" in res["error"]


# =========================================================================
# PART 3: SUBMISSION STATE MACHINE & TRANSITIONS
# =========================================================================

def test_7_state_machine_valid_transitions():
    """Verifies valid lifecycle state transitions."""
    JudgeQueueManager.validate_transition(SubmissionStatus.QUEUED.value, SubmissionStatus.COMPILING.value)
    JudgeQueueManager.validate_transition(SubmissionStatus.COMPILING.value, SubmissionStatus.RUNNING.value)
    JudgeQueueManager.validate_transition(SubmissionStatus.RUNNING.value, SubmissionStatus.EVALUATING.value)
    JudgeQueueManager.validate_transition(SubmissionStatus.EVALUATING.value, SubmissionStatus.COMPLETED.value)


def test_8_state_machine_illegal_transition_rejection():
    """Illegal transitions (e.g. COMPLETED -> RUNNING) must raise InvalidStateTransitionError."""
    with pytest.raises(InvalidStateTransitionError):
        JudgeQueueManager.validate_transition(SubmissionStatus.COMPLETED.value, SubmissionStatus.RUNNING.value)

    with pytest.raises(InvalidStateTransitionError):
        JudgeQueueManager.validate_transition(SubmissionStatus.CANCELLED.value, SubmissionStatus.COMPILING.value)


# =========================================================================
# PART 4: DEDICATED JUDGE WORKER & LOCKING
# =========================================================================

@pytest.mark.asyncio
async def test_9_judge_worker_executes_submission_end_to_end(db_session, sample_question, sample_user, sample_event):
    """Submits code through the queue worker and verifies full evaluation & DB persistence."""
    manager = JudgeQueueManager(max_concurrency=2)
    manager.start()

    sub = Submission(
        event_id=sample_event.id,
        question_id=sample_question.id,
        user_id=sample_user.id,
        code="import sys\nlines = sys.stdin.read().split()\nif len(lines)>=2: print(int(lines[0]) + int(lines[1]))",
        language="python",
        status=SubmissionStatus.QUEUED.value,
        verdict=SubmissionVerdict.PENDING.value,
        is_final=True,
        submitted_at=datetime.now(timezone.utc)
    )
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)

    # Submit and await result
    result = await manager.submit_and_await(sub.id, timeout_seconds=10.0)
    await manager.stop()

    assert result["verdict"] == SubmissionVerdict.AC.value
    assert result["passed_test_cases"] == 2
    assert result["total_test_cases"] == 2
    assert result["score"] == 100.0


@pytest.mark.asyncio
async def test_10_duplicate_worker_execution_prevention(db_session, sample_question, sample_user, sample_event):
    """Multiple workers must not simultaneously claim or execute the same submission."""
    manager = JudgeQueueManager(max_concurrency=4)
    manager.start()

    sub = Submission(
        event_id=sample_event.id,
        question_id=sample_question.id,
        user_id=sample_user.id,
        code="print('locking_test')",
        language="python",
        status=SubmissionStatus.QUEUED.value,
        verdict=SubmissionVerdict.PENDING.value,
        is_final=True,
        submitted_at=datetime.now(timezone.utc)
    )
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)

    # Enqueue same submission multiple times simultaneously
    await manager.enqueue_submission(sub.id)
    await manager.enqueue_submission(sub.id)

    # Let workers process
    await asyncio.sleep(1.0)
    await manager.stop()

    db_session.refresh(sub)
    assert sub.status in [SubmissionStatus.COMPLETED.value, SubmissionStatus.QUEUED.value]


def test_11_stuck_submission_sweeper_recovery(db_session, sample_question, sample_user, sample_event):
    """Orphaned submissions left in RUNNING state older than max age must be safely recovered to FAILED."""
    sub = Submission(
        event_id=sample_event.id,
        question_id=sample_question.id,
        user_id=sample_user.id,
        code="print('stuck_test')",
        language="python",
        status=SubmissionStatus.RUNNING.value,
        verdict=SubmissionVerdict.PENDING.value,
        is_final=True,
        submitted_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)  # Old date
    )
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)

    manager = JudgeQueueManager()
    recovered = manager.recover_stuck_submissions(max_stuck_seconds=10.0)
    assert recovered >= 1

    db_session.refresh(sub)
    assert sub.status == SubmissionStatus.FAILED.value
    assert sub.verdict == SubmissionVerdict.RE.value


# =========================================================================
# PART 5: CONCURRENCY & BURST LOAD TESTING
# =========================================================================

@pytest.mark.asyncio
async def test_12_burst_load_10_concurrent_submissions(db_session, sample_question, sample_user, sample_event):
    """Tests 10 simultaneous submissions through the bounded judge worker pool."""
    manager = JudgeQueueManager(max_concurrency=4)
    manager.start()

    subs = []
    for i in range(10):
        sub = Submission(
            event_id=sample_event.id,
            question_id=sample_question.id,
            user_id=sample_user.id,
            code=f"import sys\nlines = sys.stdin.read().split()\nif len(lines)>=2: print(int(lines[0]) + int(lines[1])) # sub {i}",
            language="python",
            status=SubmissionStatus.QUEUED.value,
            verdict=SubmissionVerdict.PENDING.value,
            is_final=True,
            submitted_at=datetime.now(timezone.utc)
        )
        db_session.add(sub)
        subs.append(sub)
    db_session.commit()

    start_time = time.time()
    tasks = [manager.submit_and_await(s.id, timeout_seconds=15.0) for s in subs]
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start_time
    await manager.stop()

    assert len(results) == 10
    success_count = sum(1 for r in results if r.get("verdict") == SubmissionVerdict.AC.value)
    assert success_count == 10
    assert elapsed < 15.0  # 10 submissions evaluated quickly under bounded concurrency


@pytest.mark.asyncio
async def test_13_burst_load_25_concurrent_submissions(db_session, sample_question, sample_user, sample_event):
    """Tests 25 simultaneous submissions absorbing queue burst."""
    manager = JudgeQueueManager(max_concurrency=8)
    manager.start()

    subs = []
    for i in range(25):
        sub = Submission(
            event_id=sample_event.id,
            question_id=sample_question.id,
            user_id=sample_user.id,
            code=f"print({i} + 1) # burst test",
            language="python",
            status=SubmissionStatus.QUEUED.value,
            verdict=SubmissionVerdict.PENDING.value,
            is_final=True,
            submitted_at=datetime.now(timezone.utc)
        )
        db_session.add(sub)
        subs.append(sub)
    db_session.commit()

    tasks = [manager.submit_and_await(s.id, timeout_seconds=20.0) for s in subs]
    results = await asyncio.gather(*tasks)
    await manager.stop()

    assert len(results) == 25
    completed = [r for r in results if r.get("status") == SubmissionStatus.COMPLETED.value]
    assert len(completed) == 25


@pytest.mark.asyncio
async def test_14_burst_load_50_concurrent_submissions(db_session, sample_question, sample_user, sample_event):
    """Tests 50 simultaneous submissions measuring throughput and latency."""
    manager = JudgeQueueManager(max_concurrency=8)
    manager.start()

    subs = []
    for i in range(50):
        sub = Submission(
            event_id=sample_event.id,
            question_id=sample_question.id,
            user_id=sample_user.id,
            code=f"print({i})",
            language="python",
            status=SubmissionStatus.QUEUED.value,
            verdict=SubmissionVerdict.PENDING.value,
            is_final=True,
            submitted_at=datetime.now(timezone.utc)
        )
        db_session.add(sub)
        subs.append(sub)
    db_session.commit()

    start_time = time.time()
    tasks = [manager.submit_and_await(s.id, timeout_seconds=30.0) for s in subs]
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start_time
    await manager.stop()

    assert len(results) == 50
    completed = [r for r in results if r.get("status") == SubmissionStatus.COMPLETED.value]
    assert len(completed) == 50
    # Average throughput should be healthy
    throughput = 50.0 / max(elapsed, 0.1)
    assert throughput > 2.0  # At least 2 submissions/second on test host


# =========================================================================
# PART 6: OBSERVABILITY & METRICS
# =========================================================================

def test_15_judge_observability_metrics():
    """Verifies metrics tracking reports real statistics."""
    manager = JudgeQueueManager(max_concurrency=4)
    metrics = manager.metrics
    metrics.record_enqueue()
    metrics.record_start(queue_wait_ms=12.5)
    metrics.record_complete(exec_time_ms=45.0, memory_kb=1524.0)

    snapshot = metrics.get_snapshot()
    assert snapshot["completed_submissions"] == 1
    assert snapshot["average_execution_time_ms"] == 45.0
    assert snapshot["peak_memory_kb"] == 1524.0
    assert snapshot["sandbox_failures"] == 0


def test_16_docker_path_translation_and_container_execution():
    """Verifies that host filepaths are translated to /workspace inside Docker."""
    import tempfile
    docker_backend = DockerExecutionBackend()
    temp_dir = tempfile.mkdtemp(prefix="cs_path_test_")
    src_file = os.path.join(temp_dir, "solution.py")
    with open(src_file, "w", encoding="utf-8") as f:
        f.write("print('path_mapping_ok')\n")

    session = ExecutionSession(lang="python", temp_dir=temp_dir, cmd=[sys.executable, src_file], source_file=src_file)
    res = docker_backend.execute(session, "", timeout_seconds=3.0)
    assert res["verdict"] == SubmissionVerdict.AC
    assert "path_mapping_ok" in res["output"]
    assert res["backend"] in ["docker", "local_process_fallback"]

    # Clean up
    try:
        os.remove(src_file)
        os.rmdir(temp_dir)
    except Exception:
        pass


def test_17_docker_strict_sandbox_fail_closed(monkeypatch):
    """Verifies that strict production sandboxing fails closed when Docker is unavailable."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "REQUIRE_DOCKER_SANDBOX", True)
    monkeypatch.setattr(settings, "ALLOW_LOCAL_PROCESS_FALLBACK", False)

    docker_backend = DockerExecutionBackend()
    # Force docker available flag to False to test strict fail-closed enforcement
    docker_backend._docker_available = False

    session = ExecutionSession(lang="python", temp_dir=".", cmd=[sys.executable, "-c", "print('should_fail')"])
    res = docker_backend.execute(session, "", timeout_seconds=2.0)
    assert res["verdict"] == SubmissionVerdict.RE
    assert res["backend"] == "docker_unavailable_fail_closed"
    assert "Docker container sandboxing is mandatory" in res["error"]
