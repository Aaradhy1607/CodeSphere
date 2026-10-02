import os
import sys
import time
import uuid
import logging
import asyncio
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.models import (
    Submission, SubmissionVerdict, SubmissionStatus, Question, Event, User
)
from app.services.code_runner import code_runner

logger = logging.getLogger("codesphere.judge_queue")


class InvalidStateTransitionError(Exception):
    """Raised when an illegal submission state transition is attempted."""
    pass


# Strict lifecycle state transition graph
VALID_STATE_TRANSITIONS = {
    SubmissionStatus.QUEUED.value: {
        SubmissionStatus.COMPILING.value,
        SubmissionStatus.RUNNING.value,
        SubmissionStatus.CANCELLED.value,
        SubmissionStatus.FAILED.value,
    },
    SubmissionStatus.COMPILING.value: {
        SubmissionStatus.RUNNING.value,
        SubmissionStatus.EVALUATING.value,
        SubmissionStatus.COMPLETED.value,  # Direct completion on CE
        SubmissionStatus.FAILED.value,
    },
    SubmissionStatus.RUNNING.value: {
        SubmissionStatus.EVALUATING.value,
        SubmissionStatus.COMPLETED.value,
        SubmissionStatus.FAILED.value,
    },
    SubmissionStatus.EVALUATING.value: {
        SubmissionStatus.COMPLETED.value,
        SubmissionStatus.FAILED.value,
    },
    SubmissionStatus.FAILED.value: {
        SubmissionStatus.QUEUED.value,  # Allowed only for explicit retries
    },
    SubmissionStatus.COMPLETED.value: set(),  # Terminal immutable state
    SubmissionStatus.CANCELLED.value: set(),  # Terminal immutable state
}


class JudgeMetrics:
    """Thread-safe judge observability metrics tracker."""
    def __init__(self):
        self.queued_count: int = 0
        self.running_count: int = 0
        self.completed_count: int = 0
        self.failed_count: int = 0
        self.total_processed: int = 0
        self.total_queue_wait_ms: float = 0.0
        self.total_exec_time_ms: float = 0.0
        self.peak_memory_kb: float = 0.0
        self.sandbox_failures: int = 0
        self.recent_latencies: List[float] = []

    def record_enqueue(self):
        self.queued_count += 1

    def record_start(self, queue_wait_ms: float):
        if self.queued_count > 0:
            self.queued_count -= 1
        self.running_count += 1
        self.total_queue_wait_ms += max(0.0, queue_wait_ms)

    def record_complete(self, exec_time_ms: float, memory_kb: float):
        if self.running_count > 0:
            self.running_count -= 1
        self.completed_count += 1
        self.total_processed += 1
        self.total_exec_time_ms += max(0.0, exec_time_ms)
        self.peak_memory_kb = max(self.peak_memory_kb, memory_kb)
        self.recent_latencies.append(exec_time_ms)
        if len(self.recent_latencies) > 1000:
            self.recent_latencies.pop(0)

    def record_fail(self):
        if self.running_count > 0:
            self.running_count -= 1
        elif self.queued_count > 0:
            self.queued_count -= 1
        self.failed_count += 1
        self.total_processed += 1
        self.sandbox_failures += 1

    def get_snapshot(self) -> Dict[str, Any]:
        avg_wait = (self.total_queue_wait_ms / max(1, self.total_processed)) if self.total_processed > 0 else 0.0
        avg_exec = (self.total_exec_time_ms / max(1, self.completed_count)) if self.completed_count > 0 else 0.0
        return {
            "queued_submissions": max(0, self.queued_count),
            "running_submissions": max(0, self.running_count),
            "completed_submissions": self.completed_count,
            "failed_submissions": self.failed_count,
            "total_processed": self.total_processed,
            "average_queue_wait_ms": round(avg_wait, 2),
            "average_execution_time_ms": round(avg_exec, 2),
            "peak_memory_kb": round(self.peak_memory_kb, 2),
            "sandbox_failures": self.sandbox_failures,
        }


