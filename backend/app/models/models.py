import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Float, Enum, JSON,
    Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum

class UserRole(str, enum.Enum):
    STUDENT = "STUDENT"
    FACULTY = "FACULTY"
    QUESTION_SETTER = "QUESTION_SETTER"
    REVIEWER = "REVIEWER"
    PLACEMENT_ADMIN = "PLACEMENT_ADMIN"
    ADMIN = "ADMIN"
    SUPER_ADMIN = "SUPER_ADMIN"

class AccountStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"

class Permission(str, enum.Enum):
    # Student Data
    VIEW_STUDENTS = "VIEW_STUDENTS"
    MANAGE_STUDENTS = "MANAGE_STUDENTS"
    EXPORT_STUDENT_DATA = "EXPORT_STUDENT_DATA"

    # Questions & AI Lab
    VIEW_QUESTIONS = "VIEW_QUESTIONS"
    CREATE_QUESTION = "CREATE_QUESTION"
    EDIT_QUESTION = "EDIT_QUESTION"
    DELETE_QUESTION = "DELETE_QUESTION"
    REVIEW_QUESTION = "REVIEW_QUESTION"

    # Assessment Rounds
    CREATE_ASSESSMENT = "CREATE_ASSESSMENT"
    EDIT_ASSESSMENT = "EDIT_ASSESSMENT"
    PUBLISH_ASSESSMENT = "PUBLISH_ASSESSMENT"
    DELETE_ASSESSMENT = "DELETE_ASSESSMENT"
    VIEW_ASSESSMENT_RESULTS = "VIEW_ASSESSMENT_RESULTS"

    # Code Execution
    SUBMIT_CODE = "SUBMIT_CODE"
    VIEW_OWN_SUBMISSIONS = "VIEW_OWN_SUBMISSIONS"
    VIEW_ALL_SUBMISSIONS = "VIEW_ALL_SUBMISSIONS"

    # Analytics & Reports
    VIEW_ANALYTICS = "VIEW_ANALYTICS"
    VIEW_PLACEMENT_ANALYTICS = "VIEW_PLACEMENT_ANALYTICS"

    # System & User Administration
    MANAGE_USERS = "MANAGE_USERS"
    MANAGE_ROLES = "MANAGE_ROLES"
    VIEW_AUDIT_LOGS = "VIEW_AUDIT_LOGS"
    MANAGE_SYSTEM_SETTINGS = "MANAGE_SYSTEM_SETTINGS"

