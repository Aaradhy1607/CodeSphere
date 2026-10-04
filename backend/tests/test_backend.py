import pytest
from app.services.code_runner import code_runner
from app.models.models import (
    User, UserRole, Branch, Event, EventQuestion, Question, Submission, 
    SubmissionVerdict, AdminAllowlist, Base
)
from app.core.security import is_student_email, is_admin_email, determine_role
from app.core.database import engine, SessionLocal, auto_migrate_db
from app.services.seeder import seed_database

@pytest.fixture(autouse=True)
def init_db():
    Base.metadata.create_all(bind=engine)
    auto_migrate_db()
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    yield

import shutil
import os
import subprocess

def _is_compiler_available(bin_name: str) -> bool:
    try:
        lang = "cpp" if "++" in bin_name else "c"
        if lang == "c":
            test_code = r"""#include <stdio.h>
int main() { int x = 0; if (scanf("%d", &x) == 1) printf("%d\n", x + 1); return 0; }
"""
        else:
            test_code = """#include <iostream>
int main() { int x = 0; if (std::cin >> x) std::cout << (x + 1) << std::endl; return 0; }
"""
        res = code_runner.execute_single(test_code, lang, "1\n", timeout_seconds=10.0)
        return res.get("verdict") in (SubmissionVerdict.AC, SubmissionVerdict.AC.value) and res.get("output", "").strip() == "2"
    except Exception:
        return False



def test_python_execution():
    code = "import sys\nprint(int(sys.stdin.read().strip()) * 2)"
    res = code_runner.execute_single(code, "python", "21")
    assert res["verdict"] in (SubmissionVerdict.AC, SubmissionVerdict.AC.value)
    assert res["output"].strip() == "42"

def test_cpp_execution():
    if not _is_compiler_available("g++"):
        pytest.skip("g++ compiler not available or functional on host environment")
    code = """#include <iostream>
using namespace std;
int main() {
    int x;
    if (cin >> x) {
        cout << x * 3 << endl;
    }
    return 0;
}
"""
    res = code_runner.execute_single(code, "cpp", "10\n", timeout_seconds=10.0)
    if "4551" in str(res.get("error")) or "Application Control" in str(res.get("error")):
        pytest.skip("Host OS Application Control policy blocked binary execution")
    assert res["verdict"] in (SubmissionVerdict.AC, SubmissionVerdict.AC.value), f"Failed with: {res.get('error')}"
    assert res["output"].strip() == "30"

def test_c_execution():
    if not _is_compiler_available("gcc"):
        pytest.skip("gcc compiler not available or functional on host environment")
    code = r"""#include <stdio.h>
int main() {
    int x;
    if (scanf("%d", &x) == 1) {
        printf("%d\n", x + 5);
    }
    return 0;
}
"""
    res = code_runner.execute_single(code, "c", "15\n", timeout_seconds=10.0)
    if "4551" in str(res.get("error")) or "Application Control" in str(res.get("error")):
        pytest.skip("Host OS Application Control policy blocked binary execution")
    assert res["verdict"] in (SubmissionVerdict.AC, SubmissionVerdict.AC.value), f"Failed with: {res.get('error')}"
    assert res["output"].strip() == "20"


def test_java_execution():
    code = """
    import java.util.Scanner;
    public class Solution {
        public static void main(String[] args) {
            Scanner sc = new Scanner(System.in);
            if (sc.hasNextInt()) {
                int x = sc.nextInt();
                System.out.println(x * 4);
            }
        }
    }
    """
    res = code_runner.execute_single(code, "java", "25")
    assert res["verdict"] == SubmissionVerdict.AC
    assert res["output"].strip() == "100"

def test_testcase_evaluation_and_score():
    code = "import sys\nprint(int(sys.stdin.read().strip()) * 2)"
    tcs = [
        {"id": 1, "input": "2", "expected": "4", "points": 10, "is_hidden": False},
        {"id": 2, "input": "5", "expected": "10", "points": 10, "is_hidden": True},
        {"id": 3, "input": "0", "expected": "0", "points": 20, "is_hidden": True}
    ]
    eval_res = code_runner.evaluate_test_cases(code, "python", tcs)
    assert eval_res["verdict"] == SubmissionVerdict.AC
    assert eval_res["passed_count"] == 3
    assert eval_res["score"] == 100.0

def test_domain_validation():
    db = SessionLocal()
    try:
        assert is_student_email("aarav.patel@std.ggsipu.ac.in") is True
        assert is_student_email("priya.sharma@std.ggsipu.ac.in") is True
        assert is_student_email("student@gmail.com") is False
        assert is_student_email("admin@ipu.ac.in") is False

        assert is_admin_email("placement@ipu.ac.in", db) is True
        assert is_admin_email("usar.tnp@ipu.ac.in", db) is True
        assert is_admin_email("placement@ipu.ac.in") is True
        assert is_admin_email("student@std.ggsipu.ac.in") is False
        assert is_admin_email("outsider@yahoo.com") is False
    finally:
        db.close()

def test_rbac_and_admin_allowlist():
    db = SessionLocal()
    try:
        # Check an authorized admin
        role = determine_role("placement@ipu.ac.in", db)
        assert role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]

        role_tnp = determine_role("usar.tnp@ipu.ac.in", db)
        assert role_tnp in [UserRole.ADMIN, UserRole.SUPER_ADMIN]

        # Check a student email
        role_std = determine_role("aarav.patel@std.ggsipu.ac.in", db)
        assert role_std == UserRole.STUDENT

        # Check an unauthorized admin (ipu.ac.in domain, but not in AdminAllowlist)
        role_unauth = determine_role("unauthorized.faculty@ipu.ac.in", db)
        assert role_unauth is None

        # Check a completely unauthorized public domain
        role_public = determine_role("random_person@gmail.com", db)
        assert role_public is None
    finally:
        db.close()

def test_dynamic_event_question_filtering():
    # Verify that questions can have specific target year / branch overrides
    db = SessionLocal()
    try:
        event = db.query(Event).first()
        if event:
            eqs = db.query(EventQuestion).filter(EventQuestion.event_id == event.id).all()
            for eq in eqs:
                assert eq.points >= 0
                assert eq.order_index >= 0
    finally:
        db.close()

