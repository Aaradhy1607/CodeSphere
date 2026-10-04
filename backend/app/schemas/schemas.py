from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import List, Optional, Dict, Any, Union
from datetime import datetime

# ================= AUTH & USER SCHEMAS =================
class UserBase(BaseModel):
    email: EmailStr
    full_name: str

class UserCreate(UserBase):
    password: Optional[str] = None
    role: str = "STUDENT"

class StudentProfileCreate(BaseModel):
    enrollment_no: str
    branch: str = Field(..., description="AIML, AIDS, IIOT, AR")
    academic_year: int = Field(..., ge=1, le=4)
    phone: Optional[str] = None

class StudentProfileOut(StudentProfileCreate):
    id: int
    is_approved: bool
    total_events_participated: int
    total_lifetime_score: float
    total_problems_solved: int
    average_score: float
    consistency_score: float
    placement_readiness_rating: str

    model_config = ConfigDict(from_attributes=True)

class UserOut(UserBase):
    id: int
    role: str
    status: str = "ACTIVE"
    is_active: bool
    avatar_url: Optional[str] = None
    permissions: List[str] = []
    created_at: datetime
    last_login_at: Optional[datetime] = None
    student_profile: Optional[StudentProfileOut] = None

    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user: UserOut
    permissions: List[str] = []
    needs_onboarding: bool = False

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirmRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6)

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6)

class UpdateUserRoleRequest(BaseModel):
    role: str = Field(..., description="STUDENT, FACULTY, QUESTION_SETTER, REVIEWER, PLACEMENT_ADMIN, ADMIN, SUPER_ADMIN")

class UpdateUserStatusRequest(BaseModel):
    status: str = Field(..., description="ACTIVE, DISABLED, PENDING_VERIFICATION")

class AuditLogOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    actor_email: str
    action: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status: str
    details: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class LoginRequest(BaseModel):
    email: str = Field(..., description="Institutional email address or student enrollment number")
    password: str = Field(..., min_length=1, description="Institutional account password")

class GoogleAuthRequest(BaseModel):
    credential: str = Field(..., min_length=1, description="Verified Google OIDC ID token")
    email: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    enrollment_no: Optional[str] = None
    branch: Optional[str] = None
    academic_year: Optional[int] = None

class StudentOnboardingRequest(BaseModel):
    full_name: str
    enrollment_no: str
    branch: str = Field(..., description="AIML, AIDS, IIOT, AR")
    academic_year: int = Field(..., ge=1, le=4)
    phone: Optional[str] = None