ROLE_PERMISSIONS: dict[str, list[Permission]] = {
    UserRole.STUDENT.value: [
        Permission.SUBMIT_CODE,
        Permission.VIEW_OWN_SUBMISSIONS,
    ],
    UserRole.FACULTY.value: [
        Permission.VIEW_STUDENTS,
        Permission.VIEW_QUESTIONS,
        Permission.VIEW_ASSESSMENT_RESULTS,
        Permission.VIEW_ANALYTICS,
        Permission.VIEW_PLACEMENT_ANALYTICS,
    ],
    UserRole.QUESTION_SETTER.value: [
        Permission.VIEW_QUESTIONS,
        Permission.CREATE_QUESTION,
        Permission.EDIT_QUESTION,
        Permission.SUBMIT_CODE,
    ],
    UserRole.REVIEWER.value: [
        Permission.VIEW_QUESTIONS,
        Permission.EDIT_QUESTION,
        Permission.REVIEW_QUESTION,
        Permission.SUBMIT_CODE,
    ],
    UserRole.PLACEMENT_ADMIN.value: [
        Permission.VIEW_STUDENTS,
        Permission.MANAGE_STUDENTS,
        Permission.EXPORT_STUDENT_DATA,
        Permission.VIEW_QUESTIONS,
        Permission.CREATE_ASSESSMENT,
        Permission.EDIT_ASSESSMENT,
        Permission.PUBLISH_ASSESSMENT,
        Permission.VIEW_ASSESSMENT_RESULTS,
        Permission.VIEW_ANALYTICS,
        Permission.VIEW_PLACEMENT_ANALYTICS,
        Permission.VIEW_ALL_SUBMISSIONS,
    ],
    UserRole.ADMIN.value: [
        Permission.VIEW_STUDENTS,
        Permission.MANAGE_STUDENTS,
        Permission.EXPORT_STUDENT_DATA,
        Permission.VIEW_QUESTIONS,
        Permission.CREATE_QUESTION,
        Permission.EDIT_QUESTION,
        Permission.DELETE_QUESTION,
        Permission.REVIEW_QUESTION,
        Permission.CREATE_ASSESSMENT,
        Permission.EDIT_ASSESSMENT,
        Permission.PUBLISH_ASSESSMENT,
        Permission.DELETE_ASSESSMENT,
        Permission.VIEW_ASSESSMENT_RESULTS,
        Permission.SUBMIT_CODE,
        Permission.VIEW_OWN_SUBMISSIONS,
        Permission.VIEW_ALL_SUBMISSIONS,
        Permission.VIEW_ANALYTICS,
        Permission.VIEW_PLACEMENT_ANALYTICS,
        Permission.MANAGE_USERS,
    ],
    UserRole.SUPER_ADMIN.value: [
        Permission.VIEW_STUDENTS,
        Permission.MANAGE_STUDENTS,
        Permission.EXPORT_STUDENT_DATA,
        Permission.VIEW_QUESTIONS,
        Permission.CREATE_QUESTION,
        Permission.EDIT_QUESTION,
        Permission.DELETE_QUESTION,
        Permission.REVIEW_QUESTION,
        Permission.CREATE_ASSESSMENT,
        Permission.EDIT_ASSESSMENT,
        Permission.PUBLISH_ASSESSMENT,
        Permission.DELETE_ASSESSMENT,
        Permission.VIEW_ASSESSMENT_RESULTS,
        Permission.SUBMIT_CODE,
        Permission.VIEW_OWN_SUBMISSIONS,
        Permission.VIEW_ALL_SUBMISSIONS,
        Permission.VIEW_ANALYTICS,
        Permission.VIEW_PLACEMENT_ANALYTICS,
        Permission.MANAGE_USERS,
        Permission.MANAGE_ROLES,
        Permission.VIEW_AUDIT_LOGS,
        Permission.MANAGE_SYSTEM_SETTINGS,
    ],
}

def get_permissions_for_role(role: str) -> list[str]:
    role_key = str(role).upper()
    perms = ROLE_PERMISSIONS.get(role_key, [])
    return [p.value for p in perms]

class Branch(str, enum.Enum):
    AIML = "AIML"
    AIDS = "AIDS"
    IIOT = "IIOT"
    AR = "AR"
    ALL = "ALL"

class EventStatus(str, enum.Enum):
    UPCOMING = "UPCOMING"
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"
    RESULTS_RELEASED = "RESULTS_RELEASED"

class QuestionType(str, enum.Enum):
    CODING = "CODING"
    MCQ = "MCQ"
    SUBJECTIVE = "SUBJECTIVE"

class BloomsLevel(str, enum.Enum):
    REMEMBER = "REMEMBER"
    UNDERSTAND = "UNDERSTAND"
    APPLY = "APPLY"
    ANALYZE = "ANALYZE"
    EVALUATE = "EVALUATE"
    CREATE = "CREATE"

class QuestionStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    AI_GENERATED = "AI_GENERATED"
    PENDING_REVIEW = "PENDING_REVIEW"
    UNDER_REVIEW = "PENDING_REVIEW"  # backward compatibility alias
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"

