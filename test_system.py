"""
test_system.py - Comprehensive Verification & Validation Suite for PrepPilot
Tests syntax, database CRUD in an isolated temporary test database,
adaptive logic, non-destructive rescheduling, document extraction, and cleanup.
"""

import os
import sys
import tempfile
import py_compile
from datetime import datetime, timedelta

# Ensure PrepPilot directory is on sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)


def test_syntax_and_compilation():
    print("1. Checking Python syntax on all source files...")
    py_files = [
        "database.py",
        "pdf_reader.py",
        "syllabus_analyzer.py",
        "question_generator.py",
        "performance_analyzer.py",
        "study_planner.py",
        "viva.py",
        "mistake_memory.py",
        "agent.py",
        "ai_service.py",
        "utils.py",
        "app.py"
    ]
    for pf in py_files:
        path = os.path.join(BASE_DIR, pf)
        py_compile.compile(path, doraise=True)
    print("   [PASS] All 12 source files compile without syntax errors.")


def test_isolated_database_crud():
    print("2. Testing isolated database initialization and CRUD operations...")
    import database
    import performance_analyzer
    import study_planner
    import mistake_memory
    import agent

    # Use a temporary isolated database path
    temp_dir = tempfile.mkdtemp()
    test_db_path = os.path.join(temp_dir, "test_exam.db")

    try:
        # Initialize schema
        database.init_db(db_path=test_db_path)
        assert os.path.exists(test_db_path), "Test DB file was not created."

        # Verify tables start completely empty
        students = database.get_all_students(db_path=test_db_path)
        assert len(students) == 0, f"Expected 0 students in empty DB, found {len(students)}"

        # Create student
        exam_date = (datetime.now() + timedelta(days=20)).strftime("%Y-%m-%d")
        sid = database.create_student("Test Student", "CS", "4", exam_date, 3.5, db_path=test_db_path)
        assert sid > 0, "Failed to create student."

        # Create subject
        sub_id = database.create_subject(sid, "Operating Systems", "CS401", db_path=test_db_path)
        assert sub_id > 0, "Failed to create subject."

        # Create topics
        t1_id = database.add_topic(sub_id, 1, "Processes", "CPU Scheduling", "Medium", "High", db_path=test_db_path)
        t2_id = database.add_topic(sub_id, 1, "Processes", "Deadlocks", "Hard", "High", db_path=test_db_path)
        assert t1_id > 0 and t2_id > 0, "Failed to insert topics."

        # Record question & attempt
        qid = database.add_question(
            t1_id, "What is Round Robin?", "MCQ", ["A", "B", "C", "D"], "A", "Explanation", "Medium", db_path=test_db_path
        )
        aid = database.record_attempt(
            sid, qid, "A", 1, 1.0, "Correct", "practice", db_path=test_db_path
        )
        assert aid > 0, "Failed to record attempt."

        # Verify performance updated
        perf = database.get_performance_by_student(sid, db_path=test_db_path)
        assert len(perf) == 1, "Expected 1 performance record."
        assert perf[0]["accuracy"] == 100.0, f"Expected 100.0 accuracy, got {perf[0]['accuracy']}"

        # Record mistake on Deadlocks
        mid = database.log_mistake(
            sid, sub_id, t2_id, "What causes deadlock?", "Memory leak", "Circular wait", "Concept misunderstanding", db_path=test_db_path
        )
        assert mid > 0, "Failed to log mistake."

        mistakes = database.get_mistakes_by_student(sid, db_path=test_db_path)
        assert len(mistakes) == 1, "Expected 1 mistake record."

        # Test Study Planner & Non-Destructive Rescheduling
        slots = [
            {"topic_id": t1_id, "plan_date": exam_date, "time_slot": "Morning", "status": "pending", "notes": "Study"}
        ]
        database.save_study_plan_slots(sid, slots, db_path=test_db_path)
        plan = database.get_study_plan_by_student(sid, db_path=test_db_path)
        assert len(plan) == 1, "Expected 1 study plan slot."

        # Mark missed -> verify rescheduling
        rescheduled_date = database.reschedule_missed_slot(plan[0]["id"], db_path=test_db_path)
        assert rescheduled_date is not None, "Rescheduled date was None."

        updated_plan = database.get_study_plan_by_student(sid, db_path=test_db_path)
        assert len(updated_plan) == 2, f"Expected 2 slots after reschedule, found {len(updated_plan)}"
        assert updated_plan[0]["status"] == "missed", "Original slot should be marked 'missed'."
        assert updated_plan[1]["status"] == "pending", "Rescheduled slot should be 'pending'."

        # Test Agent decision on this state
        decision = agent.get_agent_decision(sid, subject_id=sub_id, db_path=test_db_path)
        assert "action_code" in decision, "Agent decision missing action_code."
        print(f"   [Agent Decision Verified]: {decision.get('action_code')} - {decision.get('recommended_action_title')}")

        print("   [PASS] Isolated database CRUD, performance tracking, mistake logging, and rescheduling verified.")
    finally:
        # Guaranteed cleanup of isolated test database
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
        if os.path.exists(temp_dir):
            try:
                os.rmdir(temp_dir)
            except Exception:
                pass
        print("   [CLEANUP] Temporary test database deleted completely.")


def test_document_extraction():
    print("3. Testing document extraction...")
    import pdf_reader
    import io

    # Test TXT extraction
    sample_text = "Unit 1: Introduction to AI\nTopic 1.1: Search Algorithms\nUnit 2: Knowledge Representation"
    bio = io.BytesIO(sample_text.encode("utf-8"))
    extracted = pdf_reader.extract_text_from_file(bio, "syllabus.txt")
    assert "Search Algorithms" in extracted, "Failed to extract plain text."
    print("   [PASS] Text document extraction verified.")


def main():
    print("=" * 60)
    print("RUNNING PREPPILOT SYSTEM VERIFICATION SUITE")
    print("=" * 60)

    test_syntax_and_compilation()
    test_isolated_database_crud()
    test_document_extraction()

    print("=" * 60)
    print("ALL VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    main()