class JudgeQueueManager:
    """
    Production-Grade Judge Queue & Worker Pool.
    Decouples submission ingestion from execution with bounded concurrency,
    idempotent job claiming, failure recovery, and state machine validation.
    """
    def __init__(self, max_concurrency: int = 8):
        self.max_concurrency = max_concurrency
        self.queue: asyncio.Queue = asyncio.Queue()
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.metrics = JudgeMetrics()
        self.is_running = False
        self._workers: List[asyncio.Task] = []
        self._claimed_submission_ids: Set[int] = set()
        self._lock = asyncio.Lock()
        self._events: Dict[int, asyncio.Event] = {}

    def start(self, worker_count: Optional[int] = None):
        """Starts asynchronous judging worker tasks."""
        if not self.is_running:
            self.is_running = True
            count = worker_count or self.max_concurrency
            for i in range(count):
                task = asyncio.create_task(self._worker_loop(f"judge-worker-{i+1}"))
                self._workers.append(task)
            logger.info(f"[CodeSphere Judge] Started {count} concurrent judge worker tasks.")

    async def stop(self):
        """Gracefully shuts down judge workers."""
        self.is_running = False
        for worker in self._workers:
            worker.cancel()
        self._workers.clear()
        logger.info("[CodeSphere Judge] Judge worker pool stopped.")

    @staticmethod
    def validate_transition(current_status: str, target_status: str):
        """Ensures state transitions obey the strict submission lifecycle."""
        valid_next = VALID_STATE_TRANSITIONS.get(current_status, set())
        if target_status not in valid_next:
            raise InvalidStateTransitionError(
                f"Illegal submission state transition: '{current_status}' -> '{target_status}'. "
                f"Valid next states: {list(valid_next)}"
            )

    async def enqueue_submission(
        self,
        submission_id: int,
        enqueued_at: Optional[float] = None
    ) -> bool:
        """Enqueues a submission for asynchronous judging."""
        enqueue_time = enqueued_at or time.time()
        self.metrics.record_enqueue()
        await self.queue.put((submission_id, enqueue_time))
        logger.debug(f"[Judge Queue] Enqueued submission #{submission_id} (Queue size: {self.queue.qsize()})")
        return True

    async def submit_and_await(
        self,
        submission_id: int,
        timeout_seconds: float = 30.0
    ) -> Dict[str, Any]:
        """
        Enqueues submission and waits for worker evaluation completion (used by synchronous APIs).
        """
        event = asyncio.Event()
        self._events[submission_id] = event
        await self.enqueue_submission(submission_id)

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            logger.warning(f"[Judge Queue] Awaiting submission #{submission_id} timed out after {timeout_seconds}s")
        finally:
            self._events.pop(submission_id, None)

        db = SessionLocal()
        try:
            sub = db.query(Submission).filter(Submission.id == submission_id).first()
            if sub:
                return {
                    "submission_id": sub.id,
                    "status": getattr(sub, "status", SubmissionStatus.COMPLETED.value),
                    "verdict": sub.verdict,
                    "score": sub.score,
                    "passed_test_cases": sub.passed_test_cases,
                    "total_test_cases": sub.total_test_cases,
                    "execution_time_ms": sub.execution_time_ms,
                    "memory_used_kb": sub.memory_used_kb,
                    "error_message": sub.error_message,
                    "is_final": sub.is_final
                }
            return {"submission_id": submission_id, "status": SubmissionStatus.FAILED.value, "error_message": "Submission not found."}
        finally:
            db.close()

    async def _worker_loop(self, worker_name: str):
        """Continuous worker execution loop claiming and evaluating submissions."""
        while self.is_running:
            try:
                submission_id, enqueued_at = await self.queue.get()
                queue_wait_ms = (time.time() - enqueued_at) * 1000.0

                async with self._lock:
                    if submission_id in self._claimed_submission_ids:
                        logger.warning(f"[{worker_name}] Submission #{submission_id} is already claimed by another worker; skipping.")
                        self.queue.task_done()
                        continue
                    self._claimed_submission_ids.add(submission_id)

                async with self.semaphore:
                    self.metrics.record_start(queue_wait_ms)
                    try:
                        loop = asyncio.get_running_loop()
                        await loop.run_in_executor(None, self._execute_submission_sync, submission_id, worker_name)
                    except Exception as e:
                        logger.error(f"[{worker_name}] Critical failure judging submission #{submission_id}: {e}", exc_info=True)
                        self.metrics.record_fail()
                    finally:
                        async with self._lock:
                            self._claimed_submission_ids.discard(submission_id)
                        
                        # Notify waiting listeners
                        if submission_id in self._events:
                            self._events[submission_id].set()

                        self.queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{worker_name}] Unhandled exception in worker loop: {e}", exc_info=True)
                await asyncio.sleep(0.5)

    def _execute_submission_sync(self, submission_id: int, worker_name: str):
        """
        Synchronous judge execution handler executed inside worker threadpool.
        Manages DB transactions, state transitions, sandbox execution, and verdict persistence.
        """
        db = SessionLocal()
        start_exec = time.time()
        try:
            sub = db.query(Submission).filter(Submission.id == submission_id).first()
            if not sub:
                logger.error(f"[{worker_name}] Submission #{submission_id} not found in database.")
                self.metrics.record_fail()
                return

            # Check and transition status: QUEUED -> COMPILING
            current_status = getattr(sub, "status", SubmissionStatus.QUEUED.value) or SubmissionStatus.QUEUED.value
            try:
                self.validate_transition(current_status, SubmissionStatus.COMPILING.value)
            except InvalidStateTransitionError as e:
                logger.error(f"[{worker_name}] State transition failed for submission #{submission_id}: {e}")
                self.metrics.record_fail()
                return

            sub.status = SubmissionStatus.COMPILING.value
            db.commit()

            question = db.query(Question).filter(Question.id == sub.question_id).first()
            if not question:
                sub.status = SubmissionStatus.FAILED.value
                sub.error_message = "Associated question not found."
                db.commit()
                self.metrics.record_fail()
                return

            # Server-authoritative time and memory limits derived from question definition
            time_limit = getattr(question, "time_limit_seconds", 3.0) or 3.0
            test_cases = question.test_cases or []

            # Transition: COMPILING -> RUNNING / EVALUATING
            self.validate_transition(sub.status, SubmissionStatus.RUNNING.value)
            sub.status = SubmissionStatus.RUNNING.value
            db.commit()

            # Execute via sandboxed code runner
            eval_res = code_runner.evaluate_test_cases(
                code=sub.code,
                language=sub.language,
                test_cases=test_cases,
                timeout_seconds=time_limit
            )

            # Transition: RUNNING -> EVALUATING -> COMPLETED
            self.validate_transition(sub.status, SubmissionStatus.EVALUATING.value)
            sub.status = SubmissionStatus.EVALUATING.value
            db.commit()

            sub.verdict = eval_res.get("verdict", SubmissionVerdict.WA.value)
            sub.passed_test_cases = eval_res.get("passed_count", 0)
            sub.total_test_cases = eval_res.get("total_count", len(test_cases))
            sub.score = eval_res.get("score", 0.0)
            sub.execution_time_ms = eval_res.get("max_time_ms", 0.0)
            sub.memory_used_kb = eval_res.get("peak_memory_kb", 0.0)
            sub.error_message = eval_res.get("error_message")
            sub.test_case_results = eval_res.get("test_case_results", [])
            sub.is_final = True

            self.validate_transition(sub.status, SubmissionStatus.COMPLETED.value)
            sub.status = SubmissionStatus.COMPLETED.value
            db.commit()

            exec_duration_ms = (time.time() - start_exec) * 1000.0
            self.metrics.record_complete(exec_duration_ms, sub.memory_used_kb)
            logger.info(
                f"[{worker_name}] Submission #{submission_id} judged successfully: "
                f"Verdict={sub.verdict}, Score={sub.score}, Time={sub.execution_time_ms:.1f}ms, Memory={sub.memory_used_kb:.1f}KB"
            )

        except Exception as e:
            db.rollback()
            logger.error(f"[{worker_name}] Exception during judging submission #{submission_id}: {e}", exc_info=True)
            try:
                sub = db.query(Submission).filter(Submission.id == submission_id).first()
                if sub:
                    sub.status = SubmissionStatus.FAILED.value
                    sub.verdict = SubmissionVerdict.RE.value
                    sub.error_message = "Internal judge execution error."
                    db.commit()
            except Exception:
                pass
            self.metrics.record_fail()
        finally:
            db.close()

    def recover_stuck_submissions(self, max_stuck_seconds: float = 300.0) -> int:
        """
        Sweeper utility to recover submissions left orphaned in running/compiling states
        due to sudden host reboots or worker crashes.
        """
        db = SessionLocal()
        recovered_count = 0
        try:
            now = datetime.now(timezone.utc)
            stuck_subs = db.query(Submission).filter(
                Submission.status.in_([
                    SubmissionStatus.QUEUED.value,
                    SubmissionStatus.COMPILING.value,
                    SubmissionStatus.RUNNING.value,
                    SubmissionStatus.EVALUATING.value,
                ])
            ).all()

            for sub in stuck_subs:
                submitted_at = sub.submitted_at
                if submitted_at.tzinfo is None:
                    submitted_at = submitted_at.replace(tzinfo=timezone.utc)
                age_seconds = (now - submitted_at).total_seconds()
                if age_seconds > max_stuck_seconds:
                    logger.warning(f"[Judge Sweeper] Recovering orphaned submission #{sub.id} (stuck in {sub.status} for {age_seconds:.1f}s)")
                    sub.status = SubmissionStatus.FAILED.value
                    sub.verdict = SubmissionVerdict.RE.value
                    sub.error_message = "Execution timed out or host worker restarted."
                    recovered_count += 1
            if recovered_count > 0:
                db.commit()
            return recovered_count
        except Exception as e:
            logger.error(f"[Judge Sweeper] Error during stuck submission recovery: {e}")
            db.rollback()
            return 0
        finally:
            db.close()


# Global Singleton Instance
judge_queue_manager = JudgeQueueManager(max_concurrency=settings.CODE_RUNNER_MAX_CONCURRENCY)
