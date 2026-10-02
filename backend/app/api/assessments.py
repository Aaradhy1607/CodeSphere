import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.core.rate_limiter import api_general_rate_limiter
from app.models.models import (
    Assessment, AssessmentQuestion, AssessmentAttempt, AttemptAnswer,
    AntiCheatEvent, AssessmentResult, User, UserRole, Permission,
    AssessmentStatus, AttemptStatus, Question, TestCase, AuditLog
)
from app.schemas.schemas import (
    AssessmentCreate, AssessmentUpdate, AssessmentOut, AssessmentDetailOut,
    AttemptStateOut, AttemptStartRequest, AnswerSaveRequest, AnswerSaveResponse,
    AntiCheatEventCreate, AntiCheatEventOut, HeartbeatRequest, HeartbeatResponse,
    AssessmentSubmitRequest, AssessmentResultOut, MonitorDashboardOut,
    AdminAttemptActionRequest, AssessmentQuestionOut, ContestQualityReportOut
)
from app.services.assessment_service import assessment_service
from app.services.evaluation_engine import evaluation_engine
from app.services.contest_quality import contest_quality_validator

router = APIRouter(prefix="/assessments", tags=["Assessment Engine & Proctoring"])


# =====================================================================
# ASSESSMENT CRUD & LIFECYCLE ENDPOINTS
# =====================================================================

