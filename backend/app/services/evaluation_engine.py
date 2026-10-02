import datetime
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from app.models.models import (
    Question, TestCase, QuestionType, SubmissionVerdict,
    Assessment, AssessmentAttempt, AttemptAnswer, AssessmentResult, AttemptStatus
)
from app.services.code_runner import code_runner

class AssessmentEvaluationEngine:
    def __init__(self):
        pass

    def evaluate_mcq(
        self,
        question: Question,
        answer_data: Dict[str, Any],
        marks: float,
        negative_marks: float,
        option_mapping_for_q: Optional[Dict[str, str]] = None
    ) -> Tuple[float, str, Dict[str, Any]]:
        """
        Evaluates Single-Choice MCQ.
        Translates candidate's selected option using attempt's option mapping if randomized.
        """
        selected_option = answer_data.get("selected_option")
        if not selected_option:
            return 0.0, "SKIPPED", {"reason": "No option selected", "is_correct": False}

        # If option randomization was applied, translate candidate's option key back to original key
        actual_selected = selected_option
        if option_mapping_for_q and selected_option in option_mapping_for_q:
            actual_selected = option_mapping_for_q[selected_option]

        # Determine correct answer
        expected_correct = None
        if question.correct_answer:
            expected_correct = str(question.correct_answer).strip()
        elif question.options and isinstance(question.options, list):
            for opt in question.options:
                if isinstance(opt, dict) and opt.get("is_correct"):
                    expected_correct = str(opt.get("id", "")).strip()
                    break

        is_correct = (expected_correct is not None and str(actual_selected).strip().upper() == expected_correct.upper())
        
        if is_correct:
            return marks, "CORRECT", {
                "selected_option": selected_option,
                "translated_option": actual_selected,
                "is_correct": True,
                "earned_marks": marks
            }
        else:
            deduction = negative_marks if negative_marks > 0 else 0.0
            score = -deduction
            return score, "INCORRECT", {
                "selected_option": selected_option,
                "translated_option": actual_selected,
                "is_correct": False,
                "deduction": deduction,
                "earned_marks": score
            }

    def evaluate_multiselect(
        self,
        question: Question,
        answer_data: Dict[str, Any],
        marks: float,
        negative_marks: float,
        option_mapping_for_q: Optional[Dict[str, str]] = None
    ) -> Tuple[float, str, Dict[str, Any]]:
        """
        Evaluates Multiple-Select / Multi-Choice Questions.
        Supports partial scoring or full all-or-nothing matching.
        """
        selected_options = answer_data.get("selected_options") or []
        if not selected_options:
            return 0.0, "SKIPPED", {"reason": "No options selected", "is_correct": False}

        # Translate selected options
        actual_selected_set = set()
        for opt in selected_options:
            actual_opt = opt
            if option_mapping_for_q and opt in option_mapping_for_q:
                actual_opt = option_mapping_for_q[opt]
            actual_selected_set.add(str(actual_opt).strip().upper())

        # Determine correct options set
        expected_correct_set = set()
        if question.options and isinstance(question.options, list):
            for opt in question.options:
                if isinstance(opt, dict) and opt.get("is_correct"):
                    expected_correct_set.add(str(opt.get("id", "")).strip().upper())

        if not expected_correct_set and question.correct_answer:
            try:
                parsed_ans = json.loads(question.correct_answer)
                if isinstance(parsed_ans, list):
                    expected_correct_set = {str(x).strip().upper() for x in parsed_ans if str(x).strip()}
                elif isinstance(parsed_ans, str):
                    expected_correct_set = {x.strip().upper() for x in parsed_ans.split(",") if x.strip()}
            except Exception:
                raw_ans = question.correct_answer.strip("[]'\" ")
                expected_correct_set = {x.strip().strip("'\"").upper() for x in raw_ans.split(",") if x.strip()}

        if not expected_correct_set:
            return 0.0, "ERROR", {"error": "No correct answer configured"}

        correct_picks = actual_selected_set.intersection(expected_correct_set)
        incorrect_picks = actual_selected_set - expected_correct_set

        if len(correct_picks) == len(expected_correct_set) and len(incorrect_picks) == 0:
            return marks, "CORRECT", {
                "selected_options": selected_options,
                "is_correct": True,
                "earned_marks": marks
            }
        elif len(incorrect_picks) > 0 and len(correct_picks) == 0:
            deduction = negative_marks if negative_marks > 0 else 0.0
            return -deduction, "INCORRECT", {
                "selected_options": selected_options,
                "is_correct": False,
                "earned_marks": -deduction
            }
        else:
            # Partial scoring: ratio of correctly chosen minus incorrect penalty
            ratio = max(0.0, (len(correct_picks) - len(incorrect_picks)) / len(expected_correct_set))
            score = round(ratio * marks, 2)
            verdict = "PARTIAL" if score > 0 else "INCORRECT"
            return score, verdict, {
                "selected_options": selected_options,
                "correct_count": len(correct_picks),
                "total_correct": len(expected_correct_set),
                "earned_marks": score
            }

    def evaluate_coding(
        self,
        question: Question,
        answer_data: Dict[str, Any],
        marks: float
    ) -> Tuple[float, str, Dict[str, Any], float, float]:
        """
        Evaluates Coding submissions using the sandboxed CodeRunner.
        Evaluates against all visible and hidden test cases.
        Returns: (score, verdict, details, execution_time_ms, memory_used_kb)
        """
        code = answer_data.get("code", "").strip()
        language = answer_data.get("language", "python").strip()

        if not code:
            return 0.0, "SKIPPED", {"reason": "No code submitted"}, 0.0, 0.0

        test_cases = question.test_cases or []
        if not test_cases:
            return marks, SubmissionVerdict.AC, {"note": "No test cases configured, full marks awarded"}, 0.0, 0.0

        eval_result = code_runner.evaluate_test_cases(code, language, test_cases)
        
        passed_count = eval_result.get("passed_count", 0)
        total_count = eval_result.get("total_count", len(test_cases))
        verdict = eval_result.get("verdict", SubmissionVerdict.WA)
        
        ratio = (passed_count / total_count) if total_count > 0 else 0.0
        score = round(ratio * marks, 2)

        return (
            score,
            verdict,
            eval_result,
            eval_result.get("max_time_ms", 0.0),
            0.0
        )

    def evaluate_subjective(
        self,
        question: Question,
        answer_data: Dict[str, Any],
        marks: float
    ) -> Tuple[float, str, Dict[str, Any]]:
        """
        Stores subjective answer for manual review.
        """
        text = answer_data.get("subjective_text", "").strip()
        if not text:
            return 0.0, "SKIPPED", {"reason": "No subjective response provided"}

        return 0.0, "MANUAL_REVIEW", {
            "submitted_length": len(text),
            "status": "PENDING_FACULTY_EVALUATION",
            "max_marks": marks
        }

    def evaluate_attempt(
        self,
        db: Session,
        attempt: AssessmentAttempt
    ) -> AssessmentResult:
        """
        Evaluates all answers in the attempt, records detailed question/section/difficulty breakdowns,
        and saves or updates the AssessmentResult.
        """
        assessment = attempt.assessment
        questions_map = {aq.question_id: aq for aq in assessment.questions}
        option_mapping = attempt.option_mapping or {}

        # Fetch all answers for attempt
        answers = {ans.question_id: ans for ans in attempt.answers}

        total_score = 0.0
        max_score = 0.0
        correct_count = 0
        incorrect_count = 0
        skipped_count = 0
        attempted_count = 0
        
        question_breakdown = []
        section_breakdown: Dict[str, Dict[str, Any]] = {}
        difficulty_breakdown: Dict[str, Dict[str, Any]] = {
            "EASY": {"total": 0, "correct": 0, "score": 0.0, "max_score": 0.0},
            "MEDIUM": {"total": 0, "correct": 0, "score": 0.0, "max_score": 0.0},
            "HARD": {"total": 0, "correct": 0, "score": 0.0, "max_score": 0.0},
        }
        topic_breakdown: Dict[str, Dict[str, Any]] = {}

        for q_id in (attempt.question_order or [aq.question_id for aq in assessment.questions]):
            aq = questions_map.get(q_id)
            if not aq:
                continue

            q = aq.question
            q_marks = aq.marks
            q_neg_marks = aq.negative_marks if aq.negative_marks > 0 else (assessment.negative_mark_rate * q_marks if assessment.negative_marking else 0.0)
            max_score += q_marks

            section = aq.section_name or "General"
            if section not in section_breakdown:
                section_breakdown[section] = {"total_questions": 0, "score": 0.0, "max_score": 0.0, "correct": 0}
            section_breakdown[section]["total_questions"] += 1
            section_breakdown[section]["max_score"] += q_marks

            # Categorize difficulty
            diff_score = q.difficulty_score or 5
            diff_key = "EASY" if diff_score <= 3 else ("MEDIUM" if diff_score <= 7 else "HARD")
            difficulty_breakdown[diff_key]["total"] += 1
            difficulty_breakdown[diff_key]["max_score"] += q_marks

            # Categorize topic
            topic = q.topic or q.subject or "General"
            if topic not in topic_breakdown:
                topic_breakdown[topic] = {"total": 0, "correct": 0, "score": 0.0, "max_score": 0.0}
            topic_breakdown[topic]["total"] += 1
            topic_breakdown[topic]["max_score"] += q_marks

            ans = answers.get(q_id)
            earned_score = 0.0
            verdict = "SKIPPED"
            details = {}
            exec_time = 0.0
            mem_used = 0.0

            if ans and ans.answer_data:
                q_type = (q.question_type or QuestionType.CODING.value).upper()
                q_opt_map = option_mapping.get(str(q_id), {})

                if q_type == QuestionType.MCQ.value:
                    earned_score, verdict, details = self.evaluate_mcq(q, ans.answer_data, q_marks, q_neg_marks, q_opt_map)
                elif q_type in ["MULTIPLE_SELECT", "MSQ"]:
                    earned_score, verdict, details = self.evaluate_multiselect(q, ans.answer_data, q_marks, q_neg_marks, q_opt_map)
                elif q_type == QuestionType.CODING.value:
                    earned_score, verdict, details, exec_time, mem_used = self.evaluate_coding(q, ans.answer_data, q_marks)
                elif q_type == QuestionType.SUBJECTIVE.value:
                    earned_score, verdict, details = self.evaluate_subjective(q, ans.answer_data, q_marks)
                else:
                    earned_score, verdict, details = self.evaluate_mcq(q, ans.answer_data, q_marks, q_neg_marks, q_opt_map)

                ans.is_evaluated = True
                ans.score_awarded = earned_score
                ans.evaluation_verdict = str(verdict)
                ans.evaluation_details = details
                ans.execution_time_ms = exec_time
                ans.memory_used_kb = mem_used

            if verdict in ["CORRECT", SubmissionVerdict.AC]:
                correct_count += 1
                attempted_count += 1
                section_breakdown[section]["correct"] += 1
                difficulty_breakdown[diff_key]["correct"] += 1
                topic_breakdown[topic]["correct"] += 1
            elif verdict in ["INCORRECT", "PARTIAL", SubmissionVerdict.WA, SubmissionVerdict.TLE, SubmissionVerdict.MLE, SubmissionVerdict.CE, SubmissionVerdict.RE]:
                incorrect_count += 1
                attempted_count += 1
            elif verdict == "MANUAL_REVIEW":
                attempted_count += 1
            else:
                skipped_count += 1

            total_score += earned_score
            section_breakdown[section]["score"] += earned_score
            difficulty_breakdown[diff_key]["score"] += earned_score
            topic_breakdown[topic]["score"] += earned_score

            question_breakdown.append({
                "question_id": q_id,
                "title": q.title,
                "question_type": q.question_type,
                "section_name": section,
                "marks": q_marks,
                "earned_score": earned_score,
                "verdict": str(verdict),
                "is_correct": verdict in ["CORRECT", SubmissionVerdict.AC],
                "details": details if assessment.allow_review or assessment.show_results_immediately else {}
            })

        # Clamped final total score
        total_score = max(0.0, round(total_score, 2))
        percentage = round((total_score / max_score * 100.0), 2) if max_score > 0 else 0.0
        accuracy = round((correct_count / attempted_count * 100.0), 2) if attempted_count > 0 else 0.0
        passed = (percentage >= (assessment.passing_score or 50.0))

        # Time spent
        now = datetime.datetime.now(datetime.timezone.utc)
        sub_time = attempt.submitted_at or now
        start_t = attempt.start_time.replace(tzinfo=datetime.timezone.utc) if attempt.start_time.tzinfo is None else attempt.start_time
        sub_t = sub_time.replace(tzinfo=datetime.timezone.utc) if sub_time.tzinfo is None else sub_time
        time_spent_seconds = max(0.0, (sub_t - start_t).total_seconds())

        # Update attempt fields
        attempt.score = total_score
        attempt.total_marks = max_score
        attempt.percentage = percentage
        attempt.accuracy = accuracy
        attempt.passed = passed
        if not attempt.submitted_at:
            attempt.submitted_at = now

        # Upsert AssessmentResult
        result = db.query(AssessmentResult).filter(AssessmentResult.attempt_id == attempt.id).first()
        if not result:
            result = AssessmentResult(
                attempt_id=attempt.id,
                assessment_id=assessment.id,
                user_id=attempt.candidate_id,
            )
            db.add(result)

        result.total_score = total_score
        result.max_score = max_score
        result.percentage = percentage
        result.accuracy = accuracy
        result.passed = passed
        result.total_questions = len(question_breakdown)
        result.attempted_count = attempted_count
        result.correct_count = correct_count
        result.incorrect_count = incorrect_count
        result.skipped_count = skipped_count
        result.time_spent_seconds = time_spent_seconds
        result.question_breakdown = question_breakdown
        result.section_breakdown = section_breakdown
        result.difficulty_breakdown = difficulty_breakdown
        result.topic_breakdown = topic_breakdown

        # Calculate percentile & rank dynamically if multiple attempts exist
        all_results = (
            db.query(AssessmentResult)
            .filter(AssessmentResult.assessment_id == assessment.id)
            .order_by(AssessmentResult.total_score.desc(), AssessmentResult.time_spent_seconds.asc())
            .all()
        )
        
        # Include current result in sorting if not already committed
        candidate_results = [r for r in all_results if r.attempt_id != attempt.id]
        candidate_results.append(result)
        candidate_results.sort(key=lambda r: (r.total_score, -r.time_spent_seconds), reverse=True)

        total_cohort = len(candidate_results)
        for idx, cr in enumerate(candidate_results):
            cr.rank = idx + 1
            cr.total_candidates = total_cohort
            if total_cohort > 1:
                # Standard percentile rank: ((N - Rank) / (N - 1)) * 100
                cr.percentile = round(((total_cohort - (idx + 1)) / (total_cohort - 1)) * 100.0, 2)
            else:
                cr.percentile = 100.0

        db.flush()
        return result

evaluation_engine = AssessmentEvaluationEngine()
