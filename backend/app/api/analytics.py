import csv
import io
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List, Optional, Dict, Any

from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.core.cache import cache
from app.core.rate_limiter import api_general_rate_limiter
from app.models.models import (
    User, StudentProfile, Event, Question, Submission, StudentReport, UserRole, SubmissionVerdict,
    Permission, get_permissions_for_role
)
from app.schemas.schemas import PlacementAnalyticsOut, LifetimeLeaderboardEntry, StudentComparisonOut

router = APIRouter(prefix="/analytics", tags=["Placement Cell Analytics"])

@router.get("/overview", response_model=PlacementAnalyticsOut, dependencies=[Depends(api_general_rate_limiter)])
def get_analytics_overview(
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.VIEW_ANALYTICS))
):
    cache_key = "analytics:overview"
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data

    total_students = db.query(StudentProfile).count()
    total_events = db.query(Event).count()
    total_submissions = db.query(Submission).count()

    # Branch-wise analytics computed dynamically from real database
    branches = ["AIML", "AIDS", "IIOT", "AR"]
    branch_stats = {}
    for b in branches:
        profs = db.query(StudentProfile).filter(StudentProfile.branch == b).all()
        count = len(profs)
        avg = round(sum(p.average_score for p in profs) / max(count, 1), 1) if count > 0 else 0.0
        top_score = max((p.total_lifetime_score for p in profs), default=0.0)
        ready_count = sum(1 for p in profs if p.placement_readiness_rating == "Ready")
        branch_stats[b] = {
            "total_students": count,
            "average_score": avg,
            "top_score": top_score,
            "placement_ready_count": ready_count
        }

    # Year-wise analytics computed dynamically
    year_stats = {}
    for y in [1, 2, 3, 4]:
        profs = db.query(StudentProfile).filter(StudentProfile.academic_year == y).all()
        count = len(profs)
        avg = round(sum(p.average_score for p in profs) / max(count, 1), 1) if count > 0 else 0.0
        year_stats[y] = {
            "total_students": count,
            "average_score": avg,
            "ready_count": sum(1 for p in profs if p.placement_readiness_rating == "Ready")
        }

    # Topic mastery computed from actual submissions & question tags
    topic_scores: Dict[str, List[float]] = {}
    final_submissions = (
        db.query(Submission)
        .options(joinedload(Submission.question))
        .filter(Submission.is_final == True)
        .all()
    )
    
    for sub in final_submissions:
        q = sub.question
        if q and q.topic_tags:
            for tag in q.topic_tags:
                tag_clean = tag.strip()
                if tag_clean not in topic_scores:
                    topic_scores[tag_clean] = []
                topic_scores[tag_clean].append(sub.score)

    topic_mastery = {}
    for tag, scores in topic_scores.items():
        topic_mastery[tag] = round(sum(scores) / max(len(scores), 1), 1)

    # If no submissions yet, discover all tags from question bank with 0.0 baseline
    if not topic_mastery:
        all_questions = db.query(Question).all()
        for q in all_questions:
            for tag in (q.topic_tags or []):
                topic_mastery[tag.strip()] = 0.0

    # Top performers (real lifetime scores)
    top_profs = (
        db.query(User)
        .options(joinedload(User.student_profile))
        .join(StudentProfile)
        .filter(User.role == UserRole.STUDENT, User.is_active == True)
        .order_by(StudentProfile.total_lifetime_score.desc())
        .limit(5)
        .all()
    )
    
    top_performers = []
    for idx, u in enumerate(top_profs):
        p = u.student_profile
        top_performers.append(LifetimeLeaderboardEntry(
            rank=idx + 1,
            user_id=u.id,
            full_name=u.full_name,
            enrollment_no=p.enrollment_no if p else "",
            branch=p.branch if p else "",
            academic_year=p.academic_year if p else 0,
            events_participated=p.total_events_participated if p else 0,
            total_lifetime_score=p.total_lifetime_score if p else 0.0,
            total_problems_solved=p.total_problems_solved if p else 0,
            average_score=p.average_score if p else 0.0,
            consistency_score=p.consistency_score if p else 100.0,
            placement_readiness_rating=p.placement_readiness_rating if p else "Developing"
        ).model_dump())

    # Needs attention students (lowest average or zero participations)
    attention_profs = (
        db.query(User)
        .options(joinedload(User.student_profile))
        .join(StudentProfile)
        .filter(User.role == UserRole.STUDENT, User.is_active == True)
        .order_by(StudentProfile.average_score.asc())
        .limit(5)
        .all()
    )
    
    needs_attention = []
    for idx, u in enumerate(attention_profs):
        p = u.student_profile
        needs_attention.append(LifetimeLeaderboardEntry(
            rank=idx + 1,
            user_id=u.id,
            full_name=u.full_name,
            enrollment_no=p.enrollment_no if p else "",
            branch=p.branch if p else "",
            academic_year=p.academic_year if p else 0,
            events_participated=p.total_events_participated if p else 0,
            total_lifetime_score=p.total_lifetime_score if p else 0.0,
            total_problems_solved=p.total_problems_solved if p else 0,
            average_score=p.average_score if p else 0.0,
            consistency_score=p.consistency_score if p else 100.0,
            placement_readiness_rating=p.placement_readiness_rating if p else "Developing"
        ).model_dump())

    result = PlacementAnalyticsOut(
        total_registered_students=total_students,
        total_events_conducted=total_events,
        total_submissions=total_submissions,
        branch_performance=branch_stats,
        year_performance=year_stats,
        topic_mastery=topic_mastery,
        top_performers=top_performers,
        needs_attention_students=needs_attention
    ).model_dump()

    cache.set(cache_key, result, ttl=60)
    return result