@router.get("/", response_model=List[AssessmentOut], dependencies=[Depends(api_general_rate_limiter)])
def list_assessments(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status_filter: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List assessments with role-based filtering and candidate attempt status.
    """
    assessment_service.update_assessment_lifecycle(db)
    
    is_staff = current_user.role in ["ADMIN", "SUPER_ADMIN", "FACULTY", "PLACEMENT_ADMIN"]
    query = db.query(Assessment).options(joinedload(Assessment.questions), joinedload(Assessment.attempts))

    if status_filter:
        query = query.filter(Assessment.status == status_filter.upper())
    elif not is_staff:
        # Students should not see DRAFT or ARCHIVED assessments
        query = query.filter(Assessment.status.in_([
            AssessmentStatus.SCHEDULED.value,
            AssessmentStatus.PUBLISHED.value,
            AssessmentStatus.ACTIVE.value,
            AssessmentStatus.COMPLETED.value
        ]))

    assessments = query.order_by(Assessment.start_time.desc()).offset(skip).limit(limit).all()

    # Pre-fetch student's attempts for status indicators
    user_attempts_map: Dict[int, AssessmentAttempt] = {}
    if not is_staff:
        user_atts = (
            db.query(AssessmentAttempt)
            .filter(AssessmentAttempt.candidate_id == current_user.id)
            .order_by(AssessmentAttempt.attempt_number.desc())
            .all()
        )
        for att in user_atts:
            if att.assessment_id not in user_attempts_map:
                user_attempts_map[att.assessment_id] = att

    results = []
    for a in assessments:
        # Filter eligibility for students
        if not is_staff and not assessment_service.check_candidate_eligibility(a, current_user):
            continue

        q_count = len(a.questions)
        participants_count = db.query(AssessmentAttempt.candidate_id).filter(AssessmentAttempt.assessment_id == a.id).distinct().count()

        user_att = user_attempts_map.get(a.id)
        user_att_status = user_att.status if user_att else None
        user_att_id = user_att.id if user_att else None
        user_score = user_att.score if user_att and user_att.status != AttemptStatus.IN_PROGRESS.value else None

        a_out = AssessmentOut(
            id=a.id,
            title=a.title,
            description=a.description,
            instructions=a.instructions,
            duration_minutes=a.duration_minutes,
            start_time=a.start_time,
            end_time=a.end_time,
            max_attempts=a.max_attempts,
            passing_score=a.passing_score,
            total_marks=a.total_marks,
            negative_marking=a.negative_marking,
            negative_mark_rate=a.negative_mark_rate,
            randomize_questions=a.randomize_questions,
            randomize_options=a.randomize_options,
            allowed_languages=a.allowed_languages or ["python", "cpp", "c", "java"],
            candidate_assignment=a.candidate_assignment or {"type": "ALL", "targets": []},
            anti_cheat_policy=a.anti_cheat_policy or {},
            show_results_immediately=a.show_results_immediately,
            allow_review=a.allow_review,
            status=a.status,
            created_by_id=a.created_by_id,
            created_at=a.created_at,
            updated_at=a.updated_at,
            total_questions=q_count,
            total_participants=participants_count,
            user_attempt_status=user_att_status,
            user_attempt_id=user_att_id,
            user_score=user_score
        )
        results.append(a_out)

    return results

@router.get("/{assessment_id}", dependencies=[Depends(api_general_rate_limiter)])
def get_assessment(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed assessment configuration and questions.
    """
    assessment_service.update_assessment_lifecycle(db)
    
    assessment = (
        db.query(Assessment)
        .options(joinedload(Assessment.questions).joinedload(AssessmentQuestion.question).joinedload(Question.test_cases))
        .filter(Assessment.id == assessment_id)
        .first()
    )
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found.")

    is_staff = current_user.role in ["ADMIN", "SUPER_ADMIN", "FACULTY", "PLACEMENT_ADMIN"]
    if not is_staff and not assessment_service.check_candidate_eligibility(assessment, current_user):
        raise HTTPException(status_code=403, detail="You are not eligible for this assessment.")

    questions_list = []
    for aq in assessment.questions:
        q = aq.question
        # Sanitize for student if exam not completed or not staff
        if is_staff:
            visible_tcs = [
                {
                    "id": tc.id,
                    "input_data": tc.input_data,
                    "expected_output": tc.expected_output,
                    "explanation": tc.explanation,
                    "points": tc.points,
                    "is_hidden": tc.is_hidden
                }
                for tc in (q.test_cases or [])
            ]
            opts = q.options or []
        else:
            visible_tcs = [
                {
                    "id": tc.id,
                    "input_data": tc.input_data,
                    "expected_output": tc.expected_output,
                    "explanation": tc.explanation,
                    "points": tc.points
                }
                for tc in (q.test_cases or []) if not tc.is_hidden
            ]
            opts = [
                {"id": o.get("id"), "text": o.get("text", "")} if isinstance(o, dict)
                else {"id": str(o), "text": str(o)}
                for o in (q.options or [])
            ]

        questions_list.append({
            "id": aq.id,
            "question_id": q.id,
            "title": q.title,
            "slug": q.slug,
            "problem_statement": q.problem_statement,
            "question_type": q.question_type,
            "subject": q.subject,
            "topic": q.topic,
            "blooms_level": q.blooms_level,
            "section_name": aq.section_name or "General",
            "order_index": aq.order_index,
            "marks": aq.marks,
            "negative_marks": aq.negative_marks,
            "is_mandatory": aq.is_mandatory,
            "options": opts,
            "input_format": q.input_format or "",
            "output_format": q.output_format or "",
            "constraints": q.constraints or "",
            "examples": q.examples or [],
            "visible_test_cases": visible_tcs,
            "image_url": q.image_url
        })

    participants_count = db.query(AssessmentAttempt.candidate_id).filter(AssessmentAttempt.assessment_id == assessment.id).distinct().count()

    return {
        "id": assessment.id,
        "title": assessment.title,
        "description": assessment.description,
        "instructions": assessment.instructions,
        "duration_minutes": assessment.duration_minutes,
        "start_time": assessment.start_time,
        "end_time": assessment.end_time,
        "max_attempts": assessment.max_attempts,
        "passing_score": assessment.passing_score,
        "total_marks": assessment.total_marks,
        "negative_marking": assessment.negative_marking,
        "negative_mark_rate": assessment.negative_mark_rate,
        "randomize_questions": assessment.randomize_questions,
        "randomize_options": assessment.randomize_options,
        "allowed_languages": assessment.allowed_languages or ["python", "cpp", "c", "java"],
        "candidate_assignment": assessment.candidate_assignment or {"type": "ALL", "targets": []},
        "anti_cheat_policy": assessment.anti_cheat_policy or {},
        "show_results_immediately": assessment.show_results_immediately,
        "allow_review": assessment.allow_review,
        "status": assessment.status,
        "created_by_id": assessment.created_by_id,
        "created_at": assessment.created_at,
        "updated_at": assessment.updated_at,
        "total_questions": len(questions_list),
        "total_participants": participants_count,
        "questions": questions_list
    }

@router.post("/", response_model=AssessmentOut)
def create_assessment(
    req: AssessmentCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.CREATE_ASSESSMENT))
):
    """
    Create a new assessment with question links and configuration.
    """
    # Calculate total marks from questions or default
    total_calc = sum(q.marks or 10.0 for q in req.questions) if req.questions else req.total_marks

    assessment = Assessment(
        title=req.title.strip(),
        description=req.description,
        instructions=req.instructions,
        duration_minutes=req.duration_minutes,
        start_time=req.start_time,
        end_time=req.end_time,
        max_attempts=req.max_attempts,
        passing_score=req.passing_score,
        total_marks=total_calc or req.total_marks,
        negative_marking=req.negative_marking,
        negative_mark_rate=req.negative_mark_rate,
        randomize_questions=req.randomize_questions,
        randomize_options=req.randomize_options,
        allowed_languages=req.allowed_languages or ["python", "cpp", "c", "java"],
        candidate_assignment=req.candidate_assignment or {"type": "ALL", "targets": []},
        anti_cheat_policy=req.anti_cheat_policy or {
            "max_tab_switches": 5,
            "action": "WARN",
            "require_fullscreen": True,
            "block_clipboard": True
        },
        show_results_immediately=req.show_results_immediately,
        allow_review=req.allow_review,
        status=AssessmentStatus.DRAFT.value,
        created_by_id=admin.id
    )
    db.add(assessment)
    db.flush()

    for idx, q_link in enumerate(req.questions):
        aq = AssessmentQuestion(
            assessment_id=assessment.id,
            question_id=q_link.question_id,
            section_name=q_link.section_name or "General",
            order_index=idx + 1,
            marks=q_link.marks or 10.0,
            negative_marks=q_link.negative_marks or 0.0,
            is_mandatory=q_link.is_mandatory if q_link.is_mandatory is not None else True
        )
        db.add(aq)

    db.commit()
    db.refresh(assessment)
    assessment_service.update_assessment_lifecycle(db)

    return AssessmentOut(
        id=assessment.id,
        title=assessment.title,
        description=assessment.description,
        instructions=assessment.instructions,
        duration_minutes=assessment.duration_minutes,
        start_time=assessment.start_time,
        end_time=assessment.end_time,
        max_attempts=assessment.max_attempts,
        passing_score=assessment.passing_score,
        total_marks=assessment.total_marks,
        negative_marking=assessment.negative_marking,
        negative_mark_rate=assessment.negative_mark_rate,
        randomize_questions=assessment.randomize_questions,
        randomize_options=assessment.randomize_options,
        allowed_languages=assessment.allowed_languages,
        candidate_assignment=assessment.candidate_assignment,
        anti_cheat_policy=assessment.anti_cheat_policy,
        show_results_immediately=assessment.show_results_immediately,
        allow_review=assessment.allow_review,
        status=assessment.status,
        created_by_id=assessment.created_by_id,
        created_at=assessment.created_at,
        updated_at=assessment.updated_at,
        total_questions=len(req.questions),
        total_participants=0
    )