class ValidationStatus(str, enum.Enum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"

class AssessmentStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"
    PUBLISHED = "PUBLISHED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"

class AttemptStatus(str, enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    EXPIRED = "EXPIRED"
    TERMINATED = "TERMINATED"
    INVALIDATED = "INVALIDATED"

class AntiCheatEventType(str, enum.Enum):
    TAB_BLUR = "TAB_BLUR"
    TAB_VISIBILITY_CHANGE = "TAB_VISIBILITY_CHANGE"
    FULLSCREEN_EXIT = "FULLSCREEN_EXIT"
    COPY = "COPY"
    PASTE = "PASTE"
    CUT = "CUT"
    RIGHT_CLICK = "RIGHT_CLICK"
    KEYBOARD_SHORTCUT = "KEYBOARD_SHORTCUT"
    SUSPICIOUS_NAVIGATION = "SUSPICIOUS_NAVIGATION"
    RECONNECT = "RECONNECT"
    MULTIPLE_SESSIONS = "MULTIPLE_SESSIONS"
    SESSION_ANOMALY = "SESSION_ANOMALY"

class AntiCheatSeverity(str, enum.Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class SubmissionVerdict(str, enum.Enum):
    AC = "Accepted"
    WA = "Wrong Answer"
    TLE = "Time Limit Exceeded"
    MLE = "Memory Limit Exceeded"
    OLE = "Output Limit Exceeded"
    CE = "Compilation Error"
    RE = "Runtime Error"
    PENDING = "Pending"

class SubmissionStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    COMPILING = "COMPILING"
    RUNNING = "RUNNING"
    EVALUATING = "EVALUATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class TestCaseCategory(str, enum.Enum):
    NORMAL = "NORMAL"
    BOUNDARY = "BOUNDARY"
    MINIMUM = "MINIMUM"
    MAXIMUM = "MAXIMUM"
    EMPTY = "EMPTY"
    SINGLETON = "SINGLETON"
    DUPLICATE = "DUPLICATE"
    SORTED = "SORTED"
    REVERSE_SORTED = "REVERSE_SORTED"
    ADVERSARIAL = "ADVERSARIAL"
    OVERFLOW = "OVERFLOW"
    PERFORMANCE = "PERFORMANCE"
    RANDOM = "RANDOM"


class AdminAllowlist(Base):
    __tablename__ = "admin_allowlist"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=True)
    assigned_role = Column(String(50), default=UserRole.ADMIN.value, nullable=False)
    added_by = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_role_status", "role", "status"),
        Index("ix_users_email_status", "email", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), default=UserRole.STUDENT.value, nullable=False, index=True)
    status = Column(String(50), default=AccountStatus.ACTIVE.value, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))

    student_profile = relationship("StudentProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    submissions = relationship("Submission", back_populates="user", cascade="all, delete-orphan")
    reports = relationship("StudentReport", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    password_reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("ix_refresh_tokens_user_revoked", "user_id", "is_revoked"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    token_hash = Column(String(255), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    is_revoked = Column(Boolean, default=False, nullable=False)
    replaced_by_hash = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    user = relationship("User", back_populates="refresh_tokens")

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        Index("ix_password_reset_user_used", "user_id", "is_used"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    token_hash = Column(String(255), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    user = relationship("User", back_populates="password_reset_tokens")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_action_created", "action", "created_at"),
        Index("ix_audit_logs_actor_created", "actor_email", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_email = Column(String(255), nullable=False, index=True)
    action = Column(String(100), nullable=False, index=True) # e.g. LOGIN_SUCCESS, LOGIN_FAILED, LOGOUT, ROLE_CHANGED, STATUS_CHANGED, PASSWORD_RESET
    ip_address = Column(String(100), nullable=True)
    user_agent = Column(String(500), nullable=True)
    status = Column(String(50), default="SUCCESS", index=True) # SUCCESS, FAILED, WARNING
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), index=True)

class StudentProfile(Base):
    __tablename__ = "student_profiles"
    __table_args__ = (
        Index("ix_student_profiles_branch_year", "branch", "academic_year"),
        Index("ix_student_profiles_score", "total_lifetime_score"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    enrollment_no = Column(String(50), unique=True, index=True, nullable=False)
    branch = Column(String(50), nullable=False, index=True)  # AIML, AIDS, IIOT, AR
    academic_year = Column(Integer, nullable=False, index=True)  # 1, 2, 3, 4
    phone = Column(String(20), nullable=True)
    is_approved = Column(Boolean, default=True)
    
    # Lifetime Analytics Aggregate fields
    total_events_participated = Column(Integer, default=0)
    total_lifetime_score = Column(Float, default=0.0)
    total_problems_solved = Column(Integer, default=0)
    average_score = Column(Float, default=0.0)
    consistency_score = Column(Float, default=100.0) # 0-100 index
    placement_readiness_rating = Column(String(50), default="Developing") # Ready, High Potential, Developing, Needs Focus
    
    user = relationship("User", back_populates="student_profile")

class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_status_start", "status", "start_time"),
        Index("ix_events_branch_year", "target_branch", "target_year"),
    )

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    target_branch = Column(String(50), default="ALL", index=True)  # ALL, AIML, AIDS, IIOT, AR
    target_year = Column(Integer, default=0, index=True)  # 0 for ALL, 1, 2, 3, 4
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False, index=True)
    duration_minutes = Column(Integer, default=120)
    status = Column(String(50), default=EventStatus.UPCOMING, index=True)
    
    # Flags & Controls
    allow_branch_questions = Column(Boolean, default=False)
    is_leaderboard_visible = Column(Boolean, default=True)
    are_solutions_released = Column(Boolean, default=False)
    are_results_released = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    event_questions = relationship("EventQuestion", back_populates="event", cascade="all, delete-orphan")
    submissions = relationship("Submission", back_populates="event", cascade="all, delete-orphan")
    reports = relationship("StudentReport", back_populates="event", cascade="all, delete-orphan")

class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        Index("ix_questions_status_diff", "status", "difficulty_score"),
        Index("ix_questions_validation", "validation_status"),
        Index("ix_questions_type_status", "question_type", "status"),
        Index("ix_questions_similarity_hash", "similarity_hash"),
        Index("ix_questions_versioning", "parent_question_id", "version_number"),
    )

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, index=True, nullable=False)
    problem_statement = Column(Text, nullable=False)
    input_format = Column(Text, nullable=False, default="")
    output_format = Column(Text, nullable=False, default="")
    constraints = Column(Text, nullable=False, default="")
    
    # Question Taxonomy & Categorization
    question_type = Column(String(50), default=QuestionType.CODING.value, index=True) # CODING, MCQ, SUBJECTIVE
    subject = Column(String(100), default="Data Structures & Algorithms", index=True)
    topic = Column(String(100), nullable=True, index=True)
    subtopic = Column(String(100), nullable=True)
    blooms_level = Column(String(50), default=BloomsLevel.APPLY.value) # REMEMBER, UNDERSTAND, APPLY, ANALYZE, EVALUATE, CREATE
    
    # Grading & Timing
    marks = Column(Integer, default=100)
    negative_marks = Column(Float, default=0.0)
    time_estimate_minutes = Column(Integer, default=30)
    learning_objective = Column(Text, nullable=True)
    concept_tags = Column(JSON, default=list) # ["Sliding Window", "Prefix Sum"]
    
    # MCQ / Subjective Specific Fields
    options = Column(JSON, default=list) # [{"id": "A", "text": "...", "is_correct": bool}]
    correct_answer = Column(Text, nullable=True) # "A" or model answer for subjective
    explanation = Column(Text, nullable=True) # Detailed solution explanation
    
    # Multimodal / Image Support
    image_url = Column(String(500), nullable=True)
    image_metadata = Column(JSON, nullable=True) # {filename, size_bytes, mime_type, uploaded_at}
    
    # Structured JSON fields for Coding
    examples = Column(JSON, default=list)  # [{input, output, explanation}]
    topic_tags = Column(JSON, default=list)  # ["Arrays", "Dynamic Programming", "Trees", etc.]
    
    difficulty_score = Column(Integer, default=5, index=True)  # 1-10 slider
    expected_time_complexity = Column(String(100), default="O(N)")
    expected_space_complexity = Column(String(100), default="O(1)")
    
    time_limit_seconds = Column(Float, default=2.0)
    memory_limit_mb = Column(Integer, default=256)
    
    # Reference solutions for multiple languages: {"python": "...", "cpp": "...", "java": "...", "c": "..."}
    reference_solutions = Column(JSON, default=dict)
    
    # Review & Lifecycle Status
    status = Column(String(50), default=QuestionStatus.DRAFT.value, index=True)
    validation_status = Column(String(50), default=ValidationStatus.PENDING.value, index=True)
    validation_notes = Column(Text, nullable=True)
    
    # Quality Scoring & Deduplication
    quality_score = Column(Float, default=0.0) # 0-100 deterministic quality score
    quality_breakdown = Column(JSON, default=dict) # {completeness, clarity, correctness, difficulty_consistency, test_coverage, notes}
    similarity_hash = Column(String(64), nullable=True)
    similarity_score = Column(Float, default=0.0)
    duplicate_of_id = Column(Integer, ForeignKey("questions.id", ondelete="SET NULL"), nullable=True)
    
    # Versioning & Audit
    version_number = Column(Integer, default=1)
    parent_question_id = Column(Integer, ForeignKey("questions.id", ondelete="SET NULL"), nullable=True)
    is_latest = Column(Boolean, default=True, index=True)
    change_summary = Column(String(255), nullable=True)
    
    # Reviewer Audit
    author_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewer_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewer_feedback = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Self-Improving Adaptive Feedback & Signals
    total_attempts = Column(Integer, default=0)
    correct_attempts = Column(Integer, default=0)
    average_time_seconds = Column(Float, default=0.0)
    experienced_difficulty = Column(Float, default=5.0) # Calibrated dynamically from attempts
    discrimination_index = Column(Float, nullable=True)
    skip_count = Column(Integer, default=0)
    
    # AI Generation metadata
    is_ai_generated = Column(Boolean, default=False)
    ai_prompt_blueprint = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))

    test_cases = relationship("TestCase", back_populates="question", cascade="all, delete-orphan")
    event_questions = relationship("EventQuestion", back_populates="question", cascade="all, delete-orphan")
    submissions = relationship("Submission", back_populates="question", cascade="all, delete-orphan")
    feedback_entries = relationship("QuestionFeedback", back_populates="question", cascade="all, delete-orphan")
    author = relationship("User", foreign_keys=[author_id])
    reviewer = relationship("User", foreign_keys=[reviewer_id])

class QuestionFeedback(Base):
    __tablename__ = "question_feedback"
    __table_args__ = (
        Index("ix_question_feedback_qid_type", "question_id", "feedback_type"),
    )

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    feedback_type = Column(String(50), default="REVIEWER_NOTE", index=True) # REVIEWER_NOTE, FACULTY_REVIEW, ATTEMPT_CALIBRATION, QUALITY_AUDIT
    rating = Column(Integer, default=5) # 1-5 rating
    comment = Column(Text, nullable=True)
    metrics_snapshot = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), index=True)

    question = relationship("Question", back_populates="feedback_entries")
    user = relationship("User")

