from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.models import Assessment, AssessmentQuestion, Question, TestCase
from app.services.duplicate_detector import duplicate_detector

class ContestQualityValidator:
    """
    Contest & Assessment Problem Set Quality Validator for CodeSphere.
    
    Performs deterministic multi-dimensional audits on assessment problem sets:
    1. Internal Duplicate & Semantic Overlap Detection across problems.
    2. Difficulty Spread & Distribution Balance (Easy, Medium, Hard).
    3. Topic & Concept Concentration (flags single-topic dominance).
    4. Test Suite Rigor across all problems (flags weak hidden test counts).
    5. Workload & Time Allocation vs Assessment Duration.
    
    Produces actionable warnings and quality scores without altering assessment records.
    """

    @classmethod
    def validate_assessment_problem_set(
        cls,
        assessment_id: int,
        db: Session
    ) -> Dict[str, Any]:
        """
        Audits an assessment's problem set and generates a comprehensive quality report.
        """
        assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
        if not assessment:
            return {"error": "Assessment not found"}

        aqs = db.query(AssessmentQuestion).filter(
            AssessmentQuestion.assessment_id == assessment_id
        ).order_by(AssessmentQuestion.order_index.asc()).all()

        if not aqs:
            return {
                "assessment_id": assessment_id,
                "assessment_title": assessment.title,
                "problem_count": 0,
                "quality_score": 0.0,
                "grade": "F",
                "is_ready_to_publish": False,
                "errors": ["The assessment contains no questions. Add at least 1-3 questions before publishing."],
                "warnings": []
            }

        questions = [aq.question for aq in aqs if aq.question]
        q_count = len(questions)

        errors: List[str] = []
        warnings: List[str] = []

        # 1. Internal Duplicate Check
        duplicate_pairs: List[Dict[str, Any]] = []
        for i in range(len(questions)):
            for j in range(i + 1, len(questions)):
                q1 = questions[i]
                q2 = questions[j]
                cmp_res = duplicate_detector.compare_statements(q1.problem_statement or "", q2.problem_statement or "")
                if cmp_res.get("is_duplicate") or cmp_res.get("similarity_score", 0.0) >= 0.70:
                    duplicate_pairs.append({
                        "question_a_id": q1.id,
                        "question_a_title": q1.title,
                        "question_b_id": q2.id,
                        "question_b_title": q2.title,
                        "similarity_score": cmp_res.get("similarity_score", 0.0),
                        "category": cmp_res.get("category", "SIMILAR")
                    })
                    errors.append(f"High similarity ({round(cmp_res.get('similarity_score', 0.0) * 100)}%) detected between '{q1.title}' and '{q2.title}'.")

        # 2. Difficulty Distribution
        diff_scores = [q.difficulty_score or 5 for q in questions]
        easy_count = sum(1 for d in diff_scores if d <= 3)
        med_count = sum(1 for d in diff_scores if 4 <= d <= 7)
        hard_count = sum(1 for d in diff_scores if d >= 8)

        if q_count >= 3:
            if easy_count == q_count:
                warnings.append(f"All {q_count} problems are Easy. Consider adding Medium/Hard problems for balanced ranking differentiation.")
            elif hard_count == q_count:
                warnings.append(f"All {q_count} problems are Hard. Students may face a harsh completion bottleneck.")

        # 3. Topic Concentration Analysis
        topic_counts: Dict[str, int] = {}
        for q in questions:
            t = (q.topic or q.subject or "Uncategorized").strip()
            topic_counts[t] = topic_counts.get(t, 0) + 1

        for topic, count in topic_counts.items():
            if q_count >= 3 and (count / q_count) >= 0.60:
                warnings.append(f"Topic concentration alert: {count} out of {q_count} problems are tagged '{topic}' ({round((count/q_count)*100)}%). Diversify problem topics.")

        # 4. Test Case Coverage Audit
        weak_test_problems = []
        for q in questions:
            if q.question_type == "CODING":
                tcs = q.test_cases or []
                hidden = [tc for tc in tcs if tc.is_hidden]
                if len(hidden) < 3:
                    weak_test_problems.append({"id": q.id, "title": q.title, "hidden_count": len(hidden)})
                    errors.append(f"Problem '{q.title}' (ID #{q.id}) has only {len(hidden)} hidden test case(s). Minimum 3 required for secure assessment evaluation.")

        # 5. Workload & Time Estimation
        total_est_minutes = sum(q.time_estimate_minutes or 30 for q in questions)
        duration_minutes = assessment.duration_minutes or 60

        if total_est_minutes > duration_minutes * 1.3:
            warnings.append(f"Estimated problem completion time ({total_est_minutes} mins) exceeds assessment duration ({duration_minutes} mins) by more than 30%.")
        elif total_est_minutes < duration_minutes * 0.4:
            warnings.append(f"Estimated problem completion time ({total_est_minutes} mins) is significantly shorter than assessment duration ({duration_minutes} mins).")

        # Deterministic Contest Quality Score (0 - 100)
        score = 100.0
        if duplicate_pairs:
            score -= (len(duplicate_pairs) * 20.0)
        if weak_test_problems:
            score -= (len(weak_test_problems) * 15.0)
        if warnings:
            score -= (len(warnings) * 5.0)

        score = round(max(0.0, min(100.0, score)), 1)
        grade = "A+" if score >= 90 else ("A" if score >= 80 else ("B" if score >= 70 else ("C" if score >= 50 else "D")))

        return {
            "assessment_id": assessment_id,
            "assessment_title": assessment.title,
            "problem_count": q_count,
            "quality_score": score,
            "grade": grade,
            "is_ready_to_publish": len(errors) == 0 and score >= 65.0,
            "difficulty_spread": {
                "easy_count": easy_count,
                "medium_count": med_count,
                "hard_count": hard_count,
                "average_difficulty": round(sum(diff_scores) / max(q_count, 1), 1)
            },
            "topic_distribution": topic_counts,
            "time_budget": {
                "total_estimated_minutes": total_est_minutes,
                "assessment_duration_minutes": duration_minutes,
                "is_reasonable": abs(total_est_minutes - duration_minutes) <= (duration_minutes * 0.4)
            },
            "duplicate_pairs": duplicate_pairs,
            "weak_test_problems": weak_test_problems,
            "errors": errors,
            "warnings": warnings
        }

contest_quality_validator = ContestQualityValidator()
