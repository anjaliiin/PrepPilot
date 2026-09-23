"""
agent.py - Autonomous AI Agent Brain for PrepPilot
Orchestrates the continuous adaptive learning loop:
Reads profile -> Evaluates syllabus -> Analyzes performance -> Examines mistake memory ->
Assesses remaining exam days -> Selects and executes the Next Best Action.
"""

from datetime import datetime
from typing import Dict, Any, Optional
import database
import performance_analyzer
import mistake_memory
import ai_service


def get_agent_decision(student_id: int, subject_id: Optional[int] = None,
                       db_path: str = database.DEFAULT_DB_PATH) -> Dict[str, Any]:
    """
    Evaluates the student's complete preparation state from SQLite and selects
    the optimal Next Best Action for the dashboard.
    """
    student = database.get_student_by_id(student_id, db_path=db_path)
    if not student:
        return {
            "action_code": "SETUP_PROFILE",
            "action_title": "Complete Profile Setup",
            "action_desc": "Please set your exam date and profile details.",
            "target_page": "Settings"
        }

    # 1. Check days remaining
    try:
        exam_dt = datetime.strptime(student["exam_date"], "%Y-%m-%d").date()
        days_remaining = (exam_dt - datetime.now().date()).days
    except Exception:
        days_remaining = 30

    # 2. Get syllabus topics
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
        return {
            "action_code": "UPLOAD_SYLLABUS",
            "action_title": "Upload Your Syllabus",
            "action_desc": "Upload your exam syllabus to unlock personalized AI preparation.",
            "target_page": "Syllabus"
        }

    # 3. Analyze performance and mistake patterns
    perf_summary = performance_analyzer.get_student_performance_summary(
        student_id, subject_id=subject_id, db_path=db_path
    )
    mistake_analytics = mistake_memory.get_mistake_analytics(student_id, db_path=db_path)

    # 4. If no attempts recorded at all, recommend Diagnostic Test
    if perf_summary["total_attempts"] == 0:
        first_topic = topics[0]
        return {
            "action_code": "DIAGNOSTIC_TEST",
            "action_title": "Take Diagnostic Test",
            "target_topic_name": first_topic["topic_name"],
            "target_topic_id": first_topic["id"],
            "weak_topic_highlight": "Baseline Assessment Pending",
            "repeated_mistake_highlight": "None recorded yet",
            "recommended_action_title": "Start 10-Question Diagnostic Assessment",
            "action_desc": "Evaluate your baseline strengths and pinpoint weak topics across your uploaded syllabus.",
            "reasoning": "A diagnostic test maps your initial knowledge distribution so the AI agent can tailor difficulty.",
            "button_label": "Start Diagnostic Test",
            "target_page": "Diagnostic Test"
        }

    # 5. Check if repeated mistakes exist
    repeated_mistakes = mistake_analytics.get("repeated_topics", [])
    if repeated_mistakes and repeated_mistakes[0]["mistake_count"] >= 3:
        target_tname = repeated_mistakes[0]["topic_name"]
        target_t = next((t for t in topics if t["topic_name"] == target_tname), topics[0])
        return {
            "action_code": "REVIEW_MISTAKES",
            "action_title": f"Review Mistakes in {target_tname}",
            "target_topic_name": target_tname,
            "target_topic_id": target_t["id"],
            "weak_topic_highlight": target_tname,
            "repeated_mistake_highlight": f"{repeated_mistakes[0]['mistake_count']} recent errors",
            "recommended_action_title": f"Review Mistakes in {target_tname} → Reinforce Foundation",
            "action_desc": "You have repeated errors in this topic. Review mistake reasons and targeted rules.",
            "reasoning": "Repeated errors trigger the mistake-memory circuit to halt error compounding.",
            "button_label": "Open Mistake Memory",
            "target_page": "Mistake Memory"
        }

    # 6. Check weak topics (< 50% accuracy)
    weak_topics = perf_summary.get("weak_topics", [])
    if weak_topics:
        # Prioritize High importance weak topic
        weak_sorted = sorted(
            weak_topics,
            key=lambda x: (0 if x.get("importance") == "High" else 1, x["accuracy"])
        )
        target_weak = weak_sorted[0]
        return {
            "action_code": "GENERATE_EASY_QUESTIONS",
            "action_title": f"Remediate {target_weak['topic_name']}",
            "target_topic_name": target_weak["topic_name"],
            "target_topic_id": target_weak["topic_id"],
            "weak_topic_highlight": target_weak["topic_name"],
            "repeated_mistake_highlight": f"{target_weak['accuracy']}% accuracy",
            "recommended_action_title": f"Revise {target_weak['topic_name']} → Take 5 Easy Questions",
            "action_desc": "Build back conceptual confidence with guided foundational questions.",
            "reasoning": f"Accuracy is at {target_weak['accuracy']}%. Adaptive difficulty drops to Easy to rebuild mastery.",
            "button_label": "Practice Foundational Questions",
            "target_page": "Practice Test"
        }

    # 7. Check if exam is imminent (<= 7 days)
    if days_remaining <= 7:
        return {
            "action_code": "MOCK_TEST",
            "action_title": "Timed Mock Exam Simulation",
            "target_topic_name": "Full Syllabus",
            "target_topic_id": topics[0]["id"],
            "weak_topic_highlight": "Exam Approaching",
            "repeated_mistake_highlight": f"{days_remaining} Days Remaining",
            "recommended_action_title": "Take Full-Length Timed Mock Test",
            "action_desc": "Sharpen exam stamina and test pacing with a timed mock exam covering all units.",
            "reasoning": "When exam date is within 7 days, full-length simulations provide highest test-day readiness.",
            "button_label": "Launch Mock Exam",
            "target_page": "Mock Test"
        }

    # 8. Check moderate topics (50% - 75%)
    moderate_topics = perf_summary.get("moderate_topics", [])
    if moderate_topics:
        target_mod = moderate_topics[0]
        return {
            "action_code": "GENERATE_MEDIUM_QUESTIONS",
            "action_title": f"Elevate {target_mod['topic_name']}",
            "target_topic_name": target_mod["topic_name"],
            "target_topic_id": target_mod["topic_id"],
            "weak_topic_highlight": target_mod["topic_name"],
            "repeated_mistake_highlight": f"{target_mod['accuracy']}% accuracy",
            "recommended_action_title": f"Solve Medium Challenge on {target_mod['topic_name']}",
            "action_desc": "Step up difficulty to Medium to cement exam-level problem solving.",
            "reasoning": "Accuracy is between 50% and 75%; student is ready for standard exam difficulty.",
            "button_label": "Practice Medium Questions",
            "target_page": "Practice Test"
        }

    # 9. Strong topics (>75%) -> Hard Questions or AI Viva
    strong_topics = perf_summary.get("strong_topics", [])
    if strong_topics:
        target_strong = strong_topics[0]
        return {
            "action_code": "VIVA",
            "action_title": f"Deep Oral Viva: {target_strong['topic_name']}",
            "target_topic_name": target_strong["topic_name"],
            "target_topic_id": target_strong["topic_id"],
            "weak_topic_highlight": "None (Strong Mastery)",
            "repeated_mistake_highlight": f"{target_strong['accuracy']}% accuracy",
            "recommended_action_title": f"Challenge Yourself: Viva on {target_strong['topic_name']}",
            "action_desc": "Defend concepts in an interactive oral exam with dynamic follow-up scrutiny.",
            "reasoning": "Topic accuracy exceeds 75%. Oral viva probing tests deep transfer understanding.",
            "button_label": "Start AI Viva",
            "target_page": "AI Viva"
        }

    # Default fallback to first topic revision
    first_t = topics[0]
    return {
        "action_code": "REVISION",
        "action_title": f"Revise {first_t['topic_name']}",
        "target_topic_name": first_t["topic_name"],
        "target_topic_id": first_t["id"],
        "weak_topic_highlight": "General Review",
        "repeated_mistake_highlight": "None",
        "recommended_action_title": f"Review Flashcards & Notes for {first_t['topic_name']}",
        "action_desc": "Review key definitions, formulas, and flashcards.",
        "reasoning": "Solidifying syllabus fundamentals keeps retention high.",
        "button_label": "Open Revision Notes",
        "target_page": "Topic Explanation"
    }