class TestCase(Base):
    __tablename__ = "test_cases"
    __table_args__ = (
        Index("ix_test_cases_qid_hidden", "question_id", "is_hidden"),
    )


    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, index=True)
    input_data = Column(Text, nullable=False)
    expected_output = Column(Text, nullable=False)
    is_hidden = Column(Boolean, default=False, index=True)  # Hidden test cases not exposed to students
    category = Column(String(50), default=TestCaseCategory.NORMAL.value, index=True)
    explanation = Column(Text, nullable=True)
    points = Column(Integer, default=10)

    question = relationship("Question", back_populates="test_cases")


class EventQuestion(Base):
    __tablename__ = "event_questions"
    __table_args__ = (
        Index("ix_event_questions_event_order", "event_id", "order_index"),
        UniqueConstraint("event_id", "question_id", "branch_override", "year_override", name="uq_event_question_branch_year"),
    )

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, index=True)
    
    # Branch or year specific variation (e.g. 1st year gets beginner problem, 3rd year gets advanced)
    branch_override = Column(String(50), default="ALL")  # ALL, AIML, AIDS, IIOT, AR
    year_override = Column(Integer, default=0)           # 0 for ALL, 1, 2, 3, 4
    
    order_index = Column(Integer, default=0)
    points = Column(Integer, default=100)

    event = relationship("Event", back_populates="event_questions")
    question = relationship("Question", back_populates="event_questions")

