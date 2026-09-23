"""
question_generator.py - Syllabus-Grounded Question Generation for PrepPilot
Generates diagnostic tests, topic-specific practice questions, and mock exams strictly
grounded in the student's uploaded syllabus topics.
"""

from typing import List, Dict, Any, Optional
import random
import database
import ai_service


def generate_diagnostic_test(subject_id: int, student_id: int, count: int = 10,
                             db_path: str = database.DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """
    Generates approximately 10 diagnostic questions across different topics and units
    from the uploaded syllabus with a balanced mix of Easy, Medium, and Hard difficulty.
    """
    topics = database.get_topics_by_subject(subject_id, db_path=db_path)
    if not topics:
        raise ValueError("No topics found for this subject. Please upload and analyze a syllabus first.")

    # Select representative topics across available units
    selected_topics = []
    if len(topics) <= count:
        selected_topics = topics
    else:
        # Group by unit to ensure full syllabus coverage
        units_map: Dict[int, List[Dict[str, Any]]] = {}
        for t in topics:
            u_num = t.get("unit_number", 1)
            units_map.setdefault(u_num, []).append(t)

        unit_keys = list(units_map.keys())
        idx = 0
        while len(selected_topics) < count:
            current_unit = unit_keys[idx % len(unit_keys)]
            if units_map[current_unit]:
                # Pick one topic from unit
                selected_topics.append(units_map[current_unit].pop(0))
            idx += 1
            if not any(units_map.values()):
                break

    # Balanced difficulties
    diff_cycle = ["Easy", "Medium", "Hard", "Medium", "Easy"]
    q_type_cycle = ["MCQ", "MCQ", "True/False", "Short Answer", "Conceptual"]

    diagnostic_questions = []
    subject_row = database.get_subjects_by_student(student_id, db_path=db_path)
    subject_name = subject_row[0]["name"] if subject_row else "Subject"

    for i, topic in enumerate(selected_topics):
        diff = diff_cycle[i % len(diff_cycle)]
        q_type = q_type_cycle[i % len(q_type_cycle)]

        # Call AI service for this syllabus topic
        raw_qs = ai_service.generate_questions(
            topic_name=topic["topic_name"],
            unit_name=topic.get("unit_name", ""),
            subject_name=subject_name,
            question_type=q_type,
            difficulty=diff,
            count=1
        )

        for q in raw_qs:
            qid = database.add_question(
                topic_id=topic["id"],
                question_text=q["question_text"],
                question_type=q.get("question_type", q_type),
                options=q.get("options", []),
                correct_answer=q["correct_answer"],
                explanation=q.get("explanation", ""),
                difficulty=diff,
                db_path=db_path
            )
            diagnostic_questions.append({
                "id": qid,
                "topic_id": topic["id"],
                "topic_name": topic["topic_name"],
                "unit_name": topic.get("unit_name", ""),
                "question_text": q["question_text"],
                "question_type": q.get("question_type", q_type),
                "options": q.get("options", []),
                "correct_answer": q["correct_answer"],
                "explanation": q.get("explanation", ""),
                "difficulty": diff
            })
            if len(diagnostic_questions) >= count:
                break

        if len(diagnostic_questions) >= count:
            break

    return diagnostic_questions


def generate_practice_questions_for_topic(topic_id: int, subject_name: str,
                                          question_type: str = "MCQ",
                                          difficulty: str = "Medium",
                                          count: int = 5,
                                          db_path: str = database.DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """
    Generates new practice questions for a specific topic, grounded in the syllabus,
    persists them in the database, and returns them.
    """
    topic = database.get_topic_by_id(topic_id, db_path=db_path)
    if not topic:
        raise ValueError(f"Topic ID {topic_id} not found.")

    raw_qs = ai_service.generate_questions(
        topic_name=topic["topic_name"],
        unit_name=topic.get("unit_name", ""),
        subject_name=subject_name,
        question_type=question_type,
        difficulty=difficulty,
        count=count
    )

    questions = []
    for q in raw_qs:
        qid = database.add_question(
            topic_id=topic_id,
            question_text=q["question_text"],
            question_type=q.get("question_type", question_type),
            options=q.get("options", []),
            correct_answer=q["correct_answer"],
            explanation=q.get("explanation", ""),
            difficulty=difficulty,
            db_path=db_path
        )
        questions.append({
            "id": qid,
            "topic_id": topic_id,
            "topic_name": topic["topic_name"],
            "unit_name": topic.get("unit_name", ""),
            "question_text": q["question_text"],
            "question_type": q.get("question_type", question_type),
            "options": q.get("options", []),
            "correct_answer": q["correct_answer"],
            "explanation": q.get("explanation", ""),
            "difficulty": difficulty
        })

    return questions


def generate_mock_test_paper(subject_id: int, count: int = 15, difficulty: str = "Mixed",
                             db_path: str = database.DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """
    Generates a comprehensive mock test covering the entire uploaded syllabus.
    """
    topics = database.get_topics_by_subject(subject_id, db_path=db_path)
    if not topics:
        raise ValueError("No topics available in syllabus for mock test generation.")

    # Cycle through topics
    sampled_topics = [topics[i % len(topics)] for i in range(count)]
    random.shuffle(sampled_topics)

    mock_questions = []
    difficulties = ["Easy", "Medium", "Hard"] if difficulty == "Mixed" else [difficulty]
    types = ["MCQ", "MCQ", "Short Answer", "True/False"]

    for i, topic in enumerate(sampled_topics):
        chosen_diff = difficulties[i % len(difficulties)]
        chosen_type = types[i % len(types)]

        raw_qs = ai_service.generate_questions(
            topic_name=topic["topic_name"],
            unit_name=topic.get("unit_name", ""),
            subject_name="",
            question_type=chosen_type,
            difficulty=chosen_diff,
            count=1
        )

        for q in raw_qs:
            qid = database.add_question(
                topic_id=topic["id"],
                question_text=q["question_text"],
                question_type=q.get("question_type", chosen_type),
                options=q.get("options", []),
                correct_answer=q["correct_answer"],
                explanation=q.get("explanation", ""),
                difficulty=chosen_diff,
                db_path=db_path
            )
            mock_questions.append({
                "id": qid,
                "topic_id": topic["id"],
                "topic_name": topic["topic_name"],
                "unit_name": topic.get("unit_name", ""),
                "question_text": q["question_text"],
                "question_type": q.get("question_type", chosen_type),
                "options": q.get("options", []),
                "correct_answer": q["correct_answer"],
                "explanation": q.get("explanation", ""),
                "difficulty": chosen_diff
            })
            if len(mock_questions) >= count:
                break
        if len(mock_questions) >= count:
            break

    return mock_questions
