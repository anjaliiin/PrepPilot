"""
performance_analyzer.py - Performance Tracking & Readiness Analytics for PrepPilot
Categorizes topics into Strong, Moderate, Weak, and Not Studied, and calculates
Preparation Readiness score and Plotly visualization datasets.
"""

from typing import Dict, Any, List, Optional
import database


def get_student_performance_summary(student_id: int, subject_id: Optional[int] = None,
                                    db_path: str = database.DEFAULT_DB_PATH) -> Dict[str, Any]:
    """
    Computes a comprehensive performance summary for the student:
    - Strong topics (>75% accuracy)
    - Moderate topics (50% - 75% accuracy)
    - Weak topics (<50% accuracy)
    - Not studied topics (0 attempts)
    - Overall accuracy and Preparation Readiness Score
    """
    conn = database.get_db_connection(db_path)

    # 1. Fetch all syllabus topics for subject(s)
    if subject_id:
        topic_rows = conn.execute("SELECT * FROM topics WHERE subject_id = ?", (subject_id,)).fetchall()
    else:
        topic_rows = conn.execute("""
            SELECT t.* FROM topics t
            JOIN subjects s ON t.subject_id = s.id
            WHERE s.student_id = ?
        """, (student_id,)).fetchall()

    all_topics = [dict(r) for r in topic_rows]

    # 2. Fetch recorded performance records
    perf_records = database.get_performance_by_student(student_id, db_path=db_path)
    perf_map = {p["topic_id"]: p for p in perf_records}

    strong_topics = []
    moderate_topics = []
    weak_topics = []
    not_studied_topics = []

    total_attempts_all = 0
    correct_attempts_all = 0

    for t in all_topics:
        tid = t["id"]
        if tid in perf_map:
            p = perf_map[tid]
            acc = p["accuracy"]
            total_attempts_all += p["total_attempts"]
            correct_attempts_all += p["correct_attempts"]

            t_summary = {
                "topic_id": tid,
                "topic_name": t["topic_name"],
                "unit_name": t.get("unit_name", ""),
                "unit_number": t.get("unit_number", 1),
                "importance": t.get("importance", "Medium"),
                "accuracy": round(acc, 1),
                "total_attempts": p["total_attempts"],
                "correct_attempts": p["correct_attempts"],
                "last_attempted": p.get("last_attempted", "")
            }

            if acc > 75.0:
                strong_topics.append(t_summary)
            elif acc >= 50.0:
                moderate_topics.append(t_summary)
            else:
                weak_topics.append(t_summary)
        else:
            not_studied_topics.append({
                "topic_id": tid,
                "topic_name": t["topic_name"],
                "unit_name": t.get("unit_name", ""),
                "unit_number": t.get("unit_number", 1),
                "importance": t.get("importance", "Medium"),
                "accuracy": 0.0,
                "total_attempts": 0,
                "correct_attempts": 0,
                "last_attempted": None
            })

    overall_accuracy = (
        round((correct_attempts_all / total_attempts_all) * 100.0, 1)
        if total_attempts_all > 0 else 0.0
    )

    total_topics_count = len(all_topics)
    attempted_topics_count = len(strong_topics) + len(moderate_topics) + len(weak_topics)
    coverage_pct = (
        round((attempted_topics_count / total_topics_count) * 100.0, 1)
        if total_topics_count > 0 else 0.0
    )

    # Preparation Readiness calculation:
    # 50% weighted on syllabus coverage + 50% weighted on accuracy of covered topics
    if total_topics_count == 0 or total_attempts_all == 0:
        readiness_score = 0.0
    else:
        readiness_score = round((0.5 * coverage_pct) + (0.5 * overall_accuracy), 1)

    conn.close()

    return {
        "total_topics": total_topics_count,
        "attempted_topics": attempted_topics_count,
        "coverage_percentage": coverage_pct,
        "overall_accuracy": overall_accuracy,
        "preparation_readiness": min(100.0, max(0.0, readiness_score)),
        "strong_topics": strong_topics,
        "moderate_topics": moderate_topics,
        "weak_topics": weak_topics,
        "not_studied_topics": not_studied_topics,
        "total_attempts": total_attempts_all,
        "correct_attempts": correct_attempts_all
    }


def get_performance_trends(student_id: int, db_path: str = database.DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Returns chronological attempt records for plotting progress trend curves."""
    conn = database.get_db_connection(db_path)
    rows = conn.execute("""
        SELECT a.attempted_at, a.is_correct, a.score, a.attempt_type, t.topic_name
        FROM attempts a
        JOIN questions q ON a.question_id = q.id
        JOIN topics t ON q.topic_id = t.id
        WHERE a.student_id = ?
        ORDER BY a.attempted_at ASC
    """, (student_id,)).fetchall()
    trends = [dict(r) for r in rows]
    conn.close()
    return trends