class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        Index("ix_submissions_event_user", "event_id", "user_id"),
        Index("ix_submissions_event_question_user", "event_id", "question_id", "user_id"),
        Index("ix_submissions_user_submitted", "user_id", "submitted_at"),
        Index("ix_submissions_verdict", "verdict"),
    )

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    code = Column(Text, nullable=False)
    language = Column(String(50), nullable=False)  # python, cpp, c, java
    
    verdict = Column(String(50), default=SubmissionVerdict.PENDING)
    status = Column(String(50), default=SubmissionStatus.QUEUED.value, index=True)
    passed_test_cases = Column(Integer, default=0)
    total_test_cases = Column(Integer, default=0)
    score = Column(Float, default=0.0)
    
    execution_time_ms = Column(Float, default=0.0)
    memory_used_kb = Column(Float, default=0.0)
    error_message = Column(Text, nullable=True)
    
    # Structured detailed test logs
    test_case_results = Column(JSON, default=list) # [{test_case_id, is_hidden, passed, execution_time_ms, actual_output}]
    
    is_final = Column(Boolean, default=False)  # Once true, locked
    submitted_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), index=True)

    user = relationship("User", back_populates="submissions")
    event = relationship("Event", back_populates="submissions")
    question = relationship("Question", back_populates="submissions")