class AdminAllowlistCreate(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    assigned_role: str = "ADMIN"

class AdminAllowlistOut(BaseModel):
    id: int
    email: str
    name: Optional[str] = None
    assigned_role: str = "ADMIN"
    added_by: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ================= TEST CASE SCHEMAS =================
class TestCaseBase(BaseModel):
    input_data: str
    expected_output: str
    is_hidden: bool = False
    category: Optional[str] = "NORMAL"
    explanation: Optional[str] = None
    points: int = 10

class TestCaseCreate(TestCaseBase):
    pass

class TestCaseOut(TestCaseBase):
    id: int
    question_id: int

    model_config = ConfigDict(from_attributes=True)


# ================= QUESTION SCHEMAS =================
class ExampleCase(BaseModel):
    input: str
    output: str
    explanation: Optional[str] = None

class MCQOption(BaseModel):
    id: str = "A" # A, B, C, D
    text: str
    is_correct: bool = False

class QuestionBase(BaseModel):
    title: str
    problem_statement: str
    input_format: Optional[str] = ""
    output_format: Optional[str] = ""
    constraints: Optional[str] = ""
    
    # Question Taxonomy & Configuration
    question_type: str = "CODING" # CODING, MCQ, SUBJECTIVE
    subject: Optional[str] = "Data Structures & Algorithms"
    topic: Optional[str] = None
    subtopic: Optional[str] = None
    blooms_level: Optional[str] = "APPLY" # REMEMBER, UNDERSTAND, APPLY, ANALYZE, EVALUATE, CREATE
    
    # Grading & Timing
    marks: int = 100
    negative_marks: float = 0.0
    time_estimate_minutes: int = 30
    learning_objective: Optional[str] = None
    concept_tags: List[str] = []
    
    # MCQ / Subjective
    options: List[Union[Dict[str, Any], str]] = []
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    
    # Multimodal / Image
    image_url: Optional[str] = None
    image_metadata: Optional[Dict[str, Any]] = None
    
    # Coding Specific Fields
    examples: List[Dict[str, Any]] = []
    topic_tags: List[str] = []
    difficulty_score: int = Field(5, ge=1, le=10)
    expected_time_complexity: str = "O(N)"
    expected_space_complexity: str = "O(1)"
    time_limit_seconds: float = 2.0
    memory_limit_mb: int = 256
    reference_solutions: Dict[str, str] = {} # e.g. {"python": "...", "cpp": "..."}
    status: str = "DRAFT" # DRAFT, AI_GENERATED, PENDING_REVIEW, APPROVED, REJECTED, PUBLISHED, ARCHIVED

class QuestionCreate(QuestionBase):
    test_cases: List[TestCaseCreate] = []
    change_summary: Optional[str] = None

class QuestionUpdate(BaseModel):
    title: Optional[str] = None
    problem_statement: Optional[str] = None
    input_format: Optional[str] = None
    output_format: Optional[str] = None
    constraints: Optional[str] = None
    question_type: Optional[str] = None
    subject: Optional[str] = None
    topic: Optional[str] = None
    subtopic: Optional[str] = None
    blooms_level: Optional[str] = None
    marks: Optional[int] = None
    negative_marks: Optional[float] = None
    time_estimate_minutes: Optional[int] = None
    learning_objective: Optional[str] = None
    concept_tags: Optional[List[str]] = None
    options: Optional[List[Union[Dict[str, Any], str]]] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    image_url: Optional[str] = None
    image_metadata: Optional[Dict[str, Any]] = None
    examples: Optional[List[Dict[str, Any]]] = None
    topic_tags: Optional[List[str]] = None
    difficulty_score: Optional[int] = None
    expected_time_complexity: Optional[str] = None
    expected_space_complexity: Optional[str] = None
    reference_solutions: Optional[Dict[str, str]] = None
    status: Optional[str] = None
    validation_status: Optional[str] = None
    validation_notes: Optional[str] = None
    reviewer_feedback: Optional[str] = None
    rejection_reason: Optional[str] = None
    change_summary: Optional[str] = None

class QuestionOut(QuestionBase):
    id: int
    slug: str
    status: str
    validation_status: str
    validation_notes: Optional[str] = None
    is_ai_generated: bool
    quality_score: Optional[float] = 0.0
    quality_breakdown: Optional[Dict[str, Any]] = None
    similarity_score: Optional[float] = 0.0
    duplicate_of_id: Optional[int] = None
    version_number: int = 1
    parent_question_id: Optional[int] = None
    is_latest: bool = True
    author_id: Optional[int] = None
    reviewer_id: Optional[int] = None
    reviewer_feedback: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    total_attempts: Optional[int] = 0
    correct_attempts: Optional[int] = 0
    average_time_seconds: Optional[float] = 0.0
    experienced_difficulty: Optional[float] = 5.0
    discrimination_index: Optional[float] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    test_cases_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)

class QuestionDetailOut(QuestionOut):
    test_cases: List[TestCaseOut] = []

class QuestionReviewRequest(BaseModel):
    action: str = Field(..., description="APPROVE, REJECT, REQUEST_CHANGES")
    feedback: Optional[str] = None
    rejection_reason: Optional[str] = None
    force: bool = False

class QuestionPublishRequest(BaseModel):
    is_published: bool = True

