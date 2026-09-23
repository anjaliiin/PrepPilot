"""
mistake_memory.py - Mistake Logging, Taxonomy, and Targeted Remediation for PrepPilot
Stores student errors, classifies them into pedagogical mistake categories,
and generates targeted remediation for repeated weak spots.
"""

from typing import Dict, Any, List, Optional
from collections import Counter
import database
import ai_service

MISTAKE_TYPES = [
    "Concept misunderstanding",
    "Forgot definition",
    "Calculation error",
    "Confused concepts",
    "Careless mistake",
    "Incomplete answer"
]


def log_student_mistake(student_id: int, subject_id: int, topic_id: int,
                        question_text: str, student_answer: str, correct_answer: str,
                        mistake_type: Optional[str] = None,
                        db_path: str = database.DEFAULT_DB_PATH) -> int:
    """
    Logs an incorrect answer to the mistake memory table.
    If mistake_type is not provided, AI categorizes it automatically.
    """
    if not mistake_type or mistake_type not in MISTAKE_TYPES:
        try:
            mistake_type = ai_service.identify_mistake(
                question_text=question_text,
                student_answer=student_answer,
                correct_answer=correct_answer
            )
        except Exception:
            mistake_type = "Concept misunderstanding"

    mid = database.log_mistake(
        student_id=student_id,
        subject_id=subject_id,
        topic_id=topic_id,
        question_text=question_text,
        student_answer=student_answer,
        correct_answer=correct_answer,
        mistake_type=mistake_type,
        db_path=db_path
    )
    return mid


def get_mistake_analytics(student_id: int, db_path: str = database.DEFAULT_DB_PATH) -> Dict[str, Any]:
    """
    Analyzes mistake patterns:
    - Counts and percentages per mistake category
    - Topics with the highest repeat mistakes
    - Recent mistakes list
    """
    mistakes = database.get_mistakes_by_student(student_id, db_path=db_path)
    total_mistakes = len(mistakes)

    type_counts = Counter([m["mistake_type"] for m in mistakes])
    topic_counts = Counter([m["topic_name"] for m in mistakes])

    type_breakdown = []
    for mt in MISTAKE_TYPES:
        cnt = type_counts.get(mt, 0)
        pct = round((cnt / total_mistakes) * 100.0, 1) if total_mistakes > 0 else 0.0
        type_breakdown.append({
            "type": mt,
            "count": cnt,
            "percentage": pct
        })

    repeated_topics = [
        {"topic_name": t_name, "mistake_count": cnt}
        for t_name, cnt in topic_counts.most_common(5)
    ]

    return {
        "total_mistakes": total_mistakes,
        "type_breakdown": type_breakdown,
        "repeated_topics": repeated_topics,
        "recent_mistakes": mistakes[:15]
    }


def generate_targeted_remediation(mistake_id: int, db_path: str = database.DEFAULT_DB_PATH) -> Dict[str, Any]:
    """
    Generates targeted pedagogical guidance for a specific mistake, explaining
    the underlying trap and offering a clarifying micro-concept explanation.
    """
    conn = database.get_db_connection(db_path)
    row = conn.execute("""
        SELECT m.*, t.topic_name, t.unit_name, s.name as subject_name
        FROM mistakes m
        JOIN topics t ON m.topic_id = t.id
        JOIN subjects s ON m.subject_id = s.id
        WHERE m.id = ?
    """, (mistake_id,)).fetchone()
    conn.close()

    if not row:
        raise ValueError(f"Mistake record {mistake_id} not found.")

    m = dict(row)
    system_prompt = (
        "You are an empathetic master tutor specializing in error remediation. "
        "Analyze the student's mistake and provide a targeted correction module. "
        "Return valid JSON:\n"
        "{\n"
        '  "core_misconception": "Explanation of what went wrong in reasoning",\n'
        '  "correct_rule": "The crystal clear rule/principle to remember",\n'
        '  "memory_hook": "A memorable mnemonic or rule of thumb",\n'
        '  "practice_micro_question": "A quick similar question to verify understanding",\n'
        '  "micro_answer": "Expected answer for the micro question"\n'
        "}"
    )

    prompt = (
        f"Subject: {m['subject_name']}\n"
        f"Topic: {m['topic_name']}\n"
        f"Mistake Category: {m['mistake_type']}\n"
        f"Question: {m['question_text']}\n"
        f"Student Answer: {m['student_answer']}\n"
        f"Correct Answer: {m['correct_answer']}\n"
        "Generate a targeted correction module."
    )

    resp = ai_service.call_llm(prompt, system_prompt=system_prompt, json_mode=True)
    return ai_service._clean_json_response(resp)
