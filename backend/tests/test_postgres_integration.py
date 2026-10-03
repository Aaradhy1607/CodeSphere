import os
import uuid
import datetime
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.models.models import (
    Base, User, UserRole, AccountStatus, Event, EventStatus, EventQuestion,
    Question, QuestionType, Submission, SubmissionStatus, SubmissionVerdict, StudentProfile
)
from app.core.security import get_password_hash, create_access_token, verify_password
from app.core.database import auto_migrate_db

POSTGRES_URL = os.getenv("POSTGRES_TEST_DATABASE_URL") or os.getenv("TEST_DATABASE_URL")
if not POSTGRES_URL and os.getenv("DATABASE_URL", "").startswith("postgresql"):
    POSTGRES_URL = os.getenv("DATABASE_URL")

if POSTGRES_URL:
    if POSTGRES_URL.startswith("postgres://"):
        POSTGRES_URL = POSTGRES_URL.replace("postgres://", "postgresql+psycopg2://", 1)
    elif POSTGRES_URL.startswith("postgresql://") and not POSTGRES_URL.startswith("postgresql+"):
        POSTGRES_URL = POSTGRES_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

def get_db_engine():
    if POSTGRES_URL:
        return create_engine(POSTGRES_URL, pool_pre_ping=True)
    return create_engine("sqlite:///:memory:", pool_pre_ping=True)

def test_postgres_schema_creation_and_migrations():
    """Verify clean schema initialization and auto-migration."""
    engine = get_db_engine()
    Base.metadata.create_all(bind=engine)
    
    # Run auto-migration helper to verify DDL compatibility
    auto_migrate_db(engine)
    
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
        assert result == 1

def test_postgres_transaction_rollback():
    """Verify transaction isolation and rollback behavior."""
    engine = get_db_engine()
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSession()
    
    test_email = "rollback.test@std.ggsipu.ac.in"
    try:
        # Clean existing
        db.query(User).filter(User.email == test_email).delete()
        db.commit()

        user = User(
            email=test_email,
            full_name="Rollback Candidate",
            role=UserRole.STUDENT.value,
            status=AccountStatus.ACTIVE.value,
            hashed_password=get_password_hash("StrongTestPassword2026!"),
            is_active=True
        )
        db.add(user)
        db.flush()
        
        # Roll back without committing
        db.rollback()
        
        # Confirm user does not exist
        persisted = db.query(User).filter(User.email == test_email).first()
        assert persisted is None
    finally:
        db.close()

def test_postgres_user_auth_and_rbac_flow():
    """Verify user persistence, password verification, and RBAC mapping against real PostgreSQL / SQL engine."""
    engine = get_db_engine()
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSession()
    
    test_email = "pg.student@std.ggsipu.ac.in"
    try:
        db.query(User).filter(User.email == test_email).delete()
        db.commit()

        raw_pw = "PostgresSecurePassword2026!"
        user = User(
            email=test_email,
            full_name="Postgres Verified Student",
            role=UserRole.STUDENT.value,
            status=AccountStatus.ACTIVE.value,
            hashed_password=get_password_hash(raw_pw),
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        assert user.id is not None
        assert verify_password(raw_pw, user.hashed_password) is True
        assert verify_password("wrong_password", user.hashed_password) is False

        # Token generation verification
        token = create_access_token(subject=str(user.id), extra_claims={"role": user.role, "email": user.email})
        assert token is not None
        assert isinstance(token, str)
    finally:
        db.query(User).filter(User.email == test_email).delete()
        db.commit()
        db.close()

def test_postgres_assessment_and_submission_lifecycle():
    """Verify assessment creation, question relation, and submission persistence in PostgreSQL / SQL engine."""
    engine = get_db_engine()
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSession()
    
    try:
        # 1. Create Host User
        creator = User(
            email="pg.faculty@ipu.ac.in",
            full_name="Postgres Faculty",
            role=UserRole.FACULTY.value,
            hashed_password=get_password_hash("FacultyPass2026!"),
            is_active=True
        )
        db.add(creator)
        db.commit()
        db.refresh(creator)

        # 2. Create Event
        now = datetime.datetime.now(datetime.timezone.utc)
        event = Event(
            title="PostgreSQL Placement Drive 2026",
            description="Testing live PostgreSQL relations",
            start_time=now,
            end_time=now + datetime.timedelta(hours=2),
            status=EventStatus.ACTIVE.value,
            created_by_id=creator.id
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        # 3. Create Question
        question = Question(
            title="Postgres Two Sum",
            slug=f"pg-two-sum-{uuid.uuid4().hex[:6]}",
            question_type=QuestionType.CODING.value,
            problem_statement="Find indices that sum to target.",
            marks=100
        )
        db.add(question)
        db.commit()
        db.refresh(question)

        # Link Question to Event
        eq = EventQuestion(
            event_id=event.id,
            question_id=question.id,
            points=100,
            order_index=1
        )
        db.add(eq)
        db.commit()

        # 4. Create Student & Submission
        student = User(
            email="pg.candidate@std.ggsipu.ac.in",
            full_name="Postgres Candidate",
            role=UserRole.STUDENT.value,
            hashed_password=get_password_hash("CandidatePass2026!"),
            is_active=True
        )
        db.add(student)
        db.commit()
        db.refresh(student)

        sub = Submission(
            user_id=student.id,
            event_id=event.id,
            question_id=question.id,
            language="python",
            code="def solution(): return True",
            status=SubmissionStatus.COMPLETED.value,
            verdict=SubmissionVerdict.AC.value,
            score=100.0,
            is_final=True
        )
        db.add(sub)
        db.commit()
        db.refresh(sub)

        assert sub.id is not None
        assert sub.verdict == SubmissionVerdict.AC.value

        # Cleanup
        db.delete(sub)
        db.delete(eq)
        db.delete(question)
        db.delete(event)
        db.delete(student)
        db.delete(creator)
        db.commit()
    finally:
        db.close()