class QuestionVersionOut(BaseModel):
    id: int
    version_number: int
    title: str
    status: str
    change_summary: Optional[str] = None
    is_latest: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class QuestionFeedbackCreate(BaseModel):
    feedback_type: str = "REVIEWER_NOTE" # REVIEWER_NOTE, FACULTY_REVIEW, QUALITY_AUDIT
    rating: int = Field(5, ge=1, le=5)
    comment: Optional[str] = None
    metrics_snapshot: Optional[Dict[str, Any]] = None

class QuestionFeedbackOut(BaseModel):
    id: int
    question_id: int
    user_id: Optional[int] = None
    feedback_type: str
    rating: int
    comment: Optional[str] = None
    metrics_snapshot: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DuplicateCheckRequest(BaseModel):
    title: str
    problem_statement: str
    topic: Optional[str] = None
    exclude_question_id: Optional[int] = None

class DuplicateCheckResult(BaseModel):
    is_duplicate: bool
    similarity_score: float
    matched_question_id: Optional[int] = None
    matched_title: Optional[str] = None
    match_reason: str
    normalized_similarity_percent: float
    category: Optional[str] = "UNIQUE"
    level_1_exact: Optional[bool] = False
    level_2_lexical: Optional[float] = 0.0
    level_3_semantic: Optional[float] = 0.0

class QuestionAnalyticsOut(BaseModel):
    question_id: int
    title: str
    total_attempts: int
    correct_attempts: int
    success_rate_percent: float
    average_time_seconds: float
    designed_difficulty: int
    experienced_difficulty: float
    difficulty_deviation: float
    discrimination_index: Optional[float] = None
    skip_count: int
    status: str
    quality_score: float
    quality_breakdown: Dict[str, Any]

class ImageUploadResponse(BaseModel):
    image_url: str
    filename: str
    size_bytes: int
    mime_type: str

# ================= AI GENERATION SCHEMAS =================
class AIQuestionGenerateRequest(BaseModel):
    subject: Optional[str] = "Data Structures & Algorithms"
    topic: str = "Dynamic Programming"
    sub_topic: Optional[str] = "Grid & Subsequence optimization"
    difficulty_score: int = Field(5, ge=1, le=10) # 1-3 Easy, 4-7 Medium, 8-10 Hard
    relative_difficulty: str = Field("similar", description="easier, similar, harder")
    question_type: str = "CODING" # CODING, MCQ, SUBJECTIVE
    blooms_level: Optional[str] = "APPLY"
    marks: int = 100
    negative_marks: float = 0.0
    time_estimate_minutes: int = 30
    learning_objective: Optional[str] = None
    concept_tags: List[str] = []
    reference_blueprint: Optional[str] = None
    target_branch: Optional[str] = "ALL"
    target_year: Optional[int] = 0
    language_focus: Optional[str] = "python"
    image_base64: Optional[str] = None # Optional base64 encoded diagram for multimodal analysis
    image_mime_type: Optional[str] = None

class AIQuestionValidationResult(BaseModel):
    is_valid: bool
    status: str
    details: List[Dict[str, Any]] = []
    validation_notes: str
    language_results: Optional[Dict[str, Any]] = None
    failing_details: Optional[List[Dict[str, Any]]] = None
    quality_score: Optional[float] = 0.0
    quality_breakdown: Optional[Dict[str, Any]] = None
    similarity_result: Optional[Dict[str, Any]] = None

class MultiLangSolutionGenerateRequest(BaseModel):
    source_code: Optional[str] = None
    source_language: Optional[str] = "python"

class MultiLangSolutionResult(BaseModel):
    question_id: int
    reference_solutions: Dict[str, str]
    validation_report: Dict[str, Any]


# ================= EVENT SCHEMAS =================
class EventQuestionLink(BaseModel):
    question_id: int
    branch_override: Optional[str] = "ALL"
    year_override: Optional[int] = 0
    points: int = 100
    order_index: int = 0

class EventBase(BaseModel):
    title: str
    description: Optional[str] = None
    target_branch: str = "ALL" # ALL, AIML, AIDS, IIOT, AR
    target_year: int = 0       # 0 for ALL, 1, 2, 3, 4
    start_time: datetime
    end_time: datetime
    duration_minutes: int = 120
    is_leaderboard_visible: bool = True
    allow_branch_questions: bool = False

