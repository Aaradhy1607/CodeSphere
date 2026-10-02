import random
import uuid
import datetime
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status

from app.models.models import (
    Assessment, AssessmentQuestion, AssessmentAttempt, AttemptAnswer,
    AntiCheatEvent, AntiCheatSeverity, AssessmentStatus, AttemptStatus,
    User, Question, QuestionType, TestCase, AssessmentResult
)
from app.services.evaluation_engine import evaluation_engine

class AssessmentService:
    def __init__(self):
        pass

    def update_assessment_lifecycle(self, db: Session):
        """
        Updates assessment statuses based on current server-authoritative time.
        DRAFT/SCHEDULED/PUBLISHED -> ACTIVE when window opens.
        ACTIVE -> COMPLETED when window closes.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        assessments = db.query(Assessment).all()
        changed = False

        for a in assessments:
            if a.status in [AssessmentStatus.ARCHIVED.value, AssessmentStatus.DRAFT.value]:
                continue

            start_t = a.start_time.replace(tzinfo=datetime.timezone.utc) if a.start_time.tzinfo is None else a.start_time
            end_t = a.end_time.replace(tzinfo=datetime.timezone.utc) if a.end_time.tzinfo is None else a.end_time

            if now < start_t:
                if a.status not in [AssessmentStatus.SCHEDULED.value, AssessmentStatus.PUBLISHED.value]:
                    a.status = AssessmentStatus.SCHEDULED.value
                    changed = True
            elif start_t <= now <= end_t:
                if a.status != AssessmentStatus.ACTIVE.value:
                    a.status = AssessmentStatus.ACTIVE.value
                    changed = True
            elif now > end_t:
                if a.status != AssessmentStatus.COMPLETED.value:
                    a.status = AssessmentStatus.COMPLETED.value
                    changed = True

        if changed:
            db.commit()

    def check_candidate_eligibility(self, assessment: Assessment, user: User) -> bool:
        """
        Verifies if candidate is authorized to take this assessment based on assignment rules.
        """
        assignment = assessment.candidate_assignment or {"type": "ALL"}
        assign_type = assignment.get("type", "ALL").upper()
        targets = assignment.get("targets", [])

        if assign_type == "ALL":
            return True

        if assign_type == "BRANCH":
            user_branch = user.student_profile.branch if user.student_profile else None
            return user_branch in targets or "ALL" in targets

        if assign_type == "YEAR":
            user_year = user.student_profile.academic_year if user.student_profile else None
            return user_year in targets or 0 in targets

        if assign_type in ["USER", "SPECIFIC", "CANDIDATE"]:
            return (user.id in targets) or (user.email in targets)

        return True

    def sanitize_question_for_exam(
        self,
        question: Question,
        aq: AssessmentQuestion,
        shuffled_options: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Sanitizes question data for student exam payload.
        Ensures NO correct answers, explanations, or hidden test cases are exposed to candidate.
        """
        # Sanitized options
        opts_to_return = []
        if shuffled_options is not None:
            opts_to_return = shuffled_options
        elif question.options and isinstance(question.options, list):
            for opt in question.options:
                if isinstance(opt, dict):
                    opts_to_return.append({
                        "id": opt.get("id"),
                        "text": opt.get("text", "")
                    })
                elif isinstance(opt, str):
                    opts_to_return.append({
                        "id": opt,
                        "text": opt
                    })

        # Only visible test cases
        visible_tcs = []
        for tc in (question.test_cases or []):
            if not tc.is_hidden:
                visible_tcs.append({
                    "id": tc.id,
                    "input_data": tc.input_data,
                    "expected_output": tc.expected_output,
                    "explanation": tc.explanation,
                    "points": tc.points
                })

        return {
            "id": aq.id,
            "question_id": question.id,
            "title": question.title,
            "slug": question.slug,
            "problem_statement": question.problem_statement,
            "question_type": question.question_type,
            "subject": question.subject,
            "topic": question.topic,
            "blooms_level": question.blooms_level,
            "section_name": aq.section_name or "General",
            "order_index": aq.order_index,
            "marks": aq.marks,
            "negative_marks": aq.negative_marks,
            "is_mandatory": aq.is_mandatory,
            "options": opts_to_return,
            "input_format": question.input_format or "",
            "output_format": question.output_format or "",
            "constraints": question.constraints or "",
            "examples": question.examples or [],
            "visible_test_cases": visible_tcs,
            "image_url": question.image_url
        }

    def start_or_resume_attempt(
        self,
        db: Session,
        assessment_id: int,
        user: User,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AssessmentAttempt:
        """
        Starts a new attempt or resumes an existing active attempt with deterministic stable randomization.
        """
        self.update_assessment_lifecycle(db)

        assessment = (
            db.query(Assessment)
            .options(joinedload(Assessment.questions).joinedload(AssessmentQuestion.question).joinedload(Question.test_cases))
            .filter(Assessment.id == assessment_id)
            .first()
        )
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found.")

        # Status validation
        if assessment.status in [AssessmentStatus.DRAFT.value, AssessmentStatus.ARCHIVED.value]:
            raise HTTPException(status_code=403, detail=f"Assessment is in '{assessment.status}' status and cannot be attempted.")

        now = datetime.datetime.now(datetime.timezone.utc)
        start_t = assessment.start_time.replace(tzinfo=datetime.timezone.utc) if assessment.start_time.tzinfo is None else assessment.start_time
        end_t = assessment.end_time.replace(tzinfo=datetime.timezone.utc) if assessment.end_time.tzinfo is None else assessment.end_time

        if now < start_t:
            raise HTTPException(status_code=400, detail=f"Assessment has not started yet. Starts at {start_t.isoformat()}.")
        if now > end_t:
            raise HTTPException(status_code=400, detail=f"Assessment has ended at {end_t.isoformat()}.")

        # Check candidate eligibility
        if not self.check_candidate_eligibility(assessment, user):
            raise HTTPException(status_code=403, detail="You are not assigned / eligible for this assessment.")

        # Check existing attempts
        existing_attempts = (
            db.query(AssessmentAttempt)
            .filter(AssessmentAttempt.assessment_id == assessment_id, AssessmentAttempt.candidate_id == user.id)
            .order_by(AssessmentAttempt.attempt_number.desc())
            .all()
        )

        # Check if there is an in-progress attempt
        for att in existing_attempts:
            if att.status == AttemptStatus.IN_PROGRESS.value:
                # Check expiry
                exp_t = att.expiry_time.replace(tzinfo=datetime.timezone.utc) if att.expiry_time.tzinfo is None else att.expiry_time
                if now > exp_t:
                    # Auto submit expired attempt
                    att.status = AttemptStatus.EXPIRED.value
                    evaluation_engine.evaluate_attempt(db, att)
                    db.commit()
                else:
                    # Resume existing in-progress attempt!
                    # Generate fresh session token to enforce single-active tab
                    att.session_token = str(uuid.uuid4())
                    att.last_heartbeat_at = now
                    if client_ip:
                        att.client_ip = client_ip
                    if user_agent:
                        att.user_agent = user_agent
                    db.commit()
                    return att

        # Check max attempts limit
        completed_count = len([att for att in existing_attempts if att.status != AttemptStatus.IN_PROGRESS.value])
        if completed_count >= (assessment.max_attempts or 1):
            raise HTTPException(
                status_code=400,
                detail=f"Maximum attempt limit ({assessment.max_attempts}) reached for this assessment."
            )

        # Create brand new attempt
        attempt_id = str(uuid.uuid4())
        seed = random.randint(100000, 999999)
        rng = random.Random(seed)

        # Determine question order
        raw_question_ids = [aq.question_id for aq in assessment.questions]
        question_order = list(raw_question_ids)
        if assessment.randomize_questions:
            rng.shuffle(question_order)

        # Determine option mappings for MCQs
        option_mapping: Dict[str, Dict[str, str]] = {}
        standard_keys = ["A", "B", "C", "D", "E", "F", "G", "H"]

        if assessment.randomize_options:
            for aq in assessment.questions:
                q = aq.question
                if q.question_type in [QuestionType.MCQ.value, "MULTIPLE_SELECT", "MSQ"] and q.options and isinstance(q.options, list):
                    original_opts = []
                    for idx, o in enumerate(q.options):
                        orig_id = o.get("id") if isinstance(o, dict) else standard_keys[idx]
                        orig_text = o.get("text") if isinstance(o, dict) else str(o)
                        original_opts.append((orig_id, orig_text))

                    # Deterministic shuffle for this question
                    q_rng = random.Random(f"{seed}_{q.id}")
                    shuffled_tuples = list(original_opts)
                    q_rng.shuffle(shuffled_tuples)

                    # Map shuffled keys (A, B, C...) to original keys
                    q_opt_map = {}
                    for new_idx, (orig_id, orig_text) in enumerate(shuffled_tuples):
                        assigned_key = standard_keys[new_idx] if new_idx < len(standard_keys) else str(new_idx)
                        q_opt_map[assigned_key] = orig_id
                    
                    option_mapping[str(q.id)] = q_opt_map

        # Server-authoritative duration & expiry
        attempt_duration = datetime.timedelta(minutes=assessment.duration_minutes)
        computed_expiry = now + attempt_duration
        # Ensure attempt does not exceed overall assessment window end time
        if computed_expiry > end_t:
            computed_expiry = end_t

        new_attempt = AssessmentAttempt(
            id=attempt_id,
            assessment_id=assessment.id,
            candidate_id=user.id,
            attempt_number=completed_count + 1,
            status=AttemptStatus.IN_PROGRESS.value,
            start_time=now,
            expiry_time=computed_expiry,
            seed=seed,
            question_order=question_order,
            option_mapping=option_mapping,
            integrity_score=100.0,
            session_token=str(uuid.uuid4()),
            client_ip=client_ip,
            user_agent=user_agent,
            last_heartbeat_at=now
        )

        db.add(new_attempt)
        db.commit()
        db.refresh(new_attempt)
        return new_attempt

    def get_attempt_state(
        self,
        db: Session,
        attempt_id: str,
        user: User
    ) -> Dict[str, Any]:
        """
        Retrieves the exact attempt state, server-authoritative remaining time, saved answers,
        and sanitized questions in candidate's assigned random order.
        """
        attempt = (
            db.query(AssessmentAttempt)
            .options(
                joinedload(AssessmentAttempt.assessment).joinedload(Assessment.questions).joinedload(AssessmentQuestion.question).joinedload(Question.test_cases),
                joinedload(AssessmentAttempt.answers)
            )
            .filter(AssessmentAttempt.id == attempt_id)
            .first()
        )
        if not attempt:
            raise HTTPException(status_code=404, detail="Attempt not found.")

        # IDOR / Authorization check: Candidate can only access their own attempt; Admin/Faculty can inspect
        is_owner = (attempt.candidate_id == user.id)
        is_staff = (user.role in ["ADMIN", "SUPER_ADMIN", "FACULTY", "PLACEMENT_ADMIN"])
        if not is_owner and not is_staff:
            raise HTTPException(status_code=403, detail="Access denied. You cannot view another candidate's attempt.")

        now = datetime.datetime.now(datetime.timezone.utc)
        exp_t = attempt.expiry_time.replace(tzinfo=datetime.timezone.utc) if attempt.expiry_time.tzinfo is None else attempt.expiry_time

        # If expired and still marked IN_PROGRESS, auto-evaluate
        if attempt.status == AttemptStatus.IN_PROGRESS.value and now > exp_t:
            attempt.status = AttemptStatus.EXPIRED.value
            evaluation_engine.evaluate_attempt(db, attempt)
            db.commit()

        rem_seconds = max(0, int((exp_t - now).total_seconds())) if attempt.status == AttemptStatus.IN_PROGRESS.value else 0

        # Construct sanitized question list in candidate's randomized question order
        assessment = attempt.assessment
        questions_by_id = {aq.question_id: aq for aq in assessment.questions}
        option_mapping = attempt.option_mapping or {}
        standard_keys = ["A", "B", "C", "D", "E", "F", "G", "H"]

        sanitized_questions = []
        for q_id in (attempt.question_order or [aq.question_id for aq in assessment.questions]):
            aq = questions_by_id.get(q_id)
            if not aq:
                continue
            q = aq.question

            # Compute shuffled options for student view if randomized
            shuffled_opts = None
            q_map = option_mapping.get(str(q_id))
            if q_map and q.options and isinstance(q.options, list):
                # Reverse mapping from original option to text
                orig_text_map = {}
                for idx, o in enumerate(q.options):
                    o_id = o.get("id") if isinstance(o, dict) else standard_keys[idx]
                    o_text = o.get("text") if isinstance(o, dict) else str(o)
                    orig_text_map[o_id] = o_text

                shuffled_opts = []
                for assigned_key, orig_id in sorted(q_map.items()):
                    shuffled_opts.append({
                        "id": assigned_key,
                        "text": orig_text_map.get(orig_id, "")
                    })

            sanitized_q = self.sanitize_question_for_exam(q, aq, shuffled_opts)
            sanitized_questions.append(sanitized_q)

        # Saved answers
        saved_answers: Dict[str, Any] = {}
        answered_ids: List[int] = []
        flagged_ids: List[int] = []

        for ans in attempt.answers:
            saved_answers[str(ans.question_id)] = ans.answer_data or {}
            answered_ids.append(ans.question_id)
            if ans.is_flagged:
                flagged_ids.append(ans.question_id)

        return {
            "attempt_id": attempt.id,
            "assessment_id": assessment.id,
            "assessment_title": assessment.title,
            "status": attempt.status,
            "start_time": attempt.start_time,
            "expiry_time": attempt.expiry_time,
            "server_time": now,
            "remaining_seconds": rem_seconds,
            "total_questions": len(sanitized_questions),
            "answered_question_ids": answered_ids,
            "flagged_question_ids": flagged_ids,
            "saved_answers": saved_answers,
            "questions": sanitized_questions,
            "anti_cheat_policy": assessment.anti_cheat_policy or {},
            "integrity_score": attempt.integrity_score,
            "session_token": attempt.session_token or ""
        }

    def save_answer(
        self,
        db: Session,
        attempt_id: str,
        question_id: int,
        answer_data: Dict[str, Any],
        is_flagged: bool,
        user: User
    ) -> Tuple[bool, datetime.datetime, int]:
        """
        Idempotent answer persistence with optimistic concurrency and server-authoritative timer enforcement.
        """
        attempt = db.query(AssessmentAttempt).filter(AssessmentAttempt.id == attempt_id).first()
        if not attempt:
            raise HTTPException(status_code=404, detail="Attempt not found.")

        # IDOR check
        if attempt.candidate_id != user.id:
            raise HTTPException(status_code=403, detail="Cannot save answer for another candidate's attempt.")

        # Status check
        if attempt.status != AttemptStatus.IN_PROGRESS.value:
            raise HTTPException(status_code=400, detail=f"Attempt is already {attempt.status} and cannot accept answers.")

        # Expiry check with 15-second grace period for network latency
        now = datetime.datetime.now(datetime.timezone.utc)
        exp_t = attempt.expiry_time.replace(tzinfo=datetime.timezone.utc) if attempt.expiry_time.tzinfo is None else attempt.expiry_time
        grace_period = datetime.timedelta(seconds=15)

        if now > (exp_t + grace_period):
            attempt.status = AttemptStatus.EXPIRED.value
            evaluation_engine.evaluate_attempt(db, attempt)
            db.commit()
            raise HTTPException(status_code=400, detail="Exam time has expired. Attempt has been auto-submitted.")

        # Upsert answer
        ans = (
            db.query(AttemptAnswer)
            .filter(AttemptAnswer.attempt_id == attempt_id, AttemptAnswer.question_id == question_id)
            .first()
        )

        version = 1
        if not ans:
            ans = AttemptAnswer(
                attempt_id=attempt_id,
                question_id=question_id,
                answer_data=answer_data,
                is_flagged=is_flagged,
                version=1,
                saved_at=now
            )
            db.add(ans)
        else:
            ans.answer_data = answer_data
            ans.is_flagged = is_flagged
            ans.version = (ans.version or 1) + 1
            ans.saved_at = now
            version = ans.version

        attempt.last_heartbeat_at = now
        db.commit()
        return True, now, version

    def record_anti_cheat_event(
        self,
        db: Session,
        attempt_id: str,
        event_type: str,
        severity: str,
        metadata_json: Dict[str, Any],
        user: User
    ) -> AntiCheatEvent:
        """
        Records an immutable anti-cheat audit event, recalculates attempt integrity score,
        and applies configured assessment policy (warn, restrict, terminate).
        """
        attempt = db.query(AssessmentAttempt).filter(AssessmentAttempt.id == attempt_id).first()
        if not attempt:
            raise HTTPException(status_code=404, detail="Attempt not found.")

        if attempt.candidate_id != user.id:
            raise HTTPException(status_code=403, detail="Unauthorized.")

        now = datetime.datetime.now(datetime.timezone.utc)
        sev_upper = (severity or "INFO").upper()

        event = AntiCheatEvent(
            attempt_id=attempt_id,
            candidate_id=user.id,
            event_type=event_type.upper(),
            severity=sev_upper,
            metadata_json=metadata_json or {},
            timestamp=now
        )
        db.add(event)
        db.flush()

        # Integrity deductions: INFO=0, LOW=2, MEDIUM=5, HIGH=10, CRITICAL=25
        deductions = {
            AntiCheatSeverity.INFO.value: 0.0,
            AntiCheatSeverity.LOW.value: 2.0,
            AntiCheatSeverity.MEDIUM.value: 5.0,
            AntiCheatSeverity.HIGH.value: 10.0,
            AntiCheatSeverity.CRITICAL.value: 25.0,
        }
        deduction = deductions.get(sev_upper, 2.0)
        attempt.integrity_score = max(0.0, round((attempt.integrity_score or 100.0) - deduction, 1))

        # Check assessment anti-cheat policy
        policy = attempt.assessment.anti_cheat_policy or {}
        max_switches = policy.get("max_tab_switches", 5)
        policy_action = policy.get("action", "WARN").upper()

        if event_type.upper() in ["TAB_BLUR", "TAB_VISIBILITY_CHANGE", "FULLSCREEN_EXIT"]:
            # Count tab switch events
            switch_count = (
                db.query(AntiCheatEvent)
                .filter(
                    AntiCheatEvent.attempt_id == attempt_id,
                    AntiCheatEvent.event_type.in_(["TAB_BLUR", "TAB_VISIBILITY_CHANGE", "FULLSCREEN_EXIT"])
                )
                .count()
            )
            if switch_count >= max_switches and policy_action == "TERMINATE" and attempt.status == AttemptStatus.IN_PROGRESS.value:
                attempt.status = AttemptStatus.TERMINATED.value
                evaluation_engine.evaluate_attempt(db, attempt)

        db.commit()
        db.refresh(event)
        return event

    def submit_attempt(
        self,
        db: Session,
        attempt_id: str,
        user: User,
        final_sync_answers: Optional[Dict[str, Any]] = None
    ) -> AssessmentResult:
        """
        Finalizes and grades the candidate's assessment attempt.
        Applies duplicate submission protection and final sync synchronization.
        """
        attempt = (
            db.query(AssessmentAttempt)
            .options(
                joinedload(AssessmentAttempt.assessment).joinedload(Assessment.questions).joinedload(AssessmentQuestion.question).joinedload(Question.test_cases),
                joinedload(AssessmentAttempt.answers)
            )
            .filter(AssessmentAttempt.id == attempt_id)
            .first()
        )
        if not attempt:
            raise HTTPException(status_code=404, detail="Attempt not found.")

        # IDOR check
        if attempt.candidate_id != user.id and user.role not in ["ADMIN", "SUPER_ADMIN"]:
            raise HTTPException(status_code=403, detail="Cannot submit another candidate's attempt.")

        # Duplicate submission protection
        if attempt.status in [AttemptStatus.SUBMITTED.value, AttemptStatus.EXPIRED.value, AttemptStatus.TERMINATED.value]:
            # If already submitted, return the existing result idempotently
            result = db.query(AssessmentResult).filter(AssessmentResult.attempt_id == attempt.id).first()
            if result:
                return result
            # Otherwise evaluate
            return evaluation_engine.evaluate_attempt(db, attempt)

        now = datetime.datetime.now(datetime.timezone.utc)
        
        # Save any final sync answers passed with submit payload
        if final_sync_answers and isinstance(final_sync_answers, dict):
            for q_id_str, ans_val in final_sync_answers.items():
                try:
                    q_id = int(q_id_str)
                    existing_ans = next((a for a in attempt.answers if a.question_id == q_id), None)
                    if not existing_ans:
                        new_ans = AttemptAnswer(
                            attempt_id=attempt_id,
                            question_id=q_id,
                            answer_data=ans_val if isinstance(ans_val, dict) else {"selected_option": ans_val},
                            is_flagged=False,
                            version=1,
                            saved_at=now
                        )
                        db.add(new_ans)
                    else:
                        existing_ans.answer_data = ans_val if isinstance(ans_val, dict) else {"selected_option": ans_val}
                        existing_ans.saved_at = now
                except (ValueError, TypeError):
                    continue
            db.flush()

        # Mark attempt as submitted
        attempt.status = AttemptStatus.SUBMITTED.value
        attempt.submitted_at = now

        # Run multi-type evaluation engine
        result = evaluation_engine.evaluate_attempt(db, attempt)
        db.commit()
        db.refresh(result)
        return result

assessment_service = AssessmentService()
