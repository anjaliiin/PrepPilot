"""
ai_service.py - Unified AI Provider Client for PrepPilot
Supports Google Gemini and OpenAI-compatible APIs.
NO fake fallback data is generated on failure; real user-friendly exceptions are raised.
"""

import os
import json
import re
from typing import List, Dict, Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class AIServiceError(Exception):
    """Custom exception raised when AI service calls fail or keys are missing."""
    pass


def get_ai_config() -> Dict[str, str]:
    """Retrieves current AI provider settings from environment variables."""
    provider = os.getenv("AI_PROVIDER", "gemini").lower()
    api_key = os.getenv("AI_API_KEY", "").strip()
    model = os.getenv("AI_MODEL", "")

    if not model:
        if provider == "gemini":
            model = "gemini-2.5-flash"
        else:
            model = "gpt-4o-mini"

    return {
        "provider": provider,
        "api_key": api_key,
        "model": model,
        "base_url": os.getenv("OPENAI_BASE_URL", "").strip() or None
    }


def call_llm(prompt: str, system_prompt: str = "", json_mode: bool = False,
             override_key: Optional[str] = None, override_provider: Optional[str] = None) -> str:
    """
    Executes a prompt against the configured AI provider (Gemini or OpenAI).
    Raises AIServiceError on misconfiguration or failure without returning fake data.
    """
    cfg = get_ai_config()
    provider = (override_provider or cfg["provider"]).lower()
    api_key = override_key or cfg["api_key"]
    model_name = cfg["model"]

    if not api_key:
        raise AIServiceError(
            f"No API key configured for '{provider}'. "
            f"Please configure your AI_API_KEY in the Settings tab or in your .env file."
        )

    if provider == "gemini":
        return _call_gemini(prompt, system_prompt, model_name, api_key, json_mode)
    elif provider in ("openai", "openai-compatible"):
        return _call_openai(prompt, system_prompt, model_name, api_key, cfg.get("base_url"), json_mode)
    else:
        raise AIServiceError(f"Unsupported AI provider '{provider}'. Must be 'gemini' or 'openai'.")


def _call_gemini(prompt: str, system_prompt: str, model_name: str, api_key: str, json_mode: bool) -> str:
    """Call Google Gemini API using google-genai or google-generativeai."""
    # Attempt google-genai first (official standard)
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        config = types.GenerateContentConfig()
        if system_prompt:
            config.system_instruction = system_prompt
        if json_mode:
            config.response_mime_type = "application/json"

        response = client.models.generate_content(
            model=model_name or "gemini-2.5-flash",
            contents=prompt,
            config=config
        )
        if response and response.text:
            return response.text
        raise AIServiceError("Empty response received from Gemini API.")
    except ImportError:
        pass
    except Exception as e:
        # Fall through to legacy SDK if google-genai had client init issues, else raise
        err_msg = str(e)
        if "API_KEY_INVALID" in err_msg or "PERMISSION_DENIED" in err_msg:
            raise AIServiceError(f"Gemini API authentication failed: {err_msg}")
        raise AIServiceError(f"Gemini API request failed: {err_msg}")

    # Fallback to google-generativeai if google-genai is not installed
    try:
        import google.generativeai as legacy_genai
        legacy_genai.configure(api_key=api_key)
        full_system = f"{system_prompt}\n\n" if system_prompt else ""
        if json_mode:
            full_system += "Respond strictly with valid JSON. Do not wrap in markdown quotes if possible.\n"

        model = legacy_genai.GenerativeModel(
            model_name=model_name or "gemini-1.5-flash",
            system_instruction=full_system if system_prompt else None
        )
        response = model.generate_content(prompt)
        if response and response.text:
            return response.text
        raise AIServiceError("Empty response received from Gemini GenerativeModel.")
    except Exception as e:
        raise AIServiceError(f"Gemini API call failed: {str(e)}")


def _call_openai(prompt: str, system_prompt: str, model_name: str, api_key: str,
                 base_url: Optional[str], json_mode: bool) -> str:
    """Call OpenAI or OpenAI-compatible API."""
    try:
        from openai import OpenAI
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        client = OpenAI(**client_kwargs)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        req_kwargs: Dict[str, Any] = {
            "model": model_name or "gpt-4o-mini",
            "messages": messages,
            "temperature": 0.3
        }
        if json_mode:
            req_kwargs["response_format"] = {"type": "json_object"}

        response = client.chat.completions.create(**req_kwargs)
        content = response.choices[0].message.content
        if content:
            return content
        raise AIServiceError("Empty response received from OpenAI-compatible API.")
    except Exception as e:
        raise AIServiceError(f"OpenAI-compatible API call failed: {str(e)}")


