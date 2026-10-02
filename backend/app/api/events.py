import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional, Dict, Any

from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.core.cache import cache, invalidate_events_cache
from app.core.rate_limiter import api_general_rate_limiter
from app.models.models import (
    Event, Question, EventQuestion, User, UserRole, EventStatus, Submission, TestCase,
    Permission, get_permissions_for_role
)
from app.schemas.schemas import EventCreate, EventUpdate, EventOut, EventDetailOut

router = APIRouter(prefix="/events", tags=["Event Management"])

def _update_event_statuses(db: Session):
    now = datetime.datetime.now(datetime.timezone.utc)
    events = db.query(Event).all()
    changed = False
    for e in events:
        if e.status != EventStatus.RESULTS_RELEASED:
            # Normalize timezone if necessary
            start = e.start_time.replace(tzinfo=datetime.timezone.utc) if e.start_time.tzinfo is None else e.start_time
            end = e.end_time.replace(tzinfo=datetime.timezone.utc) if e.end_time.tzinfo is None else e.end_time
            if now < start and e.status != EventStatus.UPCOMING:
                e.status = EventStatus.UPCOMING
                changed = True
            elif start <= now <= end and e.status != EventStatus.ACTIVE:
                e.status = EventStatus.ACTIVE
                changed = True
            elif now > end and e.status == EventStatus.ACTIVE:
                e.status = EventStatus.ENDED
                changed = True
    if changed:
        db.commit()
        invalidate_events_cache()

@router.get("/", response_model=List[EventOut], dependencies=[Depends(api_general_rate_limiter)])
def list_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _update_event_statuses(db)
    
    is_staff = current_user.role in [UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value, UserRole.PLACEMENT_ADMIN.value, UserRole.FACULTY.value]
    user_branch = current_user.student_profile.branch if current_user.student_profile else "ALL"
    user_year = current_user.student_profile.academic_year if current_user.student_profile else 0

    cache_key = f"events:list:{current_user.role}:{user_branch}:{user_year}:{skip}:{limit}"
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data

    events = (
        db.query(Event)
        .options(joinedload(Event.event_questions))
        .order_by(Event.start_time.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    # Enrich with counts and student eligibility
    result = []
    for e in events:
        # Check target eligibility for students
        if not is_staff:
            if e.target_branch != "ALL" and e.target_branch != user_branch:
                continue
            if e.target_year > 0 and e.target_year != user_year:
                continue

        questions_count = len(e.event_questions)
        participants_count = db.query(Submission.user_id).filter(Submission.event_id == e.id).distinct().count()
        e_out = EventOut(
            id=e.id,
            title=e.title,
            description=e.description,
            target_branch=e.target_branch,
            target_year=e.target_year,
            start_time=e.start_time,
            end_time=e.end_time,
            duration_minutes=e.duration_minutes,
            status=e.status,
            is_leaderboard_visible=e.is_leaderboard_visible,
            allow_branch_questions=e.allow_branch_questions,
            are_solutions_released=e.are_solutions_released,
            are_results_released=e.are_results_released,
            created_at=e.created_at,
            total_questions=questions_count,
            total_participants=participants_count
        )
        result.append(e_out.model_dump())

    cache.set(cache_key, result, ttl=30)
    return result

@router.get("/{event_id}", dependencies=[Depends(api_general_rate_limiter)])
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _update_event_statuses(db)
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")

    is_staff = current_user.role in [UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value, UserRole.PLACEMENT_ADMIN.value, UserRole.FACULTY.value]
    student_branch = current_user.student_profile.branch if current_user.student_profile else "ALL"
    student_year = current_user.student_profile.academic_year if current_user.student_profile else 0

    # Get questions with eager loaded question and test_cases
    eqs = (
        db.query(EventQuestion)
        .options(joinedload(EventQuestion.question).joinedload(Question.test_cases))
        .filter(EventQuestion.event_id == event_id)
        .order_by(EventQuestion.order_index.asc())
        .all()
    )
    
    questions_list = []
    can_see_solutions = is_staff or event.are_solutions_released

    for eq in eqs:
        # Academic year & branch differentiation filter for students
        if not is_staff:
            if eq.year_override > 0 and eq.year_override != student_year:
                continue
            if eq.branch_override != "ALL" and eq.branch_override != student_branch:
                continue

        q = eq.question
        # Visible test cases
        visible_tcs = [
            {
                "id": tc.id,
                "input_data": tc.input_data,
                "expected_output": tc.expected_output,
                "explanation": tc.explanation,
                "is_hidden": False,
                "points": tc.points
            }
            for tc in q.test_cases if not tc.is_hidden or is_admin
        ]

        q_dict = {
            "id": q.id,
            "title": q.title,
            "slug": q.slug,
            "problem_statement": q.problem_statement,
            "input_format": q.input_format,
            "output_format": q.output_format,
            "constraints": q.constraints,
            "examples": q.examples or [],
            "topic_tags": q.topic_tags or [],
            "difficulty_score": q.difficulty_score,
            "expected_time_complexity": q.expected_time_complexity,
            "expected_space_complexity": q.expected_space_complexity,
            "points": eq.points,
            "order_index": eq.order_index,
            "branch_override": eq.branch_override,
            "year_override": eq.year_override,
            "visible_test_cases": visible_tcs,
            "reference_solutions": q.reference_solutions if can_see_solutions else {}
        }
        questions_list.append(q_dict)

    participants_count = db.query(Submission.user_id).filter(Submission.event_id == event.id).distinct().count()

    return {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "target_branch": event.target_branch,
        "target_year": event.target_year,
        "start_time": event.start_time,
        "end_time": event.end_time,
        "duration_minutes": event.duration_minutes,
        "status": event.status,
        "is_leaderboard_visible": event.is_leaderboard_visible,
        "allow_branch_questions": event.allow_branch_questions,
        "are_solutions_released": event.are_solutions_released,
        "are_results_released": event.are_results_released,
        "created_at": event.created_at,
        "total_questions": len(questions_list),
        "total_participants": participants_count,
        "questions": questions_list
    }

@router.post("/", response_model=EventOut)
def create_event(
    req: EventCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.CREATE_ASSESSMENT))
):
    event = Event(
        title=req.title.strip(),
        description=req.description,
        target_branch=req.target_branch,
        target_year=req.target_year,
        start_time=req.start_time,
        end_time=req.end_time,
        duration_minutes=req.duration_minutes,
        is_leaderboard_visible=req.is_leaderboard_visible,
        allow_branch_questions=req.allow_branch_questions,
        created_by_id=admin.id
    )
    db.add(event)
    db.flush()

    for idx, q_link in enumerate(req.questions):
        eq = EventQuestion(
            event_id=event.id,
            question_id=q_link.question_id,
            branch_override=q_link.branch_override or "ALL",
            year_override=q_link.year_override or 0,
            points=q_link.points or 100,
            order_index=idx + 1
        )
        db.add(eq)

    db.commit()
    db.refresh(event)
    _update_event_statuses(db)
    invalidate_events_cache()

    return EventOut(
        id=event.id,
        title=event.title,
        description=event.description,
        target_branch=event.target_branch,
        target_year=event.target_year,
        start_time=event.start_time,
        end_time=event.end_time,
        duration_minutes=event.duration_minutes,
        status=event.status,
        is_leaderboard_visible=event.is_leaderboard_visible,
        allow_branch_questions=event.allow_branch_questions,
        are_solutions_released=event.are_solutions_released,
        are_results_released=event.are_results_released,
        created_at=event.created_at,
        total_questions=len(req.questions),
        total_participants=0
    )

