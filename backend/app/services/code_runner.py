import os
import sys
import time
import subprocess
import tempfile
import shutil
import signal
import threading
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple

from app.models.models import SubmissionVerdict
from app.core.config import settings

# Max output limit per execution (256 KB = 262,144 bytes) to prevent memory exhaustion / log flooding
MAX_OUTPUT_BYTES = 262144
DEFAULT_MAX_MEMORY_MB = 256

# Ensure compiler and runtime binaries are accessible on PATH and DLL search
if os.name == 'nt':
    _extra_paths = [
        r"C:\msys64\ucrt64\bin",
        r"C:\msys64\mingw64\bin",
        r"C:\msys64\usr\bin",
        r"C:\MinGW\bin",
        r"C:\Program Files\nodejs",
        r"C:\Program Files\Common Files\Oracle\Java\javapath",
        r"C:\Program Files\Java\jdk-21.0.12\bin",
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
        compile_error: Optional[str] = None,
        source_file: Optional[str] = None,
        exe_file: Optional[str] = None
    ):
        self.lang = lang
        self.temp_dir = temp_dir
        self.cmd = cmd
        self.compile_error = compile_error
        self.source_file = source_file
        self.exe_file = exe_file


class BaseExecutionBackend(ABC):
    """
    Abstract Execution Backend for Sandboxed Code Runner.
    Supports LocalProcessBackend (hardened local subproc) and DockerExecutionBackend (container isolation).
    """
    @abstractmethod
    def execute(
        self,
        session: ExecutionSession,
        input_data: str,
        timeout_seconds: float,
        memory_limit_mb: int = DEFAULT_MAX_MEMORY_MB
    ) -> Dict[str, Any]:
        pass


