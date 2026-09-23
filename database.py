"""
database.py - SQLite Database Management for PrepPilot
Handles schema initialization, connection pooling, and CRUD operations for all entities.
Starts completely empty with zero fake/demo data.
"""

import os
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "exam.db")


def get_db_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Returns a SQLite connection with foreign keys enabled and dict-like row factory."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initializes the database schema if it doesn't already exist."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        course TEXT,
        semester TEXT,
        exam_date TEXT NOT NULL,
        daily_study_hours REAL DEFAULT 3.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        code TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS syllabus (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
        file_name TEXT,
        raw_text TEXT,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
        unit_number INTEGER,
        unit_name TEXT,
        topic_name TEXT NOT NULL,
        difficulty_level TEXT DEFAULT 'Medium',
        importance TEXT DEFAULT 'Medium'
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
        question_text TEXT NOT NULL,
        question_type TEXT NOT NULL,
        options_json TEXT,
        correct_answer TEXT NOT NULL,
        explanation TEXT,
        difficulty TEXT DEFAULT 'Medium'
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
        question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
        student_answer TEXT,
        is_correct INTEGER DEFAULT 0,
        score REAL DEFAULT 0.0,
        feedback TEXT,
        attempt_type TEXT,
        attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS performance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
        topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
        accuracy REAL DEFAULT 0.0,
        total_attempts INTEGER DEFAULT 0,
        correct_attempts INTEGER DEFAULT 0,
        last_attempted TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(student_id, topic_id)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS mistakes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
        subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
        topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
        question_text TEXT NOT NULL,
        student_answer TEXT,
        correct_answer TEXT,
        mistake_type TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS study_plan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
        topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
        plan_date TEXT NOT NULL,
        time_slot TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        notes TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS mock_tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
        subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
        total_questions INTEGER NOT NULL,
        score REAL NOT NULL,
        accuracy REAL NOT NULL,
        time_taken_sec INTEGER DEFAULT 0,
        completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS viva_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
        topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
        transcript_json TEXT,
        overall_score REAL,
        feedback TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Indices for performance
    cur.execute("CREATE INDEX IF NOT EXISTS idx_topics_subject ON topics(subject_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_questions_topic ON questions(topic_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_attempts_student ON attempts(student_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_perf_student_topic ON performance(student_id, topic_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_mistakes_student ON mistakes(student_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_plan_student_date ON study_plan(student_id, plan_date);")

    conn.commit()
    conn.close()


# -------------------------------------------------------------
# STUDENT CRUD
# -------------------------------------------------------------

def create_student(name: str, course: str, semester: str, exam_date: str,
                   daily_study_hours: float, db_path: str = DEFAULT_DB_PATH) -> int:
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO students (name, course, semester, exam_date, daily_study_hours)
        VALUES (?, ?, ?, ?, ?)
    """, (name.strip(), course.strip(), semester.strip(), exam_date.strip(), float(daily_study_hours)))
    student_id = cur.lastrowid
    conn.commit()
    conn.close()
    return student_id


def get_all_students(db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    rows = conn.execute("SELECT * FROM students ORDER BY id DESC").fetchall()
    students = [dict(row) for row in rows]
    conn.close()
    return students


def get_student_by_id(student_id: int, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    row = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_student(student_id: int, name: str, course: str, semester: str,
                   exam_date: str, daily_study_hours: float, db_path: str = DEFAULT_DB_PATH) -> None:
    conn = get_db_connection(db_path)
    conn.execute("""
        UPDATE students
        SET name = ?, course = ?, semester = ?, exam_date = ?, daily_study_hours = ?
        WHERE id = ?
    """, (name.strip(), course.strip(), semester.strip(), exam_date.strip(), float(daily_study_hours), student_id))
    conn.commit()
    conn.close()


# -------------------------------------------------------------
# SUBJECT & SYLLABUS CRUD
# -------------------------------------------------------------

def create_subject(student_id: int, name: str, code: str = "", db_path: str = DEFAULT_DB_PATH) -> int:
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO subjects (student_id, name, code)
        VALUES (?, ?, ?)
    """, (student_id, name.strip(), code.strip()))
    subject_id = cur.lastrowid
    conn.commit()
    conn.close()
    return subject_id


