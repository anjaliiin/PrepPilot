"""
study_planner.py - Personalized Study Planner with Dynamic Rescheduling for PrepPilot
Generates a structured revision timetable prioritizing weak and high-importance topics,
and shifts missed topics non-destructively to future slots without rebuilding the entire schedule.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import database
import ai_service
import performance_analyzer


def generate_study_plan(student_id: int, subject_id: Optional[int] = None,
                        db_path: str = database.DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """
    Constructs a personalized day-by-day study schedule based on:
    - Days remaining to exam
    - Daily study hours
    - Weak topics (prioritized early)
    - Topic importance (High > Medium > Low)
    """
    student = database.get_student_by_id(student_id, db_path=db_path)
    if not student:
        raise ValueError("Student not found.")

    exam_date_str = student["exam_date"]
    try:
        exam_dt = datetime.strptime(exam_date_str, "%Y-%m-%d").date()
    except Exception:
        raise ValueError(f"Invalid exam date format '{exam_date_str}'. Expected YYYY-MM-DD.")

    today = datetime.now().date()
    days_remaining = (exam_dt - today).days
    if days_remaining <= 0:
        days_remaining = 1

    # Fetch topics
    conn = database.get_db_connection(db_path)
    if subject_id:
        topic_rows = conn.execute("SELECT * FROM topics WHERE subject_id = ?", (subject_id,)).fetchall()
    else:
        topic_rows = conn.execute("""
            SELECT t.* FROM topics t
            JOIN subjects s ON t.subject_id = s.id
            WHERE s.student_id = ?
        """, (student_id,)).fetchall()
    conn.close()

    topics = [dict(r) for r in topic_rows]
    if not topics:
        raise ValueError("No topics available to schedule. Please upload and analyze a syllabus first.")

    perf_summary = performance_analyzer.get_student_performance_summary(student_id, subject_id=subject_id, db_path=db_path)
    weak_ids = {w["topic_id"] for w in perf_summary["weak_topics"]}

    # Sort topics: Weak first, then High importance, then others
    importance_weight = {"High": 3, "Medium": 2, "Low": 1}
    sorted_topics = sorted(
        topics,
        key=lambda t: (
            1 if t["id"] in weak_ids else 2,
            -importance_weight.get(t.get("importance", "Medium"), 2),
            t.get("unit_number", 1)
        )
    )

    daily_hours = float(student.get("daily_study_hours", 3.0))
    slots_per_day = max(1, int(daily_hours / 1.5))  # ~1.5 hours per slot

    time_slots = [
        "Morning (09:00 - 10:30)",
        "Afternoon (14:00 - 15:30)",
        "Evening (17:00 - 18:30)",
        "Night (20:30 - 22:00)"
    ]

    # Generate slots
    generated_slots = []
    current_day_offset = 0
    slot_idx_in_day = 0

    for topic in sorted_topics:
        slot_date = (today + timedelta(days=current_day_offset)).strftime("%Y-%m-%d")
        slot_name = time_slots[slot_idx_in_day % len(time_slots)]

        is_weak = topic["id"] in weak_ids
        notes = "Focus on core concept remediation & practice" if is_weak else f"{topic.get('importance', 'Medium')} priority syllabus topic"

        generated_slots.append({
            "topic_id": topic["id"],
            "plan_date": slot_date,
            "time_slot": slot_name,
            "status": "pending",
            "notes": notes
        })

        slot_idx_in_day += 1
        if slot_idx_in_day >= slots_per_day:
            slot_idx_in_day = 0
            current_day_offset = min(days_remaining - 1, current_day_offset + 1)

    # Persist slots into database
    database.save_study_plan_slots(student_id, generated_slots, db_path=db_path)
    return database.get_study_plan_by_student(student_id, db_path=db_path)


def mark_plan_completed(plan_id: int, db_path: str = database.DEFAULT_DB_PATH) -> None:
    """Marks a scheduled slot as completed."""
    database.update_plan_status(plan_id, "completed", db_path=db_path)


def reschedule_missed_topic(plan_id: int, db_path: str = database.DEFAULT_DB_PATH) -> Optional[str]:
    """
    Moves a missed study slot to the next available date/slot non-destructively,
    leaving completed and future planned slots intact.
    """
    return database.reschedule_missed_slot(plan_id, db_path=db_path)