class EventCreate(EventBase):
    questions: List[EventQuestionLink] = []

class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    target_branch: Optional[str] = None
    target_year: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    status: Optional[str] = None
    is_leaderboard_visible: Optional[bool] = None
    are_solutions_released: Optional[bool] = None
    are_results_released: Optional[bool] = None
    questions: Optional[List[EventQuestionLink]] = None

class EventOut(EventBase):
    id: int
    status: str
    are_solutions_released: bool
    are_results_released: bool
    created_at: datetime
    total_questions: int = 0
    total_participants: int = 0

    model_config = ConfigDict(from_attributes=True)

class EventDetailOut(EventOut):
    questions: List[Dict[str, Any]] = []

# ================= CODE EXECUTION SCHEMAS =================
class CodeRunRequest(BaseModel):
    question_id: int
    code: str
    language: str # python, cpp, c, java
    custom_input: Optional[str] = None

class CodeRunResult(BaseModel):
    verdict: str
    passed: bool
    execution_time_ms: float
    memory_used_kb: float
    output: str
    expected_output: Optional[str] = None
    error_message: Optional[str] = None
    sample_results: List[Dict[str, Any]] = []

class FinalSubmitRequest(BaseModel):
    event_id: int
    question_id: int
    code: str
    language: str

class FinalSubmitResult(BaseModel):
    submission_id: int
    verdict: str
    score: float
    passed_test_cases: int
    total_test_cases: int
    execution_time_ms: float
    error_message: Optional[str] = None
    is_final: bool

class AsyncSubmitResult(BaseModel):
    submission_id: int
    status: str
    message: str = "Submission queued for evaluation."
    enqueued_at: datetime

class SubmissionStatusOut(BaseModel):
    submission_id: int
    status: str
    verdict: Optional[str] = None
    passed_test_cases: int = 0
    total_test_cases: int = 0
    score: float = 0.0
    execution_time_ms: float = 0.0
    memory_used_kb: float = 0.0
    error_message: Optional[str] = None
    is_final: bool = True
    submitted_at: datetime
    test_case_results: Optional[List[Dict[str, Any]]] = None

    model_config = ConfigDict(from_attributes=True)

class JudgeMetricsOut(BaseModel):
    queued_submissions: int
    running_submissions: int
    completed_submissions: int
    failed_submissions: int
    total_processed: int
    average_queue_wait_ms: float
    average_execution_time_ms: float
    peak_memory_kb: float
    sandbox_failures: int
    active_workers: int
    sandbox_backend: str
    docker_available: bool

class SubmissionOut(BaseModel):
    id: int
    event_id: int
    question_id: int
    question_title: Optional[str] = None
    user_id: int
    student_name: Optional[str] = None
    enrollment_no: Optional[str] = None
    branch: Optional[str] = None
    language: str
    code: str
    verdict: str
    status: Optional[str] = "COMPLETED"
    passed_test_cases: int
    total_test_cases: int
    score: float
    execution_time_ms: float
    error_message: Optional[str] = None
    is_final: bool
    submitted_at: datetime
    reference_solution: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# ================= LEADERBOARD SCHEMAS =================
class LeaderboardEntry(BaseModel):
    rank: int
    user_id: int
    full_name: str
    enrollment_no: str
    branch: str
    academic_year: int
    total_score: float
    problems_solved: int
    total_time_ms: float
    last_submission_time: Optional[datetime] = None

class LifetimeLeaderboardEntry(BaseModel):
    rank: int
    user_id: int
    full_name: str
    enrollment_no: str
    branch: str
    academic_year: int
    events_participated: int
    total_lifetime_score: float
    total_problems_solved: int
    average_score: float
    consistency_score: float
    placement_readiness_rating: str

