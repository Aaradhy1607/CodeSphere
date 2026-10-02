import re
from typing import Dict, Any, List, Optional

class QuestionQualityScorer:
    """
    Deterministic Quality Evaluation Engine for CodeSphere Questions.
    Evaluates Completeness, Clarity, Technical Correctness, Difficulty Consistency,
    and Test Case Edge-Coverage without fabricating metrics.
    """

    @classmethod
    def evaluate(
        cls,
        title: str,
        problem_statement: str,
        input_format: str,
        output_format: str,
        constraints: str,
        examples: List[Dict[str, Any]],
        difficulty_score: int,
        expected_time_complexity: str,
        expected_space_complexity: str,
        reference_solutions: Dict[str, str],
        test_cases: List[Dict[str, Any]],
        question_type: str = "CODING",
        options: Optional[List[Dict[str, Any]]] = None,
        correct_answer: Optional[str] = None
    ) -> Dict[str, Any]:
        
        breakdown = {
            "completeness": 0.0,
            "clarity": 0.0,
            "correctness": 0.0,
            "difficulty_consistency": 0.0,
            "test_coverage": 0.0,
            "dimension_notes": []
        }

        # 1. Completeness (Max 20 pts)
        completeness_pts = 0.0
        if title and len(title.strip()) >= 5:
            completeness_pts += 3.0
        if problem_statement and len(problem_statement.strip()) >= 50:
            completeness_pts += 6.0
        elif problem_statement and len(problem_statement.strip()) >= 20:
            completeness_pts += 3.0

        if question_type == "CODING":
            if input_format and len(input_format.strip()) >= 10:
                completeness_pts += 3.0
            if output_format and len(output_format.strip()) >= 10:
                completeness_pts += 3.0
            if constraints and len(constraints.strip()) >= 5:
                completeness_pts += 3.0
            if examples and len(examples) >= 1:
                completeness_pts += 2.0
        elif question_type == "MCQ":
            if options and len(options) >= 2:
                completeness_pts += 6.0
            if correct_answer:
                completeness_pts += 5.0
        else: # SUBJECTIVE
            if correct_answer or len(problem_statement) >= 100:
                completeness_pts += 11.0

        breakdown["completeness"] = min(round(completeness_pts, 1), 20.0)

        # 2. Clarity (Max 20 pts)
        clarity_pts = 0.0
        words = problem_statement.split() if problem_statement else []
        if len(words) >= 25:
            clarity_pts += 6.0
        if any(heading in problem_statement for heading in ["###", "**Input", "**Output", "Example", "Note", "Task"]):
            clarity_pts += 5.0
        if examples and any(isinstance(ex, dict) and ex.get("explanation") for ex in examples):
            clarity_pts += 5.0
        if constraints and ("<=" in constraints or ">=" in constraints or "10^" in constraints or "0 <=" in constraints):
            clarity_pts += 4.0

        breakdown["clarity"] = min(round(clarity_pts, 1), 20.0)

        # 3. Technical Correctness & Solutions (Max 20 pts)
        correctness_pts = 0.0
        if question_type == "CODING":
            if reference_solutions:
                # Up to 4 languages supported
                langs_present = [l for l in ["python", "cpp", "c", "java"] if reference_solutions.get(l) and len(reference_solutions[l].strip()) > 15]
                correctness_pts += min(len(langs_present) * 4.0, 16.0)
                if "python" in langs_present:
                    correctness_pts += 2.0
                if "cpp" in langs_present or "java" in langs_present:
                    correctness_pts += 2.0
            else:
                breakdown["dimension_notes"].append("Missing reference solutions in primary languages.")
        elif question_type == "MCQ":
            if options:
                has_correct = any(isinstance(opt, dict) and opt.get("is_correct") for opt in options) or bool(correct_answer)
                if has_correct:
                    correctness_pts += 15.0
                if len(options) == 4:
                    correctness_pts += 5.0
        else: # SUBJECTIVE
            correctness_pts = 18.0

        breakdown["correctness"] = min(round(correctness_pts, 1), 20.0)

        # 4. Difficulty Consistency (Max 20 pts)
        diff_pts = 0.0
        diff = max(1, min(10, difficulty_score))
        if 1 <= diff <= 10:
            diff_pts += 8.0

        if question_type == "CODING":
            tc = expected_time_complexity.upper() if expected_time_complexity else ""
            sc = expected_space_complexity.upper() if expected_space_complexity else ""
            
            # Low difficulty (1-3) should normally be O(1), O(N), O(N log N)
            # High difficulty (7-10) with complex bounds
            if diff <= 3 and any(k in tc for k in ["O(1)", "O(N)", "O(LOG N)"]):
                diff_pts += 6.0
            elif 4 <= diff <= 7 and any(k in tc for k in ["O(N)", "O(N LOG N)", "O(N^2)", "O(N+M)"]):
                diff_pts += 6.0
            elif diff >= 8:
                diff_pts += 6.0
            else:
                diff_pts += 3.0

            if sc:
                diff_pts += 6.0
        else:
            diff_pts += 12.0

        breakdown["difficulty_consistency"] = min(round(diff_pts, 1), 20.0)

        # 5. Test Case Edge Coverage (Max 20 pts)
        test_pts = 0.0
        if question_type == "CODING":
            if test_cases:
                visible = [tc for tc in test_cases if isinstance(tc, dict) and not tc.get("is_hidden")]
                hidden = [tc for tc in test_cases if isinstance(tc, dict) and tc.get("is_hidden")]

                # Visible cases (0-8 pts)
                if len(visible) >= 2:
                    test_pts += 8.0
                elif len(visible) == 1:
                    test_pts += 4.0

                # Hidden cases & edge vectors (0-12 pts)
                if len(hidden) >= 4:
                    test_pts += 12.0
                elif len(hidden) >= 2:
                    test_pts += 8.0
                elif len(hidden) == 1:
                    test_pts += 4.0
            else:
                breakdown["dimension_notes"].append("No test cases defined yet.")
        else:
            test_pts = 20.0 # Not applicable to MCQ/Subjective

        breakdown["test_coverage"] = min(round(test_pts, 1), 20.0)

        total_score = round(
            breakdown["completeness"] +
            breakdown["clarity"] +
            breakdown["correctness"] +
            breakdown["difficulty_consistency"] +
            breakdown["test_coverage"],
            1
        )

        # Quality Grade Classification
        grade = "A+" if total_score >= 90 else ("A" if total_score >= 80 else ("B" if total_score >= 70 else ("C" if total_score >= 50 else "D")))

        if total_score < 70 and not breakdown["dimension_notes"]:
            breakdown["dimension_notes"].append("Add more comprehensive hidden test vectors and detailed constraint descriptions.")

        return {
            "quality_score": total_score,
            "grade": grade,
            "breakdown": breakdown,
            "is_ready_for_review": total_score >= 60.0
        }

quality_scorer = QuestionQualityScorer()
