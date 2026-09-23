"""
syllabus_analyzer.py - Syllabus Analysis and Topic Extraction for PrepPilot
Extracts structured units, topics, subtopics, difficulty, and importance from raw text,
saves them to SQLite, and formats the curriculum hierarchy tree.
"""

from typing import Dict, Any, List
import database
import ai_service


def analyze_and_store_syllabus(subject_id: int, file_name: str, raw_text: str,
                               db_path: str = database.DEFAULT_DB_PATH) -> Dict[str, Any]:
    """
    Parses raw syllabus text via AI, saves raw syllabus into SQLite,
    persists extracted topics to the database, and returns the structured result.
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("Syllabus text is empty. Please upload a valid document with syllabus content.")

    # 1. Save raw syllabus to database
    database.save_syllabus(subject_id, file_name, raw_text, db_path=db_path)

    # 2. Invoke AI parser
    parsed_data = ai_service.parse_syllabus_structure(raw_text)

    # 3. Store units and topics
    units = parsed_data.get("units", [])
    if not units:
        raise ValueError("No units or topics could be extracted from the uploaded syllabus. Please check the document content.")

    stored_topics = []
    for unit in units:
        unit_num = unit.get("unit_number", 1)
        unit_name = unit.get("unit_name", f"Unit {unit_num}")
        topics_list = unit.get("topics", [])

        for t in topics_list:
            t_name = t.get("topic_name", "").strip()
            if not t_name:
                continue
            diff = t.get("difficulty_level", "Medium")
            imp = t.get("importance", "Medium")

            topic_id = database.add_topic(
                subject_id=subject_id,
                unit_number=unit_num,
                unit_name=unit_name,
                topic_name=t_name,
                difficulty_level=diff,
                importance=imp,
                db_path=db_path
            )
            stored_topics.append({
                "id": topic_id,
                "unit_number": unit_num,
                "unit_name": unit_name,
                "topic_name": t_name,
                "difficulty_level": diff,
                "importance": imp
            })

    parsed_data["stored_topics_count"] = len(stored_topics)
    parsed_data["stored_topics"] = stored_topics
    return parsed_data


def format_syllabus_tree(subject_name: str, units_data: List[Dict[str, Any]]) -> str:
    """
    Generates a clean ASCII tree representation of the extracted syllabus structure.
    Example:
    Subject
     ├── Unit 1
     │    ├── Topic 1
     │    └── Topic 2
     └── Unit 2
          └── Topic 1
    """
    lines = [f"📚 {subject_name}"]
    total_units = len(units_data)

    for u_idx, unit in enumerate(units_data):
        is_last_unit = (u_idx == total_units - 1)
        u_prefix = "└── " if is_last_unit else "├── "
        child_indent = "    " if is_last_unit else "│   "

        unit_label = f"Unit {unit.get('unit_number', u_idx + 1)}: {unit.get('unit_name', 'Untitled')}"
        lines.append(f" {u_prefix}{unit_label}")

        topics = unit.get("topics", [])
        total_topics = len(topics)
        for t_idx, topic in enumerate(topics):
            is_last_topic = (t_idx == total_topics - 1)
            t_prefix = "└── " if is_last_topic else "├── "

            topic_name = topic.get("topic_name", "Topic") if isinstance(topic, dict) else str(topic)
            imp = topic.get("importance", "Medium") if isinstance(topic, dict) else "Medium"
            diff = topic.get("difficulty_level", "Medium") if isinstance(topic, dict) else "Medium"
            lines.append(f" {child_indent}{t_prefix}{topic_name} [{imp} Priority | {diff}]")

    return "\n".join(lines)
