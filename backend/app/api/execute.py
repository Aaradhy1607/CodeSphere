import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional, Dict, Any

from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.core.cache import cache, invalidate_leaderboards_cache, invalidate_analytics_cache
from app.core.rate_limiter import code_exec_rate_limiter
from app.models.models import (
    Event, Question, TestCase, Submission, StudentProfile,
    User, UserRole, EventStatus, SubmissionVerdict, SubmissionStatus, Permission
)
from app.schemas.schemas import (
    CodeRunRequest, CodeRunResult, FinalSubmitRequest, FinalSubmitResult,
    SubmissionOut, AsyncSubmitResult, SubmissionStatusOut, JudgeMetricsOut,
    StudentSubmissionHistoryOut
)
from app.services.code_runner import code_runner
from app.services.judge_queue import judge_queue_manager
from app.services.submission_analytics import submission_analytics

# Multi-language enabled router
router = APIRouter(prefix="/execute", tags=["Code Execution & Judging"])


@router.post("/run", response_model=CodeRunResult, dependencies=[Depends(code_exec_rate_limiter)])
def run_code_sample(
    req: CodeRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SUBMIT_CODE))
):
    """
    Runs user code against sample visible test cases or custom input in the sandbox.
    """
    question = db.query(Question).options(joinedload(Question.test_cases)).filter(Question.id == req.question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found.")

    if req.custom_input is not None and req.custom_input != "":
        # Single custom execution
        res = code_runner.execute_single(req.code, req.language, req.custom_input)
        return CodeRunResult(
            verdict=res["verdict"],
            passed=res["verdict"] == SubmissionVerdict.AC,
            execution_time_ms=res["time_ms"],
            memory_used_kb=res.get("memory_kb", 0.0),
            output=res["output"],
            error_message=res["error"],
            sample_results=[]
        )

    # Run visible test cases
    visible_tcs = [
        {
            "id": tc.id,
            "input": tc.input_data,
            "expected": tc.expected_output,
            "is_hidden": False,
            "points": tc.points
        }
        for tc in question.test_cases if not tc.is_hidden
    ]

    if not visible_tcs:
        # Fallback to single sample run
        first_ex = question.examples[0] if question.examples else {"input": "1", "output": ""}
        res = code_runner.execute_single(req.code, req.language, first_ex.get("input", ""))
        return CodeRunResult(
            verdict=res["verdict"],
            passed=res["verdict"] == SubmissionVerdict.AC,
            execution_time_ms=res["time_ms"],
            memory_used_kb=res.get("memory_kb", 0.0),
            output=res["output"],
            expected_output=first_ex.get("output", ""),
            error_message=res["error"],
            sample_results=[]
        )

    eval_res = code_runner.evaluate_test_cases(req.code, req.language, visible_tcs)
    return CodeRunResult(
        verdict=eval_res["verdict"],
        passed=eval_res["passed_count"] == eval_res["total_count"],
        execution_time_ms=eval_res["max_time_ms"],
        memory_used_kb=eval_res.get("peak_memory_kb", 0.0),
        output=eval_res["test_case_results"][0]["output"] if eval_res["test_case_results"] else "",
        expected_output=eval_res["test_case_results"][0]["expected"] if eval_res["test_case_results"] else "",
        error_message=eval_res["error_message"],
        sample_results=eval_res["test_case_results"]
    )

@router.post("/submit", response_model=FinalSubmitResult, dependencies=[Depends(code_exec_rate_limiter)])
def submit_final_code(
    req: FinalSubmitRequest,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SUBMIT_CODE))
):
    """
    Evaluates all hidden and visible test cases, awards final score, and locks submission.
    Supports X-Idempotency-Key header to prevent duplicate execution during network retries.
    """
    # Check Idempotency Cache
    if x_idempotency_key:
        idempotency_cache_key = f"idempotency:submit:{current_user.id}:{x_idempotency_key}"
        cached_result = cache.get(idempotency_cache_key)
        if cached_result:
            return FinalSubmitResult(**cached_result)

    event = db.query(Event).filter(Event.id == req.event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")

    now = datetime.datetime.now()
    # Check event active window unless staff/admin
    if "ADMIN" not in current_user.role and current_user.role != UserRole.FACULTY.value:
        if now < event.start_time:
            raise HTTPException(status_code=400, detail="This event has not started yet.")
        if now > event.end_time and event.status != EventStatus.ACTIVE:
            raise HTTPException(status_code=400, detail="This event has ended. Submissions are closed.")

    # Check one final submission rule
    existing = db.query(Submission).filter(
        Submission.event_id == req.event_id,
        Submission.question_id == req.question_id,
        Submission.user_id == current_user.id,
        Submission.is_final == True
    ).first()

    if existing and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=400,
            detail="You have already submitted your final solution for this question. Only one final submission is permitted."
        )

    question = db.query(Question).filter(Question.id == req.question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found.")

    all_tcs = [
        {
            "id": tc.id,
            "input": tc.input_data,
            "expected": tc.expected_output,
            "is_hidden": tc.is_hidden,
            "points": tc.points
        }
        for tc in question.test_cases
    ]

    # Evaluate against ALL test cases
    eval_res = code_runner.evaluate_test_cases(req.code, req.language, all_tcs)

    # Create submission record
    sub = Submission(
        event_id=event.id,
        question_id=question.id,
        user_id=current_user.id,
        code=req.code,
        language=req.language,
        verdict=eval_res["verdict"],
        passed_test_cases=eval_res["passed_count"],
        total_test_cases=eval_res["total_count"],
        score=eval_res["score"],
        execution_time_ms=eval_res["max_time_ms"],
        memory_used_kb=eval_res.get("peak_memory_kb", 0.0),
        error_message=eval_res["error_message"],
        test_case_results=eval_res["test_case_results"],
        status=SubmissionStatus.COMPLETED.value,
        is_final=True,
        submitted_at=now
    )
    db.add(sub)
    db.flush()

    # Recalculate lifetime student performance
    if current_user.student_profile:
        prof = current_user.student_profile
        all_subs = db.query(Submission).filter(Submission.user_id == current_user.id, Submission.is_final == True).all()
        distinct_events = db.query(Submission.event_id).filter(Submission.user_id == current_user.id, Submission.is_final == True).distinct().count()
        solved_count = sum(1 for s in all_subs if s.verdict == SubmissionVerdict.AC)
        total_score_sum = sum(s.score for s in all_subs)

        prof.total_events_participated = distinct_events
        prof.total_problems_solved = solved_count
        prof.total_lifetime_score = round(total_score_sum, 1)
        prof.average_score = round(total_score_sum / max(distinct_events, 1), 1)
        
        # Placement readiness calculation
        if prof.total_problems_solved >= 10 and prof.average_score >= 80:
            prof.placement_readiness_rating = "Ready"
        elif prof.total_problems_solved >= 5 and prof.average_score >= 60:
            prof.placement_readiness_rating = "High Potential"
        elif prof.total_problems_solved >= 2:
            prof.placement_readiness_rating = "Developing"
        else:
            prof.placement_readiness_rating = "Needs Focus"

    db.commit()
    db.refresh(sub)
    invalidate_leaderboards_cache()
    invalidate_analytics_cache()

    final_res = FinalSubmitResult(
        submission_id=sub.id,
        verdict=sub.verdict,
        score=sub.score,
        passed_test_cases=sub.passed_test_cases,
        total_test_cases=sub.total_test_cases,
        execution_time_ms=sub.execution_time_ms,
        error_message=sub.error_message,
        is_final=True
    )

    if x_idempotency_key:
        idempotency_cache_key = f"idempotency:submit:{current_user.id}:{x_idempotency_key}"
        cache.set(idempotency_cache_key, final_res.model_dump(), ttl=300)

    return final_res

@router.get("/my-submission/{event_id}/{question_id}", response_model=Optional[SubmissionOut], dependencies=[Depends(code_exec_rate_limiter)])
def get_my_submission(
    event_id: int,
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    sub = (
        db.query(Submission)
        .options(
            joinedload(Submission.question),
            joinedload(Submission.event),
            joinedload(Submission.user).joinedload(User.student_profile)
        )
        .filter(
            Submission.event_id == event_id,
            Submission.question_id == question_id,
            Submission.user_id == current_user.id,
            Submission.is_final == True
        )
        .order_by(Submission.submitted_at.desc())
        .first()
    )

    if not sub:
        return None

    # Check if event reference solution is released
    ref_sol = None
    if sub.event and sub.event.are_solutions_released and sub.question:
        ref_sol = sub.question.reference_solutions.get(sub.language, list(sub.question.reference_solutions.values())[0] if sub.question.reference_solutions else "")

    return SubmissionOut(
        id=sub.id,
        event_id=sub.event_id,
        question_id=sub.question_id,
        question_title=sub.question.title if sub.question else "",
        user_id=sub.user_id,
        student_name=sub.user.full_name if sub.user else "",
        enrollment_no=sub.user.student_profile.enrollment_no if sub.user and sub.user.student_profile else "",
        branch=sub.user.student_profile.branch if sub.user and sub.user.student_profile else "",
        language=sub.language,
        code=sub.code,
        verdict=sub.verdict,
        passed_test_cases=sub.passed_test_cases,
        total_test_cases=sub.total_test_cases,
        score=sub.score,
        execution_time_ms=sub.execution_time_ms,
        error_message=sub.error_message,
        is_final=sub.is_final,
        submitted_at=sub.submitted_at,
        reference_solution=ref_sol
    )

@router.post("/submit-async", response_model=AsyncSubmitResult, dependencies=[Depends(code_exec_rate_limiter)])
async def submit_code_async(
    req: FinalSubmitRequest,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SUBMIT_CODE))
):
    """
    Asynchronous submission endpoint.
    Creates a QUEUED submission record and enqueues to the Judge Worker Pool immediately.
    """
    event = db.query(Event).filter(Event.id == req.event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")

    now = datetime.datetime.now()
    if "ADMIN" not in current_user.role and current_user.role != UserRole.FACULTY.value:
        if now < event.start_time:
            raise HTTPException(status_code=400, detail="This event has not started yet.")
        if now > event.end_time and event.status != EventStatus.ACTIVE:
            raise HTTPException(status_code=400, detail="This event has ended. Submissions are closed.")

    # Check one final submission rule
    existing = db.query(Submission).filter(
        Submission.event_id == req.event_id,
        Submission.question_id == req.question_id,
        Submission.user_id == current_user.id,
        Submission.is_final == True
    ).first()

    if existing and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=400,
            detail="You have already submitted your final solution for this question."
        )

    question = db.query(Question).filter(Question.id == req.question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found.")

    sub = Submission(
        event_id=event.id,
        question_id=question.id,
        user_id=current_user.id,
        code=req.code,
        language=req.language,
        status=SubmissionStatus.QUEUED.value,
        verdict=SubmissionVerdict.PENDING.value,
        is_final=True,
        submitted_at=datetime.datetime.now(datetime.timezone.utc)
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    # Enqueue to judge worker pool
    await judge_queue_manager.enqueue_submission(sub.id)

    return AsyncSubmitResult(
        submission_id=sub.id,
        status=SubmissionStatus.QUEUED.value,
        message="Submission queued successfully for asynchronous evaluation.",
        enqueued_at=sub.submitted_at
    )

@router.get("/status/{submission_id}", response_model=SubmissionStatusOut)
def get_submission_status(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Pollable status endpoint returning current state machine position and verdict details.
    """
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found.")

    # Candidate or staff authorization check
    is_staff = current_user.role in ["ADMIN", "SUPER_ADMIN", "FACULTY", "PLACEMENT_ADMIN"]
    if not is_staff and sub.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied to this submission.")

    # Sanitize test results to ensure hidden tests are never leaked
    sanitized_results = []
    for tc in (sub.test_case_results or []):
        is_hidden = tc.get("is_hidden", False)
        sanitized_results.append({
            "test_case_id": tc.get("test_case_id"),
            "is_hidden": is_hidden,
            "passed": tc.get("passed", False),
            "verdict": tc.get("verdict"),
            "time_ms": tc.get("time_ms", 0.0),
            "memory_kb": tc.get("memory_kb", 0.0),
            "output": tc.get("output", "") if not is_hidden else "",
            "expected": tc.get("expected", "") if not is_hidden else "[HIDDEN]",
            "error": tc.get("error") if not is_hidden else None
        })

    return SubmissionStatusOut(
        submission_id=sub.id,
        status=getattr(sub, "status", SubmissionStatus.COMPLETED.value) or SubmissionStatus.COMPLETED.value,
        verdict=sub.verdict,
        passed_test_cases=sub.passed_test_cases or 0,
        total_test_cases=sub.total_test_cases or 0,
        score=sub.score or 0.0,
        execution_time_ms=sub.execution_time_ms or 0.0,
        memory_used_kb=sub.memory_used_kb or 0.0,
        error_message=sub.error_message,
        is_final=sub.is_final,
        submitted_at=sub.submitted_at,
        test_case_results=sanitized_results
    )

@router.get("/metrics", response_model=JudgeMetricsOut)
def get_judge_observability_metrics(
    current_user: User = Depends(get_current_user)
):
    """
    Observability metrics endpoint reporting queue latencies, active workers,
    total throughput, and sandbox backend availability.
    """
    snapshot = judge_queue_manager.metrics.get_snapshot()
    is_docker = hasattr(code_runner.backend, "is_docker_active") and code_runner.backend.is_docker_active()
    backend_name = "docker" if is_docker else "local_process"

    return JudgeMetricsOut(
        queued_submissions=snapshot["queued_submissions"],
        running_submissions=snapshot["running_submissions"],
        completed_submissions=snapshot["completed_submissions"],
        failed_submissions=snapshot["failed_submissions"],
        total_processed=snapshot["total_processed"],
        average_queue_wait_ms=snapshot["average_queue_wait_ms"],
        average_execution_time_ms=snapshot["average_execution_time_ms"],
        peak_memory_kb=snapshot["peak_memory_kb"],
        sandbox_failures=snapshot["sandbox_failures"],
        active_workers=len(judge_queue_manager._workers),
        sandbox_backend=backend_name,
        docker_available=bool(is_docker)
    )

@router.get("/my-submission-history/{question_id}", response_model=StudentSubmissionHistoryOut)
def get_my_submission_history(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves student's own submission history, runtime/memory efficiency progression,
    and factual code heuristics without revealing hidden test inputs/outputs.
    """
    res = submission_analytics.get_student_submission_history(
        user_id=current_user.id,
        question_id=question_id,
        db=db
    )
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res

