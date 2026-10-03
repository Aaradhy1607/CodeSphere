import os
import sys
import logging
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import SessionLocal, Base, engine, auto_migrate_db
from app.models.models import (
    User, UserRole, AccountStatus, StudentProfile, AdminAllowlist,
    RefreshToken, PasswordResetToken, AuditLog, Event, EventQuestion,
    Question, TestCase, QuestionFeedback, Submission, StudentReport,
    Assessment, AssessmentQuestion, AssessmentAttempt, AttemptAnswer,
    AntiCheatEvent, AssessmentResult
)
from app.services.seeder import seed_database

logger = logging.getLogger("codesphere.purge")

def purge_mock_and_test_data(db: Session) -> dict:
    """
    Safely and transactionally purges all mock, dummy, sample, and test-generated records
    from the database while preserving the primary Super Admin and legitimate configuration.
    
    Ensures the production baseline contains ONLY:
    1. Exactly one primary Super Administrator (configured via INITIAL_ADMIN_EMAIL)
    2. Required primary AdminAllowlist entry for the Super Administrator
    3. Zero mock/demo/sample accounts, assessments, submissions, or telemetry.
    """
    admin_email = settings.INITIAL_ADMIN_EMAIL.strip().lower()
    if not admin_email:
        raise RuntimeError("FATAL: INITIAL_ADMIN_EMAIL is not configured in settings.")

    # 1. Ensure Super Admin is bootstrapped first
    seed_database(db)

    super_admin = db.query(User).filter(
        User.email == admin_email,
        User.role == UserRole.SUPER_ADMIN.value
    ).first()

    if not super_admin:
        # Check if user exists with another id
        super_admin = db.query(User).filter(User.role == UserRole.SUPER_ADMIN.value).first()

    if not super_admin:
        raise RuntimeError("FATAL: Could not locate or initialize Super Admin account.")

    primary_super_admin_id = super_admin.id
    primary_super_admin_email = super_admin.email

    try:
        # Delete dependent assessment attempts & results
        db.query(AssessmentResult).delete(synchronize_session=False)
        db.query(AttemptAnswer).delete(synchronize_session=False)
        db.query(AntiCheatEvent).delete(synchronize_session=False)
        db.query(AssessmentAttempt).delete(synchronize_session=False)
        db.query(AssessmentQuestion).delete(synchronize_session=False)
        db.query(Assessment).delete(synchronize_session=False)

        # Delete dependent submissions & reports
        db.query(StudentReport).delete(synchronize_session=False)
        db.query(Submission).delete(synchronize_session=False)
        db.query(EventQuestion).delete(synchronize_session=False)
        db.query(Event).delete(synchronize_session=False)

        # Delete questions and test cases
        db.query(QuestionFeedback).delete(synchronize_session=False)
        db.query(TestCase).delete(synchronize_session=False)
        db.query(Question).delete(synchronize_session=False)

        # Delete tokens & audit logs for non-superadmin users
        db.query(RefreshToken).filter(RefreshToken.user_id != primary_super_admin_id).delete(synchronize_session=False)
        db.query(PasswordResetToken).filter(PasswordResetToken.user_id != primary_super_admin_id).delete(synchronize_session=False)
        db.query(AuditLog).filter(AuditLog.user_id != primary_super_admin_id, AuditLog.actor_email != primary_super_admin_email).delete(synchronize_session=False)

        # Delete all student profiles
        db.query(StudentProfile).delete(synchronize_session=False)

        # Delete non-superadmin allowlist entries
        db.query(AdminAllowlist).filter(AdminAllowlist.email != primary_super_admin_email).delete(synchronize_session=False)

        # Delete all non-superadmin users
        db.query(User).filter(User.id != primary_super_admin_id).delete(synchronize_session=False)

        db.commit()

        # Generate verified post-purge inventory
        inventory = {
            "super_admin_count": db.query(User).filter(User.role == UserRole.SUPER_ADMIN.value).count(),
            "other_users_count": db.query(User).filter(User.role != UserRole.SUPER_ADMIN.value).count(),
            "student_profiles_count": db.query(StudentProfile).count(),
            "admin_allowlist_count": db.query(AdminAllowlist).count(),
            "assessments_count": db.query(Assessment).count(),
            "submissions_count": db.query(Submission).count(),
            "events_count": db.query(Event).count(),
            "questions_count": db.query(Question).count(),
            "super_admin_email": primary_super_admin_email
        }
        return inventory

    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Database purge failed and was completely rolled back: {str(e)}")

if __name__ == "__main__":
    auto_migrate_db()
    session = SessionLocal()
    try:
        inv = purge_mock_and_test_data(session)
        print("==================================================")
        print("DATABASE PURGE COMPLETE — CLEAN PRODUCTION BASELINE")
        print("==================================================")
        print(f"SUPER_ADMIN Count:      {inv['super_admin_count']}")
        print(f"Other Users Count:      {inv['other_users_count']}")
        print(f"Student Profiles Count: {inv['student_profiles_count']}")
        print(f"Admin Allowlist Count:  {inv['admin_allowlist_count']}")
        print(f"Assessments Count:      {inv['assessments_count']}")
        print(f"Submissions Count:      {inv['submissions_count']}")
        print(f"Events Count:           {inv['events_count']}")
        print(f"Questions Count:        {inv['questions_count']}")
        print("==================================================")
    finally:
        session.close()