def _clean_json_response(raw_text: str) -> Any:
    """Sanitizes and extracts valid JSON from model responses containing markdown backticks."""
    text = raw_text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Match outermost bracket or brace
        match = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        raise AIServiceError(f"Model returned invalid JSON format: {raw_text[:300]}")


# -------------------------------------------------------------
# HIGH-LEVEL SYLLABUS & ADAPTIVE SERVICES
# -------------------------------------------------------------

def parse_syllabus_structure(raw_text: str) -> Dict[str, Any]:
    """
    Parses raw syllabus text into structured subject, units, topics, subtopics, difficulty, and importance.
    """
    system_prompt = (
        "You are an expert academic curriculum parser. "
        "Analyze the provided syllabus text carefully and extract the subject, all units, topics, and subtopics. "
        "For every topic, estimate: "
        "- difficulty_level ('Easy', 'Medium', 'Hard') "
        "- importance ('High', 'Medium', 'Low') based on curriculum weightage and core exam relevance. "
        "Return strictly valid JSON matching this schema:\n"
        "{\n"
        '  "subject_name": "String",\n'
        '  "subject_code": "String",\n'
        '  "units": [\n'
        "    {\n"
        '      "unit_number": 1,\n'
        '      "unit_name": "Unit Title",\n'
        '      "topics": [\n'
        "        {\n"
        '          "topic_name": "Topic Name",\n'
        '          "subtopics": ["Subtopic 1", "Subtopic 2"],\n'
        '          "difficulty_level": "Medium",\n'
        '          "importance": "High"\n'
        "        }\n"
        "      ]\n"
        "    }\n"
        "  ]\n"
        "}"
    )

    prompt = f"Analyze this syllabus text and extract all topics:\n\n{raw_text[:20000]}"
    resp = call_llm(prompt, system_prompt=system_prompt, json_mode=True)
    return _clean_json_response(resp)


def generate_questions(topic_name: str, unit_name: str, subject_name: str,
                       question_type: str = "MCQ", difficulty: str = "Medium",
                       count: int = 5) -> List[Dict[str, Any]]:
    """
    Generates practice or mock questions strictly grounded in the given topic and syllabus.
    Types: 'MCQ', 'True/False', 'Short Answer', 'Conceptual'
    """
    system_prompt = (
        "You are an expert exam question creator. "
        "Generate questions STRICTLY grounded in the specified syllabus topic. "
        "Do not invent unrelated topics. "
        "For MCQ questions, provide exactly 4 distinct options in 'options' and the exact correct string in 'correct_answer'. "
        "For True/False, provide options ['True', 'False'] and correct_answer 'True' or 'False'. "
        "For Short Answer and Conceptual, provide options as empty list and a comprehensive reference correct answer. "
        "Always provide an 'explanation' detailing why the answer is correct. "
        "Return JSON with a single key 'questions' containing a list of question objects matching:\n"
        "{\n"
        '  "questions": [\n'
        "    {\n"
        '      "question_text": "...",\n'
        '      "question_type": "...",\n'
        '      "options": ["A", "B", "C", "D"],\n'
        '      "correct_answer": "...",\n'
        '      "explanation": "...",\n'
        '      "difficulty": "Easy|Medium|Hard"\n'
        "    }\n"
        "  ]\n"
        "}"
    )

    prompt = (
        f"Subject: {subject_name}\n"
        f"Unit: {unit_name}\n"
        f"Topic: {topic_name}\n"
        f"Question Type: {question_type}\n"
        f"Difficulty: {difficulty}\n"
        f"Number of questions required: {count}\n"
        "Generate high quality exam questions now."
    )

    resp = call_llm(prompt, system_prompt=system_prompt, json_mode=True)
    data = _clean_json_response(resp)
    if isinstance(data, dict) and "questions" in data:
        return data["questions"]
    elif isinstance(data, list):
        return data
    raise AIServiceError("Invalid questions format returned by AI.")