@router.put("/{event_id}")
def update_event(
    event_id: int,
    req: EventUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.EDIT_ASSESSMENT))
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")

    if req.title is not None:
        event.title = req.title.strip()
    if req.description is not None:
        event.description = req.description
    if req.target_branch is not None:
        event.target_branch = req.target_branch
    if req.target_year is not None:
        event.target_year = req.target_year
    if req.start_time is not None:
        event.start_time = req.start_time
    if req.end_time is not None:
        event.end_time = req.end_time
    if req.duration_minutes is not None:
        event.duration_minutes = req.duration_minutes
    if req.status is not None:
        event.status = req.status
    if req.is_leaderboard_visible is not None:
        event.is_leaderboard_visible = req.is_leaderboard_visible
    if req.are_solutions_released is not None:
        event.are_solutions_released = req.are_solutions_released
    if req.are_results_released is not None:
        event.are_results_released = req.are_results_released

    if req.questions is not None:
        db.query(EventQuestion).filter(EventQuestion.event_id == event_id).delete()
        for idx, q_link in enumerate(req.questions):
            eq = EventQuestion(
                event_id=event.id,
                question_id=q_link.question_id,
                branch_override=q_link.branch_override or "ALL",
                year_override=q_link.year_override or 0,
                points=q_link.points or 100,
                order_index=idx + 1
            )
            db.add(eq)

    db.commit()
    db.refresh(event)
    invalidate_events_cache()
    return {"message": "Event updated successfully.", "event_id": event.id}

@router.delete("/{event_id}")
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.DELETE_ASSESSMENT))
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")
    
    db.delete(event)
    db.commit()
    invalidate_events_cache()
    return {"message": f"Event '{event.title}' deleted successfully."}

@router.post("/{event_id}/release-results")
def release_results(
    event_id: int,
    release: bool = True,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.PUBLISH_ASSESSMENT))
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")
    event.are_results_released = release
    if release:
        event.status = EventStatus.RESULTS_RELEASED
    db.commit()
    invalidate_events_cache()
    return {"message": f"Results {'released' if release else 'unreleased'} for {event.title}."}

@router.post("/{event_id}/release-solutions")
def release_solutions(
    event_id: int,
    release: bool = True,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.PUBLISH_ASSESSMENT))
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")
    event.are_solutions_released = release
    db.commit()
    invalidate_events_cache()
    return {"message": f"Reference solutions {'released' if release else 'hidden'} for {event.title}."}

@router.post("/{event_id}/toggle-leaderboard")
def toggle_leaderboard(
    event_id: int,
    visible: bool = True,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.EDIT_ASSESSMENT))
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")
    event.is_leaderboard_visible = visible
    db.commit()
    invalidate_events_cache()
    return {"message": f"Leaderboard visibility set to {visible}."}

