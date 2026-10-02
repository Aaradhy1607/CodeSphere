import os
import time
import uuid
import logging
import datetime
from contextlib import asynccontextmanager
from typing import Dict, List, Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import engine, Base, SessionLocal, auto_migrate_db, check_db_health
from app.core.cache import cache
from app.services.worker import task_worker
from app.services.judge_queue import judge_queue_manager
from app.services.seeder import seed_database
from app.api import (
    auth, students, events, questions, execute, leaderboards, analytics, reports, assessments
)

# Structured Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("codesphere.server")

# System Metrics Storage (In-memory ring buffer)
START_TIME = time.time()
METRICS: Dict[str, Any] = {
    "total_requests": 0,
    "total_errors": 0,
    "recent_latencies_ms": [],
    "status_codes": {},
    "endpoints": {}
}

def record_metric(path: str, status_code: int, duration_ms: float):
    METRICS["total_requests"] += 1
    if status_code >= 500:
        METRICS["total_errors"] += 1
    
    METRICS["status_codes"][str(status_code)] = METRICS["status_codes"].get(str(status_code), 0) + 1
    METRICS["endpoints"][path] = METRICS["endpoints"].get(path, 0) + 1
    
    # Keep last 1,000 latencies for accurate percentile computation
    METRICS["recent_latencies_ms"].append(duration_ms)
    if len(METRICS["recent_latencies_ms"]) > 1000:
        METRICS["recent_latencies_ms"].pop(0)

def calculate_percentiles(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "avg": 0.0}
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    return {
        "p50": round(sorted_vals[int(n * 0.50)], 2),
        "p95": round(sorted_vals[min(int(n * 0.95), n - 1)], 2),
        "p99": round(sorted_vals[min(int(n * 0.99), n - 1)], 2),
        "avg": round(sum(sorted_vals) / n, 2),
        "min": round(sorted_vals[0], 2),
        "max": round(sorted_vals[-1], 2),
    }

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[CodeSphere] Starting server initialization...")
    # Initialize Database tables and columns
    Base.metadata.create_all(bind=engine)
    auto_migrate_db()
    
    # Seed initial USAR dataset
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()

    # Check and log cache backend status
    cache_health = cache.check_health()
    if cache_health.get("backend") == "redis" and cache_health.get("status") == "HEALTHY":
        logger.info(f"[REDIS CONNECTED] Connected to Redis at {settings.REDIS_URL} (latency: {cache_health.get('latency_ms')}ms)")
    else:
        logger.info(f"[CACHE INITIALIZED] Backend: {cache_health.get('backend')} | Status: {cache_health.get('status')}")

    # Start background task worker and judge queue worker
    task_worker.start(worker_count=settings.WORKER_CONCURRENCY)
    judge_queue_manager.start(worker_count=settings.CODE_RUNNER_MAX_CONCURRENCY)
    
    # Sweep any stuck submissions left from a previous crash/reboot
    recovered = judge_queue_manager.recover_stuck_submissions(max_stuck_seconds=300.0)
    if recovered > 0:
        logger.warning(f"[CodeSphere Judge] Recovered {recovered} orphaned submissions from previous session.")

    logger.info(f"[CodeSphere] Server ready in {settings.ENVIRONMENT} mode. Background task and judge workers active.")
    
    yield
    
    # Graceful shutdown
    logger.info("[CodeSphere] Shutting down background and judge workers...")
    await task_worker.stop()
    await judge_queue_manager.stop()
    logger.info("[CodeSphere] Server shutdown complete.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Request Correlation ID & Latency Middleware
@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    
    start_time = time.time()
    try:
        response: Response = await call_next(request)
    except Exception as exc:
        duration_ms = (time.time() - start_time) * 1000.0
        record_metric(request.url.path, 500, duration_ms)
        logger.error(f"[{request_id}] Unhandled error on {request.method} {request.url.path}: {exc}", exc_info=True)
        raise exc

    duration_ms = (time.time() - start_time) * 1000.0
    record_metric(request.url.path, response.status_code, duration_ms)
    
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-Ms"] = str(round(duration_ms, 2))
    
    # Log structured summary for non-health endpoints
    if not request.url.path.startswith("/health") and not request.url.path.startswith("/metrics"):
        logger.info(f"[{request_id}] {request.method} {request.url.path} -> {response.status_code} ({round(duration_ms, 2)}ms)")
    
    return response

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:[0-9]+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(students.router, prefix=settings.API_V1_STR)
app.include_router(events.router, prefix=settings.API_V1_STR)
app.include_router(questions.router, prefix=settings.API_V1_STR)
app.include_router(execute.router, prefix=settings.API_V1_STR)
app.include_router(leaderboards.router, prefix=settings.API_V1_STR)
app.include_router(analytics.router, prefix=settings.API_V1_STR)
app.include_router(reports.router, prefix=settings.API_V1_STR)
app.include_router(assessments.router, prefix=settings.API_V1_STR)

# Mount Static File Serving for Uploaded Question Media/Diagrams
uploads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads"))
os.makedirs(os.path.join(uploads_dir, "questions"), exist_ok=True)
app.mount("/static/uploads", StaticFiles(directory=uploads_dir), name="uploads")

@app.get("/")
def root():
    return {
        "platform": "CodeSphere",
        "institution": "University School of Automation and Robotics (USAR)",
        "status": "online",
        "environment": settings.ENVIRONMENT,
        "version": "3.0.0",
        "documentation": "/docs"
    }

# ================= HEALTH & READINESS PROBES =================

@app.get("/health")
@app.get("/health/liveness")
def liveness_probe():
    """Liveness probe: verifies the process is responsive."""
    uptime = time.time() - START_TIME
    return {
        "status": "ALIVE",
        "service": "codesphere-backend",
        "uptime_seconds": round(uptime, 2),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }

@app.get("/health/readiness")
def readiness_probe():
    """Readiness probe: validates critical dependencies (PostgreSQL/SQLite, Redis/Cache, Worker)."""
    db_status = check_db_health()
    cache_status = cache.check_health()
    worker_stats = task_worker.get_stats()
    
    is_ready = db_status.get("status") == "HEALTHY"
    overall_status = "READY" if is_ready else "UNREADY"
    
    return {
        "status": overall_status,
        "environment": settings.ENVIRONMENT,
        "database": db_status,
        "cache": cache_status,
        "worker": worker_stats,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }

# ================= PRODUCTION SYSTEM METRICS =================

@app.get("/metrics")
def get_metrics():
    """Returns runtime telemetry, latency percentiles, database pool stats, and throughput."""
    uptime = time.time() - START_TIME
    latencies = calculate_percentiles(METRICS["recent_latencies_ms"])
    db_health = check_db_health()
    
    return {
        "uptime_seconds": round(uptime, 2),
        "total_requests": METRICS["total_requests"],
        "total_errors": METRICS["total_errors"],
        "error_rate_percent": round((METRICS["total_errors"] / max(METRICS["total_requests"], 1)) * 100.0, 2),
        "latencies_ms": latencies,
        "status_codes": METRICS["status_codes"],
        "database_pool": db_health.get("pool", {}),
        "cache_backend": cache.check_health(),
        "worker_queue": task_worker.get_stats()
    }

# CodeSphere Production Readiness Verification 2026



