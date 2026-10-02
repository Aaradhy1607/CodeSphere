import os
import sys
import time
import subprocess
import tempfile
import shutil
from typing import Dict, Any, List, Optional
from app.models.models import SubmissionVerdict

# Ensure compiler and runtime binaries are accessible on PATH and DLL search
if os.name == 'nt':
    _extra_paths = [
        r"C:\msys64\ucrt64\bin",
        r"C:\msys64\mingw64\bin",
        r"C:\Program Files\nodejs",
        r"C:\Program Files\Common Files\Oracle\Java\javapath",
        r"C:\Windows\system32",
        r"C:\Windows",
    ]
    _cur_p = os.environ.get("PATH") or os.environ.get("Path") or ""
    for _p in _extra_paths:
        if os.path.exists(_p) and _p.lower() not in _cur_p.lower():
            _cur_p = f"{_p};{_cur_p}"
    os.environ["PATH"] = _cur_p
    os.environ["Path"] = _cur_p

    if hasattr(os, "add_dll_directory"):
        for _p in [r"C:\msys64\ucrt64\bin", r"C:\msys64\mingw64\bin"]:
            if os.path.exists(_p):
                try:
                    os.add_dll_directory(_p)
                except Exception:
                    pass

class ExecutionSession:
    def __init__(
        self,
        lang: str,
        temp_dir: str,
        cmd: Optional[List[str]] = None,
        compile_error: Optional[str] = None
    ):
        self.lang = lang
        self.temp_dir = temp_dir
        self.cmd = cmd
        self.compile_error = compile_error

import threading
from app.core.config import settings

