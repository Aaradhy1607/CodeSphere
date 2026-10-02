from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional, Dict, Any

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.cache import cache
from app.core.rate_limiter import api_general_rate_limiter
from app.models.models import (
    Event, Submission, User, StudentProfile, UserRole, SubmissionVerdict
)
from app.schemas.schemas import LeaderboardEntry, LifetimeLeaderboardEntry

router = APIRouter(prefix="/leaderboards", tags=["Leaderboards"])

@router.get("/event/{event_id}", response_model=List[LeaderboardEntry], dependencies=[Depends(api_general_rate_limiter)])
def get_event_leaderboard(
    event_id: int,
    branch: Optional[str] = "ALL",
    academic_year: Optional[int] = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cache_key = f"leaderboards:event:{event_id}:{branch}:{academic_year}"
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data

    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")

    if not event.is_leaderboard_visible and "ADMIN" not in current_user.role and current_user.role != UserRole.FACULTY.value:
        raise HTTPException(
            status_code=403,
            detail="Leaderboard visibility is currently restricted by the Placement Cell for this event."
        )

    # Fetch all final submissions with eager loaded user and student profile
    submissions = (
        db.query(Submission)
        .options(joinedload(Submission.user).joinedload(User.student_profile))
        .filter(
            Submission.event_id == event_id,
            Submission.is_final == True
        )
        .all()
    )

    # Group by student
    student_scores: Dict[int, Dict[str, Any]] = {}
    for sub in submissions:
        uid = sub.user_id
        if uid not in student_scores:
            u = sub.user
            prof = u.student_profile if u else None
            student_scores[uid] = {
                "user_id": uid,
                "full_name": u.full_name if u else "Student",
                "enrollment_no": prof.enrollment_no if prof else "N/A",
                "branch": prof.branch if prof else "N/A",
                "academic_year": prof.academic_year if prof else 0,
                "total_score": 0.0,
                "problems_solved": 0,
                "total_time_ms": 0.0,
                "last_submission_time": sub.submitted_at
            }
        
        student_scores[uid]["total_score"] += sub.score
        if sub.verdict == SubmissionVerdict.AC:
            student_scores[uid]["problems_solved"] += 1
        student_scores[uid]["total_time_ms"] += sub.execution_time_ms
        if sub.submitted_at and (not student_scores[uid]["last_submission_time"] or sub.submitted_at > student_scores[uid]["last_submission_time"]):
            student_scores[uid]["last_submission_time"] = sub.submitted_at

    # Filter
    filtered_list = list(student_scores.values())
    if branch and branch != "ALL":
        filtered_list = [s for s in filtered_list if s["branch"] == branch]
    if academic_year and academic_year > 0:
        filtered_list = [s for s in filtered_list if s["academic_year"] == academic_year]

    # Sort: Total Score Descending, Problems Solved Descending, Total Time ms Ascending
    filtered_list.sort(key=lambda x: (-x["total_score"], -x["problems_solved"], x["total_time_ms"]))

    # Assign ranks
    ranked = []
    for idx, item in enumerate(filtered_list):
        ranked.append(LeaderboardEntry(
            rank=idx + 1,
            user_id=item["user_id"],
            full_name=item["full_name"],
            enrollment_no=item["enrollment_no"],
            branch=item["branch"],
            academic_year=item["academic_year"],
            total_score=round(item["total_score"], 1),
            problems_solved=item["problems_solved"],
            total_time_ms=round(item["total_time_ms"], 2),
            last_submission_time=item["last_submission_time"]
        ).model_dump())

    cache.set(cache_key, ranked, ttl=15)
    return ranked

@router.get("/lifetime", response_model=List[LifetimeLeaderboardEntry], dependencies=[Depends(api_general_rate_limiter)])
def get_lifetime_leaderboard(
    branch: Optional[str] = "ALL",
    academic_year: Optional[int] = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cache_key = f"leaderboards:lifetime:{branch}:{academic_year}"
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data

    query = (
        db.query(User)
        .options(joinedload(User.student_profile))
        .join(StudentProfile)
        .filter(User.role == UserRole.STUDENT, User.is_active == True)
    )
    
    if branch and branch != "ALL":
        query = query.filter(StudentProfile.branch == branch)
    if academic_year and academic_year > 0:
        query = query.filter(StudentProfile.academic_year == academic_year)

    students = query.all()

    # Sort by total_lifetime_score descending, then average_score descending, then problems_solved
    sorted_students = sorted(
        students,
        key=lambda u: (
            - (u.student_profile.total_lifetime_score if u.student_profile else 0),
            - (u.student_profile.average_score if u.student_profile else 0),
            - (u.student_profile.total_problems_solved if u.student_profile else 0)
        )
    )

    ranked = []
    for idx, u in enumerate(sorted_students):
        prof = u.student_profile
        ranked.append(LifetimeLeaderboardEntry(
            rank=idx + 1,
            user_id=u.id,
            full_name=u.full_name,
            enrollment_no=prof.enrollment_no if prof else "N/A",
            branch=prof.branch if prof else "N/A",
            academic_year=prof.academic_year if prof else 0,
            events_participated=prof.total_events_participated if prof else 0,
            total_lifetime_score=prof.total_lifetime_score if prof else 0.0,
            total_problems_solved=prof.total_problems_solved if prof else 0,
            average_score=prof.average_score if prof else 0.0,
            consistency_score=prof.consistency_score if prof else 100.0,
            placement_readiness_rating=prof.placement_readiness_rating if prof else "Developing"
        ).model_dump())

    cache.set(cache_key, ranked, ttl=30)
    return ranked
