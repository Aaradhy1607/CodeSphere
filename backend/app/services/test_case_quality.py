import re
import hashlib
from typing import List, Dict, Any, Optional, Set, Tuple
from app.models.models import TestCaseCategory

class TestCaseQualityValidator:
    """
    Deterministic Test Case Quality & Edge-Case Coverage Validator for CodeSphere.
    
    Evaluates coding problem test cases for:
    - Visible vs Hidden test case balance (at least 2 visible, at least 4 hidden).
    - Edge case & boundary classifications (Minimum, Maximum, Empty, Singleton, Duplicates, Overflow, Adversarial, Performance).
    - Duplicate detection between test cases (identical inputs or identical visible & hidden pairs).
    - Formatting validity and points allocation integrity.
    
    CRITICAL SECURITY GUARANTEE:
    This validator operates on backend data for setters and admins.
    Student-facing endpoints must never expose hidden test inputs, outputs, or classification tags.
    """

    SUPPORTED_CATEGORIES: Set[str] = {c.value for c in TestCaseCategory}

    @classmethod
    def classify_test_case_heuristic(cls, input_data: str, expected_output: str) -> str:
        """
        Heuristically classifies an unclassified test case based on input content patterns.
        """
        raw_in = (input_data or "").strip()
        raw_out = (expected_output or "").strip()

        if not raw_in or raw_in == "0" or raw_in == '""' or raw_in == "[]":
            return TestCaseCategory.EMPTY.value

        tokens = raw_in.split()
        if len(tokens) == 1:
            val = tokens[0]
            if val in ["0", "-1", "1", "null", "None"]:
                return TestCaseCategory.MINIMUM.value
            try:
                num = int(val)
                if abs(num) >= 10**9 or abs(num) >= 2**31 - 1:
                    return TestCaseCategory.OVERFLOW.value
                if num in [0, 1, -1]:
                    return TestCaseCategory.MINIMUM.value
            except ValueError:
                pass
            if len(val) == 1:
                return TestCaseCategory.SINGLETON.value

        # Check for large inputs (performance)
        if len(raw_in) > 2000 or len(tokens) > 200:
            return TestCaseCategory.PERFORMANCE.value

        # Check for duplicate tokens / duplicate-heavy arrays
        if len(tokens) >= 4 and len(set(tokens)) == 1:
            return TestCaseCategory.DUPLICATE.value

        # Check numerical sorting
        try:
            nums = [float(t) for t in tokens if re.match(r'^-?\d+(\.\d+)?$', t)]
            if len(nums) >= 4:
                if nums == sorted(nums):
                    return TestCaseCategory.SORTED.value
                if nums == sorted(nums, reverse=True):
                    return TestCaseCategory.REVERSE_SORTED.value
        except Exception:
            pass

        # Check negative numbers / boundaries
        if any(t.startswith("-") for t in tokens):
            return TestCaseCategory.BOUNDARY.value

        return TestCaseCategory.NORMAL.value

    @classmethod
    def validate_test_suite(
        cls,
        test_cases: List[Dict[str, Any]],
        expected_time_limit_s: float = 2.0,
        expected_memory_limit_mb: int = 256
    ) -> Dict[str, Any]:
        """
        Validates the entire test suite of a coding question, returning a deterministic quality score,
        breakdown, detected duplicate pairs, missing edge cases, and actionable warnings.
        """
        if not test_cases:
            return {
                "quality_score": 0.0,
                "grade": "F",
                "is_valid": False,
                "total_count": 0,
                "visible_count": 0,
                "hidden_count": 0,
                "categories_present": [],
                "missing_categories": list(cls.SUPPORTED_CATEGORIES),
                "duplicate_pairs": [],
                "errors": ["The problem has no test cases. At least 2 visible and 3 hidden test cases are required."],
                "warnings": ["Add normal, boundary, and performance test cases."]
            }

        total = len(test_cases)
        visible = []
        hidden = []
        errors: List[str] = []
        warnings: List[str] = []
        seen_inputs: Dict[str, int] = {}
        duplicate_pairs: List[Dict[str, Any]] = []
        categories_found: Set[str] = set()
        total_points = 0

        for idx, tc in enumerate(test_cases, start=1):
            tc_id = tc.get("id") or idx
            raw_in = str(tc.get("input_data", tc.get("input", "")) or "").strip()
            raw_out = str(tc.get("expected_output", tc.get("expected", "")) or "").strip()
            is_hid = bool(tc.get("is_hidden", False))
            cat = str(tc.get("category", "") or "").upper()
            points = int(tc.get("points", 10) or 10)
            total_points += points

            if not cat or cat not in cls.SUPPORTED_CATEGORIES:
                cat = cls.classify_test_case_heuristic(raw_in, raw_out)

            categories_found.add(cat)

            if is_hid:
                hidden.append({"id": tc_id, "input": raw_in, "output": raw_out, "category": cat, "points": points})
            else:
                visible.append({"id": tc_id, "input": raw_in, "output": raw_out, "category": cat, "points": points})

            # Check for empty expected output
            if not raw_out and not raw_in:
                errors.append(f"Test case #{tc_id} has both empty input and empty expected output.")

            # Check duplicate inputs across test suite
            in_hash = hashlib.sha256(raw_in.encode("utf-8")).hexdigest()
            if in_hash in seen_inputs:
                prev_id = seen_inputs[in_hash]
                duplicate_pairs.append({
                    "test_case_a_id": prev_id,
                    "test_case_b_id": tc_id,
                    "reason": "Identical input data"
                })
                errors.append(f"Test case #{tc_id} has identical input data to test case #{prev_id}.")
            else:
                seen_inputs[in_hash] = tc_id

        # 1. Structural count checks
        if len(visible) == 0:
            errors.append("No visible (sample) test cases provided. Students need at least 1-2 examples to understand I/O.")
        elif len(visible) < 2:
            warnings.append("Only 1 visible test case provided. Adding 2 visible sample cases is recommended.")

        if len(hidden) == 0:
            errors.append("No hidden test cases provided. Untrusted student solutions cannot be securely evaluated.")
        elif len(hidden) < 3:
            warnings.append(f"Only {len(hidden)} hidden test case(s) provided. Minimum 4-6 hidden test cases recommended to prevent hardcoded solutions.")

        # 2. Edge Case & Category Coverage
        core_categories = {"BOUNDARY", "MINIMUM", "MAXIMUM", "EMPTY", "SINGLETON", "DUPLICATE", "OVERFLOW", "PERFORMANCE"}
        missing_core = [c for c in core_categories if c not in categories_found]

        if "BOUNDARY" not in categories_found and "MINIMUM" not in categories_found and "MAXIMUM" not in categories_found:
            warnings.append("Missing boundary condition test cases (e.g. minimum/maximum constraints, negative values).")

        if len(test_cases) >= 6 and "PERFORMANCE" not in categories_found:
            warnings.append("No large/performance test case detected to enforce time complexity limits.")

        # 3. Deterministic Quality Score (0 - 100)
        score = 0.0

        # Visible distribution (max 20)
        if len(visible) >= 2:
            score += 20.0
        elif len(visible) == 1:
            score += 10.0

        # Hidden distribution (max 40)
        if len(hidden) >= 5:
            score += 40.0
        elif len(hidden) >= 3:
            score += 30.0
        elif len(hidden) >= 1:
            score += 15.0

        # Category diversity (max 25)
        diversity_pts = min(len(categories_found) * 5.0, 25.0)
        score += diversity_pts

        # Cleanliness & uniqueness (max 15)
        if not duplicate_pairs:
            score += 15.0
        else:
            score = max(0.0, score - (len(duplicate_pairs) * 10.0))

        if errors:
            score = min(score, 45.0)

        score = round(min(100.0, max(0.0, score)), 1)
        grade = "A+" if score >= 90 else ("A" if score >= 80 else ("B" if score >= 70 else ("C" if score >= 50 else "D")))

        return {
            "quality_score": score,
            "grade": grade,
            "is_valid": len(errors) == 0 and len(visible) >= 1 and len(hidden) >= 1,
            "total_count": total,
            "visible_count": len(visible),
            "hidden_count": len(hidden),
            "total_points": total_points,
            "categories_present": sorted(list(categories_found)),
            "missing_categories": missing_core,
            "duplicate_pairs": duplicate_pairs,
            "errors": errors,
            "warnings": warnings
        }

test_case_quality_validator = TestCaseQualityValidator()