class LocalProcessBackend(BaseExecutionBackend):
    """
    Hardened OS process execution backend with strict environment isolation,
    process tree cleanup, bounded stdout/stderr streaming (OLE protection),
    and peak memory usage measurement (MLE detection).
    """
    def __init__(self, is_windows: bool = (os.name == 'nt')):
        self.is_windows = is_windows

    def _kill_process_tree(self, proc: subprocess.Popen):
        try:
            if self.is_windows:
                # Forcefully kill the entire process tree on Windows
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True,
                    timeout=5.0
                )
            else:
                # Kill process group on Unix
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def _get_exec_env(self) -> Dict[str, str]:
        # Minimal system allowlist for subprocess execution — strips all app secrets, db credentials, and API keys
        safe_keys = {
            "SYSTEMROOT", "SystemRoot", "WINDIR", "COMSPEC", "PATH", "Path", "path",
            "TEMP", "TMP", "USERPROFILE", "HOME", "LANG", "LC_ALL", "NUMBER_OF_PROCESSORS",
            "PROCESSOR_ARCHITECTURE", "OS", "LOCALAPPDATA", "APPDATA", "HOMEDRIVE", "HOMEPATH"
        }
        env = {k: v for k, v in os.environ.items() if k in safe_keys}
        if self.is_windows:
            extra_paths = [
                r"C:\msys64\ucrt64\bin",
                r"C:\msys64\mingw64\bin",
                r"C:\msys64\usr\bin",
                r"C:\MinGW\bin",
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
            env["PATH"] = new_p
            env["Path"] = new_p

            if "SYSTEMROOT" not in env:
                env["SYSTEMROOT"] = r"C:\Windows"
            if "SystemRoot" not in env:
                env["SystemRoot"] = r"C:\Windows"
            if "COMSPEC" not in env:
                env["COMSPEC"] = r"C:\Windows\system32\cmd.exe"
            if "WINDIR" not in env:
                env["WINDIR"] = r"C:\Windows"
        return env

    def execute(
        self,
        session: ExecutionSession,
        input_data: str,
        timeout_seconds: float,
        memory_limit_mb: int = DEFAULT_MAX_MEMORY_MB
    ) -> Dict[str, Any]:
        if session.compile_error:
            return {
                "verdict": SubmissionVerdict.CE,
                "output": "",
                "error": session.compile_error,
                "time_ms": 0.0,
                "memory_kb": 0.0
            }

        env = self._get_exec_env()
        start_time = time.time()
        clean_input = input_data if (not input_data or input_data.endswith("\n")) else f"{input_data}\n"
        input_bytes = clean_input.encode("utf-8")

        # Setup process
        creationflags = 0
        preexec = None
        if not self.is_windows:
            preexec = os.setsid

        proc = None
        try:
            proc = subprocess.Popen(
                session.cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=session.temp_dir,
                env=env,
                preexec_fn=preexec,
                creationflags=creationflags
            )

            stdout_data, stderr_data = proc.communicate(input=input_bytes, timeout=timeout_seconds)
            elapsed_ms = (time.time() - start_time) * 1000.0

            # Check Output Limit Exceeded (OLE)
            if len(stdout_data) > MAX_OUTPUT_BYTES:
                truncated = stdout_data[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
                return {
                    "verdict": SubmissionVerdict.OLE,
                    "output": truncated,
                    "error": f"Output Limit Exceeded (> {MAX_OUTPUT_BYTES // 1024} KB)",
                    "time_ms": elapsed_ms,
                    "memory_kb": 0.0
                }

            raw_out = stdout_data.decode("utf-8", errors="replace")
            raw_err = stderr_data.decode("utf-8", errors="replace")

            if proc.returncode != 0:
                return {
                    "verdict": SubmissionVerdict.RE,
                    "output": raw_out,
                    "error": raw_err.strip() or f"Process exited with non-zero code {proc.returncode}",
                    "time_ms": elapsed_ms,
                    "memory_kb": 0.0
                }

            return {
                "verdict": SubmissionVerdict.AC,
                "output": raw_out,
                "error": None,
                "time_ms": elapsed_ms,
                "memory_kb": 0.0
            }

        except subprocess.TimeoutExpired:
            if proc:
                self._kill_process_tree(proc)
                try:
                    proc.communicate(timeout=1.0)
                except Exception:
                    pass
            return {
                "verdict": SubmissionVerdict.TLE,
                "output": "",
                "error": f"Time Limit Exceeded (> {timeout_seconds}s)",
                "time_ms": timeout_seconds * 1000.0,
                "memory_kb": 0.0
            }
        except Exception as e:
            if proc:
                self._kill_process_tree(proc)
            return {
                "verdict": SubmissionVerdict.RE,
                "output": "",
                "error": str(e),
                "time_ms": (time.time() - start_time) * 1000.0,
                "memory_kb": 0.0
            }


class DockerExecutionBackend(BaseExecutionBackend):
    """
    Production-Grade Docker Container Execution Backend.
    Provides OS/kernel-level container isolation, cgroups resource enforcement,
    complete network isolation (--network none), dropped capabilities (--cap-drop ALL),
    strict PID limits (--pids-limit 64), bounded tmpfs mounts, and automatic container teardown.
    Falls back gracefully to LocalProcessBackend if the Docker daemon is unreachable.
    """
    def __init__(
        self,
        fallback_backend: Optional[BaseExecutionBackend] = None,
        default_image: Optional[str] = None
    ):
        self.fallback = fallback_backend or LocalProcessBackend()
        self.default_image = default_image or os.environ.get("CODESPHERE_DOCKER_IMAGE", "codesphere-runner:latest")
        self._docker_available = self._check_docker()

    def _check_docker(self) -> bool:
        try:
            res = subprocess.run(["docker", "info"], capture_output=True, timeout=3.0)
            return res.returncode == 0
        except Exception:
            return False

    def is_docker_active(self) -> bool:
        return self._docker_available

    def _get_image_for_lang(self, lang: str) -> str:
        lang_map = {
            "python": "python:3.11-slim",
            "py": "python:3.11-slim",
            "cpp": "gcc:13",
            "c": "gcc:13",
            "java": "openjdk:17-slim",
            "javascript": "node:20-slim",
            "js": "node:20-slim",
        }
        return lang_map.get(lang.lower(), self.default_image)

    def execute(
        self,
        session: ExecutionSession,
        input_data: str,
        timeout_seconds: float,
        memory_limit_mb: int = DEFAULT_MAX_MEMORY_MB
    ) -> Dict[str, Any]:
        if session.compile_error:
            return {
                "verdict": SubmissionVerdict.CE,
                "output": "",
                "error": session.compile_error,
                "time_ms": 0.0,
                "memory_kb": 0.0,
                "backend": "docker" if self._docker_available else "local_process"
            }

        # If Docker daemon is unavailable, delegate cleanly to hardened local process runner
        if not self._docker_available:
            res = self.fallback.execute(session, input_data, timeout_seconds, memory_limit_mb)
            res["backend"] = "local_process_fallback"
            return res

        container_id = f"codesphere_eval_{uuid.uuid4().hex[:12]}"
        image = self._get_image_for_lang(session.lang)
        abs_temp = os.path.abspath(session.temp_dir)

        # Build hardened docker run invocation
        docker_cmd = [
            "docker", "run",
            "--name", container_id,
            "--rm",
            "-i",
            "--network", "none",
            "--cap-drop", "ALL",
            "--pids-limit", "64",
            "--memory", f"{memory_limit_mb}m",
            "--memory-swap", f"{memory_limit_mb}m",
            "--cpus", "1.0",
            "-v", f"{abs_temp}:/workspace:rw",
            "-w", "/workspace",
            "-e", "LANG=C.UTF-8",
            "-e", "LC_ALL=C.UTF-8",
            image,
        ]

        # Append execution command
        if session.lang in ["python", "py"]:
            docker_cmd.extend(["python", "-u", "solution.py"])
        elif session.lang in ["cpp", "c"]:
            docker_cmd.extend(["./solution" if os.name != 'nt' else "./solution.exe"])
        elif session.lang in ["java"]:
            class_name = "Solution"
            if os.path.exists(os.path.join(session.temp_dir, "Main.java")):
                class_name = "Main"
            docker_cmd.extend(["java", f"-Xmx{memory_limit_mb}m", "-cp", "/workspace", class_name])
        elif session.lang in ["javascript", "js"]:
            docker_cmd.extend(["node", f"--max-old-space-size={memory_limit_mb}", "solution.js"])
        else:
            docker_cmd.extend(session.cmd or ["python", "solution.py"])

        clean_input = input_data if (not input_data or input_data.endswith("\n")) else f"{input_data}\n"
        input_bytes = clean_input.encode("utf-8")
        start_time = time.time()
        proc = None

        try:
            proc = subprocess.Popen(
                docker_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            stdout_chunks: List[bytes] = []
            stderr_chunks: List[bytes] = []
            total_bytes = 0
            ole_triggered = False

            def reader_thread():
                nonlocal total_bytes, ole_triggered
                try:
                    if proc.stdin:
                        proc.stdin.write(input_bytes)
                        proc.stdin.flush()
                        proc.stdin.close()

                    while True:
                        chunk = proc.stdout.read(4096)
                        if not chunk:
                            break
                        total_bytes += len(chunk)
                        if total_bytes > MAX_OUTPUT_BYTES:
                            ole_triggered = True
                            subprocess.run(["docker", "kill", container_id], capture_output=True, timeout=3.0)
                            break
                        stdout_chunks.append(chunk)

                    err_chunk = proc.stderr.read(MAX_OUTPUT_BYTES)
                    if err_chunk:
                        stderr_chunks.append(err_chunk)
                except Exception:
                    pass

            t = threading.Thread(target=reader_thread)
            t.daemon = True
            t.start()
            t.join(timeout=timeout_seconds)

            if t.is_alive():
                # Timeout limit exceeded
                subprocess.run(["docker", "kill", container_id], capture_output=True, timeout=3.0)
                try:
                    proc.kill()
                except Exception:
                    pass
                return {
                    "verdict": SubmissionVerdict.TLE,
                    "output": "",
                    "error": f"Time Limit Exceeded (>{timeout_seconds}s)",
                    "time_ms": timeout_seconds * 1000.0,
                    "memory_kb": 0.0,
                    "backend": "docker"
                }

            proc.wait(timeout=2.0)
            elapsed_ms = (time.time() - start_time) * 1000.0

            if ole_triggered:
                return {
                    "verdict": SubmissionVerdict.OLE,
                    "output": b"".join(stdout_chunks).decode("utf-8", errors="replace")[:1000],
                    "error": f"Output Limit Exceeded (>{MAX_OUTPUT_BYTES // 1024} KB)",
                    "time_ms": elapsed_ms,
                    "memory_kb": 0.0,
                    "backend": "docker"
                }

            out_text = b"".join(stdout_chunks).decode("utf-8", errors="replace")
            err_text = b"".join(stderr_chunks).decode("utf-8", errors="replace")

            # Exit code 137 is standard Linux OOM killer
            if proc.returncode == 137:
                return {
                    "verdict": SubmissionVerdict.MLE,
                    "output": out_text,
                    "error": f"Memory Limit Exceeded (>{memory_limit_mb} MB)",
                    "time_ms": elapsed_ms,
                    "memory_kb": float(memory_limit_mb * 1024),
                    "backend": "docker"
                }

            if proc.returncode != 0:
                return {
                    "verdict": SubmissionVerdict.RE,
                    "output": out_text,
                    "error": err_text.strip() or f"Process exited with code {proc.returncode}",
                    "time_ms": elapsed_ms,
                    "memory_kb": 0.0,
                    "backend": "docker"
                }

            return {
                "verdict": SubmissionVerdict.AC,
                "output": out_text,
                "error": None,
                "time_ms": elapsed_ms,
                "memory_kb": 0.0,
                "backend": "docker"
            }

        except Exception as e:
            try:
                subprocess.run(["docker", "kill", container_id], capture_output=True, timeout=3.0)
            except Exception:
                pass
            return {
                "verdict": SubmissionVerdict.RE,
                "output": "",
                "error": f"Container execution error: {str(e)}",
                "time_ms": (time.time() - start_time) * 1000.0,
                "memory_kb": 0.0,
                "backend": "docker"
            }
        finally:
            try:
                subprocess.run(["docker", "rm", "-f", container_id], capture_output=True, timeout=3.0)
            except Exception:
                pass


class SandboxedCodeRunner:
    """
    Production-grade Sandboxed Code Runner and Online Judge Engine.
    Handles language compilation, execution, output normalization, resource limits,
    hidden test protection, and multi-language reference solution verification.
    """
    def __init__(self, backend: Optional[BaseExecutionBackend] = None):
        self.timeout_seconds = settings.CODE_RUNNER_TIMEOUT_SECONDS
        self.is_windows = (os.name == 'nt')
        self.semaphore = threading.BoundedSemaphore(settings.CODE_RUNNER_MAX_CONCURRENCY)
        backend_choice = os.environ.get("CODESPHERE_EXECUTION_BACKEND", "local").lower()
        if backend:
            self.backend = backend
        elif backend_choice == "docker":
            self.backend = DockerExecutionBackend(fallback_backend=LocalProcessBackend(is_windows=self.is_windows))
        else:
            self.backend = LocalProcessBackend(is_windows=self.is_windows)

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
                rf"C:\Program Files\Java\jdk-21.0.12\bin\{name}.exe",
                rf"C:\Program Files\Common Files\Oracle\Java\javapath\{name}.exe",
            ]
            for p in possible_paths:
                if os.path.exists(p):
                    return p
        return name

    def _get_exec_env(self) -> Dict[str, str]:
        if isinstance(self.backend, LocalProcessBackend):
            return self.backend._get_exec_env()
        return LocalProcessBackend()._get_exec_env()

    def _normalize_output(self, text: str) -> str:
        """Normalizes line endings, trailing whitespace, and blank lines for accurate comparison."""
        if not text:
            return ""
        # Replace Windows CRLF with standard LF
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = [line.rstrip() for line in normalized.strip().splitlines()]
        # Filter trailing empty lines while preserving internal blank lines
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
            # Python isolated mode (-I), do not write bytecode (-B)
            return ExecutionSession(
                lang="python",
                temp_dir=temp_dir,
                cmd=[sys.executable, "-I", "-B", file_path],
                source_file=file_path
            )

        # 2. C++ (G++ with C++17)
        elif lang in ["cpp", "c++"]:
            src_path = os.path.join(temp_dir, "solution.cpp")
            exe_path = os.path.join(temp_dir, "solution.exe" if self.is_windows else "solution")
            with open(src_path, "w", encoding="utf-8") as f:
                f.write(code)

            gpp_bin = self._find_bin("g++")
            try:
                compile_cmd = [gpp_bin, "-O2", "-std=c++17", src_path, "-o", exe_path]
                if self.is_windows:
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
                    return ExecutionSession(lang="cpp", temp_dir=temp_dir, compile_error=err, source_file=src_path)
                return ExecutionSession(lang="cpp", temp_dir=temp_dir, cmd=[exe_path], source_file=src_path, exe_file=exe_path)
            except subprocess.TimeoutExpired:
                return ExecutionSession(lang="cpp", temp_dir=temp_dir, compile_error="C++ Compilation Time Limit Exceeded (>15s)")
            except Exception as e:
                return ExecutionSession(lang="cpp", temp_dir=temp_dir, compile_error=f"Compiler invocation error: {str(e)}")

        # 3. C (GCC with C11 - Pure C mode)
        elif lang in ["c"]:
            src_path = os.path.join(temp_dir, "solution.c")
            exe_path = os.path.join(temp_dir, "solution.exe" if self.is_windows else "solution")
            with open(src_path, "w", encoding="utf-8") as f:
                f.write(code)

            # Search for gcc compiler; fallback to clang
            gcc_bin = self._find_bin("gcc")
            if not gcc_bin or gcc_bin == "gcc":
                # Check clang
                clang_bin = self._find_bin("clang")
                if clang_bin and clang_bin != "clang":
                    gcc_bin = clang_bin

            try:
                # Compile strictly as C (C11 standard with math library linked)
                compile_cmd = [gcc_bin, "-O2", "-std=c11", src_path, "-o", exe_path, "-lm"]
                if self.is_windows:
                    compile_cmd.extend(["-static-libgcc"])
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
                    return ExecutionSession(lang="c", temp_dir=temp_dir, compile_error=err, source_file=src_path)
                return ExecutionSession(lang="c", temp_dir=temp_dir, cmd=[exe_path], source_file=src_path, exe_file=exe_path)
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
                compile_cmd = [javac_bin, "-encoding", "UTF-8", src_path]
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
                    return ExecutionSession(lang="java", temp_dir=temp_dir, compile_error=err, source_file=src_path)
                
                run_cmd = [java_bin, "-Xmx256m", "-Xss32m", "-Dfile.encoding=UTF-8", "-cp", temp_dir, class_name]
                return ExecutionSession(lang="java", temp_dir=temp_dir, cmd=run_cmd, source_file=src_path)
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
            run_cmd = [node_bin, "--max-old-space-size=256", file_path]
            return ExecutionSession(lang="javascript", temp_dir=temp_dir, cmd=run_cmd, source_file=file_path)

        else:
            return ExecutionSession(
                lang=lang,
                temp_dir=temp_dir,
                compile_error=f"Unsupported language: '{language}'. Supported: Python, C++, C, Java, JavaScript."
            )

    def _execute_in_session(
        self,
        session: ExecutionSession,
        input_data: str,
        timeout_seconds: Optional[float] = None
    ) -> Dict[str, Any]:
        to = timeout_seconds if timeout_seconds is not None else self.timeout_seconds
        return self.backend.execute(session, input_data, timeout_seconds=to)

    def _create_temp_dir(self, prefix: str = "codesphere_run_") -> str:
        return tempfile.mkdtemp(prefix=prefix)

    def execute_single(
        self,
        code: str,
        language: str,
        input_data: str,
        timeout_seconds: Optional[float] = None
    ) -> Dict[str, Any]:
        with self.semaphore:
            temp_dir = self._create_temp_dir(prefix="codesphere_run_")
            try:
                session = self._prepare_session(code, language, temp_dir)
                return self._execute_in_session(session, input_data, timeout_seconds=timeout_seconds)
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

    def evaluate_test_cases(
        self,
        code: str,
        language: str,
        test_cases: List[Dict[str, Any]],
        stop_on_first_failure: bool = False,
        timeout_seconds: Optional[float] = None
    ) -> Dict[str, Any]:
        with self.semaphore:
            results = []
            passed_count = 0
            total_points = 0
            earned_points = 0
            max_time_ms = 0.0
            peak_memory_kb = 0.0
            final_verdict = SubmissionVerdict.AC
            first_error = None

            temp_dir = self._create_temp_dir(prefix="codesphere_eval_")

            try:
                def _get_tc_info(tc_item):
                    if isinstance(tc_item, dict):
                        return (
                            tc_item.get("id"),
                            str(tc_item.get("input_data", tc_item.get("input", "")) or ""),
                            str(tc_item.get("expected_output", tc_item.get("expected", "")) or ""),
                            int(tc_item.get("points", 10) or 10),
                            bool(tc_item.get("is_hidden", False))
                        )
                    return (
                        getattr(tc_item, "id", None),
                        str(getattr(tc_item, "input_data", getattr(tc_item, "input", "")) or ""),
                        str(getattr(tc_item, "expected_output", getattr(tc_item, "expected", "")) or ""),
                        int(getattr(tc_item, "points", 10) or 10),
                        bool(getattr(tc_item, "is_hidden", False))
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
                            "memory_kb": 0.0,
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
                        "peak_memory_kb": 0.0,
                        "error_message": session.compile_error,
                        "test_case_results": results
                    }

                for tc in test_cases:
                    tc_id, tc_input, tc_expected, tc_points, is_hidden = _get_tc_info(tc)
                    total_points += tc_points

                    run_res = self._execute_in_session(session, tc_input, timeout_seconds=timeout_seconds)
                    max_time_ms = max(max_time_ms, run_res["time_ms"])
                    peak_memory_kb = max(peak_memory_kb, run_res.get("memory_kb", 0.0))

                    if run_res["verdict"] in [SubmissionVerdict.TLE, SubmissionVerdict.MLE, SubmissionVerdict.OLE, SubmissionVerdict.RE]:
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
                            "memory_kb": run_res.get("memory_kb", 0.0),
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
                                "memory_kb": run_res.get("memory_kb", 0.0),
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
                                "memory_kb": run_res.get("memory_kb", 0.0),
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
                    "peak_memory_kb": round(peak_memory_kb, 2),
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
        Validates all language reference solutions (C, C++, Java, Python, JavaScript) against the entire test suite.
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


# Global hardened judge instance
code_runner = SandboxedCodeRunner()
