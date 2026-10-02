import re
import uuid
import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional, Dict, Any

from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.core.cache import cache, invalidate_questions_cache
from app.core.rate_limiter import ai_rate_limiter, api_general_rate_limiter
from app.models.models import (
    Question, TestCase, User, UserRole, QuestionStatus, ValidationStatus,
    QuestionType, BloomsLevel, QuestionFeedback,
    Permission, get_permissions_for_role
)
from app.schemas.schemas import (
    QuestionCreate, QuestionUpdate, QuestionOut, QuestionDetailOut,
    AIQuestionGenerateRequest, AIQuestionValidationResult, TestCaseCreate,
    MultiLangSolutionGenerateRequest, MultiLangSolutionResult,
    QuestionReviewRequest, QuestionPublishRequest, QuestionVersionOut,
    QuestionFeedbackCreate, QuestionFeedbackOut,
    DuplicateCheckRequest, DuplicateCheckResult, QuestionAnalyticsOut,
    ImageUploadResponse
)
from app.services.gemini_ai import gemini_service
from app.services.code_runner import code_runner
from app.services.quality_scorer import quality_scorer
from app.services.duplicate_detector import duplicate_detector
from app.services.adaptive_learning import adaptive_learning_engine
from app.services.media_storage import media_storage

router = APIRouter(prefix="/questions", tags=["Question Management & Intelligent Engine"])

def _slugify(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r'[^a-z0-9\s-]', '', s)
    s = re.sub(r'[\s-]+', '-', s)
    return f"{s}-{uuid.uuid4().hex[:6]}"