@router.put("/{assessment_id}")
def update_assessment(
    assessment_id: int,
    req: AssessmentUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.EDIT_ASSESSMENT))
):
    """
    Update assessment details and question links.
    """
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found.")

    if req.title is not None:
        assessment.title = req.title.strip()
    if req.description is not None:
        assessment.description = req.description
    if req.instructions is not None:
        assessment.instructions = req.instructions
    if req.duration_minutes is not None:
        assessment.duration_minutes = req.duration_minutes
    if req.start_time is not None:
        assessment.start_time = req.start_time
    if req.end_time is not None:
        assessment.end_time = req.end_time
    if req.max_attempts is not None:
        assessment.max_attempts = req.max_attempts
    if req.passing_score is not None:
        assessment.passing_score = req.passing_score
    if req.total_marks is not None:
        assessment.total_marks = req.total_marks
    if req.negative_marking is not None:
        assessment.negative_marking = req.negative_marking
    if req.negative_mark_rate is not None:
        assessment.negative_mark_rate = req.negative_mark_rate
    if req.randomize_questions is not None:
        assessment.randomize_questions = req.randomize_questions
    if req.randomize_options is not None:
        assessment.randomize_options = req.randomize_options
    if req.allowed_languages is not None:
        assessment.allowed_languages = req.allowed_languages
    if req.candidate_assignment is not None:
        assessment.candidate_assignment = req.candidate_assignment
    if req.anti_cheat_policy is not None:
        assessment.anti_cheat_policy = req.anti_cheat_policy
    if req.show_results_immediately is not None:
        assessment.show_results_immediately = req.show_results_immediately
    if req.allow_review is not None:
        assessment.allow_review = req.allow_review
    if req.status is not None:
        assessment.status = req.status

    if req.questions is not None:
        db.query(AssessmentQuestion).filter(AssessmentQuestion.assessment_id == assessment_id).delete()
        total_calc = sum(q.marks or 10.0 for q in req.questions)
        assessment.total_marks = total_calc or assessment.total_marks
        for idx, q_link in enumerate(req.questions):
            aq = AssessmentQuestion(
                assessment_id=assessment.id,
                question_id=q_link.question_id,
                section_name=q_link.section_name or "General",
                order_index=idx + 1,
                marks=q_link.marks or 10.0,
                negative_marks=q_link.negative_marks or 0.0,
                is_mandatory=q_link.is_mandatory if q_link.is_mandatory is not None else True
            )
            db.add(aq)

    assessment.updated_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()
    db.refresh(assessment)
    assessment_service.update_assessment_lifecycle(db)

    return {"message": "Assessment updated successfully.", "assessment_id": assessment.id}

