import asyncio
import inspect
import time
import logging
import uuid
from typing import Dict, Any, Callable, Optional
from datetime import datetime, timezone

logger = logging.getLogger("codesphere.worker")

class JobStatus:
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class BackgroundTaskManager:
    """
    Asynchronous background job worker supporting retries, idempotency, and non-blocking API dispatch.
    """
    def __init__(self, max_concurrency: int = 4):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.is_running = False
        self._workers = []

    def start(self, worker_count: int = 4):
        if not self.is_running:
            self.is_running = True
            for i in range(worker_count):
                task = asyncio.create_task(self._worker_loop(f"worker-{i+1}"))
                self._workers.append(task)
            logger.info(f"Started {worker_count} background workers.")

    async def stop(self):
        self.is_running = False
        for worker in self._workers:
            worker.cancel()
        logger.info("Stopped background workers.")

    async def enqueue(
        self,
        handler: Callable,
        *args,
        job_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        max_retries: int = 3,
        **kwargs
    ) -> str:
        job_id = job_id or str(uuid.uuid4())
        
        # Idempotency check: if job with key already exists, return existing job_id
        if idempotency_key:
            for j_id, job in self.jobs.items():
                if job.get("idempotency_key") == idempotency_key:
                    logger.info(f"Idempotent task match for key {idempotency_key}, returning existing job {j_id}")
                    return j_id

        job_info = {
            "id": job_id,
            "idempotency_key": idempotency_key,
            "status": JobStatus.PENDING,
            "handler_name": getattr(handler, "__name__", str(handler)),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "started_at": None,
            "completed_at": None,
            "retries": 0,
            "max_retries": max_retries,
            "result": None,
            "error": None,
        }
        self.jobs[job_id] = job_info

        await self.queue.put((job_id, handler, args, kwargs, max_retries, 0))
        return job_id

    async def _worker_loop(self, worker_name: str):
        while self.is_running:
            try:
                job_id, handler, args, kwargs, max_retries, retry_count = await self.queue.get()
                
                async with self.semaphore:
                    job = self.jobs.get(job_id)
                    if job:
                        job["status"] = JobStatus.PROCESSING
                        job["started_at"] = datetime.now(timezone.utc).isoformat()

                    try:
                        logger.debug(f"[{worker_name}] Executing job {job_id} ({job.get('handler_name') if job else 'unknown'})")
                        if inspect.iscoroutinefunction(handler):
                            result = await handler(*args, **kwargs)
                        else:
                            # Run synchronous blocking tasks in default threadpool executor
                            loop = asyncio.get_running_loop()
                            result = await loop.run_in_executor(None, lambda: handler(*args, **kwargs))

                        if job:
                            job["status"] = JobStatus.COMPLETED
                            job["completed_at"] = datetime.now(timezone.utc).isoformat()
                            job["result"] = result
                            logger.info(f"[{worker_name}] Job {job_id} completed successfully.")

                    except Exception as e:
                        logger.error(f"[{worker_name}] Error executing job {job_id}: {e}", exc_info=True)
                        if retry_count < max_retries:
                            # Exponential backoff retry
                            backoff = 2 ** retry_count
                            logger.warning(f"[{worker_name}] Retrying job {job_id} in {backoff}s (attempt {retry_count + 1}/{max_retries})")
                            await asyncio.sleep(backoff)
                            if job:
                                job["retries"] = retry_count + 1
                            await self.queue.put((job_id, handler, args, kwargs, max_retries, retry_count + 1))
                        else:
                            if job:
                                job["status"] = JobStatus.FAILED
                                job["completed_at"] = datetime.now(timezone.utc).isoformat()
                                job["error"] = str(e)
                    finally:
                        self.queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_name} encountered loop error: {e}")

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self.jobs.get(job_id)

    def get_stats(self) -> Dict[str, Any]:
        total = len(self.jobs)
        pending = sum(1 for j in self.jobs.values() if j["status"] == JobStatus.PENDING)
        processing = sum(1 for j in self.jobs.values() if j["status"] == JobStatus.PROCESSING)
        completed = sum(1 for j in self.jobs.values() if j["status"] == JobStatus.COMPLETED)
        failed = sum(1 for j in self.jobs.values() if j["status"] == JobStatus.FAILED)
        return {
            "queue_depth": self.queue.qsize(),
            "total_jobs": total,
            "pending": pending,
            "processing": processing,
            "completed": completed,
            "failed": failed,
            "is_running": self.is_running
        }

task_worker = BackgroundTaskManager()
