import pytest
import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db, auto_migrate_db
from app.models.models import (
    User, UserRole, AccountStatus, Question, TestCase, QuestionType,
    SubmissionVerdict, SubmissionStatus, Assessment, AssessmentQuestion,
    AssessmentAttempt, Submission, TestCaseCategory
)
from app.services.problem_quality import problem_quality_engine
from app.services.test_case_quality import test_case_quality_validator
from app.services.difficulty_intelligence import difficulty_intelligence
from app.services.submission_analytics import submission_analytics
from app.services.duplicate_detector import duplicate_detector
from app.services.contest_quality import contest_quality_validator

from app.core.database import Base, engine, SessionLocal, auto_migrate_db
from app.core.security import create_access_token
import uuid

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    auto_migrate_db()
    yield

@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# =====================================================================
# PART A & B: PROBLEM QUALITY & TEST CASE SUITE VALIDATION
# =====================================================================

def test_1_problem_quality_engine_complete_and_incomplete():
    # 1. Complete high-quality problem
    complete_tcs = [
        {"id": 1, "input_data": "5\n1 2 3 4 5", "expected_output": "15", "is_hidden": False, "category": "NORMAL"},
        {"id": 2, "input_data": "3\n10 20 30", "expected_output": "60", "is_hidden": False, "category": "NORMAL"},
        {"id": 3, "input_data": "1\n0", "expected_output": "0", "is_hidden": True, "category": "MINIMUM"},
        {"id": 4, "input_data": "2\n-5 5", "expected_output": "0", "is_hidden": True, "category": "BOUNDARY"},
        {"id": 5, "input_data": "100\n" + "1 " * 100, "expected_output": "100", "is_hidden": True, "category": "PERFORMANCE"},
        {"id": 6, "input_data": "4\n1000000000 1000000000", "expected_output": "2000000000", "is_hidden": True, "category": "OVERFLOW"},
    ]
    report_good = problem_quality_engine.evaluate_problem(
        title="Sum of Array Elements",
        problem_statement="Given an array of integers, compute and return the total sum of all elements.",
        input_format="First line contains N. Second line contains N integers.",
        output_format="Print a single integer representing the sum.",
        constraints="1 <= N <= 10^5, -10^9 <= A[i] <= 10^9",
        examples=[{"input": "3\n1 2 3", "output": "6", "explanation": "1+2+3=6"}],
        difficulty_score=3,
        expected_time_complexity="O(N)",
        expected_space_complexity="O(1)",
        time_limit_seconds=2.0,
        memory_limit_mb=256,
        reference_solutions={
            "python": "import sys\ninput = sys.stdin.read\ndef solve():\n    data = input().split()\n    if data: print(sum(map(int, data[1:])))\nsolve()",
            "cpp": "#include <iostream>\nusing namespace std;\nint main() { int n; if(cin >> n){ long long s=0, x; while(n--){ cin>>x; s+=x; } cout<<s<<endl; } return 0; }"
        },
        test_cases=complete_tcs,
        question_type="CODING"
    )
    assert report_good["quality_score"] >= 80.0
    assert report_good["grade"] in ["A", "A+"]
    assert report_good["is_ready_for_review"] is True
    assert len(report_good["errors"]) == 0

    # 2. Incomplete problem (no hidden test cases, no reference solutions, invalid limits)
    report_bad = problem_quality_engine.evaluate_problem(
        title="Bad",
        problem_statement="Short",
        input_format="",
        output_format="",
        constraints="",
        examples=[],
        difficulty_score=9,
        expected_time_complexity="O(N^5)",
        expected_space_complexity="",
        time_limit_seconds=0.01,
        memory_limit_mb=10,
        reference_solutions={},
        test_cases=[],
        question_type="CODING"
    )
    assert report_bad["quality_score"] < 50.0
    assert report_bad["grade"] in ["D", "F"]
    assert report_bad["is_ready_for_review"] is False
    assert len(report_bad["errors"]) > 0