# ================= REPORT & ANALYTICS SCHEMAS =================
class StudentReportOut(BaseModel):
    id: int
    event_id: int
    event_title: Optional[str] = None
    user_id: int
    student_name: Optional[str] = None
    enrollment_no: Optional[str] = None
    branch: Optional[str] = None
    academic_year: Optional[int] = None
    score: float
    rank: int
    total_participants: int
    overall_performance_summary: str
    strengths: List[str]
    areas_for_improvement: List[str]
    topic_performance: Dict[str, str]
    time_efficiency_rating: str
    problem_solving_pattern: Optional[str] = None
    difficulty_handling: Optional[str] = None
    comparative_analysis: Optional[str] = None
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class StudentComparisonOut(BaseModel):
    id: int
    student_id: int
    user_id: int
    full_name: str
    name: str
    email: str
    enrollment_no: str
    branch: str
    academic_year: int
    total_score: float
    total_lifetime_score: float
    total_events: int
    total_solved: int
    average_score: float
    consistency: float
    placement_readiness: str
    readiness: str
    recent_scores: List[float] = []
    strengths: List[str] = []
    topic_mastery: Dict[str, float] = {}

class PlacementAnalyticsOut(BaseModel):
    total_registered_students: int
    total_events_conducted: int
    total_submissions: int
    branch_performance: Dict[str, Dict[str, Any]] # e.g. {"AIML": {"avg_score": 82, "students": 45}}
    year_performance: Dict[int, Dict[str, Any]]
    topic_mastery: Dict[str, float] # Calculated dynamically from real submissions & questions
    top_performers: List[LifetimeLeaderboardEntry]
    needs_attention_students: List[LifetimeLeaderboardEntry]

# =====================================================================
# PHASE 5 SECURE ASSESSMENT ENGINE SCHEMAS
# =====================================================================

class AssessmentQuestionInput(BaseModel):
    question_id: int
    section_name: Optional[str] = "General"
    order_index: Optional[int] = 0
    marks: Optional[float] = 10.0
    negative_marks: Optional[float] = 0.0
    is_mandatory: Optional[bool] = True

class AssessmentBase(BaseModel):
    title: str
    description: Optional[str] = None
    instructions: Optional[str] = None
    duration_minutes: int = Field(60, ge=1, le=1440)
    start_time: datetime
    end_time: datetime
    max_attempts: int = Field(1, ge=1, le=10)
    passing_score: float = Field(50.0, ge=0.0, le=100.0)
    total_marks: float = 100.0
    negative_marking: bool = False
    negative_mark_rate: float = 0.25
    randomize_questions: bool = True
    randomize_options: bool = True
    allowed_languages: List[str] = ["python", "cpp", "c", "java"]
    candidate_assignment: Dict[str, Any] = {"type": "ALL", "targets": []}
    anti_cheat_policy: Dict[str, Any] = {
        "max_tab_switches": 5,
        "action": "WARN",
        "require_fullscreen": True,
        "block_clipboard": True
    }
    show_results_immediately: bool = False
    allow_review: bool = False

class AssessmentCreate(AssessmentBase):
    questions: List[AssessmentQuestionInput] = []

class AssessmentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    instructions: Optional[str] = None
    duration_minutes: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    max_attempts: Optional[int] = None
    passing_score: Optional[float] = None
    total_marks: Optional[float] = None
    negative_marking: Optional[bool] = None
    negative_mark_rate: Optional[float] = None
    randomize_questions: Optional[bool] = None
    randomize_options: Optional[bool] = None
    allowed_languages: Optional[List[str]] = None
    candidate_assignment: Optional[Dict[str, Any]] = None
    anti_cheat_policy: Optional[Dict[str, Any]] = None
    show_results_immediately: Optional[bool] = None
    allow_review: Optional[bool] = None
    status: Optional[str] = None
    questions: Optional[List[AssessmentQuestionInput]] = None

