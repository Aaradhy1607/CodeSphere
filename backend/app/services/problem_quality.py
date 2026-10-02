import re
from typing import Dict, Any, List, Optional
from app.services.test_case_quality import test_case_quality_validator

class ProblemQualityEngine:
    """
    Comprehensive Problem Quality Engine for CodeSphere.
    
    Evaluates coding questions across:
    1. Statement Completeness & Formatting (Clarity, Markdown headers, I/O formats, Constraints, Examples).
    2. Limits & Complexity Consistency (Time limits, Memory limits, Big-O specification).
    3. Multi-Language Reference Solutions (Python, C, C++, Java, JavaScript).
    4. Test Suite Edge-Case Coverage & Balance.
    
    Returns a unified deterministic health assessment and actionable author feedback.
    """

    VALID_COMPLEXITIES = [
        "O(1)", "O(LOG N)", "O(SQRT N)", "O(N)", "O(N LOG N)", "O(N^2)", "O(N*M)",
        "O(2^N)", "O(N!)", "O(V+E)", "O(V LOG V + E)"
    ]

    @classmethod
    def evaluate_problem(
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
        time_limit_seconds: float,
        memory_limit_mb: int,
        reference_solutions: Dict[str, str],
        test_cases: List[Dict[str, Any]],
        question_type: str = "CODING"
    ) -> Dict[str, Any]:
        """
        Deep quality evaluation of a problem record.
        """
        errors: List[str] = []
        warnings: List[str] = []

        # 1. Statement & Formatting Checks (Max 25 pts)
        statement_score = 0.0
        if not title or len(title.strip()) < 4:
            errors.append("Title is missing or too short (minimum 4 characters).")
        else:
            statement_score += 4.0

        if not problem_statement or len(problem_statement.strip()) < 30:
            errors.append("Problem statement is missing or insufficient (minimum 30 characters).")
        else:
            statement_score += 8.0
            if len(problem_statement.strip()) >= 100:
                statement_score += 3.0

        if question_type == "CODING":
            if not input_format or len(input_format.strip()) < 5:
                warnings.append("Input format description is missing or brief.")
            else:
                statement_score += 3.0

            if not output_format or len(output_format.strip()) < 5:
                warnings.append("Output format description is missing or brief.")
            else:
                statement_score += 3.0

            if not constraints or len(constraints.strip()) < 5:
                warnings.append("Explicit constraints (e.g. 1 <= N <= 10^5) are missing.")
            else:
                statement_score += 2.0

            if not examples or len(examples) == 0:
                errors.append("At least 1 example with explanation is required for coding problems.")
            else:
                statement_score += 2.0
        else:
            statement_score += 10.0

        statement_score = min(statement_score, 25.0)

        # 2. Limits & Complexity Consistency (Max 20 pts)
        limits_score = 0.0
        if time_limit_seconds < 0.1 or time_limit_seconds > 15.0:
            errors.append(f"Time limit of {time_limit_seconds}s is out of valid bounds (0.1s to 15.0s).")
        else:
            limits_score += 5.0

        if memory_limit_mb < 32 or memory_limit_mb > 1024:
            errors.append(f"Memory limit of {memory_limit_mb}MB is out of valid bounds (32MB to 1024MB).")
        else:
            limits_score += 5.0

        norm_tc = (expected_time_complexity or "").upper().strip()
        norm_sc = (expected_space_complexity or "").upper().strip()

        if norm_tc:
            limits_score += 5.0
            if not any(valid in norm_tc for valid in cls.VALID_COMPLEXITIES):
                warnings.append(f"Expected time complexity '{expected_time_complexity}' does not match standard asymptotic notation (e.g. O(N), O(N log N)).")
        else:
            warnings.append("Expected time complexity is unspecified.")

        if norm_sc:
            limits_score += 5.0
        else:
            warnings.append("Expected space complexity is unspecified.")

        limits_score = min(limits_score, 20.0)

        # 3. Reference Solutions (Max 25 pts)
        solutions_score = 0.0
        if question_type == "CODING":
            if not reference_solutions or not any(v.strip() for v in reference_solutions.values() if v):
                errors.append("No reference solutions provided. Reference solutions are required to verify test cases.")
            else:
                langs = [k for k, v in reference_solutions.items() if v and len(v.strip()) > 15]
                solutions_score += min(len(langs) * 6.0, 20.0)
                if "python" in langs:
                    solutions_score += 2.5
                if "cpp" in langs or "java" in langs:
                    solutions_score += 2.5
                if len(langs) == 1:
                    warnings.append(f"Only 1 reference solution provided ({langs[0]}). Providing solutions in Python + C++/Java ensures multi-language test viability.")
        else:
            solutions_score = 25.0

        solutions_score = min(solutions_score, 25.0)

        # 4. Test Suite Quality (Max 30 pts)
        tc_report = test_case_quality_validator.validate_test_suite(
            test_cases,
            expected_time_limit_s=time_limit_seconds,
            expected_memory_limit_mb=memory_limit_mb
        )
        tc_score = round((tc_report["quality_score"] / 100.0) * 30.0, 1)

        errors.extend(tc_report["errors"])
        warnings.extend(tc_report["warnings"])

        # Deduplicate warnings and errors
        unique_errors = list(dict.fromkeys(errors))
        unique_warnings = list(dict.fromkeys(warnings))

        total_score = round(statement_score + limits_score + solutions_score + tc_score, 1)
        if unique_errors:
            total_score = min(total_score, 49.0)

        grade = "A+" if total_score >= 90 else ("A" if total_score >= 80 else ("B" if total_score >= 70 else ("C" if total_score >= 50 else "D")))

        return {
            "quality_score": total_score,
            "grade": grade,
            "is_ready_for_review": len(unique_errors) == 0 and total_score >= 65.0,
            "breakdown": {
                "statement_and_format": statement_score,
                "limits_and_complexity": limits_score,
                "reference_solutions": solutions_score,
                "test_suite_coverage": tc_score
            },
            "test_suite_report": tc_report,
            "errors": unique_errors,
            "warnings": unique_warnings
        }

problem_quality_engine = ProblemQualityEngine()