def test_2_test_case_quality_flaws_and_duplicate_detection():
    # Detects: No hidden cases + duplicate inputs
    tcs = [
        {"id": 1, "input_data": "10 20\n", "expected_output": "30", "is_hidden": False},
        {"id": 2, "input_data": "10 20\n", "expected_output": "30", "is_hidden": False}, # Duplicate
    ]
    report = test_case_quality_validator.validate_test_suite(tcs)
    assert report["is_valid"] is False
    assert report["visible_count"] == 2
    assert report["hidden_count"] == 0
    assert len(report["duplicate_pairs"]) == 1
    assert any("No hidden test cases" in err for err in report["errors"])
    assert any("identical input data" in err.lower() for err in report["errors"])


def test_3_test_case_heuristic_classification():
    # Verifies heuristic classification logic
    assert test_case_quality_validator.classify_test_case_heuristic("", "") == TestCaseCategory.EMPTY.value
    assert test_case_quality_validator.classify_test_case_heuristic("0", "0") == TestCaseCategory.EMPTY.value
    assert test_case_quality_validator.classify_test_case_heuristic("-10", "0") == TestCaseCategory.BOUNDARY.value
    assert test_case_quality_validator.classify_test_case_heuristic("2147483648", "0") == TestCaseCategory.OVERFLOW.value
    assert test_case_quality_validator.classify_test_case_heuristic("a", "1") == TestCaseCategory.SINGLETON.value
    assert test_case_quality_validator.classify_test_case_heuristic("5 5 5 5 5", "5") == TestCaseCategory.DUPLICATE.value
    assert test_case_quality_validator.classify_test_case_heuristic("1 2 3 4 5", "15") == TestCaseCategory.SORTED.value
    assert test_case_quality_validator.classify_test_case_heuristic("5 4 3 2 1", "15") == TestCaseCategory.REVERSE_SORTED.value
    assert test_case_quality_validator.classify_test_case_heuristic("1 " * 500, "500") == TestCaseCategory.PERFORMANCE.value


# =====================================================================
# PART C: DIFFICULTY INTELLIGENCE (AUTHOR vs OBSERVED)
# =====================================================================

def test_4_difficulty_intelligence_insufficient_data(db_session):
    q = Question(
        title="Unsolved Hard Problem",
        slug=f"unsolved-hard-prob-{uuid.uuid4().hex[:6]}",
        problem_statement="A problem with very few submissions.",
        difficulty_score=8
    )
    db_session.add(q)
    db_session.commit()

    # 2 submissions only (< 5 threshold)
    sub1 = Submission(event_id=1, question_id=q.id, user_id=1, code="print(1)", language="python", verdict="Wrong Answer", status="COMPLETED")
    sub2 = Submission(event_id=1, question_id=q.id, user_id=2, code="print(2)", language="python", verdict="Accepted", status="COMPLETED")
    db_session.add_all([sub1, sub2])
    db_session.commit()

    intel = difficulty_intelligence.analyze_question_difficulty(q.id, db_session)
    assert intel["has_sufficient_data"] is False
    assert intel["author_difficulty_score"] == 8.0
    assert intel["author_difficulty_label"] == "Hard"
    assert intel["observed_difficulty_score"] is None
    assert intel["observed_difficulty_label"] == "Insufficient Data"