class AssessmentQuestionOut(BaseModel):
    id: int
    question_id: int
    title: str
    slug: str
    problem_statement: str
    question_type: str
    subject: Optional[str] = None
    topic: Optional[str] = None
    blooms_level: Optional[str] = None
    section_name: str = "General"
    order_index: int = 0
    marks: float = 10.0
    negative_marks: float = 0.0
    is_mandatory: bool = True
    options: List[Dict[str, Any]] = [] # Sanitized options for exam session
    input_format: Optional[str] = ""
    output_format: Optional[str] = ""
    constraints: Optional[str] = ""
    examples: List[Dict[str, Any]] = []
    visible_test_cases: List[Dict[str, Any]] = []
    image_url: Optional[str] = None

class AssessmentOut(AssessmentBase):
    id: int
    status: str
    created_by_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    total_questions: int = 0
    total_participants: int = 0
    user_attempt_status: Optional[str] = None
    user_attempt_id: Optional[str] = None
    user_score: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)

class AssessmentDetailOut(AssessmentOut):
    questions: List[AssessmentQuestionOut] = []

class AttemptStartRequest(BaseModel):
    session_token: Optional[str] = None

class AttemptStateOut(BaseModel):
    attempt_id: str
    assessment_id: int
    assessment_title: str
    status: str
    start_time: datetime
    expiry_time: datetime
    server_time: datetime
    remaining_seconds: int
    total_questions: int
    answered_question_ids: List[int]
    flagged_question_ids: List[int]
    saved_answers: Dict[str, Any] # {str(q_id): answer_data}
    questions: List[AssessmentQuestionOut]
    anti_cheat_policy: Dict[str, Any]
    integrity_score: float
    session_token: str
    current_session_token: Optional[str] = None
    tab_switch_count: Optional[int] = 0

class AnswerSaveRequest(BaseModel):
    question_id: int
    answer_data: Optional[Dict[str, Any]] = None
    selected_options: Optional[List[str]] = None
    selected_option: Optional[str] = None
    submitted_code: Optional[str] = None
    submitted_language: Optional[str] = None
    submitted_text: Optional[str] = None
    is_flagged: Optional[bool] = False
    time_spent_seconds: Optional[float] = None
    client_timestamp: Optional[datetime] = None

class AnswerSaveResponse(BaseModel):
    success: bool
    question_id: int
    saved_at: datetime
    version: int
    is_flagged: bool

class AntiCheatEventCreate(BaseModel):
    event_type: str
    severity: Optional[str] = "INFO"
    metadata_json: Optional[Dict[str, Any]] = None
    event_data: Optional[Dict[str, Any]] = None
    client_timestamp: Optional[datetime] = None

class AntiCheatEventOut(BaseModel):
    id: int
    attempt_id: str
    candidate_id: int
    event_type: str
    severity: str
    metadata_json: Dict[str, Any]
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)

class HeartbeatRequest(BaseModel):
    session_token: str
    current_question_id: Optional[int] = None

class HeartbeatResponse(BaseModel):
    valid: bool
    remaining_seconds: int
    status: str
    integrity_score: float
    is_active: Optional[bool] = True
    terminated: bool = False
    termination_reason: Optional[str] = None

class AssessmentSubmitRequest(BaseModel):
    final_sync: Optional[Dict[str, Any]] = None
    final_sync_answers: Optional[Any] = None

class AssessmentResultOut(BaseModel):
    id: int
    attempt_id: str
    assessment_id: int
    assessment_title: str
    candidate_name: str
    enrollment_no: Optional[str] = None
    branch: Optional[str] = None
    total_score: float
    max_score: float
    percentage: float
    accuracy: float
    passed: bool
    passing_score: float
    total_questions: int
    attempted_count: int
    correct_count: int
    incorrect_count: int
    skipped_count: int
    time_spent_seconds: float
    integrity_score: float
    question_breakdown: List[Dict[str, Any]] = []
    section_breakdown: Dict[str, Any] = {}
    difficulty_breakdown: Dict[str, Any] = {}
    topic_breakdown: Dict[str, Any] = {}
    percentile: Optional[float] = None
    rank: Optional[int] = None
    total_candidates: int = 1
    allow_review: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class MonitorCandidateOut(BaseModel):
    attempt_id: str
    candidate_id: int
    candidate_name: str
    candidate_email: str
    enrollment_no: Optional[str] = None
    branch: Optional[str] = None
    status: str
    start_time: datetime
    expiry_time: datetime
    remaining_seconds: int
    progress_percent: float
    answered_count: int
    total_questions: int
    integrity_score: float
    violations_count: int
    high_severity_violations: int
    last_heartbeat_at: Optional[datetime] = None
    client_ip: Optional[str] = None
    submitted_at: Optional[datetime] = None
    score: Optional[float] = None
    passed: Optional[bool] = None

