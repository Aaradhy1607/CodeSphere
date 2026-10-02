import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.models import Question, Submission, QuestionFeedback, SubmissionVerdict

logger = logging.getLogger(__name__)

class AdaptiveLearningEngine:
    """
    Adaptive Statistical Difficulty Calibration & Psychometric Quality Feedback Engine.
    
    Calibrates question difficulty dynamically based on observed student performance
    signals (attempt count, pass rate, skip rate, and completion time) using bounded
    empirical Bayesian smoothing with explicit minimum-sample safety guards.
    
    Psychometric Item Discrimination is calculated using Kelly's 27% upper/lower cohort rule.
    """

    MIN_ATTEMPTS_FOR_CALIBRATION = 5
    MIN_ATTEMPTS_FOR_DISCRIMINATION = 10
    MAX_DIFFICULTY_DELTA_PER_UPDATE = 1.5
    SMOOTHING_PRIOR_STRENGTH = 10.0

    @classmethod
    def record_attempt_signal(
        cls,
        question_id: int,
        is_correct: bool,
        execution_time_seconds: float,
        is_skipped: bool,
        db: Session
    ) -> Dict[str, Any]:
        """
        Updates running attempt counters and applies bounded statistical calibration
        to question experienced difficulty once the minimum sample threshold is met.
        """
        q = db.query(Question).filter(Question.id == question_id).first()
        if not q:
            return {}

        q.total_attempts = (q.total_attempts or 0) + 1
        if is_correct:
            q.correct_attempts = (q.correct_attempts or 0) + 1
        if is_skipped:
            q.skip_count = (q.skip_count or 0) + 1

        # Running average completion time
        prev_time = q.average_time_seconds or 0.0
        n = q.total_attempts
        q.average_time_seconds = round(((prev_time * (n - 1)) + max(0.0, execution_time_seconds)) / n, 2)

        # 1. Minimum Sample-Size Guard
        if q.total_attempts < cls.MIN_ATTEMPTS_FOR_CALIBRATION:
            # Insufficient observations: Retain designed difficulty without premature recalibration
            q.experienced_difficulty = float(q.difficulty_score or 5.0)
        else:
            # 2. Bounded Statistical Calibration with Empirical Bayesian Smoothing
            pass_rate = q.correct_attempts / max(q.total_attempts, 1)
            skip_rate = (q.skip_count or 0) / max(q.total_attempts, 1)

            # Raw empirical difficulty mapped from [0.0, 1.0] pass rate to [10.0, 1.0] scale
            # High skip rate (>30%) introduces additional empirical difficulty friction (+0.5)
            skip_penalty = 0.5 if skip_rate > 0.30 else 0.0
            raw_empirical_diff = 10.0 - (pass_rate * 9.0) + skip_penalty
            raw_empirical_diff = max(1.0, min(10.0, raw_empirical_diff))

            # Confidence weight increases smoothly with sample size N: w = (N - MIN + 1) / (N + K)
            sample_diff = q.total_attempts - cls.MIN_ATTEMPTS_FOR_CALIBRATION + 1
            confidence_weight = min(0.90, sample_diff / (q.total_attempts + cls.SMOOTHING_PRIOR_STRENGTH))

            # Prior anchor is the author/AI designed difficulty
            prior_difficulty = float(q.difficulty_score or 5.0)
            target_calibrated = ((1.0 - confidence_weight) * prior_difficulty) + (confidence_weight * raw_empirical_diff)

            # Bounded delta update to prevent sudden fluctuations
            current_diff = float(q.experienced_difficulty if q.experienced_difficulty is not None else prior_difficulty)
            max_delta = cls.MAX_DIFFICULTY_DELTA_PER_UPDATE
            delta = target_calibrated - current_diff
            bounded_delta = max(-max_delta, min(max_delta, delta))
            new_diff = round(max(1.0, min(10.0, current_diff + bounded_delta)), 1)
            
            q.experienced_difficulty = new_diff

        # 3. Psychometric Item Discrimination Index (Kelly's 27% Rule)
        if q.total_attempts >= cls.MIN_ATTEMPTS_FOR_DISCRIMINATION:
            cls._recalculate_discrimination_index(q, db)

        db.commit()
        return {
            "total_attempts": q.total_attempts,
            "correct_attempts": q.correct_attempts,
            "experienced_difficulty": q.experienced_difficulty,
            "average_time_seconds": q.average_time_seconds,
            "discrimination_index": q.discrimination_index
        }

    @classmethod
    def _recalculate_discrimination_index(cls, question: Question, db: Session):
        """
        Calculates item discrimination index (D = Upper 27% pass rate - Lower 27% pass rate).
        D >= 0.30 represents high discrimination; D < 0.10 indicates low discrimination / ambiguous item.
        """
        subs = db.query(Submission).filter(
            Submission.question_id == question.id,
            Submission.is_final == True
        ).order_by(Submission.score.desc()).all()

        if len(subs) < cls.MIN_ATTEMPTS_FOR_DISCRIMINATION:
            return

        # Kelly's 27% rule for optimal item discrimination estimation
        k = max(1, int(round(len(subs) * 0.27)))
        top_group = subs[:k]
        bottom_group = subs[-k:]

        top_passed = sum(1 for s in top_group if s.verdict == SubmissionVerdict.AC.value)
        bottom_passed = sum(1 for s in bottom_group if s.verdict == SubmissionVerdict.AC.value)

        top_rate = top_passed / len(top_group)
        bottom_rate = bottom_passed / len(bottom_group)

        question.discrimination_index = round(top_rate - bottom_rate, 2)

    @classmethod
    def get_topic_adaptive_guidance(cls, topic: str, db: Session) -> str:
        """
        Generates prompt guidance for AI generation based on historical performance
        of previously evaluated questions on this topic.
        """
        questions = db.query(Question).filter(
            Question.topic == topic,
            Question.total_attempts >= cls.MIN_ATTEMPTS_FOR_CALIBRATION
        ).all()

        if not questions:
            return "No prior performance data for this topic. Generate with standard baseline parameters."

        avg_designed = sum(q.difficulty_score for q in questions) / len(questions)
        avg_experienced = sum(q.experienced_difficulty for q in questions if q.experienced_difficulty is not None) / len(questions)
        diff_gap = avg_experienced - avg_designed

        if diff_gap > 1.2:
            return f"Note: Students historically find '{topic}' problems harder (+{round(diff_gap, 1)} diff). Provide clearer hints in problem statements and avoid overly convoluted edge constraints."
        elif diff_gap < -1.2:
            return f"Note: Students historically find '{topic}' problems easier ({round(diff_gap, 1)} diff). Ensure hidden test vectors include strict bounds and large edge case inputs."
        
        return f"Historical difficulty for '{topic}' aligns well with designed expectations. Maintain current balanced calibration."

adaptive_learning_engine = AdaptiveLearningEngine()