def test_5_difficulty_intelligence_sufficient_data(db_session):
    q = Question(
        title="Well-Attempted Balanced Problem",
        slug=f"well-attempted-prob-{uuid.uuid4().hex[:6]}",
        problem_statement="Problem with 10 submissions.",
        difficulty_score=3
    )
    db_session.add(q)
    db_session.commit()

    # Seed 10 submissions: 6 AC, 2 WA, 1 TLE, 1 RE across 6 distinct users
    subs = [
        Submission(event_id=1, question_id=q.id, user_id=10, code="p", language="python", verdict="Accepted", execution_time_ms=120, memory_used_kb=1024, status="COMPLETED"),
        Submission(event_id=1, question_id=q.id, user_id=11, code="p", language="python", verdict="Accepted", execution_time_ms=140, memory_used_kb=1024, status="COMPLETED"),
        Submission(event_id=1, question_id=q.id, user_id=12, code="p", language="cpp", verdict="Accepted", execution_time_ms=20, memory_used_kb=512, status="COMPLETED"),
        Submission(event_id=1, question_id=q.id, user_id=13, code="p", language="cpp", verdict="Wrong Answer", execution_time_ms=25, memory_used_kb=512, status="COMPLETED"),
        Submission(event_id=1, question_id=q.id, user_id=13, code="p", language="cpp", verdict="Accepted", execution_time_ms=22, memory_used_kb=512, status="COMPLETED"),
        Submission(event_id=1, question_id=q.id, user_id=14, code="p", language="java", verdict="Time Limit Exceeded", execution_time_ms=2000, memory_used_kb=2048, status="COMPLETED"),
        Submission(event_id=1, question_id=q.id, user_id=14, code="p", language="java", verdict="Accepted", execution_time_ms=450, memory_used_kb=2048, status="COMPLETED"),
        Submission(event_id=1, question_id=q.id, user_id=15, code="p", language="python", verdict="Wrong Answer", execution_time_ms=100, memory_used_kb=1024, status="COMPLETED"),
        Submission(event_id=1, question_id=q.id, user_id=15, code="p", language="python", verdict="Runtime Error", execution_time_ms=110, memory_used_kb=1024, status="COMPLETED"),
        Submission(event_id=1, question_id=q.id, user_id=15, code="p", language="python", verdict="Accepted", execution_time_ms=90, memory_used_kb=1024, status="COMPLETED"),
    ]
    db_session.add_all(subs)
    db_session.commit()

    intel = difficulty_intelligence.analyze_question_difficulty(q.id, db_session)
    assert intel["has_sufficient_data"] is True
    assert intel["sample_count"] == 10
    assert intel["distinct_students"] == 6
    assert intel["acceptance_rate"] == 60.0
    assert intel["verdict_distribution"]["AC"] == 6
    assert intel["verdict_distribution"]["WA"] == 2
    assert intel["verdict_distribution"]["TLE"] == 1
    assert intel["verdict_distribution"]["RE"] == 1
    assert intel["observed_difficulty_score"] is not None
    assert "python" in intel["language_breakdown"]
    assert "cpp" in intel["language_breakdown"]


# =====================================================================
# PART D & E: SUBMISSION INTELLIGENCE & PERFORMANCE INSIGHTS
# =====================================================================

def test_6_submission_analytics_and_static_heuristics(db_session):
    q = Question(
        title="Two Sum Problem",
        slug=f"two-sum-prob-{uuid.uuid4().hex[:6]}",
        problem_statement="Find indices of two numbers that add up to target.",
        time_limit_seconds=2.0,
        memory_limit_mb=256
    )
    db_session.add(q)
    db_session.commit()

    # ✅ CREATE USER FIRST
    user = User(
        email=f"two-sum-user-{uuid.uuid4().hex[:6]}@test.com",
        full_name="Two Sum Test User",
        role=UserRole.STUDENT.value,
        status=AccountStatus.ACTIVE.value
    )
    db_session.add(user)
    db_session.commit()
    user_id = user.id  # ✅ Use the actual user ID
    
    # Attempt 1: O(N^2) Nested loop WA
    code_att1 = """def two_sum(nums, target):
    for i in range(len(nums)):
        for j in range(i + 1, len(nums)):
            if nums[i] + nums[j] == target:
                return [i, j]
"""
    # Attempt 2: O(N) Hash map AC
    code_att2 = """def two_sum(nums, target):
    seen = {}
    for i, num in enumerate(nums):
        diff = target - num
        if diff in seen:
            return [seen[diff], i]
        seen[num] = i
"""
    sub1 = Submission(
        event_id=1, question_id=q.id, user_id=user_id,
        code=code_att1, language="python", verdict="Wrong Answer",
        execution_time_ms=1800, memory_used_kb=2048, score=50.0,
        test_case_results=[{"passed": True}, {"passed": False}],
        status="COMPLETED"
    )
    sub2 = Submission(
        event_id=1, question_id=q.id, user_id=user_id,
        code=code_att2, language="python", verdict="Accepted",
        execution_time_ms=120, memory_used_kb=1536, score=100.0,
        test_case_results=[{"passed": True}, {"passed": True}],
        status="COMPLETED"
    )
    db_session.add_all([sub1, sub2])
    db_session.commit()

    history = submission_analytics.get_student_submission_history(user_id, q.id, db_session)
    assert history["total_submissions"] == 2
    assert history["has_accepted"] is True
    assert history["best_execution_time_ms"] == 120.0
    assert history["best_memory_kb"] == 1536.0
    assert len(history["history"]) == 2

    # Check Attempt 1 heuristics
    att1 = history["history"][0]
    assert att1["verdict"] == "Wrong Answer"
    assert att1["time_utilization_percent"] == 90.0 # 1800ms / 2000ms
    assert att1["code_heuristics"]["estimated_loop_depth"] == 2

    # Check Attempt 2 heuristics
    att2 = history["history"][1]
    assert att2["verdict"] == "Accepted"
    assert att2["time_utilization_percent"] == 6.0 # 120ms / 2000ms
    assert att2["code_heuristics"]["estimated_loop_depth"] == 1


