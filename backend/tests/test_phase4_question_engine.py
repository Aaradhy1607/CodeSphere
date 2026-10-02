import io
import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.models import (
    User, UserRole, Question, QuestionStatus, ValidationStatus,
    QuestionType, BloomsLevel, TestCase, QuestionFeedback, SubmissionVerdict
)
from app.core.database import SessionLocal
from app.services.quality_scorer import quality_scorer
from app.services.duplicate_detector import duplicate_detector
from app.services.adaptive_learning import adaptive_learning_engine
from app.services.code_runner import code_runner
from app.services.gemini_ai import gemini_service

client = TestClient(app)

def get_admin_token():
    resp = client.post("/api/v1/auth/login", json={"email": "placement@ipu.ac.in", "password": "admin123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]

def get_student_token():
    resp = client.post("/api/v1/auth/login", json={"email": "aarav.patel@std.ggsipu.ac.in", "password": "student123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]

# ================= 1. QUALITY SCORER UNIT TESTS =================
def test_quality_scorer_coding_complete():
    res = quality_scorer.evaluate(
        title="Optimal Subarray Energy Routing",
        problem_statement="Given an array of N sensor nodes, determine the maximum continuous transmission power.\n\n### Constraints\n1 <= N <= 10^5\n-10^4 <= A[i] <= 10^4\n\n**Input Format:**\nFirst line contains integer N.\n\n**Output Format:**\nPrint max sum.",
        input_format="First line contains N. Second line contains N integers.",
        output_format="Single integer max sum.",
        constraints="1 <= N <= 10^5, -10^4 <= A[i] <= 10^4",
        examples=[{"input": "4\n1 2 3 4", "output": "10", "explanation": "Sum of all positive elements is 10."}],
        difficulty_score=6,
        expected_time_complexity="O(N)",
        expected_space_complexity="O(1)",
        reference_solutions={
            "python": "import sys\ndef solve(): pass",
            "cpp": "#include <iostream>\nint main(){return 0;}",
            "c": "#include <stdio.h>\nint main(){return 0;}",
            "java": "public class Solution { public static void main(String[] args){} }"
        },
        test_cases=[
            {"input": "1", "expected": "1", "is_hidden": False, "points": 10},
            {"input": "2", "expected": "2", "is_hidden": False, "points": 10},
            {"input": "3", "expected": "3", "is_hidden": True, "points": 20},
            {"input": "4", "expected": "4", "is_hidden": True, "points": 20},
            {"input": "5", "expected": "5", "is_hidden": True, "points": 20},
            {"input": "6", "expected": "6", "is_hidden": True, "points": 20}
        ],
        question_type="CODING"
    )
    assert res["quality_score"] >= 80.0
    assert res["grade"] in ["A+", "A"]
    assert res["is_ready_for_review"] is True
    assert "completeness" in res["breakdown"]
    assert "test_coverage" in res["breakdown"]

def test_quality_scorer_incomplete_coding():
    res = quality_scorer.evaluate(
        title="Incomplete Problem",
        problem_statement="Do something with numbers.",
        input_format="",
        output_format="",
        constraints="",
        examples=[],
        difficulty_score=5,
        expected_time_complexity="",
        expected_space_complexity="",
        reference_solutions={},
        test_cases=[],
        question_type="CODING"
    )
    assert res["quality_score"] < 50.0
    assert res["is_ready_for_review"] is False

def test_quality_scorer_mcq():
    res = quality_scorer.evaluate(
        title="Time Complexity of Hash Lookup",
        problem_statement="What is the average case time complexity of searching a key in a hash table with good hashing?\n\n### Options\nConsider universal hashing with no severe collisions.",
        input_format="",
        output_format="",
        constraints="",
        examples=[],
        difficulty_score=3,
        expected_time_complexity="O(1)",
        expected_space_complexity="O(N)",
        reference_solutions={},
        test_cases=[],
        question_type="MCQ",
        options=[
            {"id": "A", "text": "O(1)", "is_correct": True},
            {"id": "B", "text": "O(log N)", "is_correct": False},
            {"id": "C", "text": "O(N)", "is_correct": False},
            {"id": "D", "text": "O(N log N)", "is_correct": False}
        ],
        correct_answer="A"
    )
    assert res["quality_score"] >= 75.0
    assert res["is_ready_for_review"] is True

# ================= 2. DUPLICATE DETECTOR 8-SCENARIO BENCHMARKS =================
def test_duplicate_detector_8_scenarios():
    # 1. Exact duplicate
    s1 = "Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target."
    r1 = duplicate_detector.compare_statements(s1, s1)
    assert r1["category"] == "DUPLICATE"
    assert r1["level_1_exact"] is True
    assert r1["similarity_score"] == 1.0

    # 2. Near duplicate (Minor whitespace/case differences)
    s2 = "  given an array of integers nums and integer target, return indices of the two numbers such that they add up to target!  "
    r2 = duplicate_detector.compare_statements(s1, s2)
    assert r2["category"] == "DUPLICATE"
    assert r2["similarity_score"] >= 0.88

    # 3. Paraphrased duplicate (Synonym substitution)
    s3_a = "Explain how binary search works."
    s3_b = "Describe the working principle of binary search."
    r3 = duplicate_detector.compare_statements(s3_a, s3_b)
    assert r3["category"] in ["DUPLICATE", "SIMILAR"]
    assert r3["similarity_score"] >= 0.70

    # 4. Related but different question (False-positive protection: Explain vs Compare)
    s4_a = "Explain binary search."
    s4_b = "Compare binary search with linear search."
    r4 = duplicate_detector.compare_statements(s4_a, s4_b)
    assert r4["is_duplicate"] is False
    assert r4["category"] in ["RELATED", "SIMILAR", "UNIQUE"]

    # 5. Completely unrelated question
    s5_a = "Implement quicksort algorithm to sort an array."
    s5_b = "Find the nth Fibonacci number using dynamic programming."
    r5 = duplicate_detector.compare_statements(s5_a, s5_b)
    assert r5["category"] == "UNIQUE"
    assert r5["is_duplicate"] is False
    assert r5["similarity_score"] < 0.45

    # 6. Different questions about same topic
    s6_a = "Find all connected components in an undirected graph using Breadth First Search."
    s6_b = "Find the topological ordering of a directed acyclic graph using Depth First Search."
    r6 = duplicate_detector.compare_statements(s6_a, s6_b)
    assert r6["is_duplicate"] is False
    assert r6["category"] in ["RELATED", "UNIQUE"]

    # 7. Same question with changed constraints
    s7_a = "Given an array of size N <= 1000, find two numbers that sum to target."
    s7_b = "Given an array of size N <= 1000000, find two numbers that sum to target in O(N log N) time."
    r7 = duplicate_detector.compare_statements(s7_a, s7_b)
    assert r7["similarity_score"] >= 0.70

    # 8. Programming problems with different requirements
    s8_a = "Find two numbers in array that add up to target value."
    s8_b = "Find three unique numbers in array that sum to zero."
    r8 = duplicate_detector.compare_statements(s8_a, s8_b)
    assert r8["is_duplicate"] is False
    assert r8["category"] in ["RELATED", "UNIQUE"]

def test_duplicate_detector_database_check():
    db = SessionLocal()
    try:
        run_uid = uuid.uuid4().hex[:8]
        test_title = f"Unique Substring Traversal Protocol {run_uid}"
        test_statement = f"Find the length of the longest substring without repeating characters in string S_{run_uid}."
        unique_slug = f"unique-substring-traversal-{run_uid}"
        
        q1 = Question(
            title=test_title,
            slug=unique_slug,
            problem_statement=test_statement,
            similarity_hash=duplicate_detector.compute_hash(f"{duplicate_detector.normalize_text(test_title)} {duplicate_detector.normalize_text(test_statement)}")
        )
        db.add(q1)
        db.commit()

        # Check exact match
        exact_res = duplicate_detector.check_duplicate(
            title=test_title,
            problem_statement=test_statement,
            db=db
        )
        assert exact_res["is_duplicate"] is True
        assert exact_res["category"] == "DUPLICATE"
        assert exact_res["similarity_score"] == 1.0
        assert exact_res["matched_question_id"] == q1.id

        # Clean up test row
        db.delete(q1)
        db.commit()
    finally:
        db.close()

# ================= 3. MANUAL QUESTION AUTHORING & API TESTS =================
def test_manual_question_creation_and_quality():
    token = get_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "title": "Autonomous Path Weight Minimization",
        "problem_statement": "Given a grid of size M x N, find the minimum path sum from top-left to bottom-right moving only right or down.\n\n### Constraints\n1 <= M, N <= 200\n0 <= Grid[i][j] <= 100",
        "input_format": "First line contains M and N. Next M lines contain N integers.",
        "output_format": "Print single integer minimum cost.",
        "constraints": "1 <= M, N <= 200",
        "question_type": "CODING",
        "subject": "Data Structures & Algorithms",
        "topic": "Dynamic Programming",
        "subtopic": "Grid Optimization",
        "blooms_level": "APPLY",
        "marks": 100,
        "negative_marks": 0.0,
        "time_estimate_minutes": 35,
        "learning_objective": "Evaluate grid DP state formulation",
        "concept_tags": ["Dynamic Programming", "Matrix Traversal"],
        "examples": [{"input": "2 2\n1 2\n1 1", "output": "3", "explanation": "Path 1->1->1 = 3"}],
        "topic_tags": ["Dynamic Programming", "Grid"],
        "difficulty_score": 5,
        "expected_time_complexity": "O(M*N)",
        "expected_space_complexity": "O(M*N)",
        "reference_solutions": {
            "python": "import sys\ndef solve(): pass\nif __name__ == '__main__': solve()"
        },
        "test_cases": [
            {"input_data": "2 2\n1 2\n1 1", "expected_output": "3", "is_hidden": False, "points": 10},
            {"input_data": "1 1\n5", "expected_output": "5", "is_hidden": True, "points": 20}
        ]
    }

    resp = client.post("/api/v1/questions/", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == payload["title"]
    assert data["status"] == "DRAFT"
    assert data["quality_score"] > 50.0
    assert data["version_number"] == 1
    assert data["is_latest"] is True
    assert len(data["test_cases"]) == 2

    qid = data["id"]

    # ================= 4. REVIEW & PUBLISH WORKFLOW =================
    # Step A: Request review / Approve
    rev_resp = client.post(
        f"/api/v1/questions/{qid}/review",
        json={"action": "APPROVE", "feedback": "Problem statement verified by reviewer", "force": True},
        headers=headers
    )
    assert rev_resp.status_code == 200
    assert rev_resp.json()["status"] == "APPROVED"

    # Step B: Publish
    pub_resp = client.post(f"/api/v1/questions/{qid}/publish", headers=headers)
    assert pub_resp.status_code == 200
    assert pub_resp.json()["status"] == "PUBLISHED"

    # ================= 5. QUESTION VERSIONING IMMUTABILITY =================
    # Updating a PUBLISHED question creates an immutable new version
    update_resp = client.put(
        f"/api/v1/questions/{qid}",
        json={"title": "Autonomous Path Weight Minimization (Enhanced V2)", "change_summary": "Clarified corner grid constraints"},
        headers=headers
    )
    assert update_resp.status_code == 200
    v2_data = update_resp.json()
    assert v2_data["id"] != qid # New version created
    assert v2_data["version_number"] == 2
    assert v2_data["parent_question_id"] == qid
    assert v2_data["is_latest"] is True

    # Check version history endpoint
    vers_resp = client.get(f"/api/v1/questions/{v2_data['id']}/versions", headers=headers)
    assert vers_resp.status_code == 200
    versions = vers_resp.json()
    assert len(versions) >= 2
    assert any(v["version_number"] == 1 for v in versions)
    assert any(v["version_number"] == 2 for v in versions)

    # Clean up test rows
    client.delete(f"/api/v1/questions/{v2_data['id']}", headers=headers)
    client.delete(f"/api/v1/questions/{qid}", headers=headers)

# ================= 6. SECURE IMAGE UPLOAD & VALIDATION =================
def test_image_upload_valid_and_invalid():
    token = get_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Valid PNG binary
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    file_payload = {"file": ("test_diagram.png", io.BytesIO(png_bytes), "image/png")}
    
    upload_resp = client.post("/api/v1/questions/upload-image", files=file_payload, headers=headers)
    assert upload_resp.status_code == 200
    upload_data = upload_resp.json()
    assert "image_url" in upload_data
    assert upload_data["image_url"].startswith("/static/uploads/questions/")
    assert upload_data["mime_type"] == "image/png"

    # Invalid executable disguised as image
    fake_exe = b"MZ\x90\x00\x03\x00\x00\x00This is an executable binary"
    bad_payload = {"file": ("malware.png", io.BytesIO(fake_exe), "image/png")}
    bad_resp = client.post("/api/v1/questions/upload-image", files=bad_payload, headers=headers)
    assert bad_resp.status_code == 400
    assert "Security validation failed" in bad_resp.json()["detail"]

# ================= 7. ADAPTIVE CALIBRATION & SAMPLE-SIZE SAFETY =================
def test_adaptive_difficulty_calibration_minimum_sample_and_bounds():
    db = SessionLocal()
    try:
        run_uid = uuid.uuid4().hex[:8]
        q = Question(
            title=f"Adaptive Invariant Test {run_uid}",
            slug=f"adaptive-invariant-test-sample-{run_uid}",
            problem_statement="Sample statement for adaptive testing",
            difficulty_score=7,
            status=QuestionStatus.APPROVED.value
        )
        db.add(q)
        db.commit()
        db.refresh(q)

        # 1. Test Minimum Sample Safety Guard: Attempts 1 to 4 should NOT change difficulty
        for i in range(4):
            adaptive_learning_engine.record_attempt_signal(
                question_id=q.id,
                is_correct=True,
                execution_time_seconds=10.0,
                is_skipped=False,
                db=db
            )
            db.refresh(q)
            assert q.total_attempts == i + 1
            # Retains original designed difficulty because N < 5
            assert q.experienced_difficulty == 7.0

        # 2. Test 5th Attempt (Trigger calibration with bounded smoothing)
        adaptive_learning_engine.record_attempt_signal(
            question_id=q.id,
            is_correct=True,
            execution_time_seconds=10.0,
            is_skipped=False,
            db=db
        )
        db.refresh(q)
        assert q.total_attempts == 5
        # Since 5/5 passed, calibrated difficulty moves downward in bounded manner
        assert q.experienced_difficulty < 7.0
        # Bounded delta prevents jump greater than MAX_DIFFICULTY_DELTA_PER_UPDATE (1.5)
        assert q.experienced_difficulty >= (7.0 - 1.5)

        # 3. Test Discrimination Index Calculation after 10 submissions
        for _ in range(6):
            adaptive_learning_engine.record_attempt_signal(
                question_id=q.id,
                is_correct=True,
                execution_time_seconds=10.0,
                is_skipped=False,
                db=db
            )
        db.refresh(q)
        assert q.total_attempts == 11
        assert q.experienced_difficulty >= 1.0
        assert q.experienced_difficulty <= 10.0

        # Query analytics endpoint
        token = get_admin_token()
        analytics_resp = client.get(f"/api/v1/questions/{q.id}/analytics", headers={"Authorization": f"Bearer {token}"})
        assert analytics_resp.status_code == 200
        an_data = analytics_resp.json()
        assert an_data["total_attempts"] == 11
        assert an_data["success_rate_percent"] == 100.0

        db.delete(q)
        db.commit()
    finally:
        db.close()

# ================= 8. CODE RUNNER MULTI-LANGUAGE BENCHMARKS =================
def test_code_runner_all_languages_and_error_handling():
    # 1. Python execution
    py_res = code_runner.execute_single("print('hello')", "python", "")
    assert py_res["verdict"] == SubmissionVerdict.AC
    assert py_res["output"].strip() == "hello"

    # 2. Runtime Error handling
    err_res = code_runner.execute_single("print(1/0)", "python", "")
    assert err_res["verdict"] == SubmissionVerdict.RE

    # 3. C++ execution & compilation error
    bad_cpp = "int main(){ not_valid_syntax; }"
    c_err = code_runner.execute_single(bad_cpp, "cpp", "")
    assert c_err["verdict"] == SubmissionVerdict.CE

    # 4. Java execution
    java_code = "public class Solution { public static void main(String[] args) { System.out.println(10 * 10); } }"
    java_res = code_runner.execute_single(java_code, "java", "")
    assert java_res["verdict"] == SubmissionVerdict.AC
    assert java_res["output"].strip() == "100"

# ================= 9. AI SERVICE JSON PARSING SAFETY =================
def test_gemini_service_safe_json_parsing():
    # Markdown wrapped JSON
    raw_md = "```json\n{\n  \"title\": \"Test Title\",\n  \"difficulty_score\": 5\n}\n```"
    parsed = gemini_service._safe_json_parse(raw_md)
    assert parsed["title"] == "Test Title"
    assert parsed["difficulty_score"] == 5

    # Control char handling
    raw_ctrl = "{\n  \"title\": \"Test\x01\x02 Title\",\n  \"val\": 42\n}"
    parsed_ctrl = gemini_service._safe_json_parse(raw_ctrl)
    assert parsed_ctrl["title"] == "Test Title"
    assert parsed_ctrl["val"] == 42

# ================= 10. RBAC QUESTION SECURITY AUDIT =================
def test_student_cannot_create_or_review_question():
    student_token = get_student_token()
    headers = {"Authorization": f"Bearer {student_token}"}

    # Student cannot create question
    resp = client.post(
        "/api/v1/questions/",
        json={"title": "Hacked Question", "problem_statement": "Statement", "difficulty_score": 1},
        headers=headers
    )
    assert resp.status_code == 403

    # Student cannot review question
    rev_resp = client.post(
        "/api/v1/questions/1/review",
        json={"action": "APPROVE"},
        headers=headers
    )
    assert rev_resp.status_code == 403
