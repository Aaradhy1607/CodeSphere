from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from app.core.database import get_db
from app.core.security import get_current_user, require_admin
from app.models.models import (
    User, StudentProfile, Event, Submission, StudentReport, UserRole, EventStatus
)
from app.schemas.schemas import StudentReportOut
from app.services.gemini_ai import gemini_service

router = APIRouter(prefix="/reports", tags=["AI Performance Reports"])

@router.get("/my-reports", response_model=List[StudentReportOut])
def get_my_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    reports = db.query(StudentReport).filter(StudentReport.user_id == current_user.id).order_by(StudentReport.generated_at.desc()).all()
    out = []
    for r in reports:
        prof = current_user.student_profile
        out.append(StudentReportOut(
            id=r.id,
            event_id=r.event_id,
            event_title=r.event.title if r.event else "Assessment",
            user_id=r.user_id,
            student_name=current_user.full_name,
            enrollment_no=prof.enrollment_no if prof else "",
            branch=prof.branch if prof else "",
            academic_year=prof.academic_year if prof else 0,
            score=r.score,
            rank=r.rank,
            total_participants=r.total_participants,
            overall_performance_summary=r.overall_performance_summary,
            strengths=r.strengths or [],
            areas_for_improvement=r.areas_for_improvement or [],
            topic_performance=r.topic_performance or {},
            time_efficiency_rating=r.time_efficiency_rating,
            problem_solving_pattern=r.problem_solving_pattern,
            difficulty_handling=r.difficulty_handling,
            comparative_analysis=r.comparative_analysis,
            generated_at=r.generated_at
        ))
    return out

@router.get("/event/{event_id}/student/{user_id}", response_model=StudentReportOut)
def get_or_generate_report(
    event_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Security: student can only view their own report unless staff/admin/faculty
    if "ADMIN" not in current_user.role and current_user.role != UserRole.FACULTY.value and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Access denied to other student diagnostic reports.")

    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Student not found.")

    # Check if report already exists
    report = db.query(StudentReport).filter(
        StudentReport.event_id == event_id,
        StudentReport.user_id == user_id
    ).first()

    if report:
        prof = target_user.student_profile
        return StudentReportOut(
            id=report.id,
            event_id=report.event_id,
            event_title=event.title,
            user_id=report.user_id,
            student_name=target_user.full_name,
            enrollment_no=prof.enrollment_no if prof else "",
            branch=prof.branch if prof else "",
            academic_year=prof.academic_year if prof else 0,
            score=report.score,
            rank=report.rank,
            total_participants=report.total_participants,
            overall_performance_summary=report.overall_performance_summary,
            strengths=report.strengths or [],
            areas_for_improvement=report.areas_for_improvement or [],
            topic_performance=report.topic_performance or {},
            time_efficiency_rating=report.time_efficiency_rating,
            problem_solving_pattern=report.problem_solving_pattern,
            difficulty_handling=report.difficulty_handling,
            comparative_analysis=report.comparative_analysis,
            generated_at=report.generated_at
        )

    # Generate new AI report
    subs = db.query(Submission).filter(
        Submission.event_id == event_id,
        Submission.user_id == user_id,
        Submission.is_final == True
    ).all()

    total_score = sum(s.score for s in subs)
    subs_data = [
        {
            "question": s.question.title if s.question else "Question",
            "topics": s.question.topic_tags if s.question else [],
            "verdict": s.verdict,
            "score": s.score,
            "time_ms": s.execution_time_ms,
            "language": s.language
        }
        for s in subs
    ]

    all_event_subs = db.query(Submission).filter(
        Submission.event_id == event_id,
        Submission.is_final == True
    ).all()

    user_scores = {}
    for s in all_event_subs:
        user_scores[s.user_id] = user_scores.get(s.user_id, 0.0) + s.score

    sorted_scores = sorted(user_scores.items(), key=lambda x: -x[1])
    rank = 1
    for idx, (uid, sc) in enumerate(sorted_scores):
        if uid == user_id:
            rank = idx + 1
            break
    total_participants = max(len(user_scores), 1)

    # Past scores
    past_subs = db.query(Submission).filter(
        Submission.user_id == user_id,
        Submission.event_id != event_id,
        Submission.is_final == True
    ).all()
    historical_scores = [ps.score for ps in past_subs]

    prof = target_user.student_profile
    ai_report_dict = gemini_service.generate_student_report(
        student_name=target_user.full_name,
        enrollment_no=prof.enrollment_no if prof else "",
        branch=prof.branch if prof else "USAR",
        academic_year=prof.academic_year if prof else 3,
        event_title=event.title,
        score=total_score,
        rank=rank,
        total_participants=total_participants,
        submissions_data=subs_data,
        historical_scores=historical_scores
    )

    new_report = StudentReport(
        event_id=event.id,
        user_id=target_user.id,
        score=total_score,
        rank=rank,
        total_participants=total_participants,
        overall_performance_summary=ai_report_dict.get("overall_performance_summary", ""),
        strengths=ai_report_dict.get("strengths", []),
        areas_for_improvement=ai_report_dict.get("areas_for_improvement", []),
        topic_performance=ai_report_dict.get("topic_performance", {}),
        time_efficiency_rating=ai_report_dict.get("time_efficiency_rating", "Standard"),
        problem_solving_pattern=ai_report_dict.get("problem_solving_pattern", ""),
        difficulty_handling=ai_report_dict.get("difficulty_handling", ""),
        comparative_analysis=ai_report_dict.get("comparative_analysis", "")
    )
    db.add(new_report)
    db.commit()
    db.refresh(new_report)

    return StudentReportOut(
        id=new_report.id,
        event_id=event.id,
        event_title=event.title,
        user_id=target_user.id,
        student_name=target_user.full_name,
        enrollment_no=prof.enrollment_no if prof else "",
        branch=prof.branch if prof else "",
        academic_year=prof.academic_year if prof else 0,
        score=new_report.score,
        rank=new_report.rank,
        total_participants=new_report.total_participants,
        overall_performance_summary=new_report.overall_performance_summary,
        strengths=new_report.strengths or [],
        areas_for_improvement=new_report.areas_for_improvement or [],
        topic_performance=new_report.topic_performance or {},
        time_efficiency_rating=new_report.time_efficiency_rating,
        problem_solving_pattern=new_report.problem_solving_pattern,
        difficulty_handling=new_report.difficulty_handling,
        comparative_analysis=new_report.comparative_analysis,
        generated_at=new_report.generated_at
    )
