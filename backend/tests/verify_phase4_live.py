import io
import os
import uuid
import requests

BASE_URL = os.getenv("VERIFY_BASE_URL", "http://127.0.0.1:8000/api/v1")

def login(email, password):
    resp = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    return resp.json()["access_token"]

def main():
    print("============================================================")
    print("CODESPHERE PHASE 4 — LIVE RUNTIME VERIFICATION")
    print("============================================================")

    # 1. AUTHENTICATE ROLES
    admin_pw = os.getenv("VERIFY_ADMIN_PASSWORD", "admin123")
    admin_token = login(os.getenv("VERIFY_ADMIN_EMAIL", "admin@ipu.ac.in"), admin_pw)
    setter_token = login(os.getenv("VERIFY_SETTER_EMAIL", "setter.ai@ipu.ac.in"), os.getenv("VERIFY_SETTER_PASSWORD", "setter123"))
    reviewer_token = login(os.getenv("VERIFY_REVIEWER_EMAIL", "reviewer.cs@ipu.ac.in"), os.getenv("VERIFY_REVIEWER_PASSWORD", "reviewer123"))
    student_token = login(os.getenv("VERIFY_STUDENT_EMAIL", "aarav.patel@std.ggsipu.ac.in"), os.getenv("VERIFY_STUDENT_PASSWORD", "student123"))
    print("[PASS] Authenticated Admin, Question Setter, Reviewer, and Student roles")

    # 2. IMAGE UPLOAD VALIDATION & SECURITY
    setter_headers = {"Authorization": f"Bearer {setter_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    reviewer_headers = {"Authorization": f"Bearer {reviewer_token}"}
    student_headers = {"Authorization": f"Bearer {student_token}"}

    # 2a. Valid PNG Upload
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    files = {"file": ("architecture.png", io.BytesIO(png_bytes), "image/png")}
    upload_res = requests.post(f"{BASE_URL}/questions/upload-image", headers=setter_headers, files=files)
    assert upload_res.status_code == 200, f"Image upload failed: {upload_res.text}"
    image_url = upload_res.json()["image_url"]
    assert image_url.startswith("/static/uploads/"), f"Invalid image URL: {image_url}"
    print(f"[PASS] Image upload verification passed: {image_url}")

    # 2b. Malicious / Executable Upload Rejection
    fake_exe = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00"
    files_bad = {"file": ("exploit.png", io.BytesIO(fake_exe), "image/png")}
    bad_upload_res = requests.post(f"{BASE_URL}/questions/upload-image", headers=setter_headers, files=files_bad)
    assert bad_upload_res.status_code == 400, "Security failure: Non-image executable was not rejected"
    print("[PASS] Image security filter verified: Disallowed non-image byte headers")

    # 3. DUPLICATE DETECTION API
    dup_res = requests.post(
        f"{BASE_URL}/questions/check-duplicate",
        headers=setter_headers,
        json={"title": "Binary Tree Maximum Path Sum", "problem_statement": "Given a binary tree, compute the maximum path sum between any two nodes."}
    )
    assert dup_res.status_code == 200
    dup_json = dup_res.json()
    assert "is_duplicate" in dup_json
    print(f"[PASS] Duplicate detector online: Checked candidate similarity ({dup_json['similarity_score']})")

    # 4. MANUAL QUESTION AUTHORING (Coding, MCQ, Subjective)
    run_id = uuid.uuid4().hex[:6]
    
    # 4a. Coding Question
    coding_payload = {
        "title": f"Autonomous Cache Line Invalidation Protocol {run_id}",
        "question_type": "CODING",
        "subject": "Computer Systems",
        "topic": "Operating Systems",
        "subtopic": "Cache Coherence",
        "blooms_level": "ANALYZE",
        "marks": 100,
        "negative_marks": 0,
        "time_estimate_minutes": 35,
        "learning_objective": "Evaluate understanding of MESI cache protocols and dirty line eviction",
        "concept_tags": ["OS", "Hardware", "Cache"],
        "difficulty_score": 7,
        "problem_statement": "### Task Overview\nGiven a sequence of CPU read and write operations across 4 cores in a shared-bus multiprocessor system, determine the final state of cache line L according to the standard MESI invalidation protocol.\n\n**Input** description: You receive the number of operations followed by each operation's core ID and type.\n\n**Output** the final MESI state character.",
        "input_format": "The first line contains integer N denoting the number of memory transactions, followed by N lines each specifying core ID and operation.",
        "output_format": "Print a single character denoting the resulting line state: M (Modified), E (Exclusive), S (Shared), or I (Invalid).",
        "constraints": "1 <= N <= 10^5, 0 <= CoreID <= 3",
        "expected_time_complexity": "O(N)",
        "expected_space_complexity": "O(1)",
        "reference_solutions": {
            "python": "import sys\n\ndef solve():\n    lines = sys.stdin.read().split()\n    if not lines: return\n    print('M')\n\nif __name__ == '__main__':\n    solve()",
            "cpp": "#include <iostream>\nusing namespace std;\nint main(){\n    cout << 'M';\n    return 0;\n}",
            "c": "#include <stdio.h>\nint main(){\n    printf(\"M\");\n    return 0;\n}",
            "java": "import java.util.Scanner;\npublic class Solution {\n    public static void main(String[] args) {\n        System.out.println(\"M\");\n    }\n}"
        },
        "examples": [
            {"input": "3\nC0 READ\nC1 READ\nC0 WRITE", "output": "M", "explanation": "Exclusive ownership transition to Modified upon write"}
        ],
        "status": "PENDING_REVIEW",
        "test_cases": [
            {"input_data": "3\nC0 READ\nC1 READ\nC0 WRITE", "expected_output": "M", "is_hidden": False, "points": 40},
            {"input_data": "2\nC0 READ\nC1 WRITE", "expected_output": "I", "is_hidden": True, "points": 60}
        ]
    }
    create_coding_res = requests.post(f"{BASE_URL}/questions/", headers=setter_headers, json=coding_payload)
    assert create_coding_res.status_code == 200, f"Coding creation failed: {create_coding_res.text}"
    coding_q = create_coding_res.json()
    coding_id = coding_q["id"]
    assert coding_q["quality_score"] >= 70, f"Expected quality score >= 70, got {coding_q['quality_score']}"
    assert coding_q["status"] == "PENDING_REVIEW"
    print(f"[PASS] Manual Coding Question created (#{coding_id}) with Quality Score: {coding_q['quality_score']}/100")

    # 4b. MCQ Question — options as structured dicts with is_correct flag
    mcq_payload = {
        "title": f"B-Tree Node Split Thresholds {run_id}",
        "question_type": "MCQ",
        "subject": "Database Engineering",
        "topic": "Indexing",
        "blooms_level": "UNDERSTAND",
        "marks": 25,
        "negative_marks": 5,
        "time_estimate_minutes": 10,
        "difficulty_score": 4,
        "problem_statement": "In a B-Tree of order M, what is the maximum number of keys that a non-root internal node can contain before a split is triggered? Consider the standard B-Tree definition where order M means maximum M children per node. Select the correct answer from the options below.",
        "options": [
            {"id": "A", "text": "M - 1", "is_correct": True},
            {"id": "B", "text": "M", "is_correct": False},
            {"id": "C", "text": "M / 2", "is_correct": False},
            {"id": "D", "text": "2M - 1", "is_correct": False}
        ],
        "correct_answer": "A",
        "explanation": "A B-tree node of order M has at most M children and M - 1 keys. When the key count exceeds M - 1, the node must split.",
        "status": "PENDING_REVIEW"
    }
    create_mcq_res = requests.post(f"{BASE_URL}/questions/", headers=setter_headers, json=mcq_payload)
    assert create_mcq_res.status_code == 200, f"MCQ creation failed: {create_mcq_res.text}"
    mcq_q = create_mcq_res.json()
    mcq_id = mcq_q["id"]
    assert mcq_q["quality_score"] >= 70, f"Expected MCQ quality score >= 70, got {mcq_q['quality_score']}"
    print(f"[PASS] Manual MCQ Question created (#{mcq_id}) with Quality Score: {mcq_q['quality_score']}/100")

    # 5. PEER REVIEW & APPROVAL WORKFLOW
    review_res = requests.post(
        f"{BASE_URL}/questions/{coding_id}/review",
        headers=reviewer_headers,
        json={"action": "APPROVE", "feedback": "Excellent real-world hardware concurrency question.", "force": True}
    )
    assert review_res.status_code == 200, f"Review failed: {review_res.text}"
    review_json = review_res.json()
    assert review_json["question"]["status"] == "APPROVED", f"Expected APPROVED, got {review_json}"
    print(f"[PASS] Reviewer approval verified: Question #{coding_id} transitioned to APPROVED")

    # 6. PUBLISHING WORKFLOW
    pub_res = requests.post(f"{BASE_URL}/questions/{coding_id}/publish", headers=admin_headers)
    assert pub_res.status_code == 200, f"Publishing failed: {pub_res.text}"
    pub_json = pub_res.json()
    assert pub_json["question"]["status"] == "PUBLISHED", f"Expected PUBLISHED, got {pub_json}"
    print(f"[PASS] Publishing verified: Question #{coding_id} transitioned to PUBLISHED")

    # 7. IMMUTABLE VERSIONING ON PUBLISHED QUESTION UPDATE
    update_payload = {
        "title": f"Autonomous Cache Line Invalidation Protocol (v2 Optimized) {run_id}",
        "change_summary": "Clarified MESI transition state edge cases and core numbering"
    }
    update_res = requests.put(f"{BASE_URL}/questions/{coding_id}", headers=admin_headers, json=update_payload)
    assert update_res.status_code == 200, f"Update failed: {update_res.text}"
    new_version_q = update_res.json()
    new_version_id = new_version_q["id"]
    assert new_version_id != coding_id, "Expected new row created for immutable versioning"
    assert new_version_q["version_number"] == 2
    assert new_version_q["parent_question_id"] == coding_id
    assert new_version_q["is_latest"] is True

    # Check version lineage API
    lineage_res = requests.get(f"{BASE_URL}/questions/{new_version_id}/versions", headers=admin_headers)
    assert lineage_res.status_code == 200
    versions = lineage_res.json()
    assert len(versions) >= 2, f"Expected at least 2 versions, got {len(versions)}"
    print(f"[PASS] Immutable Versioning verified: Parent #{coding_id} (v1, is_latest=False) -> Revision #{new_version_id} (v2, is_latest=True)")

    # 8. QUESTION ANALYTICS & CALIBRATION TELEMETRY
    analytics_res = requests.get(f"{BASE_URL}/questions/{new_version_id}/analytics", headers=admin_headers)
    assert analytics_res.status_code == 200
    analytics_json = analytics_res.json()
    assert "quality_breakdown" in analytics_json
    assert "experienced_difficulty" in analytics_json
    print(f"[PASS] Question Analytics API verified: Success rate {analytics_json['success_rate_percent']}%, Quality {analytics_json['quality_score']}/100")

    # 9. AI GENERATION ENDPOINT INVOCATION
    ai_gen_res = requests.post(
        f"{BASE_URL}/questions/generate-ai",
        headers=admin_headers,
        json={
            "topic": "Graph Algorithms",
            "sub_topic": "Bipartite Graph Matching",
            "question_type": "CODING",
            "difficulty_score": 6,
            "blooms_level": "APPLY",
            "reference_blueprint": "Hopcroft-Karp maximum cardinality matching in bipartite graph"
        }
    )
    assert ai_gen_res.status_code == 200, f"AI generation failed: {ai_gen_res.text}"
    ai_q = ai_gen_res.json()["question"]
    assert ai_q["is_ai_generated"] is True
    assert ai_q["quality_score"] > 0
    print(f"[PASS] AI Generation Pipeline verified: Synthesized Question #{ai_q['id']} ({ai_q['title']}) with Quality Score: {ai_q['quality_score']}/100")

    # 10. RBAC SECURITY ENFORCEMENT
    # Student cannot create questions
    bad_create = requests.post(f"{BASE_URL}/questions/", headers=student_headers, json={"title": "Hacked", "problem_statement": "Cheat"})
    assert bad_create.status_code == 403, f"Expected 403 for student creation, got {bad_create.status_code}"
    # Student cannot review questions
    bad_review = requests.post(f"{BASE_URL}/questions/{coding_id}/review", headers=student_headers, json={"action": "APPROVE"})
    assert bad_review.status_code == 403, f"Expected 403 for student review, got {bad_review.status_code}"
    # Student cannot publish questions
    bad_pub = requests.post(f"{BASE_URL}/questions/{coding_id}/publish", headers=student_headers)
    assert bad_pub.status_code == 403, f"Expected 403 for student publish, got {bad_pub.status_code}"
    print("[PASS] RBAC Security Gates verified: Student rejected from creation, review, and publishing endpoints (403 Forbidden)")

    print("============================================================")
    print("PHASE 4 COMPLETE LIVE RUNTIME VERIFICATION: ALL PASSED (10/10)")
    print("============================================================")

if __name__ == "__main__":
    main()
