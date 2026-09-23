"""
viva.py - Conversational Text-Based AI Viva Examiner for PrepPilot
Conducts a multi-turn oral exam simulation: asks one syllabus-grounded question at a time,
evaluates student responses semantically, dynamically probes with adaptive follow-ups,
and produces a final score and examiner appraisal saved to SQLite.
"""

from typing import Dict, Any, List
import database
import ai_service


def start_viva_session(student_id: int, topic_id: int,
                       db_path: str = database.DEFAULT_DB_PATH) -> Dict[str, Any]:
    """
    Initializes a new text-based viva session for a syllabus topic.
    Generates an opening conceptual question.
    """
    topic = database.get_topic_by_id(topic_id, db_path=db_path)
    if not topic:
        raise ValueError(f"Topic ID {topic_id} not found.")

    system_prompt = (
        "You are an academic university viva examiner. "
        "Formulate a strong, clear opening question on the specified syllabus topic. "
        "The question should test foundational principles and core understanding. "
        "Return valid JSON:\n"
        '{"question": "Opening viva question text"}'
    )

    prompt = (
        f"Unit: {topic.get('unit_name', '')}\n"
        f"Topic: {topic['topic_name']}\n"
        "Ask the first viva question."
    )

    resp = ai_service.call_llm(prompt, system_prompt=system_prompt, json_mode=True)
    data = ai_service._clean_json_response(resp)
    opening_q = data.get("question", f"Could you explain the core concepts of {topic['topic_name']}?")

    return {
        "student_id": student_id,
        "topic_id": topic_id,
        "topic_name": topic["topic_name"],
        "unit_name": topic.get("unit_name", ""),
        "current_question": opening_q,
        "turns": [],
        "scores": [],
        "turn_count": 1,
        "max_turns": 4,
        "is_concluded": False,
        "overall_score": 0.0,
        "final_feedback": ""
    }


def process_viva_answer(session_state: Dict[str, Any], student_answer: str,
                        db_path: str = database.DEFAULT_DB_PATH) -> Dict[str, Any]:
    """
    Evaluates the student's typed answer, records score and feedback,
    and generates the next follow-up question or concludes the exam.
    """
    if session_state.get("is_concluded"):
        return session_state

    current_q = session_state["current_question"]
    topic_name = session_state["topic_name"]

    # History representation for AI context
    history = []
    for turn in session_state["turns"]:
        history.append({"role": "examiner", "content": turn["question"]})
        history.append({"role": "student", "content": turn["answer"]})

    eval_result = ai_service.evaluate_viva_answer(
        topic_name=topic_name,
        current_question=current_q,
        student_answer=student_answer,
        conversation_history=history
    )

    score = float(eval_result.get("score", 7.0))
    feedback = eval_result.get("feedback", "Good explanation.")
    session_state["scores"].append(score)

    session_state["turns"].append({
        "turn": session_state["turn_count"],
        "question": current_q,
        "answer": student_answer,
        "score": score,
        "feedback": feedback
    })

    # Check conclusion
    if session_state["turn_count"] >= session_state["max_turns"] or eval_result.get("is_concluded", False):
        session_state["is_concluded"] = True
        avg_score = round(sum(session_state["scores"]) / len(session_state["scores"]), 1)
        session_state["overall_score"] = avg_score

        # Generate summary feedback
        summary_prompt = (
            f"You have finished conducting a viva on {topic_name}. "
            f"Scores across turns: {session_state['scores']}. "
            "Write a brief 2-3 sentence concluding appraisal summarizing strengths and areas to sharpen."
        )
        try:
            summary_resp = ai_service.call_llm(summary_prompt)
            session_state["final_feedback"] = summary_resp.strip()
        except Exception:
            session_state["final_feedback"] = f"Overall performance was solid with an average score of {avg_score}/10."

        # Save session to SQLite
        database.save_viva_session(
            student_id=session_state["student_id"],
            topic_id=session_state["topic_id"],
            transcript=session_state["turns"],
            overall_score=avg_score,
            feedback=session_state["final_feedback"],
            db_path=db_path
        )
    else:
        session_state["turn_count"] += 1
        session_state["current_question"] = eval_result.get(
            "follow_up_question",
            f"Can you elaborate further on how that applies to {topic_name}?"
        )

    return session_state