def test_7_hidden_test_protection_in_analytics_and_status(db_session):
    # Verify student cannot see hidden test details via history endpoint
    q = Question(title="Secret Test Question", slug=f"secret-test-q-{uuid.uuid4().hex[:6]}", problem_statement="...")
    db_session.add(q)
    db_session.commit()

    sub = Submission(
        event_id=1, question_id=q.id, user_id=1,
        code="print(42)", language="python", verdict="Accepted",
        test_case_results=[
            {"test_case_id": 1, "is_hidden": False, "passed": True, "output": "42", "expected": "42"},
            {"test_case_id": 2, "is_hidden": True, "passed": True, "output": "HIDDEN_SECRET", "expected": "HIDDEN_SECRET"}
        ],
        status="COMPLETED"
    )
    db_session.add(sub)
    db_session.commit()

    res = submission_analytics.get_student_submission_history(user_id=1, question_id=q.id, db=db_session)
    # Output only contains aggregate numbers, never inner raw output arrays
    for item in res["history"]:
        assert item["test_cases_passed"] == 2
        assert item["test_cases_total"] == 2
        assert "HIDDEN_SECRET" not in str(item)


# =====================================================================
# PART F: PROBLEM DUPLICATE DETECTION
# =====================================================================

def test_8_duplicate_detector_exact_and_semantic_statements():
    stmt1 = "Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target."
    stmt2 = "Given an array of numbers nums and an integer target, return indices of two numbers that add up to target."
    stmt_diff = "Given a string s, find the length of the longest substring without repeating characters."

    res_dup = duplicate_detector.compare_statements(stmt1, stmt2)
    assert res_dup["similarity_score"] >= 0.70
    assert res_dup["category"] in ["DUPLICATE", "SIMILAR"]

    res_unique = duplicate_detector.compare_statements(stmt1, stmt_diff)
    assert res_unique["similarity_score"] < 0.45
    assert res_unique["category"] == "UNIQUE"


# =====================================================================
# PART G: CONTEST & PROBLEM SET QUALITY
# =====================================================================

def test_9_contest_quality_validator(db_session):
    now = datetime.datetime.now(datetime.timezone.utc)
    assessment = Assessment(
        title="Mid-Term Coding Assessment",
        description="Assessment problem set audit",
        duration_minutes=60,
        start_time=now,
        end_time=now + datetime.timedelta(hours=2),
        status="DRAFT"
    )
    db_session.add(assessment)
    db_session.commit()

    # Question 1: Good
    q1 = Question(title="Q1 Array Sum", slug=f"q1-arr-sum-{uuid.uuid4().hex[:6]}", problem_statement="Sum elements in array", difficulty_score=2, topic="Arrays")
    # Question 2: Good
    q2 = Question(title="Q2 String Palindrome", slug=f"q2-str-pal-{uuid.uuid4().hex[:6]}", problem_statement="Check if palindrome string", difficulty_score=4, topic="Strings")
    # Question 3: Weak (has 0 hidden tests)
    q3 = Question(title="Q3 Weak Tests", slug=f"q3-weak-{uuid.uuid4().hex[:6]}", problem_statement="Search in matrix", difficulty_score=6, topic="Matrices")
    
    db_session.add_all([q1, q2, q3])
    db_session.commit()

    # Add test cases to Q1 & Q2
    for i in range(4):
        db_session.add(TestCase(question_id=q1.id, input_data=str(i), expected_output=str(i), is_hidden=(i >= 1)))
        db_session.add(TestCase(question_id=q2.id, input_data=str(i), expected_output=str(i), is_hidden=(i >= 1)))
    # Q3 only has 1 visible test case
    db_session.add(TestCase(question_id=q3.id, input_data="1", expected_output="1", is_hidden=False))
    db_session.commit()

    # Link to assessment
    db_session.add(AssessmentQuestion(assessment_id=assessment.id, question_id=q1.id, order_index=1, marks=100.0))
    db_session.add(AssessmentQuestion(assessment_id=assessment.id, question_id=q2.id, order_index=2, marks=100.0))
    db_session.add(AssessmentQuestion(assessment_id=assessment.id, question_id=q3.id, order_index=3, marks=100.0))
    db_session.commit()

    report = contest_quality_validator.validate_assessment_problem_set(assessment.id, db_session)
    assert report["problem_count"] == 3
    assert len(report["weak_test_problems"]) == 1
    assert report["weak_test_problems"][0]["id"] == q3.id
    assert any("has only 0 hidden test" in err for err in report["errors"])
    assert report["is_ready_to_publish"] is False


