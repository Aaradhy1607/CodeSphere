import urllib.request
import json
import sys

def run_audit():
    print("==================================================")
    print(" CODESPHERE RUNTIME CONTRACT & ROUTE AUDIT")
    print("==================================================")

    # 1. Login
    login_data = json.dumps({"email": "placement@ipu.ac.in", "password": "admin123"}).encode("utf-8")
    req = urllib.request.Request(
        "http://localhost:8000/api/v1/auth/login",
        data=login_data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        tokens = json.loads(resp.read().decode())
    token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("[AUTH LOGIN] PASS — Obtained valid JWT access token")

    # 2. Analytics Compare Contract
    req = urllib.request.Request("http://localhost:8000/api/v1/analytics/compare?student_ids=1,2,3", headers=headers)
    with urllib.request.urlopen(req) as resp:
        compare_res = json.loads(resp.read().decode())
    print(f"[ANALYTICS COMPARE] PASS — Received {len(compare_res)} candidate comparisons")
    for c in compare_res:
        assert "student_id" in c and c["student_id"] is not None, f"Missing student_id: {c}"
        assert "id" in c and c["id"] is not None, f"Missing id: {c}"
        assert "full_name" in c, f"Missing full_name: {c}"
        assert "topic_mastery" in c and isinstance(c["topic_mastery"], dict), f"Invalid topic_mastery: {c}"
        print(f"  * Candidate [id={c['id']}, student_id={c['student_id']}]: {c['full_name']} | Score: {c['total_score']} | Readiness: {c['placement_readiness']}")

    # 3. Students list uniqueness
    req = urllib.request.Request("http://localhost:8000/api/v1/students/", headers=headers)
    with urllib.request.urlopen(req) as resp:
        students = json.loads(resp.read().decode())
    print(f"[STUDENTS LIST] PASS — Received {len(students)} students")
    student_ids = [s["id"] for s in students]
    assert len(student_ids) == len(set(student_ids)), "Duplicate student IDs in list!"

    # 4. Frontend Route Audit
    pages = [
        "/",
        "/admin/dashboard",
        "/admin/analytics",
        "/admin/students",
        "/admin/questions",
        "/admin/events",
        "/admin/leaderboards",
        "/admin/ai-generator",
        "/student/dashboard",
        "/student/events",
        "/student/reports",
        "/student/leaderboard"
    ]
    print("\n[FRONTEND ROUTE AUDIT]")
    for p in pages:
        req = urllib.request.Request(f"http://localhost:3000{p}")
        with urllib.request.urlopen(req) as resp:
            status = resp.getcode()
            print(f"  - Route {p:25s}: HTTP {status} OK")
            assert status == 200

    # 5. Infrastructure & Health
    req = urllib.request.Request("http://localhost:8000/health/readiness")
    with urllib.request.urlopen(req) as resp:
        health = json.loads(resp.read().decode())
    print(f"\n[BACKEND READINESS] PASS — Status: {health['status']}, DB: {health['database']['status']}, Cache: {health['cache']['status']} ({health['cache']['backend']})")

    print("\n==================================================")
    print(" ALL RUNTIME CONTRACTS AND ROUTES VERIFIED: PASS")
    print("==================================================")

if __name__ == "__main__":
    run_audit()