def get_subjects_by_student(student_id: int, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    rows = conn.execute("SELECT * FROM subjects WHERE student_id = ? ORDER BY id ASC", (student_id,)).fetchall()
    subjects = [dict(row) for row in rows]
    conn.close()
    return subjects


def save_syllabus(subject_id: int, file_name: str, raw_text: str, db_path: str = DEFAULT_DB_PATH) -> int:
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO syllabus (subject_id, file_name, raw_text)
        VALUES (?, ?, ?)
    """, (subject_id, file_name, raw_text))
    syllabus_id = cur.lastrowid
    conn.commit()
    conn.close()
    return syllabus_id


def get_syllabus_by_subject(subject_id: int, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    row = conn.execute("SELECT * FROM syllabus WHERE subject_id = ? ORDER BY id DESC LIMIT 1", (subject_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# -------------------------------------------------------------
# TOPICS CRUD
# -------------------------------------------------------------

def add_topic(subject_id: int, unit_number: int, unit_name: str,
              topic_name: str, difficulty_level: str = "Medium",
              importance: str = "Medium", db_path: str = DEFAULT_DB_PATH) -> int:
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO topics (subject_id, unit_number, unit_name, topic_name, difficulty_level, importance)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (subject_id, unit_number, unit_name.strip(), topic_name.strip(), difficulty_level, importance))
    topic_id = cur.lastrowid
    conn.commit()
    conn.close()
    return topic_id


def get_topics_by_subject(subject_id: int, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    rows = conn.execute("""
        SELECT * FROM topics
        WHERE subject_id = ?
        ORDER BY unit_number ASC, id ASC
    """, (subject_id,)).fetchall()
    topics = [dict(row) for row in rows]
    conn.close()
    return topics


def get_topic_by_id(topic_id: int, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    row = conn.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# -------------------------------------------------------------
# QUESTIONS & ATTEMPTS
# -------------------------------------------------------------

def add_question(topic_id: int, question_text: str, question_type: str,
                 options: Optional[List[str]], correct_answer: str,
                 explanation: str, difficulty: str = "Medium",
                 db_path: str = DEFAULT_DB_PATH) -> int:
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    options_json = json.dumps(options) if options else None
    cur.execute("""
        INSERT INTO questions (topic_id, question_text, question_type, options_json, correct_answer, explanation, difficulty)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (topic_id, question_text.strip(), question_type, options_json, correct_answer.strip(), explanation.strip(), difficulty))
    qid = cur.lastrowid
    conn.commit()
    conn.close()
    return qid