@router.get("/student-topics/{user_id}")
def get_student_topic_analytics(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Computes real dynamic topic mastery for a specific student from their historical submissions.
    """
    user_perms = get_permissions_for_role(current_user.role)
    can_view = (
        Permission.VIEW_PLACEMENT_ANALYTICS in user_perms or
        Permission.VIEW_ANALYTICS in user_perms or
        current_user.role in [UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value, UserRole.PLACEMENT_ADMIN.value, UserRole.FACULTY.value]
    )
    if not can_view and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Access denied.")

    student_subs = db.query(Submission).filter(
        Submission.user_id == user_id,
        Submission.is_final == True
    ).all()

    topic_scores: Dict[str, List[float]] = {}
    for sub in student_subs:
        q = sub.question
        if q and q.topic_tags:
            for tag in q.topic_tags:
                tag_clean = tag.strip()
                if tag_clean not in topic_scores:
                    topic_scores[tag_clean] = []
                topic_scores[tag_clean].append(sub.score)

    student_topic_mastery = {}
    for tag, scores in topic_scores.items():
        student_topic_mastery[tag] = round(sum(scores) / max(len(scores), 1), 1)

    # Score trajectory across events
    events_trajectory = []
    user_reports = db.query(StudentReport).filter(StudentReport.user_id == user_id).order_by(StudentReport.generated_at.asc()).all()
    for r in user_reports:
        events_trajectory.append({
            "event_title": r.event.title if r.event else "Assessment",
            "score": r.score,
            "rank": r.rank,
            "date": r.generated_at.strftime("%b %d")
        })

    return {
        "topic_mastery": student_topic_mastery,
        "score_trajectory": events_trajectory
    }

@router.get("/compare", response_model=List[StudentComparisonOut])
def compare_students(
    student_ids: str = Query(..., description="Comma separated student user IDs"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.VIEW_PLACEMENT_ANALYTICS))
):
    ids = [int(i.strip()) for i in student_ids.split(",") if i.strip().isdigit()]
    if not ids:
        raise HTTPException(status_code=400, detail="Invalid student IDs provided.")

    users = db.query(User).filter(User.id.in_(ids)).all()
    user_map = {u.id: u for u in users}
    
    comparison = []
    # Preserve the requested ID sequence while ensuring uniqueness
    seen_ids = set()
    ordered_ids = [uid for uid in ids if uid in user_map and not (uid in seen_ids or seen_ids.add(uid))]
    
    for uid in ordered_ids:
        u = user_map[uid]
        prof = u.student_profile
        subs = db.query(Submission).filter(Submission.user_id == u.id, Submission.is_final == True).all()
        reports = db.query(StudentReport).filter(StudentReport.user_id == u.id).all()
        
        # Calculate student-specific topic mastery
        topic_scores: Dict[str, List[float]] = {}
        for sub in subs:
            q = sub.question
            if q and q.topic_tags:
                for tag in q.topic_tags:
                    tag_clean = tag.strip()
                    if tag_clean not in topic_scores:
                        topic_scores[tag_clean] = []
                    topic_scores[tag_clean].append(sub.score)
        
        topic_mastery = {}
        for tag, scores in topic_scores.items():
            topic_mastery[tag] = round(sum(scores) / max(len(scores), 1), 1)

        comparison.append(StudentComparisonOut(
            id=u.id,
            student_id=u.id,
            user_id=u.id,
            full_name=u.full_name,
            name=u.full_name,
            email=u.email,
            enrollment_no=prof.enrollment_no if prof else "N/A",
            branch=prof.branch if prof else "N/A",
            academic_year=prof.academic_year if prof else 0,
            total_score=prof.total_lifetime_score if prof else 0.0,
            total_lifetime_score=prof.total_lifetime_score if prof else 0.0,
            total_events=prof.total_events_participated if prof else 0,
            total_solved=prof.total_problems_solved if prof else 0,
            average_score=prof.average_score if prof else 0.0,
            consistency=prof.consistency_score if prof else 100.0,
            placement_readiness=prof.placement_readiness_rating if prof else "Developing",
            readiness=prof.placement_readiness_rating if prof else "Developing",
            recent_scores=[s.score for s in subs[-5:]],
            strengths=list(set([st for r in reports for st in (r.strengths or [])]))[:4],
            topic_mastery=topic_mastery
        ).model_dump())
    return comparison

@router.get("/export-csv")
def export_students_csv(
    branch: Optional[str] = "ALL",
    academic_year: Optional[int] = 0,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.EXPORT_STUDENT_DATA))
):
    """
    Exports clean, production-grade CSV of student placement analytics for recruitment drives.
    """
    query = db.query(User).join(StudentProfile).filter(User.role == UserRole.STUDENT)
    if branch and branch != "ALL":
        query = query.filter(StudentProfile.branch == branch)
    if academic_year and academic_year > 0:
        query = query.filter(StudentProfile.academic_year == academic_year)

    students = query.order_by(StudentProfile.total_lifetime_score.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Rank", "Full Name", "Enrollment Number", "College Email",
        "Branch", "Academic Year", "Total Lifetime Score",
        "Events Participated", "Problems Solved", "Average Score",
        "Consistency Index (%)", "Placement Readiness Rating"
    ])

    for idx, u in enumerate(students):
        p = u.student_profile
        writer.writerow([
            idx + 1,
            u.full_name,
            p.enrollment_no if p else "",
            u.email,
            p.branch if p else "",
            p.academic_year if p else "",
            p.total_lifetime_score if p else 0,
            p.total_events_participated if p else 0,
            p.total_problems_solved if p else 0,
            p.average_score if p else 0,
            p.consistency_score if p else 100,
            p.placement_readiness_rating if p else "Developing"
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=USAR_Placement_Coding_Analytics.csv"}
    )

@router.get("/landing-metrics")
def get_landing_metrics(db: Session = Depends(get_db)):
    """
    Public telemetry endpoint providing live placement cell statistics for the landing page.
    Zero mock data — 100% computed from real database tables.
    """
    total_students = db.query(StudentProfile).count()
    total_questions = db.query(Question).count()
    total_events = db.query(Event).count()
    active_events = db.query(Event).filter(Event.status == "ACTIVE").count()
    total_evaluations = db.query(Submission).count()
    
    # Calculate real pass rate
    ac_submissions = db.query(Submission).filter(Submission.verdict == SubmissionVerdict.AC).count()
    pass_rate = round((ac_submissions / total_evaluations * 100.0), 1) if total_evaluations > 0 else 0.0

    return {
        "total_students": total_students,
        "total_questions": total_questions,
        "total_events": total_events,
        "active_events": active_events,
        "total_evaluations": total_evaluations,
        "pass_rate_percentage": pass_rate,
        "system_status": "OPERATIONAL"
    }