def explain_topic(topic_name: str, unit_name: str, subject_name: str) -> Dict[str, Any]:
    """
    Generates structured topic notes: definition, key concepts, simple explanation,
    examples, important points, formulas, and exam notes.
    """
    system_prompt = (
        "You are an academic professor and mentor. Generate structured, exam-oriented notes "
        "for the specified topic from the syllabus. Return valid JSON:\n"
        "{\n"
        '  "definition": "Clear concise formal definition",\n'
        '  "key_concepts": ["Concept 1", "Concept 2"],\n'
        '  "simple_explanation": "Intuitive breakdown for deep understanding",\n'
        '  "examples": ["Real-world application / academic example"],\n'
        '  "important_points": ["Key point 1", "Key point 2"],\n'
        '  "formulas": ["Formulas or theorems if applicable, or N/A"],\n'
        '  "exam_oriented_notes": "Key hints, typical exam pitfalls, and how questions are framed on this topic"\n'
        "}"
    )

    prompt = (
        f"Subject: {subject_name}\n"
        f"Unit: {unit_name}\n"
        f"Topic: {topic_name}\n"
        "Explain this topic thoroughly."
    )

    resp = call_llm(prompt, system_prompt=system_prompt, json_mode=True)
    return _clean_json_response(resp)


def generate_revision_materials(topic_name: str, unit_name: str, subject_name: str) -> Dict[str, Any]:
    """Generates quick revision notes, definitions, formulas, and flashcards."""
    system_prompt = (
        "You are a revision specialist. Create fast-paced revision aids for the given topic. "
        "Return valid JSON:\n"
        "{\n"
        '  "quick_notes": ["Note 1", "Note 2"],\n'
        '  "key_definitions": [{"term": "...", "definition": "..."}],\n'
        '  "formulas_and_rules": ["Rule 1", "Rule 2"],\n'
        '  "flashcards": [\n'
        '    {"front": "Question/Term", "back": "Answer/Definition"}\n'
        "  ],\n"
        '  "quick_quiz": [\n'
        '    {"question": "Rapid fire question", "answer": "Quick answer"}\n'
        "  ]\n"
        "}"
    )

    prompt = (
        f"Subject: {subject_name}\n"
        f"Unit: {unit_name}\n"
        f"Topic: {topic_name}\n"
        "Generate revision aids and flashcards."
    )

    resp = call_llm(prompt, system_prompt=system_prompt, json_mode=True)
    return _clean_json_response(resp)


def analyze_answer(question_text: str, correct_answer: str, student_answer: str,
                   question_type: str = "Short Answer") -> Dict[str, Any]:
    """
    Performs semantic answer grading for short-answer and conceptual questions.
    Returns status ('Correct', 'Partially Correct', 'Incorrect'), score (0.0 to 1.0),
    and tripartite constructive feedback.
    """
    # For MCQ / True-False, simple exact check can also be complemented
    if question_type in ("MCQ", "True/False"):
        is_exact = student_answer.strip().lower() == correct_answer.strip().lower()
        return {
            "status": "Correct" if is_exact else "Incorrect",
            "score": 1.0 if is_exact else 0.0,
            "what_was_correct": "Selected the correct option." if is_exact else "Incorrect option chosen.",
            "what_was_missing": "" if is_exact else f"The correct answer is '{correct_answer}'.",
            "what_should_be_improved": "" if is_exact else "Review the underlying concept before re-attempting."
        }

    system_prompt = (
        "You are an academic grader. Evaluate the student's answer semantically against the reference answer. "
        "Do not rely solely on exact string matching. "
        "Grade the response as 'Correct', 'Partially Correct', or 'Incorrect'. "
        "Assign a score between 0.0 (completely incorrect) and 1.0 (fully correct). "
        "Provide constructive feedback detailing: "
        "1. what_was_correct "
        "2. what_was_missing "
        "3. what_should_be_improved\n"
        "Return valid JSON:\n"
        "{\n"
        '  "status": "Correct|Partially Correct|Incorrect",\n'
        '  "score": 0.8,\n'
        '  "what_was_correct": "...",\n'
        '  "what_was_missing": "...",\n'
        '  "what_should_be_improved": "..."\n'
        "}"
    )

    prompt = (
        f"Question: {question_text}\n"
        f"Reference Correct Answer: {correct_answer}\n"
        f"Student Answer: {student_answer}\n"
        "Evaluate this answer semantically now."
    )

    resp = call_llm(prompt, system_prompt=system_prompt, json_mode=True)
    return _clean_json_response(resp)


