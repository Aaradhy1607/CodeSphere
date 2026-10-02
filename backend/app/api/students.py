from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional, Dict, Any

from app.core.database import get_db
from app.core.security import get_current_user, require_permission, get_password_hash
from app.core.rate_limiter import api_general_rate_limiter
from app.models.models import (
    User, StudentProfile, UserRole, Submission, Event, StudentReport,
    Permission, get_permissions_for_role
)
from app.schemas.schemas import UserOut, StudentProfileCreate, StudentProfileOut

router = APIRouter(prefix="/students", tags=["Student Management"])

def _enrich_user_out(u: User) -> UserOut:
    u_out = UserOut.model_validate(u)
    u_out.permissions = get_permissions_for_role(u.role)
    return u_out

@router.get("/", response_model=List[UserOut], dependencies=[Depends(api_general_rate_limiter)])
def list_students(
    branch: Optional[str] = None,
    academic_year: Optional[int] = None,
    search: Optional[str] = None,
    is_approved: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.VIEW_STUDENTS))
):
    query = (
        db.query(User)
        .options(joinedload(User.student_profile))
        .join(StudentProfile)
        .filter(User.role == UserRole.STUDENT.value)
    )
    
    if branch and branch != "ALL":
        query = query.filter(StudentProfile.branch == branch)
    if academic_year and academic_year > 0:
        query = query.filter(StudentProfile.academic_year == academic_year)
    if is_approved is not None:
        query = query.filter(StudentProfile.is_approved == is_approved)
    if search:
        s = f"%{search.strip().lower()}%"
        query = query.filter(
            (User.full_name.ilike(s)) | (User.email.ilike(s)) | (StudentProfile.enrollment_no.ilike(s))
        )
    
    students = (
        query
        .order_by(StudentProfile.total_lifetime_score.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [_enrich_user_out(s) for s in students]

@router.post("/create", response_model=UserOut)
def create_student(
    name: str,
    email: str,
    enrollment_no: str,
    branch: str,
    academic_year: int,
    password: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.MANAGE_STUDENTS))
):
    import secrets
    email_clean = email.strip().lower()
    existing = db.query(User).filter(User.email == email_clean).first()
    if existing:
        raise HTTPException(status_code=400, detail="A student with this college email already exists.")

    initial_password = password if password else secrets.token_urlsafe(16)
    user = User(
        email=email_clean,
        full_name=name.strip(),
        role=UserRole.STUDENT.value,
        hashed_password=get_password_hash(initial_password),
        is_active=True
    )
    db.add(user)
    db.flush()

    profile = StudentProfile(
        user_id=user.id,
        enrollment_no=enrollment_no.strip(),
        branch=branch,
        academic_year=academic_year,
        is_approved=True
    )
    db.add(profile)
    db.commit()
    db.refresh(user)
    return _enrich_user_out(user)

@router.get("/{user_id}/history", dependencies=[Depends(api_general_rate_limiter)])
def get_student_history(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user_perms = get_permissions_for_role(current_user.role)
    can_view_all = Permission.VIEW_STUDENTS.value in user_perms or "ADMIN" in current_user.role

    # Allow self or staff with VIEW_STUDENTS permission
    if not can_view_all and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Access denied to other student assessment history.")

    user = db.query(User).options(joinedload(User.student_profile)).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Student not found.")

    submissions = (
        db.query(Submission)
        .options(joinedload(Submission.question), joinedload(Submission.event))
        .filter(Submission.user_id == user_id, Submission.is_final == True)
        .all()
    )
    reports = db.query(StudentReport).filter(StudentReport.user_id == user_id).all()

    return {
        "user": {
            "id": user.id,
            "name": user.full_name,
            "email": user.email,
            "role": user.role,
            "profile": {
                "enrollment_no": user.student_profile.enrollment_no if user.student_profile else "",
                "branch": user.student_profile.branch if user.student_profile else "",
                "academic_year": user.student_profile.academic_year if user.student_profile else 0,
                "total_lifetime_score": user.student_profile.total_lifetime_score if user.student_profile else 0,
                "total_events_participated": user.student_profile.total_events_participated if user.student_profile else 0,
                "total_problems_solved": user.student_profile.total_problems_solved if user.student_profile else 0,
                "average_score": user.student_profile.average_score if user.student_profile else 0,
                "consistency_score": user.student_profile.consistency_score if user.student_profile else 100,
                "placement_readiness_rating": user.student_profile.placement_readiness_rating if user.student_profile else "Developing"
            }
        },
        "submissions_count": len(submissions),
        "reports": [
            {
                "id": r.id,
                "event_id": r.event_id,
                "event_title": r.event.title if r.event else "Assessment",
                "score": r.score,
                "rank": r.rank,
                "total_participants": r.total_participants,
                "summary": r.overall_performance_summary,
                "strengths": r.strengths,
                "improvements": r.areas_for_improvement,
                "topics": r.topic_performance,
                "time_efficiency": r.time_efficiency_rating,
                "date": r.generated_at
            }
            for r in reports
        ]
    }

@router.put("/{user_id}/status")
def toggle_student_status(
    user_id: int,
    is_active: bool,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.MANAGE_STUDENTS))
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Student not found.")
    user.is_active = is_active
    db.commit()
    return {"message": f"Student status updated to {'active' if is_active else 'inactive'}."}

@router.delete("/{user_id}")
def delete_student(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.MANAGE_STUDENTS))
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Student not found.")
    if user.role != UserRole.STUDENT.value:
        raise HTTPException(status_code=400, detail="Cannot delete staff or administrator accounts via student manager.")
    
    student_name = user.full_name
    db.delete(user)
    db.commit()
    return {"message": f"Student '{student_name}' and all associated records deleted successfully."}