@router.delete("/{assessment_id}")
def delete_assessment(
    assessment_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.DELETE_ASSESSMENT))
):
    """
    Delete an assessment and all associated attempt data safely.
    """
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found.")

    db.delete(assessment)
    db.commit()
    return {"message": f"Assessment '{assessment.title}' deleted successfully."}

@router.post("/{assessment_id}/publish")
def publish_assessment(
    assessment_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.PUBLISH_ASSESSMENT))
):
    """
    Publish an assessment to make it available for candidates.
    """
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found.")

    now = datetime.datetime.now(datetime.timezone.utc)
    start_t = assessment.start_time.replace(tzinfo=datetime.timezone.utc) if assessment.start_time.tzinfo is None else assessment.start_time

    if now >= start_t:
        assessment.status = AssessmentStatus.ACTIVE.value
    else:
        assessment.status = AssessmentStatus.SCHEDULED.value

    db.commit()
    return {"message": f"Assessment published successfully with status: {assessment.status}"}

# =====================================================================
# SECURE EXAM SESSION & ATTEMPTS ENDPOINTS
# =====================================================================

@router.post("/{assessment_id}/start")
def start_or_resume_assessment(
    assessment_id: int,
    request: Request,
    body: Optional[AttemptStartRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Starts a new attempt or resumes an existing attempt.
    Returns the initial state with server-authoritative timer.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("user-agent", "")

    attempt = assessment_service.start_or_resume_attempt(
        db=db,
        assessment_id=assessment_id,
        user=current_user,
        client_ip=client_ip,
        user_agent=user_agent
    )

    return assessment_service.get_attempt_state(db, attempt.id, current_user)

@router.get("/attempts/{attempt_id}/state")
def get_attempt_state_endpoint(
    attempt_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns full attempt state, server timer, saved answers, and sanitized questions.
    """
    return assessment_service.get_attempt_state(db, attempt_id, current_user)

@router.post("/attempts/{attempt_id}/answers", response_model=AnswerSaveResponse)
def save_attempt_answer(
    attempt_id: str,
    req: AnswerSaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Autosave or explicit save of answer data for a question with idempotency.
    """
    success, saved_at, version = assessment_service.save_answer(
        db=db,
        attempt_id=attempt_id,
        question_id=req.question_id,
        answer_data=req.answer_data,
        is_flagged=bool(req.is_flagged),
        user=current_user
    )

    return AnswerSaveResponse(
        success=success,
        question_id=req.question_id,
        saved_at=saved_at,
        version=version,
        is_flagged=bool(req.is_flagged)
    )

@router.post("/attempts/{attempt_id}/events", response_model=AntiCheatEventOut)
def log_anti_cheat_event(
    attempt_id: str,
    req: AntiCheatEventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Logs an immutable anti-cheat audit event (tab switch, copy/paste, fullscreen exit, etc.).
    """
    event = assessment_service.record_anti_cheat_event(
        db=db,
        attempt_id=attempt_id,
        event_type=req.event_type,
        severity=req.severity or "INFO",
        metadata_json=req.metadata_json or {},
        user=current_user
    )

    return AntiCheatEventOut(
        id=event.id,
        attempt_id=event.attempt_id,
        candidate_id=event.candidate_id,
        event_type=event.event_type,
        severity=event.severity,
        metadata_json=event.metadata_json or {},
        timestamp=event.timestamp
    )

@router.post("/attempts/{attempt_id}/heartbeat", response_model=HeartbeatResponse)
def attempt_heartbeat(
    attempt_id: str,
    req: HeartbeatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Periodic heartbeat (every 10-15s) enforcing session integrity, active timer,
    and multiple-tab anomaly detection.
    """
    attempt = db.query(AssessmentAttempt).filter(AssessmentAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found.")

    if attempt.candidate_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized attempt heartbeat.")

    now = datetime.datetime.now(datetime.timezone.utc)
    exp_t = attempt.expiry_time.replace(tzinfo=datetime.timezone.utc) if attempt.expiry_time.tzinfo is None else attempt.expiry_time

    # Multi-session anomaly check: If candidate opened another tab and got a new session token
    if attempt.session_token and req.session_token and attempt.session_token != req.session_token:
        # Record anomaly
        event = AntiCheatEvent(
            attempt_id=attempt.id,
            candidate_id=current_user.id,
            event_type="MULTIPLE_SESSIONS",
            severity="HIGH",
            metadata_json={"stale_token": req.session_token, "active_token": attempt.session_token},
            timestamp=now
        )
        db.add(event)
        db.commit()
        return HeartbeatResponse(
            valid=False,
            remaining_seconds=0,
            status=attempt.status,
            integrity_score=attempt.integrity_score,
            terminated=True,
            termination_reason="Multiple active sessions detected. Another tab was opened."
        )

    # Expiry check
    if attempt.status == AttemptStatus.IN_PROGRESS.value and now > exp_t:
        attempt.status = AttemptStatus.EXPIRED.value
        evaluation_engine.evaluate_attempt(db, attempt)
        db.commit()
        return HeartbeatResponse(
            valid=False,
            remaining_seconds=0,
            status=AttemptStatus.EXPIRED.value,
            integrity_score=attempt.integrity_score,
            terminated=True,
            termination_reason="Time limit expired."
        )

    # Check terminated / invalidated
    if attempt.status in [AttemptStatus.TERMINATED.value, AttemptStatus.INVALIDATED.value]:
        return HeartbeatResponse(
            valid=False,
            remaining_seconds=0,
            status=attempt.status,
            integrity_score=attempt.integrity_score,
            terminated=True,
            termination_reason=f"Attempt was {attempt.status.lower()} by proctor."
        )

    attempt.last_heartbeat_at = now
    db.commit()

    rem_sec = max(0, int((exp_t - now).total_seconds()))
    return HeartbeatResponse(
        valid=True,
        remaining_seconds=rem_sec,
        status=attempt.status,
        integrity_score=attempt.integrity_score,
        terminated=False
    )

@router.post("/attempts/{attempt_id}/submit", response_model=AssessmentResultOut)
def submit_assessment(
    attempt_id: str,
    req: Optional[AssessmentSubmitRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Final submission and automatic multi-type grading.
    """
    final_sync = req.final_sync if req else None
    result = assessment_service.submit_attempt(
        db=db,
        attempt_id=attempt_id,
        user=current_user,
        final_sync_answers=final_sync
    )

    attempt = result.attempt
    assessment = result.assessment
    candidate = attempt.candidate
    student_profile = candidate.student_profile

    # If review is disabled and user is student, hide detailed solution explanations
    is_staff = current_user.role in ["ADMIN", "SUPER_ADMIN", "FACULTY", "PLACEMENT_ADMIN"]
    q_breakdown = result.question_breakdown or []
    if not is_staff and not assessment.allow_review and not assessment.show_results_immediately:
        q_breakdown = [
            {
                "question_id": q.get("question_id"),
                "title": q.get("title"),
                "question_type": q.get("question_type"),
                "section_name": q.get("section_name"),
                "marks": q.get("marks"),
                "earned_score": q.get("earned_score"),
                "verdict": q.get("verdict"),
                "is_correct": q.get("is_correct")
            }
            for q in q_breakdown
        ]

    return AssessmentResultOut(
        id=result.id,
        attempt_id=result.attempt_id,
        assessment_id=result.assessment_id,
        assessment_title=assessment.title,
        candidate_name=candidate.full_name,
        enrollment_no=student_profile.enrollment_no if student_profile else None,
        branch=student_profile.branch if student_profile else None,
        total_score=result.total_score,
        max_score=result.max_score,
        percentage=result.percentage,
        accuracy=result.accuracy,
        passed=result.passed,
        passing_score=assessment.passing_score,
        total_questions=result.total_questions,
        attempted_count=result.attempted_count,
        correct_count=result.correct_count,
        incorrect_count=result.incorrect_count,
        skipped_count=result.skipped_count,
        time_spent_seconds=result.time_spent_seconds,
        integrity_score=attempt.integrity_score,
        question_breakdown=q_breakdown,
        section_breakdown=result.section_breakdown or {},
        difficulty_breakdown=result.difficulty_breakdown or {},
        topic_breakdown=result.topic_breakdown or {},
        percentile=result.percentile,
        rank=result.rank,
        total_candidates=result.total_candidates,
        allow_review=is_staff or assessment.allow_review or assessment.show_results_immediately,
        created_at=result.created_at
    )

@router.get("/attempts/{attempt_id}/result", response_model=AssessmentResultOut)
def get_attempt_result(
    attempt_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve results and breakdown for an attempt.
    """
    attempt = db.query(AssessmentAttempt).filter(AssessmentAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found.")

    is_owner = (attempt.candidate_id == current_user.id)
    is_staff = (current_user.role in ["ADMIN", "SUPER_ADMIN", "FACULTY", "PLACEMENT_ADMIN"])
    if not is_owner and not is_staff:
        raise HTTPException(status_code=403, detail="Unauthorized to view this attempt result.")

    result = db.query(AssessmentResult).filter(AssessmentResult.attempt_id == attempt_id).first()
    if not result:
        # If attempt was submitted or expired but result not generated, generate it now
        if attempt.status != AttemptStatus.IN_PROGRESS.value:
            result = evaluation_engine.evaluate_attempt(db, attempt)
            db.commit()
        else:
            raise HTTPException(status_code=400, detail="Attempt is still in progress and has not been submitted.")

    assessment = attempt.assessment
    candidate = attempt.candidate
    student_profile = candidate.student_profile

    # If review is disabled and user is student, hide detailed solution explanations
    q_breakdown = result.question_breakdown or []
    if not is_staff and not assessment.allow_review and not assessment.show_results_immediately:
        q_breakdown = [
            {
                "question_id": q.get("question_id"),
                "title": q.get("title"),
                "question_type": q.get("question_type"),
                "section_name": q.get("section_name"),
                "marks": q.get("marks"),
                "earned_score": q.get("earned_score"),
                "verdict": q.get("verdict"),
                "is_correct": q.get("is_correct")
            }
            for q in q_breakdown
        ]

    return AssessmentResultOut(
        id=result.id,
        attempt_id=result.attempt_id,
        assessment_id=result.assessment_id,
        assessment_title=assessment.title,
        candidate_name=candidate.full_name,
        enrollment_no=student_profile.enrollment_no if student_profile else None,
        branch=student_profile.branch if student_profile else None,
        total_score=result.total_score,
        max_score=result.max_score,
        percentage=result.percentage,
        accuracy=result.accuracy,
        passed=result.passed,
        passing_score=assessment.passing_score,
        total_questions=result.total_questions,
        attempted_count=result.attempted_count,
        correct_count=result.correct_count,
        incorrect_count=result.incorrect_count,
        skipped_count=result.skipped_count,
        time_spent_seconds=result.time_spent_seconds,
        integrity_score=attempt.integrity_score,
        question_breakdown=q_breakdown,
        section_breakdown=result.section_breakdown or {},
        difficulty_breakdown=result.difficulty_breakdown or {},
        topic_breakdown=result.topic_breakdown or {},
        percentile=result.percentile,
        rank=result.rank,
        total_candidates=result.total_candidates,
        allow_review=is_staff or assessment.allow_review or assessment.show_results_immediately,
        created_at=result.created_at
    )

# =====================================================================
# REAL-TIME ASSESSMENT MONITORING & AUDIT DASHBOARD
# =====================================================================

@router.get("/{assessment_id}/monitor", response_model=MonitorDashboardOut)
def get_assessment_monitor_dashboard(
    assessment_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.VIEW_ASSESSMENT_RESULTS))
):
    """
    Real-time faculty/admin assessment monitoring dashboard.
    Tracks live candidate progress, active sessions, remaining time, and anti-cheat events.
    """
    assessment_service.update_assessment_lifecycle(db)

    assessment = (
        db.query(Assessment)
        .options(
            joinedload(Assessment.attempts).joinedload(AssessmentAttempt.candidate).joinedload(User.student_profile),
            joinedload(Assessment.attempts).joinedload(AssessmentAttempt.answers),
            joinedload(Assessment.attempts).joinedload(AssessmentAttempt.anti_cheat_events)
        )
        .filter(Assessment.id == assessment_id)
        .first()
    )
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found.")

    now = datetime.datetime.now(datetime.timezone.utc)
    total_q = len(assessment.questions)

    candidates_list = []
    active_count = 0
    submitted_count = 0
    expired_count = 0
    terminated_count = 0
    total_scores = []
    total_integrity = []
    suspicious_count = 0

    for att in assessment.attempts:
        cand = att.candidate
        prof = cand.student_profile
        exp_t = att.expiry_time.replace(tzinfo=datetime.timezone.utc) if att.expiry_time.tzinfo is None else att.expiry_time
        rem_sec = max(0, int((exp_t - now).total_seconds())) if att.status == AttemptStatus.IN_PROGRESS.value else 0

        # Auto expire check
        if att.status == AttemptStatus.IN_PROGRESS.value and now > exp_t:
            att.status = AttemptStatus.EXPIRED.value
            evaluation_engine.evaluate_attempt(db, att)

        if att.status == AttemptStatus.IN_PROGRESS.value:
            active_count += 1
        elif att.status == AttemptStatus.SUBMITTED.value:
            submitted_count += 1
            total_scores.append(att.score)
        elif att.status == AttemptStatus.EXPIRED.value:
            expired_count += 1
            total_scores.append(att.score)
        elif att.status in [AttemptStatus.TERMINATED.value, AttemptStatus.INVALIDATED.value]:
            terminated_count += 1

        ans_count = len(att.answers)
        prog_pct = round((ans_count / total_q * 100.0), 1) if total_q > 0 else 0.0

        violations = att.anti_cheat_events or []
        high_violations = sum(1 for v in violations if v.severity in ["HIGH", "CRITICAL"])
        if high_violations > 0 or att.integrity_score < 80.0:
            suspicious_count += 1

        total_integrity.append(att.integrity_score)

        candidates_list.append({
            "attempt_id": att.id,
            "candidate_id": cand.id,
            "candidate_name": cand.full_name,
            "candidate_email": cand.email,
            "enrollment_no": prof.enrollment_no if prof else None,
            "branch": prof.branch if prof else None,
            "status": att.status,
            "start_time": att.start_time,
            "expiry_time": att.expiry_time,
            "remaining_seconds": rem_sec,
            "progress_percent": prog_pct,
            "answered_count": ans_count,
            "total_questions": total_q,
            "integrity_score": att.integrity_score,
            "violations_count": len(violations),
            "high_severity_violations": high_violations,
            "last_heartbeat_at": att.last_heartbeat_at,
            "client_ip": att.client_ip,
            "submitted_at": att.submitted_at,
            "score": att.score if att.status != AttemptStatus.IN_PROGRESS.value else None,
            "passed": att.passed if att.status != AttemptStatus.IN_PROGRESS.value else None
        })

    db.commit()

    avg_score = round(sum(total_scores) / len(total_scores), 2) if total_scores else None
    avg_integrity = round(sum(total_integrity) / len(total_integrity), 1) if total_integrity else 100.0

    return MonitorDashboardOut(
        assessment_id=assessment.id,
        assessment_title=assessment.title,
        status=assessment.status,
        total_assigned=len(candidates_list),
        total_started=len(assessment.attempts),
        active_now=active_count,
        submitted_count=submitted_count,
        expired_count=expired_count,
        terminated_count=terminated_count,
        average_score=avg_score,
        average_integrity=avg_integrity,
        suspicious_candidates_count=suspicious_count,
        candidates=candidates_list
    )

@router.post("/attempts/{attempt_id}/action")
def admin_attempt_action(
    attempt_id: str,
    req: AdminAttemptActionRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.EDIT_ASSESSMENT))
):
    """
    Privileged proctor actions with RBAC and immutable audit logging.
    Supports EXTEND_TIME, TERMINATE, INVALIDATE, FORCE_SUBMIT.
    """
    attempt = db.query(AssessmentAttempt).filter(AssessmentAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found.")

    action_type = req.action.upper()
    now = datetime.datetime.now(datetime.timezone.utc)

    if action_type == "EXTEND_TIME":
        minutes = req.extend_minutes or 10
        exp_t = attempt.expiry_time.replace(tzinfo=datetime.timezone.utc) if attempt.expiry_time.tzinfo is None else attempt.expiry_time
        attempt.expiry_time = exp_t + datetime.timedelta(minutes=minutes)
        if attempt.status == AttemptStatus.EXPIRED.value:
            attempt.status = AttemptStatus.IN_PROGRESS.value
        msg = f"Extended time by {minutes} minutes."
    elif action_type == "TERMINATE":
        attempt.status = AttemptStatus.TERMINATED.value
        evaluation_engine.evaluate_attempt(db, attempt)
        msg = f"Attempt terminated by {admin.email}. Reason: {req.reason or 'Unspecified'}."
    elif action_type == "INVALIDATE":
        attempt.status = AttemptStatus.INVALIDATED.value
        attempt.score = 0.0
        attempt.percentage = 0.0
        attempt.passed = False
        msg = f"Attempt invalidated by {admin.email}."
    elif action_type == "FORCE_SUBMIT":
        attempt.status = AttemptStatus.SUBMITTED.value
        evaluation_engine.evaluate_attempt(db, attempt)
        msg = f"Attempt force-submitted by {admin.email}."
    else:
        raise HTTPException(status_code=400, detail=f"Invalid action: {req.action}")

    # Record audit log
    audit = AuditLog(
        user_id=admin.id,
        actor_email=admin.email,
        action=f"ASSESSMENT_PROCTOR_ACTION_{action_type}",
        details={
            "attempt_id": attempt_id,
            "candidate_id": attempt.candidate_id,
            "action": action_type,
            "reason": req.reason,
            "extend_minutes": req.extend_minutes
        },
        status="SUCCESS"
    )
    db.add(audit)
    db.commit()

    return {
        "message": msg,
        "attempt_id": attempt.id,
        "new_status": attempt.status,
        "new_expiry_time": attempt.expiry_time
    }

@router.get("/{assessment_id}/results")
def get_assessment_all_results(
    assessment_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.VIEW_ASSESSMENT_RESULTS))
):
    """
    Get aggregated results and student scores for an assessment.
    """
    results = (
        db.query(AssessmentResult)
        .options(joinedload(AssessmentResult.user).joinedload(User.student_profile))
        .filter(AssessmentResult.assessment_id == assessment_id)
        .order_by(AssessmentResult.rank.asc(), AssessmentResult.total_score.desc())
        .all()
    )

    out = []
    for r in results:
        prof = r.user.student_profile
        out.append({
            "result_id": r.id,
            "attempt_id": r.attempt_id,
            "user_id": r.user_id,
            "candidate_name": r.user.full_name,
            "candidate_email": r.user.email,
            "enrollment_no": prof.enrollment_no if prof else None,
            "branch": prof.branch if prof else None,
            "total_score": r.total_score,
            "max_score": r.max_score,
            "percentage": r.percentage,
            "accuracy": r.accuracy,
            "passed": r.passed,
            "rank": r.rank,
            "percentile": r.percentile,
            "time_spent_seconds": r.time_spent_seconds,
            "created_at": r.created_at
        })

    return {
        "assessment_id": assessment_id,
        "total_results": len(out),
        "results": out
    }

@router.get("/{assessment_id}/quality-report", response_model=ContestQualityReportOut, dependencies=[Depends(api_general_rate_limiter)])
def get_assessment_quality_report(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_QUESTIONS))
):
    """
    Contest & Assessment Problem Set Quality Report:
    Audits problem duplicate overlap, difficulty spread, topic concentration, and test coverage rigor.
    """
    res = contest_quality_validator.validate_assessment_problem_set(assessment_id, db)
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res