def identify_mistake(question_text: str, student_answer: str, correct_answer: str) -> str:
    """
    Categorizes the student's mistake into one of the 6 standard mistake types:
    - Concept misunderstanding
    - Forgot definition
    - Calculation error
    - Confused concepts
    - Careless mistake
    - Incomplete answer
    """
    valid_types = [
        "Concept misunderstanding",
        "Forgot definition",
        "Calculation error",
        "Confused concepts",
        "Careless mistake",
        "Incomplete answer"
    ]

    system_prompt = (
        "You are an educational diagnostician. Analyze why the student gave an incorrect answer. "
        "Classify the mistake into exactly ONE of the following categories:\n"
        "- Concept misunderstanding\n"
        "- Forgot definition\n"
        "- Calculation error\n"
        "- Confused concepts\n"
        "- Careless mistake\n"
        "- Incomplete answer\n"
        "Return valid JSON:\n"
        '{"mistake_type": "One of the 6 exact types above", "reason": "brief explanation"}'
    )

    prompt = (
        f"Question: {question_text}\n"
        f"Student Answer: {student_answer}\n"
        f"Correct Answer: {correct_answer}\n"
        "Classify the mistake."
    )

    try:
        resp = call_llm(prompt, system_prompt=system_prompt, json_mode=True)
        data = _clean_json_response(resp)
        m_type = data.get("mistake_type", "").strip()
        for vt in valid_types:
            if vt.lower() in m_type.lower():
                return vt
    except Exception:
        pass
    return "Concept misunderstanding"