# =====================================================================
# PART J & M: API ENDPOINTS & RBAC SECURITY
# =====================================================================

def test_10_api_quality_and_intelligence_endpoints(db_session):
    # Setup Admin user
    admin = User(
        email=f"setter.admin_{uuid.uuid4().hex[:6]}@ipu.ac.in",
        full_name="Problem Setter Admin",
        role=UserRole.ADMIN.value,
        status=AccountStatus.ACTIVE.value,
        is_active=True
    )
    db_session.add(admin)
    db_session.commit()

    from app.core.security import get_current_user
    app.dependency_overrides[get_current_user] = lambda: admin

    q = Question(
        title="API Test Question",
        slug=f"api-test-q-{uuid.uuid4().hex[:6]}",
        problem_statement="Given two integers A and B, print their product.",
        input_format="Two integers A and B",
        output_format="A single integer",
        constraints="1 <= A, B <= 1000",
        examples=[{"input": "3 4", "output": "12", "explanation": "3*4=12"}],
        difficulty_score=2,
        expected_time_complexity="O(1)",
        expected_space_complexity="O(1)",
        reference_solutions={"python": "import sys\na,b = map(int, sys.stdin.read().split())\nprint(a*b)"}
    )
    db_session.add(q)
    db_session.commit()

    # Add test cases
    db_session.add(TestCase(question_id=q.id, input_data="3 4", expected_output="12", is_hidden=False, category="NORMAL"))
    db_session.add(TestCase(question_id=q.id, input_data="5 6", expected_output="30", is_hidden=False, category="NORMAL"))
    db_session.add(TestCase(question_id=q.id, input_data="1 1", expected_output="1", is_hidden=True, category="MINIMUM"))
    db_session.add(TestCase(question_id=q.id, input_data="1000 1000", expected_output="1000000", is_hidden=True, category="MAXIMUM"))
    db_session.commit()

    try:
        # 1. Test Quality Report Endpoint
        res_qr = client.get(f"/api/v1/questions/{q.id}/quality-report")
        assert res_qr.status_code == 200
        qr_data = res_qr.json()
        assert qr_data["quality_score"] >= 65.0
        assert "test_suite_report" in qr_data

        # 2. Test Difficulty Intelligence Endpoint
        res_di = client.get(f"/api/v1/questions/{q.id}/difficulty-intelligence")
        assert res_di.status_code == 200
        di_data = res_di.json()
        assert di_data["author_difficulty_label"] == "Easy"
        assert di_data["has_sufficient_data"] is False # 0 submissions yet

        # 3. Test TestCase Analysis Endpoint
        res_tc = client.get(f"/api/v1/questions/{q.id}/test-case-analysis")
        assert res_tc.status_code == 200
        tc_data = res_tc.json()
        assert tc_data["visible_count"] == 2
        assert tc_data["hidden_count"] == 2
        assert "MINIMUM" in tc_data["categories_present"]
        assert "MAXIMUM" in tc_data["categories_present"]
    finally:
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]




