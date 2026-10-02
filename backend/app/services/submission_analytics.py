import re
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.models import Submission, Question, SubmissionVerdict, User

class SubmissionAnalyticsService:
    """
    Submission Intelligence & Execution Performance Insights Engine for CodeSphere.
    
    Provides students and educators with factual execution metrics:
    - Verdict progression & attempt-by-attempt improvement.
    - Resource utilization vs server limits (Time % & Memory %).
    - Diagnostic static heuristics (loop depth, recursion markers) explicitly labeled as static heuristics.
    
    CRITICAL SECURITY GUARANTEE:
    Shields hidden test inputs, outputs, and evaluator internals from student outputs.
    """

    @classmethod
    def analyze_static_code_heuristics(cls, code: str, language: str) -> Dict[str, Any]:
        """
        Extracts factual static properties of code without claiming exact theoretical Big-O.
        """
        if not code:
            return {"lines_of_code": 0, "loop_depth_estimate": 0, "has_recursion_marker": False, "heuristic_notes": []}

        lines = [l for l in code.splitlines() if l.strip() and not l.strip().startswith("//") and not l.strip().startswith("#")]
        loc = len(lines)
        notes = []

        lang = (language or "").lower()
        loop_depth = 0
        current_indent_loops = 0
        has_recursion = False

        if "python" in lang or "py" in lang:
            # Python indentation-based loop nesting analysis
            indent_loop_stack = []
            for line in lines:
                indent = len(line) - len(line.lstrip())
                # Pop indents that ended
                indent_loop_stack = [lvl for lvl in indent_loop_stack if lvl < indent]
                if re.match(r'^\s*(for|while)\s+', line):
                    indent_loop_stack.append(indent)
                    loop_depth = max(loop_depth, len(indent_loop_stack))

            # Recursion heuristic: function calling itself
            fn_defs = re.findall(r'def\s+([a-zA-Z_0-9]+)\s*\(', code)
            for fn in fn_defs:
                body_matches = re.findall(rf'{fn}\s*\(', code)
                if len(body_matches) > 1:
                    has_recursion = True
                    break

        elif lang in ["cpp", "c", "java", "javascript", "js"]:
            # Bracket/keyword nesting
            brace_depth = 0
            loop_brace_depths = []
            for line in lines:
                if re.search(r'\b(for|while)\s*\(', line):
                    loop_brace_depths.append(brace_depth)
                    loop_depth = max(loop_depth, len(loop_brace_depths))

                for char in line:
                    if char == '{':
                        brace_depth += 1
                    elif char == '}':
                        brace_depth = max(0, brace_depth - 1)
                        loop_brace_depths = [lvl for lvl in loop_brace_depths if lvl < brace_depth]

            # Recursion heuristic
            fn_defs = re.findall(r'(?:int|void|bool|double|long|auto|String)\s+([a-zA-Z_0-9]+)\s*\([^{;]*\)\s*\{', code)
            for fn in fn_defs:
                body_matches = re.findall(rf'{fn}\s*\(', code)
                if len(body_matches) > 1:
                    has_recursion = True
                    break

        if loop_depth >= 3:
            notes.append(f"High nesting level detected (estimated loop depth: {loop_depth}). May risk TLE on large N.")
        elif loop_depth == 2:
            notes.append("Nested loop structure detected (O(N²) iteration pattern).")
        elif loop_depth == 1:
            notes.append("Single loop iteration detected (O(N) iteration pattern).")

        if has_recursion:
            notes.append("Recursive call structure detected. Ensure base termination conditions avoid recursion depth limits.")

        return {
            "lines_of_code": loc,
            "estimated_loop_depth": loop_depth,
            "has_recursion_marker": has_recursion,
            "heuristic_notes": notes
        }

    @classmethod
    def get_student_submission_history(
        cls,
        user_id: int,
        question_id: int,
        db: Session
    ) -> Dict[str, Any]:
        """
        Retrieves factual submission history, performance progression, and resource efficiency
        for a specific student on a specific question without leaking hidden test details.
        """
        q = db.query(Question).filter(Question.id == question_id).first()
        if not q:
            return {"error": "Question not found"}

        submissions = db.query(Submission).filter(
            Submission.user_id == user_id,
            Submission.question_id == question_id
        ).order_by(Submission.submitted_at.asc()).all()

        if not submissions:
            return {
                "question_id": question_id,
                "question_title": q.title,
                "total_submissions": 0,
                "has_accepted": False,
                "best_execution_time_ms": None,
                "best_memory_kb": None,
                "history": []
            }

        history = []
        best_time_ms: Optional[float] = None
        best_memory_kb: Optional[float] = None
        has_ac = False

        time_limit_ms = (q.time_limit_seconds or 2.0) * 1000.0
        memory_limit_kb = (q.memory_limit_mb or 256) * 1024.0

        for idx, sub in enumerate(submissions, start=1):
            v_str = str(sub.verdict).upper()
            is_ac = ("ACCEPTED" in v_str or v_str == "AC")
            if is_ac:
                has_ac = True

            t_ms = float(sub.execution_time_ms or 0.0)
            m_kb = float(sub.memory_used_kb or 0.0)

            if is_ac:
                best_time_ms = t_ms if best_time_ms is None else min(best_time_ms, t_ms)
                best_memory_kb = m_kb if best_memory_kb is None else min(best_memory_kb, m_kb)

            time_util_pct = round((t_ms / time_limit_ms) * 100.0, 1) if time_limit_ms > 0 else 0.0
            mem_util_pct = round((m_kb / memory_limit_kb) * 100.0, 1) if memory_limit_kb > 0 else 0.0

            # Testcase summary (without disclosing hidden inputs/outputs)
            tc_results = sub.test_case_results or []
            passed_cases = sum(1 for tc in tc_results if tc.get("passed"))
            total_cases = len(tc_results) if tc_results else (q.test_cases and len(q.test_cases) or 0)

            # Static heuristic of submitted code
            heuristics = cls.analyze_static_code_heuristics(sub.code or "", sub.language or "")

            history.append({
                "attempt_number": idx,
                "submission_id": sub.id,
                "submitted_at": sub.submitted_at.isoformat() if sub.submitted_at else None,
                "language": sub.language,
                "verdict": sub.verdict,
                "score": sub.score,
                "execution_time_ms": t_ms,
                "time_limit_ms": time_limit_ms,
                "time_utilization_percent": min(100.0, time_util_pct),
                "memory_used_kb": m_kb,
                "memory_limit_kb": memory_limit_kb,
                "memory_utilization_percent": min(100.0, mem_util_pct),
                "test_cases_passed": passed_cases,
                "test_cases_total": total_cases,
                "code_heuristics": heuristics,
                "error_message": sub.error_message if not is_ac else None
            })

        # Calculate improvement trend
        improvement_note = "No attempts yet."
        if len(history) > 1:
            first_v = history[0]["verdict"]
            latest_v = history[-1]["verdict"]
            if "ACCEPTED" in str(latest_v).upper() and "ACCEPTED" not in str(first_v).upper():
                improvement_note = f"Progressed from {first_v} to Accepted in {len(history)} attempts."
            elif "ACCEPTED" in str(latest_v).upper() and "ACCEPTED" in str(first_v).upper():
                time_diff = round(history[0]["execution_time_ms"] - history[-1]["execution_time_ms"], 1)
                improvement_note = f"Consistent AC. Runtime optimized by {time_diff}ms." if time_diff > 0 else "Consistent AC."
            else:
                improvement_note = f"{len(history)} attempt(s) recorded. Keep debugging edge cases."
        elif len(history) == 1:
            improvement_note = "First attempt recorded."

        return {
            "question_id": question_id,
            "question_title": q.title,
            "total_submissions": len(submissions),
            "has_accepted": has_ac,
            "best_execution_time_ms": best_time_ms,
            "best_memory_kb": best_memory_kb,
            "improvement_note": improvement_note,
            "history": history
        }

submission_analytics = SubmissionAnalyticsService()