@router.get("/", response_model=List[QuestionOut], dependencies=[Depends(api_general_rate_limiter)])
def list_questions(
    status: Optional[str] = None,
    question_type: Optional[str] = None,
    subject: Optional[str] = None,
    difficulty_min: Optional[int] = None,
    difficulty_max: Optional[int] = None,
    topic: Optional[str] = None,
    search: Optional[str] = None,
    only_latest: bool = True,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List questions with comprehensive filtering, search, and role-based visibility.
    """
    user_perms = get_permissions_for_role(current_user.role)
    can_view_all_statuses = Permission.VIEW_QUESTIONS.value in user_perms

    cache_key = f"questions:list:{current_user.role}:{status}:{question_type}:{subject}:{difficulty_min}:{difficulty_max}:{topic}:{search}:{only_latest}:{skip}:{limit}"
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data

    query = db.query(Question).options(joinedload(Question.test_cases))
    
    if only_latest:
        query = query.filter(Question.is_latest == True)

    if not can_view_all_statuses:
        query = query.filter(Question.status.in_([QuestionStatus.APPROVED.value, QuestionStatus.PUBLISHED.value]))
    elif status and status != "ALL":
        query = query.filter(Question.status == status)

    if question_type and question_type != "ALL":
        query = query.filter(Question.question_type == question_type)
    if subject and subject != "ALL":
        query = query.filter(Question.subject == subject)
    if difficulty_min:
        query = query.filter(Question.difficulty_score >= difficulty_min)
    if difficulty_max:
        query = query.filter(Question.difficulty_score <= difficulty_max)
    if topic and topic != "ALL":
        query = query.filter(Question.topic == topic)
    if search:
        s = f"%{search.strip().lower()}%"
        query = query.filter((Question.title.ilike(s)) | (Question.problem_statement.ilike(s)))

    questions = query.order_by(Question.created_at.desc()).offset(skip).limit(limit).all()
    
    result = []
    is_admin = current_user.role in [UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value, UserRole.PLACEMENT_ADMIN.value]
    
    for q in questions:
        q_out = QuestionOut(
            id=q.id,
            title=q.title,
            slug=q.slug,
            problem_statement=q.problem_statement,
            input_format=q.input_format or "",
            output_format=q.output_format or "",
            constraints=q.constraints or "",
            question_type=q.question_type or QuestionType.CODING.value,
            subject=q.subject or "Data Structures & Algorithms",
            topic=q.topic,
            subtopic=q.subtopic,
            blooms_level=q.blooms_level or BloomsLevel.APPLY.value,
            marks=q.marks or 100,
            negative_marks=q.negative_marks or 0.0,
            time_estimate_minutes=q.time_estimate_minutes or 30,
            learning_objective=q.learning_objective,
            concept_tags=q.concept_tags or [],
            options=q.options or [],
            correct_answer=q.correct_answer if is_admin else None,
            explanation=q.explanation if is_admin else None,
            image_url=q.image_url,
            image_metadata=q.image_metadata,
            examples=q.examples or [],
            topic_tags=q.topic_tags or [],
            difficulty_score=q.difficulty_score,
            expected_time_complexity=q.expected_time_complexity,
            expected_space_complexity=q.expected_space_complexity,
            time_limit_seconds=q.time_limit_seconds,
            memory_limit_mb=q.memory_limit_mb,
            reference_solutions=q.reference_solutions if is_admin else {},
            status=q.status,
            validation_status=q.validation_status,
            validation_notes=q.validation_notes,
            is_ai_generated=q.is_ai_generated,
            quality_score=q.quality_score or 0.0,
            quality_breakdown=q.quality_breakdown,
            similarity_score=q.similarity_score or 0.0,
            duplicate_of_id=q.duplicate_of_id,
            version_number=q.version_number or 1,
            parent_question_id=q.parent_question_id,
            is_latest=q.is_latest if q.is_latest is not None else True,
            author_id=q.author_id,
            reviewer_id=q.reviewer_id,
            reviewer_feedback=q.reviewer_feedback,
            reviewed_at=q.reviewed_at,
            total_attempts=q.total_attempts or 0,
            correct_attempts=q.correct_attempts or 0,
            average_time_seconds=q.average_time_seconds or 0.0,
            experienced_difficulty=q.experienced_difficulty or 5.0,
            discrimination_index=q.discrimination_index,
            created_at=q.created_at,
            updated_at=q.updated_at,
            test_cases_count=len(q.test_cases)
        )
        result.append(q_out.model_dump())

    cache.set(cache_key, result, ttl=30)
    return result

@router.post("/upload-image", response_model=ImageUploadResponse, dependencies=[Depends(api_general_rate_limiter)])
async def upload_question_image(
    file: UploadFile = File(...),
    current_user: User = Depends(require_permission(Permission.CREATE_QUESTION))
):
    """
    Securely uploads an image/diagram to attach to a question or for AI multimodal context.
    """
    upload_res = await media_storage.save_question_image(file)
    return ImageUploadResponse(
        image_url=upload_res["image_url"],
        filename=upload_res["filename"],
        size_bytes=upload_res["size_bytes"],
        mime_type=upload_res["mime_type"]
    )

@router.post("/check-duplicate", response_model=DuplicateCheckResult, dependencies=[Depends(api_general_rate_limiter)])
def check_question_duplicate(
    req: DuplicateCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CREATE_QUESTION))
):
    """
    Pre-flight similarity scanner checking if a proposed question is an exact or near duplicate.
    """
    dup_res = duplicate_detector.check_duplicate(
        title=req.title,
        problem_statement=req.problem_statement,
        db=db,
        exclude_question_id=req.exclude_question_id
    )
    return DuplicateCheckResult(
        is_duplicate=dup_res["is_duplicate"],
        similarity_score=dup_res["similarity_score"],
        matched_question_id=dup_res["matched_question_id"],
        matched_title=dup_res["matched_title"],
        match_reason=dup_res["match_reason"],
        normalized_similarity_percent=dup_res["normalized_similarity_percent"]
    )

@router.post("/", response_model=QuestionDetailOut)
def create_question(
    req: QuestionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CREATE_QUESTION))
):
    """
    Human question authoring: creates a new question with deterministic quality scoring,
    duplicate check, and initial review state.
    """
    slug = _slugify(req.title)

    # 1. Duplicate & Similarity Check
    dup_res = duplicate_detector.check_duplicate(
        title=req.title,
        problem_statement=req.problem_statement,
        db=db
    )

    # 2. Quality Evaluation
    test_cases_dicts = [
        {"input": tc.input_data, "expected": tc.expected_output, "is_hidden": tc.is_hidden, "points": tc.points}
        for tc in req.test_cases
    ]
    quality_res = quality_scorer.evaluate(
        title=req.title,
        problem_statement=req.problem_statement,
        input_format=req.input_format or "",
        output_format=req.output_format or "",
        constraints=req.constraints or "",
        examples=req.examples or [],
        difficulty_score=req.difficulty_score,
        expected_time_complexity=req.expected_time_complexity,
        expected_space_complexity=req.expected_space_complexity,
        reference_solutions=req.reference_solutions or {},
        test_cases=test_cases_dicts,
        question_type=req.question_type or QuestionType.CODING.value,
        options=req.options or [],
        correct_answer=req.correct_answer
    )

    q = Question(
        title=req.title.strip(),
        slug=slug,
        problem_statement=req.problem_statement,
        input_format=req.input_format or "",
        output_format=req.output_format or "",
        constraints=req.constraints or "",
        question_type=req.question_type or QuestionType.CODING.value,
        subject=req.subject or "Data Structures & Algorithms",
        topic=req.topic or (req.topic_tags[0] if req.topic_tags else "General"),
        subtopic=req.subtopic,
        blooms_level=req.blooms_level or BloomsLevel.APPLY.value,
        marks=req.marks,
        negative_marks=req.negative_marks,
        time_estimate_minutes=req.time_estimate_minutes,
        learning_objective=req.learning_objective,
        concept_tags=req.concept_tags or req.topic_tags or [],
        options=req.options or [],
        correct_answer=req.correct_answer,
        explanation=req.explanation,
        image_url=req.image_url,
        image_metadata=req.image_metadata,
        examples=req.examples or [],
        topic_tags=req.topic_tags or [],
        difficulty_score=req.difficulty_score,
        expected_time_complexity=req.expected_time_complexity,
        expected_space_complexity=req.expected_space_complexity,
        time_limit_seconds=req.time_limit_seconds,
        memory_limit_mb=req.memory_limit_mb,
        reference_solutions=req.reference_solutions or {},
        status=req.status or QuestionStatus.DRAFT.value,
        validation_status=ValidationStatus.PENDING.value,
        quality_score=quality_res["quality_score"],
        quality_breakdown=quality_res["breakdown"],
        similarity_hash=dup_res.get("similarity_hash"),
        similarity_score=dup_res["similarity_score"],
        duplicate_of_id=dup_res["matched_question_id"],
        version_number=1,
        is_latest=True,
        change_summary=req.change_summary or "Initial authoring",
        author_id=current_user.id,
        is_ai_generated=False
    )
    db.add(q)
    db.flush()

    for tc in req.test_cases:
        test_case = TestCase(
            question_id=q.id,
            input_data=tc.input_data,
            expected_output=tc.expected_output,
            is_hidden=tc.is_hidden,
            explanation=tc.explanation,
            points=tc.points
        )
        db.add(test_case)

    db.commit()
    db.refresh(q)
    invalidate_questions_cache()
    return q

@router.get("/{question_id}", response_model=QuestionDetailOut, dependencies=[Depends(api_general_rate_limiter)])
def get_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    q = db.query(Question).options(joinedload(Question.test_cases)).filter(Question.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found.")

    is_admin = current_user.role in [UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value, UserRole.PLACEMENT_ADMIN.value]
    test_cases_out = []
    for tc in q.test_cases:
        if is_admin or not tc.is_hidden:
            test_cases_out.append(tc)

    return QuestionDetailOut(
        id=q.id,
        title=q.title,
        slug=q.slug,
        problem_statement=q.problem_statement,
        input_format=q.input_format or "",
        output_format=q.output_format or "",
        constraints=q.constraints or "",
        question_type=q.question_type or QuestionType.CODING.value,
        subject=q.subject or "Data Structures & Algorithms",
        topic=q.topic,
        subtopic=q.subtopic,
        blooms_level=q.blooms_level or BloomsLevel.APPLY.value,
        marks=q.marks or 100,
        negative_marks=q.negative_marks or 0.0,
        time_estimate_minutes=q.time_estimate_minutes or 30,
        learning_objective=q.learning_objective,
        concept_tags=q.concept_tags or [],
        options=q.options or [],
        correct_answer=q.correct_answer if is_admin else None,
        explanation=q.explanation if is_admin else None,
        image_url=q.image_url,
        image_metadata=q.image_metadata,
        examples=q.examples or [],
        topic_tags=q.topic_tags or [],
        difficulty_score=q.difficulty_score,
        expected_time_complexity=q.expected_time_complexity,
        expected_space_complexity=q.expected_space_complexity,
        time_limit_seconds=q.time_limit_seconds,
        memory_limit_mb=q.memory_limit_mb,
        reference_solutions=q.reference_solutions if is_admin else {},
        status=q.status,
        validation_status=q.validation_status,
        validation_notes=q.validation_notes,
        is_ai_generated=q.is_ai_generated,
        quality_score=q.quality_score or 0.0,
        quality_breakdown=q.quality_breakdown,
        similarity_score=q.similarity_score or 0.0,
        duplicate_of_id=q.duplicate_of_id,
        version_number=q.version_number or 1,
        parent_question_id=q.parent_question_id,
        is_latest=q.is_latest if q.is_latest is not None else True,
        author_id=q.author_id,
        reviewer_id=q.reviewer_id,
        reviewer_feedback=q.reviewer_feedback,
        reviewed_at=q.reviewed_at,
        total_attempts=q.total_attempts or 0,
        correct_attempts=q.correct_attempts or 0,
        average_time_seconds=q.average_time_seconds or 0.0,
        experienced_difficulty=q.experienced_difficulty or 5.0,
        discrimination_index=q.discrimination_index,
        created_at=q.created_at,
        updated_at=q.updated_at,
        test_cases_count=len(q.test_cases),
        test_cases=test_cases_out
    )

@router.put("/{question_id}", response_model=QuestionDetailOut)
def update_question(
    question_id: int,
    req: QuestionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.EDIT_QUESTION))
):
    """
    Updates an existing question. If the question was already PUBLISHED,
    creates a new immutable revision (versioning) so historical assessments remain unaffected.
    """
    q = db.query(Question).options(joinedload(Question.test_cases)).filter(Question.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found.")

    # Versioning check: If already published, clone into a new revision
    if q.status == QuestionStatus.PUBLISHED.value:
        new_version_number = (q.version_number or 1) + 1
        q.is_latest = False # Archive current as historical snapshot
        
        new_slug = _slugify(req.title or q.title)
        new_q = Question(
            title=(req.title or q.title).strip(),
            slug=new_slug,
            problem_statement=req.problem_statement if req.problem_statement is not None else q.problem_statement,
            input_format=req.input_format if req.input_format is not None else q.input_format,
            output_format=req.output_format if req.output_format is not None else q.output_format,
            constraints=req.constraints if req.constraints is not None else q.constraints,
            question_type=req.question_type or q.question_type,
            subject=req.subject or q.subject,
            topic=req.topic or q.topic,
            subtopic=req.subtopic or q.subtopic,
            blooms_level=req.blooms_level or q.blooms_level,
            marks=req.marks if req.marks is not None else q.marks,
            negative_marks=req.negative_marks if req.negative_marks is not None else q.negative_marks,
            time_estimate_minutes=req.time_estimate_minutes if req.time_estimate_minutes is not None else q.time_estimate_minutes,
            learning_objective=req.learning_objective if req.learning_objective is not None else q.learning_objective,
            concept_tags=req.concept_tags if req.concept_tags is not None else q.concept_tags,
            options=req.options if req.options is not None else q.options,
            correct_answer=req.correct_answer if req.correct_answer is not None else q.correct_answer,
            explanation=req.explanation if req.explanation is not None else q.explanation,
            image_url=req.image_url if req.image_url is not None else q.image_url,
            image_metadata=req.image_metadata if req.image_metadata is not None else q.image_metadata,
            examples=req.examples if req.examples is not None else q.examples,
            topic_tags=req.topic_tags if req.topic_tags is not None else q.topic_tags,
            difficulty_score=req.difficulty_score if req.difficulty_score is not None else q.difficulty_score,
            expected_time_complexity=req.expected_time_complexity or q.expected_time_complexity,
            expected_space_complexity=req.expected_space_complexity or q.expected_space_complexity,
            reference_solutions=req.reference_solutions if req.reference_solutions is not None else q.reference_solutions,
            status=QuestionStatus.DRAFT.value,
            validation_status=ValidationStatus.PENDING.value,
            version_number=new_version_number,
            parent_question_id=q.id,
            is_latest=True,
            change_summary=req.change_summary or f"Revision {new_version_number}",
            author_id=current_user.id,
            is_ai_generated=q.is_ai_generated
        )
        db.add(new_q)
        db.flush()

        # Copy test cases
        for tc in q.test_cases:
            new_tc = TestCase(
                question_id=new_q.id,
                input_data=tc.input_data,
                expected_output=tc.expected_output,
                is_hidden=tc.is_hidden,
                explanation=tc.explanation,
                points=tc.points
            )
            db.add(new_tc)

        db.commit()
        db.refresh(new_q)
        invalidate_questions_cache()
        return new_q

    # In-place update for DRAFT / UNDER_REVIEW / REJECTED
    if req.title is not None:
        q.title = req.title.strip()
    if req.problem_statement is not None:
        q.problem_statement = req.problem_statement
    if req.input_format is not None:
        q.input_format = req.input_format
    if req.output_format is not None:
        q.output_format = req.output_format
    if req.constraints is not None:
        q.constraints = req.constraints
    if req.question_type is not None:
        q.question_type = req.question_type
    if req.subject is not None:
        q.subject = req.subject
    if req.topic is not None:
        q.topic = req.topic
    if req.subtopic is not None:
        q.subtopic = req.subtopic
    if req.blooms_level is not None:
        q.blooms_level = req.blooms_level
    if req.marks is not None:
        q.marks = req.marks
    if req.negative_marks is not None:
        q.negative_marks = req.negative_marks
    if req.time_estimate_minutes is not None:
        q.time_estimate_minutes = req.time_estimate_minutes
    if req.learning_objective is not None:
        q.learning_objective = req.learning_objective
    if req.concept_tags is not None:
        q.concept_tags = req.concept_tags
    if req.options is not None:
        q.options = req.options
    if req.correct_answer is not None:
        q.correct_answer = req.correct_answer
    if req.explanation is not None:
        q.explanation = req.explanation
    if req.image_url is not None:
        q.image_url = req.image_url
    if req.image_metadata is not None:
        q.image_metadata = req.image_metadata
    if req.examples is not None:
        q.examples = req.examples
    if req.topic_tags is not None:
        q.topic_tags = req.topic_tags
    if req.difficulty_score is not None:
        q.difficulty_score = req.difficulty_score
    if req.expected_time_complexity is not None:
        q.expected_time_complexity = req.expected_time_complexity
    if req.expected_space_complexity is not None:
        q.expected_space_complexity = req.expected_space_complexity
    if req.reference_solutions is not None:
        q.reference_solutions = req.reference_solutions
    if req.status is not None:
        q.status = req.status
    if req.validation_status is not None:
        q.validation_status = req.validation_status
    if req.validation_notes is not None:
        q.validation_notes = req.validation_notes
    if req.reviewer_feedback is not None:
        q.reviewer_feedback = req.reviewer_feedback
    if req.rejection_reason is not None:
        q.rejection_reason = req.rejection_reason
    if req.change_summary is not None:
        q.change_summary = req.change_summary

    # Recalculate Quality Score
    test_cases_dicts = [
        {"input": tc.input_data, "expected": tc.expected_output, "is_hidden": tc.is_hidden, "points": tc.points}
        for tc in q.test_cases
    ]
    quality_res = quality_scorer.evaluate(
        title=q.title,
        problem_statement=q.problem_statement,
        input_format=q.input_format or "",
        output_format=q.output_format or "",
        constraints=q.constraints or "",
        examples=q.examples or [],
        difficulty_score=q.difficulty_score,
        expected_time_complexity=q.expected_time_complexity,
        expected_space_complexity=q.expected_space_complexity,
        reference_solutions=q.reference_solutions or {},
        test_cases=test_cases_dicts,
        question_type=q.question_type or QuestionType.CODING.value,
        options=q.options or [],
        correct_answer=q.correct_answer
    )
    q.quality_score = quality_res["quality_score"]
    q.quality_breakdown = quality_res["breakdown"]

    db.commit()
    db.refresh(q)
    invalidate_questions_cache()
    return q

@router.post("/generate-ai", dependencies=[Depends(ai_rate_limiter)])
def generate_ai_question(
    req: AIQuestionGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CREATE_QUESTION))
):
    """
    Intelligent AI Question Generation Pipeline:
    Specification -> Adaptive Learning Guidance -> Gemini Synthesizer ->
    Structural & Semantic Validation -> Quality Scoring -> Duplicate Detection ->
    Draft Persistence.
    """
    # 1. Fetch adaptive topic performance calibration guidance
    adaptive_notes = adaptive_learning_engine.get_topic_adaptive_guidance(req.topic, db)

    # 2. Synthesize structured question via Gemini with multimodal diagram understanding
    ai_result = gemini_service.generate_question(
        topic=req.topic,
        sub_topic=req.sub_topic,
        difficulty_score=req.difficulty_score,
        relative_difficulty=req.relative_difficulty,
        reference_blueprint=req.reference_blueprint,
        target_branch=req.target_branch or "ALL",
        target_year=req.target_year or 0,
        subject=req.subject or "Data Structures & Algorithms",
        question_type=req.question_type or QuestionType.CODING.value,
        blooms_level=req.blooms_level or BloomsLevel.APPLY.value,
        marks=req.marks,
        negative_marks=req.negative_marks,
        time_estimate_minutes=req.time_estimate_minutes,
        learning_objective=req.learning_objective,
        concept_tags=req.concept_tags,
        image_base64=req.image_base64,
        image_mime_type=req.image_mime_type,
        adaptive_guidance=adaptive_notes
    )

    title = ai_result.get("title", f"{req.subject}: {req.topic} Challenge")
    slug = _slugify(title)

    # 3. Duplicate & Similarity Check
    dup_res = duplicate_detector.check_duplicate(
        title=title,
        problem_statement=ai_result.get("problem_statement", ""),
        db=db
    )

    # 4. Extract Test Cases
    all_tcs_data = []
    visible_tcs = ai_result.get("visible_test_cases", [])
    hidden_tcs = ai_result.get("hidden_test_cases", [])
    for vt in visible_tcs:
        all_tcs_data.append({
            "input": vt.get("input_data", ""),
            "expected": vt.get("expected_output", ""),
            "points": vt.get("points", 10),
            "is_hidden": False,
            "explanation": vt.get("explanation", "")
        })
    for ht in hidden_tcs:
        all_tcs_data.append({
            "input": ht.get("input_data", ""),
            "expected": ht.get("expected_output", ""),
            "points": ht.get("points", 15),
            "is_hidden": True,
            "explanation": ht.get("explanation", "")
        })

    # 5. Quality Evaluation
    quality_res = quality_scorer.evaluate(
        title=title,
        problem_statement=ai_result.get("problem_statement", ""),
        input_format=ai_result.get("input_format", ""),
        output_format=ai_result.get("output_format", ""),
        constraints=ai_result.get("constraints", ""),
        examples=ai_result.get("examples", []),
        difficulty_score=req.difficulty_score,
        expected_time_complexity=ai_result.get("expected_time_complexity", "O(N)"),
        expected_space_complexity=ai_result.get("expected_space_complexity", "O(1)"),
        reference_solutions=ai_result.get("reference_solutions", {}),
        test_cases=all_tcs_data,
        question_type=req.question_type or QuestionType.CODING.value,
        options=ai_result.get("options", []),
        correct_answer=ai_result.get("correct_answer")
    )

    q = Question(
        title=title,
        slug=slug,
        problem_statement=ai_result.get("problem_statement", ""),
        input_format=ai_result.get("input_format", ""),
        output_format=ai_result.get("output_format", ""),
        constraints=ai_result.get("constraints", ""),
        question_type=req.question_type or QuestionType.CODING.value,
        subject=req.subject or "Data Structures & Algorithms",
        topic=req.topic,
        subtopic=req.sub_topic or req.topic,
        blooms_level=req.blooms_level or BloomsLevel.APPLY.value,
        marks=req.marks,
        negative_marks=req.negative_marks,
        time_estimate_minutes=req.time_estimate_minutes,
        learning_objective=req.learning_objective,
        concept_tags=ai_result.get("concept_tags", req.concept_tags or [req.topic]),
        options=ai_result.get("options", []),
        correct_answer=ai_result.get("correct_answer"),
        explanation=ai_result.get("explanation"),
        examples=ai_result.get("examples", []),
        topic_tags=ai_result.get("topic_tags", [req.topic]),
        difficulty_score=req.difficulty_score,
        expected_time_complexity=ai_result.get("expected_time_complexity", "O(N)"),
        expected_space_complexity=ai_result.get("expected_space_complexity", "O(1)"),
        reference_solutions=ai_result.get("reference_solutions", {}),
        status=QuestionStatus.AI_GENERATED.value,
        validation_status=ValidationStatus.PENDING.value,
        quality_score=quality_res["quality_score"],
        quality_breakdown=quality_res["breakdown"],
        similarity_hash=dup_res.get("similarity_hash"),
        similarity_score=dup_res["similarity_score"],
        duplicate_of_id=dup_res["matched_question_id"],
        version_number=1,
        is_latest=True,
        change_summary="AI synthesis",
        author_id=current_user.id,
        is_ai_generated=True,
        ai_prompt_blueprint=req.reference_blueprint
    )
    db.add(q)
    db.flush()

    # Add Test Cases for Coding Problems
    for tc_dict in all_tcs_data:
        tc = TestCase(
            question_id=q.id,
            input_data=tc_dict["input"],
            expected_output=tc_dict["expected"],
            is_hidden=tc_dict["is_hidden"],
            explanation=tc_dict.get("explanation"),
            points=tc_dict["points"]
        )
        db.add(tc)

    db.commit()
    db.refresh(q)

    # 6. Automated Code Execution Validation for Coding Problems
    val_report = {"status": "PASSED", "notes": "Non-coding question created"}
    if q.question_type == QuestionType.CODING.value and q.reference_solutions:
        val_report = code_runner.validate_reference_solution(q.reference_solutions, all_tcs_data)
        q.validation_status = val_report["status"]
        q.validation_notes = val_report["notes"]
        db.commit()
        db.refresh(q)

    invalidate_questions_cache()

    return {
        "question": q,
        "validation_report": val_report,
        "quality_score": quality_res["quality_score"],
        "quality_breakdown": quality_res["breakdown"],
        "similarity_result": dup_res
    }

@router.post("/{question_id}/review")
def review_question(
    question_id: int,
    req: QuestionReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.REVIEW_QUESTION))
):
    """
    Review Workflow: Approve, Reject, or Request Changes on a Question.
    Enforces server-side RBAC and logs structured reviewer feedback.
    """
    q = db.query(Question).filter(Question.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found.")

    action = req.action.upper().strip()
    now = datetime.datetime.now(datetime.timezone.utc)
    
    if action in ("APPROVE", "APPROVED"):
        if q.question_type == QuestionType.CODING.value and q.validation_status != ValidationStatus.PASSED.value and not req.force:
            raise HTTPException(
                status_code=400,
                detail="Question has not passed reference solution validation runner yet. Run validation or force approve."
            )
        q.status = QuestionStatus.APPROVED.value
        q.reviewer_id = current_user.id
        q.reviewer_feedback = req.feedback or "Approved for question bank."
        q.reviewed_at = now
        q.rejection_reason = None
    elif action == "REJECT":
        q.status = QuestionStatus.REJECTED.value
        q.reviewer_id = current_user.id
        q.reviewer_feedback = req.feedback
        q.rejection_reason = req.rejection_reason or req.feedback or "Quality standards not met."
        q.reviewed_at = now
    elif action == "REQUEST_CHANGES":
        q.status = QuestionStatus.DRAFT.value
        q.reviewer_id = current_user.id
        q.reviewer_feedback = req.feedback or "Changes requested by reviewer."
        q.reviewed_at = now
    else:
        raise HTTPException(status_code=400, detail=f"Invalid review action: '{action}'. Must be APPROVE, REJECT, or REQUEST_CHANGES.")

    # Record Feedback Audit Entry
    feedback_entry = QuestionFeedback(
        question_id=q.id,
        user_id=current_user.id,
        feedback_type="REVIEWER_NOTE",
        rating=5 if action == "APPROVE" else (2 if action == "REJECT" else 3),
        comment=req.feedback or f"Review action: {action}",
        metrics_snapshot={"action": action, "quality_score": q.quality_score}
    )
    db.add(feedback_entry)

    db.commit()
    db.refresh(q)
    invalidate_questions_cache()

    return {
        "message": f"Question #{q.id} status updated to {q.status}.",
        "question_id": q.id,
        "status": q.status,
        "reviewed_at": str(q.reviewed_at) if q.reviewed_at else None,
        "question": {
            "id": q.id,
            "status": q.status,
            "title": q.title,
            "reviewer_feedback": q.reviewer_feedback
        }
    }

@router.post("/{question_id}/publish")
def publish_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.REVIEW_QUESTION))
):
    """
    Publishes an APPROVED question to the active question bank so it can be scheduled in assessments.
    """
    q = db.query(Question).filter(Question.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found.")

    if q.status not in [QuestionStatus.APPROVED.value, QuestionStatus.DRAFT.value, QuestionStatus.AI_GENERATED.value]:
        raise HTTPException(status_code=400, detail=f"Cannot publish question in '{q.status}' status.")

    q.status = QuestionStatus.PUBLISHED.value
    db.commit()
    invalidate_questions_cache()

    return {
        "message": f"Question '{q.title}' is published to the USAR Question Bank.",
        "status": q.status,
        "question": {
            "id": q.id,
            "status": q.status,
            "title": q.title
        }
    }

@router.get("/{question_id}/versions", response_model=List[QuestionVersionOut], dependencies=[Depends(api_general_rate_limiter)])
def get_question_versions(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves full version history for a question.
    """
    q = db.query(Question).filter(Question.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found.")

    # Find root question ID
    root_id = q.parent_question_id if q.parent_question_id else q.id
    
    # Query all nodes in the version lineage
    versions = db.query(Question).filter(
        (Question.id == root_id) | (Question.parent_question_id == root_id) | (Question.parent_question_id == q.id)
    ).order_by(Question.version_number.desc()).all()

    return [
        QuestionVersionOut(
            id=v.id,
            version_number=v.version_number or 1,
            title=v.title,
            status=v.status,
            change_summary=v.change_summary,
            is_latest=v.is_latest if v.is_latest is not None else True,
            created_at=v.created_at
        )
        for v in versions
    ]

@router.get("/{question_id}/analytics", response_model=QuestionAnalyticsOut, dependencies=[Depends(api_general_rate_limiter)])
def get_question_analytics(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_ANALYTICS))
):
    """
    Returns attempt statistics, success rate, difficulty calibration, and discrimination index.
    """
    q = db.query(Question).filter(Question.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found.")

    total_att = q.total_attempts or 0
    correct_att = q.correct_attempts or 0
    success_rate = round((correct_att / max(total_att, 1)) * 100.0, 1) if total_att > 0 else 0.0
    diff_dev = round((q.experienced_difficulty or 5.0) - q.difficulty_score, 1)

    return QuestionAnalyticsOut(
        question_id=q.id,
        title=q.title,
        total_attempts=total_att,
        correct_attempts=correct_att,
        success_rate_percent=success_rate,
        average_time_seconds=q.average_time_seconds or 0.0,
        designed_difficulty=q.difficulty_score,
        experienced_difficulty=q.experienced_difficulty or 5.0,
        difficulty_deviation=diff_dev,
        discrimination_index=q.discrimination_index,
        skip_count=q.skip_count or 0,
        status=q.status,
        quality_score=q.quality_score or 0.0,
        quality_breakdown=q.quality_breakdown or {}
    )

@router.post("/{question_id}/feedback", response_model=QuestionFeedbackOut)
def submit_question_feedback(
    question_id: int,
    req: QuestionFeedbackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submits reviewer or faculty feedback on a question for continuous improvement.
    """
    q = db.query(Question).filter(Question.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found.")

    fb = QuestionFeedback(
        question_id=q.id,
        user_id=current_user.id,
        feedback_type=req.feedback_type,
        rating=req.rating,
        comment=req.comment,
        metrics_snapshot=req.metrics_snapshot or {}
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)

    return QuestionFeedbackOut(
        id=fb.id,
        question_id=fb.question_id,
        user_id=fb.user_id,
        feedback_type=fb.feedback_type,
        rating=fb.rating,
        comment=fb.comment,
        metrics_snapshot=fb.metrics_snapshot,
        created_at=fb.created_at
    )

@router.post("/{question_id}/validate")
def validate_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.REVIEW_QUESTION))
):
    """
    Executes the reference solutions against all visible and hidden test cases.
    """
    q = db.query(Question).filter(Question.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found.")

    tcs_data = [
        {
            "id": tc.id,
            "input": tc.input_data,
            "expected": tc.expected_output,
            "points": tc.points,
            "is_hidden": tc.is_hidden
        }
        for tc in q.test_cases
    ]

    val_report = code_runner.validate_reference_solution(q.reference_solutions, tcs_data)
    q.validation_status = val_report["status"]
    q.validation_notes = val_report["notes"]
    db.commit()
    invalidate_questions_cache()

    return val_report

@router.post("/{question_id}/approve")
def approve_question_legacy(
    question_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.REVIEW_QUESTION))
):
    """
    Legacy convenience endpoint to approve a question.
    """
    return review_question(
        question_id=question_id,
        req=QuestionReviewRequest(action="APPROVE", force=force, feedback="Approved via legacy review route"),
        db=db,
        current_user=current_user
    )

@router.post("/{question_id}/generate-solutions", response_model=MultiLangSolutionResult, dependencies=[Depends(ai_rate_limiter)])
def generate_multilang_solutions_for_question(
    question_id: int,
    req: MultiLangSolutionGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CREATE_QUESTION))
):
    q = db.query(Question).filter(Question.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found.")

    source_lang = req.source_language or "python"
    source_code = req.source_code
    if not source_code:
        if q.reference_solutions:
            source_code = q.reference_solutions.get(source_lang) or list(q.reference_solutions.values())[0]
        else:
            source_code = ""

    if not source_code or not source_code.strip():
        raise HTTPException(status_code=400, detail="No source reference solution provided or found on question.")

    generated_solutions = gemini_service.generate_multilang_solutions(
        problem_statement=q.problem_statement,
        input_format=q.input_format or "",
        output_format=q.output_format or "",
        constraints=q.constraints or "",
        examples=q.examples or [],
        source_code=source_code,
        source_lang=source_lang
    )

    updated_solutions = dict(q.reference_solutions or {})
    for lang_key, code_val in generated_solutions.items():
        if code_val and code_val.strip():
            updated_solutions[lang_key] = code_val

    q.reference_solutions = updated_solutions

    tcs_data = [
        {
            "id": tc.id,
            "input": tc.input_data,
            "expected": tc.expected_output,
            "points": tc.points,
            "is_hidden": tc.is_hidden
        }
        for tc in q.test_cases
    ]

    val_report = code_runner.validate_reference_solution(q.reference_solutions, tcs_data)
    q.validation_status = val_report["status"]
    q.validation_notes = val_report["notes"]
    db.commit()
    db.refresh(q)
    invalidate_questions_cache()

    return MultiLangSolutionResult(
        question_id=q.id,
        reference_solutions=q.reference_solutions,
        validation_report=val_report
    )

@router.delete("/{question_id}")
def delete_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.DELETE_QUESTION))
):
    q = db.query(Question).filter(Question.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found.")
    
    title = q.title
    db.delete(q)
    db.commit()
    invalidate_questions_cache()
    return {"message": f"Question '{title}' deleted successfully."}