def get_questions_by_topic(topic_id: int, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    rows = conn.execute("SELECT * FROM questions WHERE topic_id = ?", (topic_id,)).fetchall()
    questions = []
    for r in rows:
        d = dict(r)
        d["options"] = json.loads(d["options_json"]) if d["options_json"] else []
        questions.append(d)
    conn.close()
    return questions


def record_attempt(student_id: int, question_id: int, student_answer: str,
                   is_correct: int, score: float, feedback: str,
                   attempt_type: str, db_path: str = DEFAULT_DB_PATH) -> int:
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO attempts (student_id, question_id, student_answer, is_correct, score, feedback, attempt_type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (student_id, question_id, student_answer.strip(), is_correct, score, feedback.strip(), attempt_type))
    aid = cur.lastrowid

    # Update topic performance
    q_row = conn.execute("SELECT topic_id FROM questions WHERE id = ?", (question_id,)).fetchone()
    if q_row:
        topic_id = q_row["topic_id"]
        update_performance_record(student_id, topic_id, is_correct, conn)

    conn.commit()
    conn.close()
    return aid


def update_performance_record(student_id: int, topic_id: int, is_correct: int, conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    row = cur.execute("""
        SELECT total_attempts, correct_attempts FROM performance
        WHERE student_id = ? AND topic_id = ?
    """, (student_id, topic_id)).fetchone()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if row:
        total = row["total_attempts"] + 1
        correct = row["correct_attempts"] + (1 if is_correct else 0)
        acc = (correct / total) * 100.0 if total > 0 else 0.0
        cur.execute("""
            UPDATE performance
            SET accuracy = ?, total_attempts = ?, correct_attempts = ?, last_attempted = ?
            WHERE student_id = ? AND topic_id = ?
        """, (acc, total, correct, now, student_id, topic_id))
    else:
        total = 1
        correct = 1 if is_correct else 0
        acc = (correct / total) * 100.0
        cur.execute("""
            INSERT INTO performance (student_id, topic_id, accuracy, total_attempts, correct_attempts, last_attempted)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (student_id, topic_id, acc, total, correct, now))


def get_performance_by_student(student_id: int, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    rows = conn.execute("""
        SELECT p.*, t.topic_name, t.unit_name, t.unit_number, t.importance, t.subject_id, s.name as subject_name
        FROM performance p
        JOIN topics t ON p.topic_id = t.id
        JOIN subjects s ON t.subject_id = s.id
        WHERE p.student_id = ?
        ORDER BY p.accuracy ASC
    """, (student_id,)).fetchall()
    perf = [dict(row) for row in rows]
    conn.close()
    return perf


# -------------------------------------------------------------
# MISTAKES CRUD
# -------------------------------------------------------------

def log_mistake(student_id: int, subject_id: int, topic_id: int,
                question_text: str, student_answer: str, correct_answer: str,
                mistake_type: str, db_path: str = DEFAULT_DB_PATH) -> int:
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO mistakes (student_id, subject_id, topic_id, question_text, student_answer, correct_answer, mistake_type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (student_id, subject_id, topic_id, question_text.strip(), student_answer.strip(), correct_answer.strip(), mistake_type))
    mid = cur.lastrowid
    conn.commit()
    conn.close()
    return mid


def get_mistakes_by_student(student_id: int, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    rows = conn.execute("""
        SELECT m.*, t.topic_name, t.unit_name, s.name as subject_name
        FROM mistakes m
        JOIN topics t ON m.topic_id = t.id
        JOIN subjects s ON m.subject_id = s.id
        WHERE m.student_id = ?
        ORDER BY m.id DESC
    """, (student_id,)).fetchall()
    mistakes = [dict(row) for row in rows]
    conn.close()
    return mistakes


# -------------------------------------------------------------
# STUDY PLAN CRUD
# -------------------------------------------------------------

def save_study_plan_slots(student_id: int, slots: List[Dict[str, Any]], db_path: str = DEFAULT_DB_PATH) -> None:
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    for s in slots:
        cur.execute("""
            INSERT INTO study_plan (student_id, topic_id, plan_date, time_slot, status, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (student_id, s["topic_id"], s["plan_date"], s["time_slot"], s.get("status", "pending"), s.get("notes", "")))
    conn.commit()
    conn.close()


def get_study_plan_by_student(student_id: int, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    rows = conn.execute("""
        SELECT sp.*, t.topic_name, t.unit_name, t.importance, s.name as subject_name
        FROM study_plan sp
        JOIN topics t ON sp.topic_id = t.id
        JOIN subjects s ON t.subject_id = s.id
        WHERE sp.student_id = ?
        ORDER BY sp.plan_date ASC, sp.id ASC
    """, (student_id,)).fetchall()
    plan = [dict(row) for row in rows]
    conn.close()
    return plan


def update_plan_status(plan_id: int, status: str, db_path: str = DEFAULT_DB_PATH) -> None:
    conn = get_db_connection(db_path)
    conn.execute("UPDATE study_plan SET status = ? WHERE id = ?", (status, plan_id))
    conn.commit()
    conn.close()


def reschedule_missed_slot(plan_id: int, db_path: str = DEFAULT_DB_PATH) -> Optional[str]:
    """
    Non-destructive reschedule: marks current slot as 'missed',
    and schedules the same topic in the next available day/slot without wiping the rest of the plan.
    """
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM study_plan WHERE id = ?", (plan_id,)).fetchone()
    if not row:
        conn.close()
        return None

    # Mark as missed
    cur.execute("UPDATE study_plan SET status = 'missed' WHERE id = ?", (plan_id,))

    # Find the latest plan date for this student
    student_id = row["student_id"]
    last_row = cur.execute("""
        SELECT plan_date FROM study_plan
        WHERE student_id = ?
        ORDER BY plan_date DESC LIMIT 1
    """, (student_id,)).fetchone()

    next_date = datetime.now().strftime("%Y-%m-%d")
    if last_row and last_row["plan_date"] >= next_date:
        # Push 1 day after the latest scheduled plan date
        try:
            from datetime import timedelta
            ld = datetime.strptime(last_row["plan_date"], "%Y-%m-%d")
            next_date = (ld + timedelta(days=1)).strftime("%Y-%m-%d")
        except Exception:
            pass

    cur.execute("""
        INSERT INTO study_plan (student_id, topic_id, plan_date, time_slot, status, notes)
        VALUES (?, ?, ?, ?, 'pending', ?)
    """, (student_id, row["topic_id"], next_date, row["time_slot"], f"Rescheduled from {row['plan_date']}"))

    conn.commit()
    conn.close()
    return next_date


# -------------------------------------------------------------
# MOCK TESTS & VIVA SESSIONS
# -------------------------------------------------------------

def save_mock_test_result(student_id: int, subject_id: int, total_questions: int,
                          score: float, accuracy: float, time_taken_sec: int,
                          db_path: str = DEFAULT_DB_PATH) -> int:
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO mock_tests (student_id, subject_id, total_questions, score, accuracy, time_taken_sec)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (student_id, subject_id, total_questions, score, accuracy, time_taken_sec))
    mid = cur.lastrowid
    conn.commit()
    conn.close()
    return mid


def get_mock_tests_by_student(student_id: int, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    rows = conn.execute("""
        SELECT mt.*, s.name as subject_name
        FROM mock_tests mt
        JOIN subjects s ON mt.subject_id = s.id
        WHERE mt.student_id = ?
        ORDER BY mt.completed_at DESC
    """, (student_id,)).fetchall()
    tests = [dict(row) for row in rows]
    conn.close()
    return tests


def save_viva_session(student_id: int, topic_id: int, transcript: List[Dict[str, Any]],
                      overall_score: float, feedback: str, db_path: str = DEFAULT_DB_PATH) -> int:
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    transcript_json = json.dumps(transcript)
    cur.execute("""
        INSERT INTO viva_sessions (student_id, topic_id, transcript_json, overall_score, feedback)
        VALUES (?, ?, ?, ?, ?)
    """, (student_id, topic_id, transcript_json, overall_score, feedback.strip()))
    vid = cur.lastrowid
    conn.commit()
    conn.close()
    return vid


def get_viva_sessions_by_student(student_id: int, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    rows = conn.execute("""
        SELECT v.*, t.topic_name, t.unit_name
        FROM viva_sessions v
        JOIN topics t ON v.topic_id = t.id
        WHERE v.student_id = ?
        ORDER BY v.created_at DESC
    """, (student_id,)).fetchall()
    sessions = []
    for r in rows:
        d = dict(r)
        d["transcript"] = json.loads(d["transcript_json"]) if d["transcript_json"] else []
        sessions.append(d)
    conn.close()
    return sessions


# -------------------------------------------------------------
# RESET ALL PREPARATION DATA (Clean Slate)
# -------------------------------------------------------------

def reset_student_preparation(student_id: int, db_path: str = DEFAULT_DB_PATH) -> None:
    """Removes all learning attempts, performance, mistakes, plans, mock tests, and viva sessions for this student."""
    conn = get_db_connection(db_path)
    conn.execute("DELETE FROM attempts WHERE student_id = ?", (student_id,))
    conn.execute("DELETE FROM performance WHERE student_id = ?", (student_id,))
    conn.execute("DELETE FROM mistakes WHERE student_id = ?", (student_id,))
    conn.execute("DELETE FROM study_plan WHERE student_id = ?", (student_id,))
    conn.execute("DELETE FROM mock_tests WHERE student_id = ?", (student_id,))
    conn.execute("DELETE FROM viva_sessions WHERE student_id = ?", (student_id,))
    conn.commit()
    conn.close()
