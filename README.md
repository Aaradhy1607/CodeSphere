# CodeSphere — Enterprise College Coding Assessment & Online Judge Platform

CodeSphere is a high-concurrency, hardened college coding assessment, contest arena, and asynchronous online judge platform designed for university placement drives, coding competitions, and academic evaluations.

---

## 🏛 Platform Architecture

CodeSphere is built on a decoupled, asynchronous, and secure architecture:

```
                      +-----------------------------+
                      | Next.js 16 (App Router)     |
                      | Monaco Editor + Anti-Cheat  |
                      +--------------+--------------+
                                     |
                          REST API / JWT Session
                                     |
                                     v
                      +-----------------------------+
                      | FastAPI Backend Gateway     |
                      | Auth, RBAC, Quality Engine  |
                      +--------------+--------------+
                                     |
                         Enqueues via State Machine
                                     |
                                     v
                      +-----------------------------+
                      | JudgeQueueManager (Async)   |
                      | Worker Pool & Concurrency   |
                      +--------------+--------------+
                                     |
                                     v
           +-------------------------+-------------------------+
           |                                                   |
           v                                                   v
+-------------------------+                         +-------------------------+
| Docker Sandbox (Prod)   |                         | LocalProcess (Dev/Test) |
| --network none          |                         | Subprocess Allowlist    |
| --cap-drop ALL          |                         | Secret Scrubbing        |
| --memory / --pids-limit |                         | Output / Timeout Guard  |
+-------------------------+                         +-------------------------+
```

---

## ⚡ Key Capabilities

1. **Hardened Multi-Language Judge Engine**:
   - Supported languages: Python, C (C11), C++ (C++17), Java (OpenJDK), JavaScript (Node.js).
   - Strict verdict evaluation: `AC` (Accepted), `WA` (Wrong Answer), `TLE` (Time Limit Exceeded), `MLE` (Memory Limit Exceeded), `OLE` (Output Limit Exceeded), `CE` (Compilation Error), `RE` (Runtime Error).
   - Streaming OLE protection (standardized at **256 KB** maximum output) with proactive process termination.
   - Real peak memory telemetry via OS-level counters (`GetProcessMemoryInfo` / Linux cgroups).
   - Sanitized subprocess environments preventing host secret, JWT token, or database credential leakage.

2. **Enterprise RBAC & Security**:
   - 7 Discrete Roles: `STUDENT`, `FACULTY`, `QUESTION_SETTER`, `REVIEWER`, `PLACEMENT_ADMIN`, `ADMIN`, `SUPER_ADMIN`.
   - Granular permission matrices enforced server-side.
   - Complete Horizontal & Vertical IDOR protection.
   - Hidden test case and reference solution shielding before official result publication.
   - Server-authoritative countdown timer independent of client clock manipulation.

3. **High-Concurrency Asynchronous Queue**:
   - Non-blocking ingestion via `POST /api/v1/execute/submit-async` and status polling `GET /api/v1/execute/status/{id}`.
   - Guaranteed state lifecycle transitions: `QUEUED` -> `COMPILING` -> `RUNNING` -> `EVALUATING` -> `COMPLETED`/`FAILED`.
   - Duplicate worker claim prevention with distributed lock simulation.
   - Stuck submission sweeper recovering orphan jobs after configurable timeouts.

4. **Assessment & Proctoring Suite**:
   - Full-screen lock, tab switch tracking, and copy-paste anomaly detection.
   - Configurable penalty policies (`NONE`, `DEDUCT_INTEGRITY`, `WARNING`, `TERMINATE`).
   - Real-time autosave with answer version tracking.
   - Double-submit idempotency protection preventing race conditions.

5. **AI Quality Engine & Adaptive Learning**:
   - Multi-dimensional Problem Quality Scoring across schema, constraints, time/space complexity, and test cases.
   - Exact and semantic duplicate statement detection.
   - Deterministic adaptive learning recommendation loop tailoring problem difficulty and topic mastery based on student performance history (with robust cold-start handling).

---

## 🚀 Getting Started (Development)

### Prerequisites
- Python 3.11+
- Node.js 20+
- (Optional) Docker for containerized judging

### 1. Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env

# Run local development server
python run.py
```
Backend API will be live at `http://localhost:8000` (Docs at `http://localhost:8000/docs`).

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Frontend web application will be live at `http://localhost:3000`.

---

## 🔒 Production Deployment & Hardening

In production environments (`APP_ENV=production`):

1. **Zero-Secret Startup Validation & Fail-Closed Guard**:
   - Fails fast on startup if `SECRET_KEY` is set to insecure defaults, placeholder strings, or is under 32 characters.
   - Missing `INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD` or `DATABASE_URL` halts execution immediately.
   - SQLite is rejected in production mode; PostgreSQL connection is mandatory.
   - Single Super-Admin invariant strictly protected against duplication or silent role escalation.
   - Wildcard `*` CORS origins are forbidden; explicit allowed frontend origins are enforced.

2. **Docker Sandboxing**:
   - Untrusted student code is isolated inside isolated Docker containers with `--network none`, `--cap-drop ALL`, `--memory 256m`, and `--pids-limit 64`.
   - `CODESPHERE_EXECUTION_BACKEND=docker`
   - `REQUIRE_DOCKER_SANDBOX=true`
   - `ALLOW_LOCAL_PROCESS_FALLBACK=false`

3. **Running with Docker Compose**:
```bash
export POSTGRES_USER=codesphere_admin
export POSTGRES_PASSWORD=$(openssl rand -hex 24)
export SECRET_KEY=$(openssl rand -hex 32)
export INITIAL_ADMIN_EMAIL=admin@yourcollege.edu
export INITIAL_ADMIN_PASSWORD=$(openssl rand -hex 16)
export CORS_ORIGINS=https://codesphere.yourcollege.edu

docker compose -f docker-compose.yml up --build -d
```

---

## 🧪 Testing & Verification Gate

Run the complete release gates, PostgreSQL/Redis integration suites, and full regression test suite:

```bash
# Backend test suite (239+ tests) with coverage
cd backend
python -m pytest tests/ -v --cov=app --cov-report=term-missing

# Specific master hardening, PostgreSQL & Redis integration, and release gates
python -m pytest tests/test_master_production_hardening.py -v
python -m pytest tests/test_redis_integration.py -v
python -m pytest tests/test_final_release_gate.py -v
python -m pytest tests/test_final_security_closure.py -v

# Frontend TypeScript check & production build
cd ../frontend
npm ci
npx tsc --noEmit
npm run build
```

---

## 📄 License
Proprietary — Developed for university campus assessment and competitive programming evaluation.
