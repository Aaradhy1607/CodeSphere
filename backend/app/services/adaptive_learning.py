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

    @classmethod
    def get_student_adaptive_recommendation(
        cls,
        student_id: int,
        db: Session
    ) -> Dict[str, Any]:
        """
        Derives an evidence-based adaptive learning profile and recommendations for a student.
        - Cold start (< 3 submissions): flagged with has_sufficient_history: False and provides safe baseline recommendations.
        - Weak performance (overall accuracy < 40%): recommends foundational reinforcement (difficulty 2.5 - 3.5), target weak topics.
        - Strong performance (overall accuracy >= 80%): recommends advanced challenges (difficulty 7.5 - 9.0), target complex concepts.
        - Mixed performance (40% - 80%): recommends balanced progression (difficulty 4.5 - 6.0), focus on lower-accuracy topics.
        - Never fabricates metrics; all statistics are derived directly from user's final submissions in DB.
        """
        from app.models.models import User
        user = db.query(User).filter(User.id == student_id).first()
        if not user:
            return {"error": "Student not found"}

        subs = db.query(Submission).filter(
            Submission.user_id == student_id,
            Submission.is_final == True
        ).all()

        total_attempts = len(subs)

        # Cold start / Insufficient data check
        if total_attempts < 3:
            return {
                "student_id": student_id,
                "student_name": user.full_name,
                "total_submissions": total_attempts,
                "has_sufficient_history": False,
                "overall_accuracy": round((sum(1 for s in subs if str(s.verdict).upper() in ("AC", "ACCEPTED")) / total_attempts * 100.0), 1) if total_attempts > 0 else 0.0,
                "recommended_difficulty_score": 3.0,
                "recommended_difficulty_label": "Easy",
                "learning_path_mode": "FOUNDATIONAL_BUILDER",
                "recommended_topics": ["Arrays", "Strings", "Basic Math"],
                "focus_area": "Foundational programming logic & syntax",
                "feedback_summary": f"Initial assessment baseline ({total_attempts}/3 submissions). Complete 3 or more problems to unlock tailored adaptive recommendations."
            }

        # Detailed topic accuracy breakdown
        topic_stats: Dict[str, Dict[str, int]] = {}
        ac_count = 0

        for s in subs:
            is_ac = str(s.verdict).upper() in ("AC", "ACCEPTED")
            if is_ac:
                ac_count += 1

            # Extract topic
            topic_name = "General Problem Solving"
            if s.question and s.question.topic:
                topic_name = s.question.topic.strip()

            if topic_name not in topic_stats:
                topic_stats[topic_name] = {"total": 0, "correct": 0}
            topic_stats[topic_name]["total"] += 1
            if is_ac:
                topic_stats[topic_name]["correct"] += 1

        accuracy = round((ac_count / total_attempts) * 100.0, 1)

        # Classify topic mastery
        weak_topics = []
        strong_topics = []
        for t_name, stats in topic_stats.items():
            t_acc = (stats["correct"] / stats["total"]) * 100.0
            if t_acc < 50.0:
                weak_topics.append({"topic": t_name, "accuracy": round(t_acc, 1), "attempts": stats["total"]})
            elif t_acc >= 75.0:
                strong_topics.append({"topic": t_name, "accuracy": round(t_acc, 1), "attempts": stats["total"]})

        # Sort weak topics ascending by accuracy
        weak_topics.sort(key=lambda x: x["accuracy"])
        # Sort strong topics descending by accuracy
        strong_topics.sort(key=lambda x: x["accuracy"], reverse=True)

        if accuracy < 40.0:
            rec_diff = 3.0
            rec_label = "Easy"
            mode = "CONCEPT_REINFORCEMENT"
            rec_topics = [t["topic"] for t in weak_topics[:3]] or ["Arrays", "Strings", "Sorting"]
            summary = f"Student performance indicates foundational struggle (overall accuracy {accuracy}%). Recommending reinforced practice in core concepts: {', '.join(rec_topics)}."
            focus = "Core algorithm understanding and boundary edge case handling."
        elif accuracy >= 80.0:
            rec_diff = 8.0
            rec_label = "Hard"
            mode = "ADVANCED_CHALLENGE"
            rec_topics = ["Dynamic Programming", "Graph Theory", "Advanced Trees"]
            summary = f"Student demonstrates high mastery (overall accuracy {accuracy}%). Recommending advanced optimization and complex algorithmic challenges."
            focus = "Algorithmic time-space optimization and competitive problem solving."
        else:
            rec_diff = 5.5
            rec_label = "Medium"
            mode = "BALANCED_PROGRESSION"
            rec_topics = [t["topic"] for t in weak_topics[:2]] + ([t["topic"] for t in strong_topics[:1]] or ["Greedy Algorithms"])
            summary = f"Student demonstrates steady progress (overall accuracy {accuracy}%). Recommending balanced progression focusing on weaker areas ({', '.join([t['topic'] for t in weak_topics[:2]]) or 'Intermediate Data Structures'})."
            focus = "Targeted refinement of weaker topic categories with gradual difficulty escalation."

        return {
            "student_id": student_id,
            "student_name": user.full_name,
            "total_submissions": total_attempts,
            "has_sufficient_history": True,
            "overall_accuracy": accuracy,
            "recommended_difficulty_score": rec_diff,
            "recommended_difficulty_label": rec_label,
            "learning_path_mode": mode,
            "recommended_topics": rec_topics,
            "focus_area": focus,
            "feedback_summary": summary,
            "weak_topics": weak_topics,
            "strong_topics": strong_topics
        }

adaptive_learning_engine = AdaptiveLearningEngine()