class MonitorDashboardOut(BaseModel):
    assessment_id: int
    assessment_title: str
    status: str
    total_assigned: int
    total_started: int
    active_now: int
    submitted_count: int
    expired_count: int
    terminated_count: int
    average_score: Optional[float] = None
    average_integrity: float
    suspicious_candidates_count: int
    candidates: List[MonitorCandidateOut] = []

class AdminAttemptActionRequest(BaseModel):
    action: str = Field(..., description="EXTEND_TIME, TERMINATE, INVALIDATE, FORCE_SUBMIT")
    extend_minutes: Optional[int] = 10
    reason: Optional[str] = None

# ================= PHASE 7 SCHEMAS =================
class ProblemQualityReportOut(BaseModel):
    quality_score: float
    grade: str
    is_ready_for_review: bool
    breakdown: Dict[str, float]
    test_suite_report: Dict[str, Any]
    errors: List[str] = []
    warnings: List[str] = []

class DifficultyIntelligenceOut(BaseModel):
    question_id: int
    title: str
    author_difficulty_score: float
    author_difficulty_label: str
    has_sufficient_data: bool
    sample_count: int
    min_required_samples: Optional[int] = 5
    distinct_students: Optional[int] = 0
    observed_difficulty_score: Optional[float] = None
    observed_difficulty_label: Optional[str] = None
    difficulty_gap: Optional[float] = None
    acceptance_rate: Optional[float] = 0.0
    first_attempt_ac_rate: Optional[float] = 0.0
    avg_attempts_to_ac: Optional[float] = 0.0
    avg_execution_time_ms: Optional[float] = 0.0
    avg_memory_kb: Optional[float] = 0.0
    verdict_distribution: Dict[str, int] = {}
    language_breakdown: Dict[str, Any] = {}
    notes: Optional[str] = None

class TestCaseAnalysisOut(BaseModel):
    quality_score: float
    grade: str
    is_valid: bool
    total_count: int
    visible_count: int
    hidden_count: int
    total_points: int
    categories_present: List[str] = []
    missing_categories: List[str] = []
    duplicate_pairs: List[Dict[str, Any]] = []
    errors: List[str] = []
    warnings: List[str] = []

class ContestQualityReportOut(BaseModel):
    assessment_id: int
    assessment_title: str
    problem_count: int
    quality_score: float
    grade: str
    is_ready_to_publish: bool
    difficulty_spread: Dict[str, Any] = {}
    topic_distribution: Dict[str, int] = {}
    time_budget: Dict[str, Any] = {}
    duplicate_pairs: List[Dict[str, Any]] = []
    weak_test_problems: List[Dict[str, Any]] = []
    errors: List[str] = []
    warnings: List[str] = []

class SubmissionHistoryItemOut(BaseModel):
    attempt_number: int
    submission_id: int
    submitted_at: Optional[str] = None
    language: str
    verdict: str
    score: Optional[float] = 0.0
    execution_time_ms: float
    time_limit_ms: float
    time_utilization_percent: float
    memory_used_kb: float
    memory_limit_kb: float
    memory_utilization_percent: float
    test_cases_passed: int
    test_cases_total: int
    code_heuristics: Dict[str, Any] = {}
    error_message: Optional[str] = None

class StudentSubmissionHistoryOut(BaseModel):
    question_id: int
    question_title: str
    total_submissions: int
    has_accepted: bool
    best_execution_time_ms: Optional[float] = None
    best_memory_kb: Optional[float] = None
    improvement_note: Optional[str] = None
    history: List[SubmissionHistoryItemOut] = []