class StudentReport(Base):
    __tablename__ = "student_reports"
    __table_args__ = (
        Index("ix_student_reports_event_rank", "event_id", "rank"),
        Index("ix_student_reports_user_event", "user_id", "event_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    score = Column(Float, default=0.0, index=True)
    rank = Column(Integer, default=0, index=True)
    total_participants = Column(Integer, default=0)
    
    # Gemini AI Analysis Fields
    overall_performance_summary = Column(Text, nullable=False)
    strengths = Column(JSON, default=list)
    areas_for_improvement = Column(JSON, default=list)
    topic_performance = Column(JSON, default=dict) # {"Arrays": "High", "Trees": "Needs Practice"}
    time_efficiency_rating = Column(String(100), default="Optimal")
    problem_solving_pattern = Column(Text, nullable=True)
    difficulty_handling = Column(Text, nullable=True)
    comparative_analysis = Column(Text, nullable=True)
    
    generated_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    user = relationship("User", back_populates="reports")
    event = relationship("Event", back_populates="reports")

# =====================================================================
# PHASE 5 SECURE ASSESSMENT ENGINE & ANTI-CHEAT MODELS
# =====================================================================

class Assessment(Base):
    __tablename__ = "assessments"
    __table_args__ = (
        Index("ix_assessments_status_start", "status", "start_time"),
        Index("ix_assessments_created_by", "created_by_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    instructions = Column(Text, nullable=True)
    duration_minutes = Column(Integer, default=60)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False, index=True)
    max_attempts = Column(Integer, default=1)
    passing_score = Column(Float, default=50.0)
    total_marks = Column(Float, default=100.0)
    negative_marking = Column(Boolean, default=False)
    negative_mark_rate = Column(Float, default=0.25)
    randomize_questions = Column(Boolean, default=True)
    randomize_options = Column(Boolean, default=True)
    allowed_languages = Column(JSON, default=list) # ["python", "cpp", "c", "java"]
    candidate_assignment = Column(JSON, default=dict) # {"type": "ALL", "targets": []}
    anti_cheat_policy = Column(JSON, default=dict) # {"max_tab_switches": 5, "action": "WARN", "require_fullscreen": True, "block_clipboard": True}
    show_results_immediately = Column(Boolean, default=False)
    allow_review = Column(Boolean, default=False)
    status = Column(String(50), default=AssessmentStatus.DRAFT.value)
    
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))

    created_by = relationship("User", foreign_keys=[created_by_id])
    questions = relationship("AssessmentQuestion", back_populates="assessment", cascade="all, delete-orphan", order_by="AssessmentQuestion.order_index")
    attempts = relationship("AssessmentAttempt", back_populates="assessment", cascade="all, delete-orphan")
    results = relationship("AssessmentResult", back_populates="assessment", cascade="all, delete-orphan")

class AssessmentQuestion(Base):
    __tablename__ = "assessment_questions"
    __table_args__ = (
        Index("ix_assessment_questions_assessment_order", "assessment_id", "order_index"),
        UniqueConstraint("assessment_id", "question_id", name="uq_assessment_question"),
    )

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    section_name = Column(String(100), default="General")
    order_index = Column(Integer, default=0)
    marks = Column(Float, default=10.0)
    negative_marks = Column(Float, default=0.0)
    is_mandatory = Column(Boolean, default=True)

    assessment = relationship("Assessment", back_populates="questions")
    question = relationship("Question")

class AssessmentAttempt(Base):
    __tablename__ = "assessment_attempts"
    __table_args__ = (
        Index("ix_assessment_attempts_assessment_user", "assessment_id", "candidate_id"),
        Index("ix_assessment_attempts_status_expiry", "status", "expiry_time"),
        Index("ix_assessment_attempts_session", "session_token"),
    )

    id = Column(String(64), primary_key=True, index=True) # UUID string
    assessment_id = Column(Integer, ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False)
    candidate_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    attempt_number = Column(Integer, default=1)
    status = Column(String(50), default=AttemptStatus.IN_PROGRESS.value)
    start_time = Column(DateTime, nullable=False, index=True)
    expiry_time = Column(DateTime, nullable=False) # Server-authoritative
    submitted_at = Column(DateTime, nullable=True, index=True)
    seed = Column(Integer, default=0)
    question_order = Column(JSON, default=list) # Ordered question IDs for this attempt
    option_mapping = Column(JSON, default=dict) # {str(q_id): {shuffled_key: orig_key}}
    integrity_score = Column(Float, default=100.0)
    score = Column(Float, default=0.0)
    total_marks = Column(Float, default=0.0)
    percentage = Column(Float, default=0.0)
    accuracy = Column(Float, default=0.0)
    passed = Column(Boolean, default=False)
    client_ip = Column(String(100), nullable=True)
    user_agent = Column(String(500), nullable=True)
    session_token = Column(String(128), nullable=True)
    last_heartbeat_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))

    assessment = relationship("Assessment", back_populates="attempts")
    candidate = relationship("User", foreign_keys=[candidate_id])
    answers = relationship("AttemptAnswer", back_populates="attempt", cascade="all, delete-orphan")
    anti_cheat_events = relationship("AntiCheatEvent", back_populates="attempt", cascade="all, delete-orphan")
    result = relationship("AssessmentResult", back_populates="attempt", uselist=False, cascade="all, delete-orphan")