def evaluate_viva_answer(topic_name: str, current_question: str,
                         student_answer: str, conversation_history: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Evaluates student's answer in a text-based viva oral exam session.
    Returns evaluation, mark (0-10), constructive examiner feedback,
    and a dynamic follow-up question adapting to student performance.
    """
    system_prompt = (
        "You are a friendly yet rigorous university oral examiner conducting a viva on the specified syllabus topic. "
        "Evaluate the student's answer to the current question. "
        "Provide: "
        "- score: 0 to 10 "
        "- feedback: concise examiner commentary on clarity, depth, and accuracy "
        "- follow_up_question: a challenging follow-up question that builds on what the student said or tests an edge case "
        "- is_concluded: boolean (set to true only after 4-5 rigorous questions, otherwise false)\n"
        "Return valid JSON:\n"
        "{\n"
        '  "score": 7.5,\n'
        '  "feedback": "...",\n'
        '  "follow_up_question": "...",\n'
        '  "is_concluded": false\n'
        "}"
    )

    history_str = "\n".join([f"{h['role']}: {h['content']}" for h in conversation_history[-6:]])
    prompt = (
        f"Topic: {topic_name}\n"
        f"Conversation History:\n{history_str}\n\n"
        f"Current Viva Question: {current_question}\n"
        f"Student Answer: {student_answer}\n"
        "Assess and generate the next response."
    )

    resp = call_llm(prompt, system_prompt=system_prompt, json_mode=True)
    return _clean_json_response(resp)


def select_next_action(student_profile: Dict[str, Any], topics: List[Dict[str, Any]],
                       performance_summary: Dict[str, Any], mistakes_summary: Dict[str, Any],
                       days_remaining: int) -> Dict[str, Any]:
    """
    AI Agent Next Best Action selector based on syllabus, performance, mistakes, and days remaining.
    Possible actions:
    EXPLAIN_TOPIC, GENERATE_EASY_QUESTIONS, GENERATE_MEDIUM_QUESTIONS,
    GENERATE_HARD_QUESTIONS, REVISION, MOCK_TEST, VIVA, REVIEW_MISTAKES.
    """
    system_prompt = (
        "You are the central autonomous AI Agent brain of PrepPilot. "
        "Based on the student's profile, exam date, syllabus topics, past performance, and mistake memory, "
        "select the single NEXT BEST ACTION to optimize their exam preparation. "
        "Valid action codes:\n"
        "- EXPLAIN_TOPIC\n"
        "- GENERATE_EASY_QUESTIONS\n"
        "- GENERATE_MEDIUM_QUESTIONS\n"
        "- GENERATE_HARD_QUESTIONS\n"
        "- REVISION\n"
        "- MOCK_TEST\n"
        "- VIVA\n"
        "- REVIEW_MISTAKES\n\n"
        "Rules:\n"
        "- If accuracy < 50% on a topic, recommend EXPLAIN_TOPIC or GENERATE_EASY_QUESTIONS.\n"
        "- If accuracy between 50% and 75%, recommend GENERATE_MEDIUM_QUESTIONS.\n"
        "- If accuracy > 75%, recommend GENERATE_HARD_QUESTIONS or VIVA.\n"
        "- If there are repeated mistakes or conceptual misunderstandings, recommend REVIEW_MISTAKES or REVISION.\n"
        "- If exam date is approaching (e.g. <= 7 days) and weak topics exist, prioritize high-importance weak topics, REVISION, or MOCK_TEST.\n"
        "- If no tests attempted yet, recommend a DIAGNOSTIC or GENERATE_EASY_QUESTIONS on Unit 1.\n"
        "Return valid JSON:\n"
        "{\n"
        '  "action_code": "EXPLAIN_TOPIC|GENERATE_EASY_QUESTIONS|...",\n'
        '  "target_topic": "Topic Name",\n'
        '  "target_unit": "Unit Name",\n'
        '  "reasoning": "Clear pedagogical rationale for why this is the optimal next move",\n'
        '  "action_title": "Short user-facing action title",\n'
        '  "action_description": "Detailed actionable instruction for the student"\n'
        "}"
    )

    prompt = (
        f"Student Profile: {json.dumps(student_profile)}\n"
        f"Days Remaining until Exam: {days_remaining}\n"
        f"Syllabus Topics Count: {len(topics)}\n"
        f"Sample Topics: {json.dumps([t.get('topic_name') for t in topics[:15]])}\n"
        f"Performance Summary: {json.dumps(performance_summary)}\n"
        f"Mistakes Summary: {json.dumps(mistakes_summary)}\n"
        "Determine the AI Agent Next Best Action."
    )

    resp = call_llm(prompt, system_prompt=system_prompt, json_mode=True)
    return _clean_json_response(resp)


def create_study_plan_schedule(student_profile: Dict[str, Any], topics: List[Dict[str, Any]],
                               performance: List[Dict[str, Any]], days_remaining: int) -> List[Dict[str, Any]]:
    """
    Generates a personalized daily study schedule distributing topics over available days and daily study hours.
    Prioritizes high importance and weak topics.
    """
    system_prompt = (
        "You are an academic scheduling expert. Distribute the uploaded syllabus topics into a study plan. "
        "Take into account:\n"
        "- Days remaining until exam\n"
        "- Daily study hours\n"
        "- Topic importance (High > Medium > Low)\n"
        "- Topic performance (Weak topics must be scheduled earlier and allotted more review)\n"
        "Generate a list of study slots. Each slot must map to an existing topic from the syllabus. "
        "Return valid JSON:\n"
        "{\n"
        '  "slots": [\n'
        "    {\n"
        '      "topic_name": "Exact topic name from input",\n'
        '      "day_offset": 0,\n'
        '      "time_slot": "Morning (09:00 - 10:30)",\n'
        '      "notes": "Focus on high-yield formulas and concept mastery"\n'
        "    }\n"
        "  ]\n"
        "}"
    )

    prompt = (
        f"Student: {student_profile.get('name')} | Exam in: {days_remaining} days | Daily Hours: {student_profile.get('daily_study_hours')}\n"
        f"Topics to schedule: {json.dumps([{'name': t['topic_name'], 'unit': t.get('unit_name'), 'importance': t.get('importance')} for t in topics])}\n"
        f"Past Performance on topics: {json.dumps([{'topic': p.get('topic_name'), 'acc': p.get('accuracy')} for p in performance])}\n"
        "Generate a balanced study plan."
    )

    resp = call_llm(prompt, system_prompt=system_prompt, json_mode=True)
    data = _clean_json_response(resp)
    if isinstance(data, dict) and "slots" in data:
        return data["slots"]
    elif isinstance(data, list):
        return data
    return []
