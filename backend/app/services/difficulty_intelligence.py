from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.models import Question, Submission, SubmissionVerdict

class DifficultyIntelligenceService:
    """
    Evidence-Based Problem Difficulty & Historical Verdict Analytics Engine for CodeSphere.
    
    Computes factual observed difficulty metrics strictly from real historical submissions.
    Distinguishes Author Difficulty (1-10 / Easy-Med-Hard) from Observed Difficulty.
    Guarantees zero metric fabrication: If observations are below sample threshold (N < 5),
    explicitly returns `has_sufficient_data: False`.
    """

    MIN_SAMPLES_THRESHOLD = 5

    @classmethod
    def get_difficulty_label(cls, score: float) -> str:
        if score <= 3.5:
            return "Easy"
        elif score <= 7.0:
            return "Medium"
        return "Hard"

    @classmethod
    def analyze_question_difficulty(cls, question_id: int, db: Session) -> Dict[str, Any]:
        """
        Calculates factual observed performance statistics for a question.
        """
        q = db.query(Question).filter(Question.id == question_id).first()
        if not q:
            return {"error": "Question not found"}

        author_score = float(q.difficulty_score or 5.0)
        author_label = cls.get_difficulty_label(author_score)

        # Query all submissions for this question
        submissions = db.query(Submission).filter(
            Submission.question_id == question_id
        ).order_by(Submission.submitted_at.asc()).all()

        total_subs = len(submissions)
        if total_subs < cls.MIN_SAMPLES_THRESHOLD:
            return {
                "question_id": question_id,
                "title": q.title,
                "author_difficulty_score": author_score,
                "author_difficulty_label": author_label,
                "has_sufficient_data": False,
                "sample_count": total_subs,
                "min_required_samples": cls.MIN_SAMPLES_THRESHOLD,
                "notes": f"Insufficient submission data ({total_subs}/{cls.MIN_SAMPLES_THRESHOLD} submissions). Observed difficulty will calibrate as more students submit.",
                "observed_difficulty_score": None,
                "observed_difficulty_label": "Insufficient Data",
                "acceptance_rate": 0.0,
                "first_attempt_ac_rate": 0.0,
                "avg_attempts_to_ac": 0.0,
                "avg_execution_time_ms": 0.0,
                "avg_memory_kb": 0.0,
                "verdict_distribution": {},
                "language_breakdown": {}
            }

        # Calculate verdict counts
        verdict_counts: Dict[str, int] = {
            "AC": 0, "WA": 0, "TLE": 0, "MLE": 0, "RE": 0, "CE": 0, "OLE": 0, "OTHER": 0
        }
        user_attempts: Dict[int, List[Submission]] = {}
        total_time_ms = 0.0
        total_memory_kb = 0.0
        lang_stats: Dict[str, Dict[str, Any]] = {}

        for sub in submissions:
            # Map verdict string
            v_str = str(sub.verdict).upper()
            if "ACCEPTED" in v_str or v_str == "AC":
                v_key = "AC"
            elif "WRONG" in v_str or v_str == "WA":
                v_key = "WA"
            elif "TIME LIMIT" in v_str or v_str == "TLE":
                v_key = "TLE"
            elif "MEMORY LIMIT" in v_str or v_str == "MLE":
                v_key = "MLE"
            elif "RUNTIME" in v_str or v_str == "RE":
                v_key = "RE"
            elif "COMPILATION" in v_str or v_str == "CE":
                v_key = "CE"
            elif "OUTPUT LIMIT" in v_str or v_str == "OLE":
                v_key = "OLE"
            else:
                v_key = "OTHER"

            verdict_counts[v_key] = verdict_counts.get(v_key, 0) + 1

            # Group per user
            uid = sub.user_id
            if uid not in user_attempts:
                user_attempts[uid] = []
            user_attempts[uid].append(sub)

            # Accumulate runtime/memory
            t_ms = float(sub.execution_time_ms or 0.0)
            m_kb = float(sub.memory_used_kb or 0.0)
            total_time_ms += t_ms
            total_memory_kb += m_kb

            # Language breakdown
            l_key = str(sub.language or "unknown").lower()
            if l_key not in lang_stats:
                lang_stats[l_key] = {"total": 0, "ac_count": 0, "total_time_ms": 0.0, "total_memory_kb": 0.0}
            lang_stats[l_key]["total"] += 1
            if v_key == "AC":
                lang_stats[l_key]["ac_count"] += 1
            lang_stats[l_key]["total_time_ms"] += t_ms
            lang_stats[l_key]["total_memory_kb"] += m_kb

        # Metrics computation
        ac_subs = verdict_counts["AC"]
        overall_ac_rate = round((ac_subs / total_subs) * 100.0, 1)

        # First attempt AC rate and avg attempts to solve
        distinct_users = len(user_attempts)
        first_attempt_ac_users = 0
        attempts_to_solve_list = []

        for uid, subs in user_attempts.items():
            if not subs:
                continue
            first_v = subs[0].verdict
            if "ACCEPTED" in str(first_v).upper() or str(first_v).upper() == "AC":
                first_attempt_ac_users += 1

            # Find attempts to first AC
            for idx, s in enumerate(subs, start=1):
                if "ACCEPTED" in str(s.verdict).upper() or str(s.verdict).upper() == "AC":
                    attempts_to_solve_list.append(idx)
                    break

        first_attempt_ac_rate = round((first_attempt_ac_users / distinct_users) * 100.0, 1) if distinct_users > 0 else 0.0
        avg_attempts_to_ac = round(sum(attempts_to_solve_list) / len(attempts_to_solve_list), 1) if attempts_to_solve_list else 0.0

        avg_time_ms = round(total_time_ms / total_subs, 1)
        avg_mem_kb = round(total_memory_kb / total_subs, 1)

        # Calibrated observed difficulty score (1.0 to 10.0 scale)
        # Factor 1: Inverse pass rate (100% pass -> 1.0 diff, 0% pass -> 10.0 diff)
        raw_pass_diff = 10.0 - (overall_ac_rate / 100.0 * 9.0)
        # Factor 2: First-attempt penalty
        first_fail_factor = (100.0 - first_attempt_ac_rate) / 100.0 * 1.5
        # Factor 3: TLE penalty (TLE indicates algorithmic complexity failure)
        tle_factor = (verdict_counts["TLE"] / total_subs) * 2.0

        raw_observed_score = max(1.0, min(10.0, raw_pass_diff * 0.7 + first_fail_factor + tle_factor))
        observed_difficulty_score = round(raw_observed_score, 1)
        observed_difficulty_label = cls.get_difficulty_label(observed_difficulty_score)

        # Format language breakdown
        formatted_langs = {}
        for l_k, s_dict in lang_stats.items():
            tot = s_dict["total"]
            formatted_langs[l_k] = {
                "total_submissions": tot,
                "ac_count": s_dict["ac_count"],
                "acceptance_rate": round((s_dict["ac_count"] / tot) * 100.0, 1) if tot > 0 else 0.0,
                "avg_execution_time_ms": round(s_dict["total_time_ms"] / tot, 1) if tot > 0 else 0.0,
                "avg_memory_kb": round(s_dict["total_memory_kb"] / tot, 1) if tot > 0 else 0.0
            }

        # Health / alignment note
        diff_gap = round(observed_difficulty_score - author_score, 1)
        if diff_gap >= 2.0:
            notes = f"Observed difficulty is significantly harder than author rating (+{diff_gap} gap, {overall_ac_rate}% AC rate). High frequency of TLE/WA detected."
        elif diff_gap <= -2.0:
            notes = f"Observed difficulty is noticeably easier than author rating ({diff_gap} gap, {overall_ac_rate}% AC rate)."
        else:
            notes = f"Observed difficulty ({observed_difficulty_score}/10) aligns well with author rating ({author_score}/10)."

        return {
            "question_id": question_id,
            "title": q.title,
            "author_difficulty_score": author_score,
            "author_difficulty_label": author_label,
            "has_sufficient_data": True,
            "sample_count": total_subs,
            "distinct_students": distinct_users,
            "observed_difficulty_score": observed_difficulty_score,
            "observed_difficulty_label": observed_difficulty_label,
            "difficulty_gap": diff_gap,
            "acceptance_rate": overall_ac_rate,
            "first_attempt_ac_rate": first_attempt_ac_rate,
            "avg_attempts_to_ac": avg_attempts_to_ac,
            "avg_execution_time_ms": avg_time_ms,
            "avg_memory_kb": avg_mem_kb,
            "verdict_distribution": verdict_counts,
            "language_breakdown": formatted_langs,
            "notes": notes
        }

difficulty_intelligence = DifficultyIntelligenceService()