class AttemptAnswer(Base):
    __tablename__ = "attempt_answers"
    __table_args__ = (
        Index("ix_attempt_answers_attempt_q", "attempt_id", "question_id"),
        UniqueConstraint("attempt_id", "question_id", name="uq_attempt_question_answer"),
    )

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(String(64), ForeignKey("assessment_attempts.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    answer_data = Column(JSON, default=dict) # {"selected_option": "A", "code": "...", "language": "python", "subjective_text": "..."}
    is_flagged = Column(Boolean, default=False)
    is_evaluated = Column(Boolean, default=False)
    score_awarded = Column(Float, default=0.0)
    evaluation_verdict = Column(String(50), nullable=True)
    evaluation_details = Column(JSON, default=dict)
    execution_time_ms = Column(Float, default=0.0)
    memory_used_kb = Column(Float, default=0.0)
    version = Column(Integer, default=1)
    saved_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))

    attempt = relationship("AssessmentAttempt", back_populates="answers")
    question = relationship("Question")

class AntiCheatEvent(Base):
    __tablename__ = "anti_cheat_events"
    __table_args__ = (
        Index("ix_anti_cheat_events_attempt_time", "attempt_id", "timestamp"),
        Index("ix_anti_cheat_events_candidate_time", "candidate_id", "timestamp"),
        Index("ix_anti_cheat_events_severity", "severity"),
    )

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(String(64), ForeignKey("assessment_attempts.id", ondelete="CASCADE"), nullable=False)
    candidate_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(50), default=AntiCheatSeverity.INFO.value)
    metadata_json = Column(JSON, default=dict)
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    attempt = relationship("AssessmentAttempt", back_populates="anti_cheat_events")
    candidate = relationship("User", foreign_keys=[candidate_id])

class AssessmentResult(Base):
    __tablename__ = "assessment_results"
    __table_args__ = (
        Index("ix_assessment_results_assessment_user", "assessment_id", "user_id"),
        Index("ix_assessment_results_score", "total_score"),
        Index("ix_assessment_results_rank", "rank"),
    )

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(String(64), ForeignKey("assessment_attempts.id", ondelete="CASCADE"), unique=True, nullable=False)
    assessment_id = Column(Integer, ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    total_score = Column(Float, default=0.0)
    max_score = Column(Float, default=0.0)
    percentage = Column(Float, default=0.0)
    accuracy = Column(Float, default=0.0)
    passed = Column(Boolean, default=False)
    total_questions = Column(Integer, default=0)
    attempted_count = Column(Integer, default=0)
    correct_count = Column(Integer, default=0)
    incorrect_count = Column(Integer, default=0)
    skipped_count = Column(Integer, default=0)
    time_spent_seconds = Column(Float, default=0.0)
    question_breakdown = Column(JSON, default=list)
    section_breakdown = Column(JSON, default=dict)
    difficulty_breakdown = Column(JSON, default=dict)
    topic_breakdown = Column(JSON, default=dict)
    percentile = Column(Float, nullable=True)
    rank = Column(Integer, nullable=True)
    total_candidates = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), index=True)

    attempt = relationship("AssessmentAttempt", back_populates="result")
    assessment = relationship("Assessment", back_populates="results")
    user = relationship("User", foreign_keys=[user_id])