class SandboxedCodeRunner:
    def __init__(self):
        self.timeout_seconds = settings.CODE_RUNNER_TIMEOUT_SECONDS
        self.is_windows = os.name == 'nt'
        self.semaphore = threading.BoundedSemaphore(settings.CODE_RUNNER_MAX_CONCURRENCY)

    def _find_bin(self, name: str) -> str:
        found = shutil.which(name)
        if found:
            return found
        if self.is_windows:
            possible_paths = [
                rf"C:\msys64\ucrt64\bin\{name}.exe",
                rf"C:\msys64\mingw64\bin\{name}.exe",
                rf"C:\msys64\usr\bin\{name}.exe",
                rf"C:\MinGW\bin\{name}.exe",
                rf"C:\Program Files\LLVM\bin\{name}.exe",
                rf"C:\Program Files\nodejs\{name}.cmd",
                rf"C:\Program Files\nodejs\{name}.exe",
                rf"C:\Program Files\Common Files\Oracle\Java\javapath\{name}.exe",
            ]
            for p in possible_paths:
                if os.path.exists(p):
                    return p
        return name

    def _get_exec_env(self) -> Dict[str, str]:
        # Minimal system allowlist for subprocess execution — strips all app secrets, db credentials, and API keys
        safe_keys = {
            "SYSTEMROOT", "SystemRoot", "WINDIR", "COMSPEC", "PATH", "Path", "path",
            "TEMP", "TMP", "USERPROFILE", "HOME", "LANG", "LC_ALL", "NUMBER_OF_PROCESSORS",
            "PROCESSOR_ARCHITECTURE", "OS"
        }
        env = {k: v for k, v in os.environ.items() if k in safe_keys}
        if self.is_windows:
            extra_paths = [
                r"C:\msys64\ucrt64\bin",
                r"C:\msys64\mingw64\bin",
                r"C:\Program Files\nodejs",
                r"C:\Program Files\Java\jdk-21.0.12\bin",
                r"C:\Program Files\Common Files\Oracle\Java\javapath",
                r"C:\Windows\system32",
                r"C:\Windows",
                r"C:\Windows\System32\Wbem",
                r"C:\Windows\System32\WindowsPowerShell\v1.0",
            ]
            path_keys = [k for k in list(env.keys()) if k.lower() == "path"]
            cur_p_vals = [env[k] for k in path_keys if env[k]]
            cur_p = ";".join(cur_p_vals)
            for k in path_keys:
                del env[k]

            valid_extras = [p for p in extra_paths if os.path.exists(p)]
            new_p = ";".join(valid_extras) + ";" + cur_p
            # Crucial on Windows: Only set one 'PATH' key to avoid duplicate environment blocks
            env["PATH"] = new_p

            if hasattr(os, "add_dll_directory"):
                for _p in [r"C:\msys64\ucrt64\bin", r"C:\msys64\mingw64\bin"]:
                    if os.path.exists(_p):
                        try:
                            os.add_dll_directory(_p)
                        except Exception:
                            pass

            if "SYSTEMROOT" not in env:
                env["SYSTEMROOT"] = r"C:\Windows"
            if "SystemRoot" not in env:
                env["SystemRoot"] = r"C:\Windows"
            if "COMSPEC" not in env:
                env["COMSPEC"] = r"C:\Windows\system32\cmd.exe"
            if "WINDIR" not in env:
                env["WINDIR"] = r"C:\Windows"
        return env

    def _normalize_output(self, text: str) -> str:
        """Normalizes line endings, trailing whitespace, and blank lines for accurate comparison."""
        if not text:
            return ""
        # Replace Windows CRLF with standard LF
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = [line.rstrip() for line in normalized.strip().splitlines()]
        # Filter trailing empty lines while preserving internal blank lines if any
        while lines and not lines[-1]:
            lines.pop()
        while lines and not lines[0]:
            lines.pop(0)
        return "\n".join(lines)

    def _prepare_session(self, code: str, language: str, temp_dir: str) -> ExecutionSession:
        lang = language.lower().strip()
        env = self._get_exec_env()

        # 1. PYTHON
        if lang in ["python", "py", "python3"]:
            file_path = os.path.join(temp_dir, "solution.py")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)
            return ExecutionSession(lang="python", temp_dir=temp_dir, cmd=[sys.executable, "-I", file_path])

        # 2. C++
        elif lang in ["cpp", "c++"]:
            src_path = os.path.join(temp_dir, "solution.cpp")
            exe_path = os.path.join(temp_dir, "solution.exe" if self.is_windows else "solution")
            with open(src_path, "w", encoding="utf-8") as f:
                f.write(code)

            gpp_bin = self._find_bin("g++")
            try:
                compile_cmd = [gpp_bin, "-O2", "-std=c++17", src_path, "-o", exe_path]
                if self.is_windows:
                    bin_dir = os.path.dirname(gpp_bin)
                    if bin_dir and os.path.exists(bin_dir):
                        compile_cmd.extend(["-B", bin_dir])
                    compile_cmd.extend(["-static-libgcc", "-static-libstdc++"])
                compile_proc = subprocess.run(
                    compile_cmd,
                    capture_output=True,
                    text=True,
                    timeout=15.0,
                    cwd=temp_dir,
                    env=env
                )
                if compile_proc.returncode != 0 or not os.path.exists(exe_path):
                    err = compile_proc.stderr.strip() or compile_proc.stdout.strip() or f"C++ compilation failed (exit code {compile_proc.returncode})."
                    return ExecutionSession(lang="cpp", temp_dir=temp_dir, compile_error=err)
                return ExecutionSession(lang="cpp", temp_dir=temp_dir, cmd=[exe_path])
            except subprocess.TimeoutExpired:
                return ExecutionSession(lang="cpp", temp_dir=temp_dir, compile_error="C++ Compilation Time Limit Exceeded (>15s)")
            except Exception as e:
                return ExecutionSession(lang="cpp", temp_dir=temp_dir, compile_error=f"Compiler invocation error: {str(e)}")

        # 3. C
        elif lang in ["c"]:
            src_path = os.path.join(temp_dir, "solution.c")
            exe_path = os.path.join(temp_dir, "solution.exe" if self.is_windows else "solution")
            with open(src_path, "w", encoding="utf-8") as f:
                f.write(code)

            gpp_bin = self._find_bin("g++") if self.is_windows else self._find_bin("gcc")
            try:
                compile_cmd = [gpp_bin, "-O2", "-x", "c++" if self.is_windows else "c", src_path, "-o", exe_path]
                if self.is_windows:
                    bin_dir = os.path.dirname(gpp_bin)
                    if bin_dir and os.path.exists(bin_dir):
                        compile_cmd.extend(["-B", bin_dir])
                    compile_cmd.extend(["-static-libgcc", "-static-libstdc++"])
                compile_proc = subprocess.run(
                    compile_cmd,
                    capture_output=True,
                    text=True,
                    timeout=15.0,
                    cwd=temp_dir,
                    env=env
                )
                if compile_proc.returncode != 0 or not os.path.exists(exe_path):
                    err = compile_proc.stderr.strip() or compile_proc.stdout.strip() or f"C compilation failed (exit code {compile_proc.returncode})."
                    return ExecutionSession(lang="c", temp_dir=temp_dir, compile_error=err)
                return ExecutionSession(lang="c", temp_dir=temp_dir, cmd=[exe_path])
            except subprocess.TimeoutExpired:
                return ExecutionSession(lang="c", temp_dir=temp_dir, compile_error="C Compilation Time Limit Exceeded (>15s)")
            except Exception as e:
                return ExecutionSession(lang="c", temp_dir=temp_dir, compile_error=f"Compiler invocation error: {str(e)}")

        # 4. JAVA
        elif lang in ["java"]:
            class_name = "Solution"
            if "public class Main" in code or ("class Main" in code and "public class Solution" not in code):
                class_name = "Main"

            src_path = os.path.join(temp_dir, f"{class_name}.java")
            with open(src_path, "w", encoding="utf-8") as f:
                f.write(code)

            javac_bin = self._find_bin("javac")
            java_bin = self._find_bin("java")
            try:
                compile_cmd = [javac_bin, src_path]
                compile_proc = subprocess.run(
                    compile_cmd,
                    capture_output=True,
                    text=True,
                    timeout=15.0,
                    cwd=temp_dir,
                    env=env
                )
                if compile_proc.returncode != 0:
                    err = compile_proc.stderr.strip() or compile_proc.stdout.strip() or "Java compilation error."
                    return ExecutionSession(lang="java", temp_dir=temp_dir, compile_error=err)
                run_cmd = [java_bin, "-cp", temp_dir, class_name]
                return ExecutionSession(lang="java", temp_dir=temp_dir, cmd=run_cmd)
            except subprocess.TimeoutExpired:
                return ExecutionSession(lang="java", temp_dir=temp_dir, compile_error="Java Compilation Time Limit Exceeded (>15s)")
            except Exception as e:
                return ExecutionSession(lang="java", temp_dir=temp_dir, compile_error=f"Javac invocation error: {str(e)}")

        # 5. JAVASCRIPT (Node.js)
        elif lang in ["javascript", "js", "node", "nodejs"]:
            file_path = os.path.join(temp_dir, "solution.js")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)
            node_bin = self._find_bin("node")
            run_cmd = [node_bin, file_path]
            return ExecutionSession(lang="javascript", temp_dir=temp_dir, cmd=run_cmd)

        else:
            return ExecutionSession(
                lang=lang,
                temp_dir=temp_dir,
                compile_error=f"Unsupported language: {language}. Supported: Python, C++, C, Java."
            )

    def _execute_in_session(self, session: ExecutionSession, input_data: str) -> Dict[str, Any]:
        if session.compile_error:
            return {
                "verdict": SubmissionVerdict.CE,
                "output": "",
                "error": session.compile_error,
                "time_ms": 0.0
            }

        env = self._get_exec_env()
        start_time = time.time()
        # Ensure newline at end of input for standard line-by-line scanners
        clean_input = input_data if (not input_data or input_data.endswith("\n")) else f"{input_data}\n"
        try:
            process = subprocess.run(
                session.cmd,
                input=clean_input,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                cwd=session.temp_dir,
                env=env
            )
            exec_time_ms = (time.time() - start_time) * 1000.0

            if process.returncode != 0:
                return {
                    "verdict": SubmissionVerdict.RE,
                    "output": process.stdout,
                    "error": process.stderr.strip() or f"Process exited with code {process.returncode}",
                    "time_ms": exec_time_ms
                }
            return {
                "verdict": SubmissionVerdict.AC,
                "output": process.stdout,
                "error": None,
                "time_ms": exec_time_ms
            }
        except subprocess.TimeoutExpired:
            return {
                "verdict": SubmissionVerdict.TLE,
                "output": "",
                "error": f"Time Limit Exceeded (> {self.timeout_seconds}s)",
                "time_ms": self.timeout_seconds * 1000.0
            }
        except Exception as e:
            return {
                "verdict": SubmissionVerdict.RE,
                "output": "",
                "error": str(e),
                "time_ms": 0.0
            }

    def _create_temp_dir(self, prefix: str = "codesphere_run_") -> str:
        if self.is_windows:
            base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".tmp_runs")
            os.makedirs(base_dir, exist_ok=True)
            return tempfile.mkdtemp(prefix=prefix, dir=base_dir)
        return tempfile.mkdtemp(prefix=prefix)

    def execute_single(self, code: str, language: str, input_data: str) -> Dict[str, Any]:
        with self.semaphore:
            temp_dir = self._create_temp_dir(prefix="codesphere_run_")
            try:
                session = self._prepare_session(code, language, temp_dir)
                return self._execute_in_session(session, input_data)
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

    def evaluate_test_cases(
        self,
        code: str,
        language: str,
        test_cases: List[Dict[str, Any]],
        stop_on_first_failure: bool = False
    ) -> Dict[str, Any]:
        with self.semaphore:
            results = []
            passed_count = 0
            total_points = 0
            earned_points = 0
            max_time_ms = 0.0
            final_verdict = SubmissionVerdict.AC
            first_error = None

            temp_dir = self._create_temp_dir(prefix="codesphere_eval_")

            try:
                def _get_tc_info(tc_item):
                    if isinstance(tc_item, dict):
                        return (
                            tc_item.get("id"),
                            tc_item.get("input_data", tc_item.get("input", "")),
                            tc_item.get("expected_output", tc_item.get("expected", "")),
                            tc_item.get("points", 10),
                            tc_item.get("is_hidden", False)
                        )
                    return (
                        getattr(tc_item, "id", None),
                        getattr(tc_item, "input_data", getattr(tc_item, "input", "")),
                        getattr(tc_item, "expected_output", getattr(tc_item, "expected", "")),
                        getattr(tc_item, "points", 10),
                        getattr(tc_item, "is_hidden", False)
                    )

                # Single compilation / session initialization for all test cases
                session = self._prepare_session(code, language, temp_dir)

                if session.compile_error:
                    # Compilation Error applies to all test cases
                    for tc in test_cases:
                        tc_id, tc_input, tc_expected, tc_points, is_hidden = _get_tc_info(tc)
                        total_points += tc_points
                        results.append({
                            "test_case_id": tc_id,
                            "is_hidden": is_hidden,
                            "passed": False,
                            "verdict": SubmissionVerdict.CE,
                            "time_ms": 0.0,
                            "output": "",
                            "expected": tc_expected if not is_hidden else "[HIDDEN]",
                            "error": session.compile_error
                        })
                    return {
                        "verdict": SubmissionVerdict.CE,
                        "passed_count": 0,
                        "total_count": len(test_cases),
                        "earned_points": 0,
                        "total_points": total_points,
                        "score": 0.0,
                        "max_time_ms": 0.0,
                        "error_message": session.compile_error,
                        "test_case_results": results
                    }

                for tc in test_cases:
                    tc_id, tc_input, tc_expected, tc_points, is_hidden = _get_tc_info(tc)
                    total_points += tc_points

                    run_res = self._execute_in_session(session, tc_input)
                    max_time_ms = max(max_time_ms, run_res["time_ms"])

                    if run_res["verdict"] in [SubmissionVerdict.TLE, SubmissionVerdict.RE]:
                        if final_verdict == SubmissionVerdict.AC:
                            final_verdict = run_res["verdict"]
                        if not first_error:
                            first_error = run_res["error"]
                        results.append({
                            "test_case_id": tc_id,
                            "is_hidden": is_hidden,
                            "passed": False,
                            "verdict": run_res["verdict"],
                            "time_ms": run_res["time_ms"],
                            "output": run_res["output"] if not is_hidden else "",
                            "expected": tc_expected if not is_hidden else "[HIDDEN]",
                            "error": run_res["error"]
                        })
                        if stop_on_first_failure:
                            break
                    else:
                        actual_norm = self._normalize_output(run_res["output"])
                        expected_norm = self._normalize_output(tc_expected)

                        # Exact normalized match or token-by-token match for numerical/spacing flexibility
                        is_match = (actual_norm == expected_norm)
                        if not is_match and actual_norm and expected_norm:
                            # Fallback token split match
                            actual_tokens = actual_norm.split()
                            expected_tokens = expected_norm.split()
                            if actual_tokens == expected_tokens:
                                is_match = True

                        if is_match:
                            passed_count += 1
                            earned_points += tc_points
                            results.append({
                                "test_case_id": tc_id,
                                "is_hidden": is_hidden,
                                "passed": True,
                                "verdict": SubmissionVerdict.AC,
                                "time_ms": run_res["time_ms"],
                                "output": run_res["output"] if not is_hidden else "[HIDDEN PASS]",
                                "expected": tc_expected if not is_hidden else "[HIDDEN]",
                                "error": None
                            })
                        else:
                            if final_verdict == SubmissionVerdict.AC:
                                final_verdict = SubmissionVerdict.WA
                            results.append({
                                "test_case_id": tc_id,
                                "is_hidden": is_hidden,
                                "passed": False,
                                "verdict": SubmissionVerdict.WA,
                                "time_ms": run_res["time_ms"],
                                "output": run_res["output"] if not is_hidden else "[HIDDEN FAIL]",
                                "expected": tc_expected if not is_hidden else "[HIDDEN]",
                                "error": "Output did not match expected output"
                            })
                            if stop_on_first_failure:
                                break

                total_cases = len(test_cases)
                score = (earned_points / total_points * 100.0) if total_points > 0 else (100.0 if passed_count == total_cases else 0.0)

                return {
                    "verdict": final_verdict,
                    "passed_count": passed_count,
                    "total_count": total_cases,
                    "earned_points": earned_points,
                    "total_points": total_points,
                    "score": round(score, 2),
                    "max_time_ms": round(max_time_ms, 2),
                    "error_message": first_error,
                    "test_case_results": results
                }
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

    def validate_reference_solution(
        self,
        reference_solutions: Dict[str, str],
        test_cases: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validates all language reference solutions (C, C++, Java, Python) against the entire test suite.
        Only marks the solution as valid if EVERY provided language solution passes 100% of test cases.
        """
        if not test_cases:
            return {
                "is_valid": False,
                "status": "FAILED",
                "notes": "No test cases provided for validation",
                "language_results": {},
                "failing_details": []
            }

        if not reference_solutions or not any(v.strip() for v in reference_solutions.values() if v):
            return {
                "is_valid": False,
                "status": "FAILED",
                "notes": "No reference solution code provided for validation",
                "language_results": {},
                "failing_details": []
            }

        lang_results = {}
        all_passed = True
        failing_details = []
        validated_langs = 0

        for lang, code in reference_solutions.items():
            if not code or not code.strip():
                continue
            validated_langs += 1
            eval_res = self.evaluate_test_cases(code, lang, test_cases)
            
            lang_passed = (eval_res["passed_count"] == eval_res["total_count"] and eval_res["total_count"] > 0)
            if not lang_passed:
                all_passed = False
                # Collect detailed failing cases
                for r in eval_res.get("test_case_results", []):
                    if not r.get("passed"):
                        failing_details.append({
                            "language": lang,
                            "test_case_id": r.get("test_case_id"),
                            "is_hidden": r.get("is_hidden", False),
                            "verdict": r.get("verdict"),
                            "expected": r.get("expected"),
                            "actual": r.get("output"),
                            "error": r.get("error")
                        })

            lang_results[lang] = {
                "verdict": eval_res["verdict"],
                "passed": eval_res["passed_count"],
                "total": eval_res["total_count"],
                "score": eval_res["score"],
                "error": eval_res["error_message"],
                "is_fully_passing": lang_passed,
                "test_case_results": eval_res.get("test_case_results", [])
            }

        if validated_langs == 0:
            return {
                "is_valid": False,
                "status": "FAILED",
                "notes": "No valid reference solutions found to evaluate.",
                "language_results": {},
                "failing_details": []
            }

        status = "PASSED" if all_passed else "FAILED"
        if all_passed:
            notes = f"All {validated_langs} reference solutions ({', '.join(lang_results.keys())}) passed 100% of test cases."
        else:
            failing_langs = [k for k, v in lang_results.items() if not v["is_fully_passing"]]
            notes = f"Reference solution validation failed for {', '.join(failing_langs)}. {len(failing_details)} test case mismatch(es) detected."

        return {
            "is_valid": all_passed,
            "status": status,
            "notes": notes,
            "language_results": lang_results,
            "failing_details": failing_details
        }

code_runner = SandboxedCodeRunner()

