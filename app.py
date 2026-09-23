"""
app.py - PrepPilot – AI Adaptive Exam Preparation Agent
Master Streamlit Web Application implementing all 11 core screens:
Profile/Login, Syllabus Upload, Diagnostic Test, Dashboard (Next Best Action),
Practice Drills, Explanation & Revision, Text-Based AI Viva, Mock Exam,
Mistake Memory, Study Planner, and Settings.
"""

import os
import json
import time
from datetime import datetime, date
import streamlit as st
import pandas as pd

# Core application modules
import database
import pdf_reader
import syllabus_analyzer
import question_generator
import performance_analyzer
import study_planner
import viva
import mistake_memory
import agent
import ai_service
import utils

# Initialize page configuration
st.set_page_config(
    page_title="PrepPilot – AI Adaptive Exam Preparation Agent",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply custom styling
utils.inject_custom_css()

# Auto-initialize SQLite database schema on startup (starts completely empty)
database.init_db()


# -------------------------------------------------------------
# SESSION STATE INITIALIZATION
# -------------------------------------------------------------
if "current_student_id" not in st.session_state:
    st.session_state.current_student_id = None
if "current_subject_id" not in st.session_state:
    st.session_state.current_subject_id = None
if "active_nav_page" not in st.session_state:
    st.session_state.active_nav_page = "Dashboard"
if "diagnostic_questions" not in st.session_state:
    st.session_state.diagnostic_questions = []
if "practice_questions" not in st.session_state:
    st.session_state.practice_questions = []
if "mock_test_state" not in st.session_state:
    st.session_state.mock_test_state = None
if "viva_state" not in st.session_state:
    st.session_state.viva_state = None


# -------------------------------------------------------------
# SCREEN 1: STUDENT LOGIN / PROFILE
# -------------------------------------------------------------
def render_student_login():
    st.markdown("""
        <div class='main-header'>
            <h1>🎓 Welcome to PrepPilot</h1>
            <p>Your Autonomous AI Adaptive Exam Preparation Agent</p>
        </div>
    """, unsafe_allow_html=True)

    existing_students = database.get_all_students()

    col1, col2 = st.columns([1.2, 1])

    with col1:
        st.subheader("Create Student Profile")
        with st.form("student_profile_form", clear_on_submit=False):
            name = st.text_input("Student Name *", placeholder="e.g. Sanika Palande")
            course = st.text_input("Course / Program *", placeholder="e.g. Computer Engineering")
            semester = st.text_input("Semester / Year *", placeholder="e.g. 5")
            exam_date = st.date_input("Exam Date * (Mandatory)", min_value=date.today())
            daily_hours = st.slider("Daily Study Hours *", min_value=1.0, max_value=12.0, value=3.0, step=0.5)

            st.markdown("---")
            st.markdown("**Initial Subject Details**")
            subject_name = st.text_input("Primary Subject Name *", placeholder="e.g. Database Management Systems")
            subject_code = st.text_input("Subject Code (Optional)", placeholder="e.g. CS501")

            submitted = st.form_submit_button("Save & Proceed to Syllabus Upload ➡️", use_container_width=True)

            if submitted:
                if not name.strip() or not course.strip() or not semester.strip() or not subject_name.strip():
                    st.error("Please fill in all mandatory fields (Name, Course, Semester, Exam Date, Subject Name).")
                else:
                    exam_date_str = exam_date.strftime("%Y-%m-%d")
                    sid = database.create_student(name, course, semester, exam_date_str, daily_hours)
                    sub_id = database.create_subject(sid, subject_name, subject_code)
                    st.session_state.current_student_id = sid
                    st.session_state.current_subject_id = sub_id
                    st.session_state.active_nav_page = "Syllabus"
                    st.success(f"Profile created for {name}! Moving to Syllabus Upload...")
                    st.rerun()

    with col2:
        st.subheader("Or Continue with Existing Profile")
        if existing_students:
            student_options = {
                f"{s['name']} ({s['course']} - Sem {s['semester']})": s["id"]
                for s in existing_students
            }
            selected_label = st.selectbox("Select Existing Student", list(student_options.keys()))
            if st.button("Load Profile & Continue", use_container_width=True):
                selected_id = student_options[selected_label]
                st.session_state.current_student_id = selected_id
                subjects = database.get_subjects_by_student(selected_id)
                if subjects:
                    st.session_state.current_subject_id = subjects[0]["id"]
                st.session_state.active_nav_page = "Dashboard"
                st.rerun()
        else:
            st.info("No saved profiles found. Please create your profile on the left to get started.")


# -------------------------------------------------------------
# SCREEN 2: UPLOAD SYLLABUS
# -------------------------------------------------------------
def render_syllabus_page(student: dict, subject: dict):
    st.title("📄 Upload & Analyze Syllabus")
    st.markdown(f"**Student:** {student['name']} | **Subject:** {subject['name']}")

    existing_syllabus = database.get_syllabus_by_subject(subject["id"])
    existing_topics = database.get_topics_by_subject(subject["id"])

    col1, col2 = st.columns([1, 1.2])

    with col1:
        st.subheader("Upload Document")
        uploaded_file = st.file_uploader(
            "Upload Syllabus File (.pdf, .docx, .txt)",
            type=["pdf", "docx", "txt"]
        )

        raw_text = ""
        if uploaded_file:
            try:
                raw_text = pdf_reader.extract_text_from_file(uploaded_file, uploaded_file.name)
                st.success(f"Extracted {len(raw_text)} characters from '{uploaded_file.name}'.")
                with st.expander("Preview Extracted Raw Text"):
                    st.text_area("Extracted Text", raw_text, height=200, disabled=True)
            except Exception as e:
                st.error(f"Error reading file: {str(e)}")

        analyze_btn = st.button("🔍 Analyze Syllabus & Extract Topics", type="primary", use_container_width=True)

        if analyze_btn:
            if not raw_text:
                st.error("Please upload a valid syllabus document first.")
            else:
                with st.spinner("AI Agent is parsing units, topics, difficulty, and exam weightage..."):
                    try:
                        result = syllabus_analyzer.analyze_and_store_syllabus(
                            subject_id=subject["id"],
                            file_name=uploaded_file.name,
                            raw_text=raw_text
                        )
                        st.success(f"Successfully extracted {result.get('stored_topics_count', 0)} topics across units!")
                        st.session_state.active_nav_page = "Diagnostic Test"
                        st.rerun()
                    except ai_service.AIServiceError as e:
                        st.error(f"AI Service Notice: {str(e)}")
                        st.info("Ensure your AI_API_KEY is configured in the Settings page.")
                    except Exception as e:
                        st.error(f"Analysis failed: {str(e)}")

    with col2:
        st.subheader("Extracted Curriculum Tree")
        if existing_topics:
            # Reconstruct unit hierarchy
            units_map = {}
            for t in existing_topics:
                u_num = t.get("unit_number", 1)
                u_name = t.get("unit_name", f"Unit {u_num}")
                if u_num not in units_map:
                    units_map[u_num] = {"unit_number": u_num, "unit_name": u_name, "topics": []}
                units_map[u_num]["topics"].append(t)

            tree_output = syllabus_analyzer.format_syllabus_tree(subject["name"], list(units_map.values()))
            st.markdown(f"<div class='syllabus-tree'>{tree_output}</div>", unsafe_allow_html=True)

            st.markdown(f"**Total Topics Extracted:** {len(existing_topics)}")
        else:
            st.info("No syllabus analyzed yet for this subject. Upload your syllabus document to proceed.")


# -------------------------------------------------------------
# SCREEN 3: DIAGNOSTIC TEST
# -------------------------------------------------------------
def render_diagnostic_test(student: dict, subject: dict):
    st.title("🎯 Diagnostic Assessment")
    st.markdown("Take a quick ~10 question diagnostic test covering all units to baseline your knowledge.")

    topics = database.get_topics_by_subject(subject["id"])
    if not topics:
        st.warning("Please upload and analyze your syllabus first so diagnostic questions can be grounded in your topics.")
        if st.button("Go to Syllabus Upload"):
            st.session_state.active_nav_page = "Syllabus"
            st.rerun()
        return

    if not st.session_state.diagnostic_questions:
        if st.button("Generate 10-Question Diagnostic Test", type="primary"):
            with st.spinner("Generating syllabus-grounded diagnostic questions..."):
                try:
                    questions = question_generator.generate_diagnostic_test(
                        subject_id=subject["id"],
                        student_id=student["id"],
                        count=10
                    )
                    st.session_state.diagnostic_questions = questions
                    st.rerun()
                except ai_service.AIServiceError as e:
                    st.error(f"AI Service Error: {str(e)}")
                except Exception as e:
                    st.error(f"Failed to generate questions: {str(e)}")
        return

    # Render active diagnostic form
    questions = st.session_state.diagnostic_questions
    st.info(f"Answer the following {len(questions)} diagnostic questions.")

    with st.form("diagnostic_test_form"):
        user_answers = {}
        for idx, q in enumerate(questions, start=1):
            st.markdown(f"**Q{idx} ({q['difficulty']} | {q['unit_name']}): {q['question_text']}**")
            q_type = q.get("question_type", "MCQ")

            if q_type == "MCQ" and q.get("options"):
                user_answers[q["id"]] = st.radio(
                    f"Select answer for Q{idx}",
                    options=q["options"],
                    key=f"diag_{q['id']}",
                    label_visibility="collapsed"
                )
            elif q_type == "True/False":
                user_answers[q["id"]] = st.radio(
                    f"Select answer for Q{idx}",
                    options=["True", "False"],
                    key=f"diag_{q['id']}",
                    label_visibility="collapsed"
                )
            else:
                user_answers[q["id"]] = st.text_area(
                    f"Write concise answer for Q{idx}",
                    key=f"diag_{q['id']}",
                    height=70,
                    placeholder="Enter key concepts or definition..."
                )
            st.markdown("---")

        submit_diag = st.form_submit_button("Submit Diagnostic Test 🚀", type="primary", use_container_width=True)

        if submit_diag:
            with st.spinner("Evaluating responses and grading semantically..."):
                correct_count = 0
                total = len(questions)

                for q in questions:
                    student_ans = user_answers.get(q["id"], "").strip()
                    correct_ans = q["correct_answer"]
                    q_type = q.get("question_type", "MCQ")

                    # Semantic evaluation
                    try:
                        eval_res = ai_service.analyze_answer(
                            question_text=q["question_text"],
                            correct_answer=correct_ans,
                            student_answer=student_ans,
                            question_type=q_type
                        )
                    except Exception:
                        is_match = student_ans.lower() == correct_ans.lower()
                        eval_res = {
                            "status": "Correct" if is_match else "Incorrect",
                            "score": 1.0 if is_match else 0.0,
                            "what_was_correct": "Correct" if is_match else "",
                            "what_was_missing": "" if is_match else f"Correct answer: {correct_ans}",
                            "what_should_be_improved": ""
                        }

                    is_correct_flag = 1 if eval_res.get("status") == "Correct" else 0
                    score_val = float(eval_res.get("score", 0.0))
                    if is_correct_flag:
                        correct_count += 1
                    else:
                        # Log mistake
                        mistake_memory.log_student_mistake(
                            student_id=student["id"],
                            subject_id=subject["id"],
                            topic_id=q["topic_id"],
                            question_text=q["question_text"],
                            student_answer=student_ans,
                            correct_answer=correct_ans
                        )

                    feedback_text = (
                        f"Status: {eval_res.get('status')}. "
                        f"Correct: {eval_res.get('what_was_correct', '')}. "
                        f"Missing: {eval_res.get('what_was_missing', '')}"
                    )

                    database.record_attempt(
                        student_id=student["id"],
                        question_id=q["id"],
                        student_answer=student_ans,
                        is_correct=is_correct_flag,
                        score=score_val,
                        feedback=feedback_text,
                        attempt_type="diagnostic"
                    )

                st.session_state.diagnostic_questions = []
                acc = round((correct_count / total) * 100.0, 1)
                st.success(f"Diagnostic Test Complete! Baseline Score: {acc}% ({correct_count}/{total})")
                st.session_state.active_nav_page = "Dashboard"
                st.rerun()


# -------------------------------------------------------------
# SCREEN 4: DASHBOARD & NEXT BEST ACTION
# -------------------------------------------------------------
def render_dashboard(student: dict, subject: dict):
    days_rem = utils.get_days_remaining(student["exam_date"])

    # Hero Banner
    st.markdown(f"""
        <div class='main-header'>
            <h2>👋 Welcome back, {student['name']}</h2>
            <p><strong>Course:</strong> {student['course']} | <strong>Semester:</strong> {student['semester']} |
               <strong>Subject:</strong> {subject['name']} | <strong>Exam Date:</strong> {student['exam_date']}
               <span style='background: #EF4444; color: white; padding: 2px 10px; border-radius: 12px; margin-left: 10px; font-weight: bold;'>
               ⏳ {days_rem} Days Remaining
               </span>
            </p>
        </div>
    """, unsafe_allow_html=True)

    # 1. AI Next Best Action Section (Section 7)
    agent_decision = agent.get_agent_decision(student["id"], subject_id=subject["id"])
    st.markdown(f"""
        <div class='action-card'>
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <h3 style='margin: 0; color: #1E3A8A;'>🤖 AI Next Best Action</h3>
                <span class='badge badge-high'>{agent_decision.get('action_code', 'NEXT_STEP')}</span>
            </div>
            <p style='margin-top: 0.5rem; font-size: 1.1rem; color: #1E293B;'>
                <strong>Weak / Focus Area:</strong> {agent_decision.get('weak_topic_highlight', 'N/A')} &nbsp;|&nbsp;
                <strong>Signal:</strong> {agent_decision.get('repeated_mistake_highlight', 'N/A')}
            </p>
            <h4 style='color: #2563EB; margin: 0.5rem 0;'>👉 {agent_decision.get('recommended_action_title', 'Take Next Step')}</h4>
            <p style='color: #475569;'>{agent_decision.get('action_desc', '')}</p>
            <p style='color: #64748B; font-size: 0.85rem; font-style: italic;'><strong>Agent Rationale:</strong> {agent_decision.get('reasoning', '')}</p>
        </div>
    """, unsafe_allow_html=True)

    # Quick action button from Agent Decision
    btn_label = agent_decision.get("button_label", "Proceed to Recommended Activity")
    target_page = agent_decision.get("target_page", "Practice Test")
    if st.button(f"⚡ {btn_label}", type="primary"):
        st.session_state.active_nav_page = target_page
        st.rerun()

    st.markdown("---")

    # 2. Key Metrics Row
    perf_summary = performance_analyzer.get_student_performance_summary(student["id"], subject_id=subject["id"])

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f"""
            <div class='metric-card'>
                <div style='color: #64748B; font-size: 0.9rem;'>Syllabus Coverage</div>
                <div style='font-size: 1.8rem; font-weight: 700; color: #1E3A8A;'>{perf_summary['coverage_percentage']}%</div>
                <div style='color: #94A3B8; font-size: 0.8rem;'>{perf_summary['attempted_topics']}/{perf_summary['total_topics']} Topics</div>
            </div>
        """, unsafe_allow_html=True)
    with m2:
        st.markdown(f"""
            <div class='metric-card'>
                <div style='color: #64748B; font-size: 0.9rem;'>Overall Accuracy</div>
                <div style='font-size: 1.8rem; font-weight: 700; color: #10B981;'>{perf_summary['overall_accuracy']}%</div>
                <div style='color: #94A3B8; font-size: 0.8rem;'>{perf_summary['correct_attempts']}/{perf_summary['total_attempts']} Questions</div>
            </div>
        """, unsafe_allow_html=True)
    with m3:
        st.markdown(f"""
            <div class='metric-card'>
                <div style='color: #64748B; font-size: 0.9rem;'>Weak Topics (< 50%)</div>
                <div style='font-size: 1.8rem; font-weight: 700; color: #EF4444;'>{len(perf_summary['weak_topics'])}</div>
                <div style='color: #94A3B8; font-size: 0.8rem;'>High Priority Remediation</div>
            </div>
        """, unsafe_allow_html=True)
    with m4:
        st.markdown(f"""
            <div class='metric-card'>
                <div style='color: #64748B; font-size: 0.9rem;'>Mastered Topics (> 75%)</div>
                <div style='font-size: 1.8rem; font-weight: 700; color: #3B82F6;'>{len(perf_summary['strong_topics'])}</div>
                <div style='color: #94A3B8; font-size: 0.8rem;'>Exam Ready</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 3. Charts Row
    c1, c2 = st.columns([1, 1])

    with c1:
        st.plotly_chart(utils.create_readiness_gauge(perf_summary["preparation_readiness"]), use_container_width=True)

    with c2:
        mistake_stats = mistake_memory.get_mistake_analytics(student["id"])
        st.plotly_chart(utils.create_mistake_donut_chart(mistake_stats["type_breakdown"]), use_container_width=True)

    # 4. Topic Accuracy Breakdown
    all_studied = perf_summary["strong_topics"] + perf_summary["moderate_topics"] + perf_summary["weak_topics"]
    if all_studied:
        st.plotly_chart(utils.create_topic_accuracy_chart(all_studied), use_container_width=True)

    # 5. Weak Topics List
    if perf_summary["weak_topics"]:
        st.subheader("⚠️ Priority Weak Topics")
        weak_df = pd.DataFrame(perf_summary["weak_topics"])[["topic_name", "unit_name", "importance", "accuracy", "total_attempts"]]
        weak_df.columns = ["Topic", "Unit", "Importance", "Accuracy (%)", "Attempts"]
        st.dataframe(weak_df, use_container_width=True)


# -------------------------------------------------------------
# SCREEN 5: PRACTICE TEST
# -------------------------------------------------------------
def render_practice_test(student: dict, subject: dict):
    st.title("✍️ Practice Questions")
    topics = database.get_topics_by_subject(subject["id"])
    if not topics:
        st.info("Please upload a syllabus first.")
        return

    topic_map = {f"Unit {t.get('unit_number', 1)}: {t['topic_name']} ({t.get('importance', 'Med')} Priority)": t for t in topics}
    selected_label = st.selectbox("Select Topic to Practice", list(topic_map.keys()))
    selected_topic = topic_map[selected_label]

    # Compute current topic accuracy for adaptive guidance
    conn = database.get_db_connection()
    p_row = conn.execute("SELECT accuracy FROM performance WHERE student_id = ? AND topic_id = ?",
                         (student["id"], selected_topic["id"])).fetchone()
    conn.close()

    current_acc = p_row["accuracy"] if p_row else None
    if current_acc is None:
        rec_diff = "Easy"
        diff_info = "No attempts yet → Starting with Easy foundational questions."
    elif current_acc < 50.0:
        rec_diff = "Easy"
        diff_info = f"Current accuracy {current_acc}% (< 50%) → Adapted to Easy questions."
    elif current_acc <= 75.0:
        rec_diff = "Medium"
        diff_info = f"Current accuracy {current_acc}% (50-75%) → Adapted to Medium standard questions."
    else:
        rec_diff = "Hard"
        diff_info = f"Current accuracy {current_acc}% (> 75%) → Adapted to Hard challenging questions."

    st.info(f"🎯 **Adaptive Difficulty Suggestion:** {diff_info}")

    col1, col2, col3 = st.columns(3)
    with col1:
        diff = st.selectbox("Difficulty", ["Easy", "Medium", "Hard"], index=["Easy", "Medium", "Hard"].index(rec_diff))
    with col2:
        q_type = st.selectbox("Question Type", ["MCQ", "True/False", "Short Answer", "Conceptual"])
    with col3:
        q_count = st.slider("Question Count", min_value=1, max_value=10, value=3)

    if st.button("Generate Questions for Topic", type="primary"):
        with st.spinner("Generating syllabus-grounded questions..."):
            try:
                qs = question_generator.generate_practice_questions_for_topic(
                    topic_id=selected_topic["id"],
                    subject_name=subject["name"],
                    question_type=q_type,
                    difficulty=diff,
                    count=q_count
                )
                st.session_state.practice_questions = qs
                st.rerun()
            except ai_service.AIServiceError as e:
                st.error(f"AI Service Error: {str(e)}")
            except Exception as e:
                st.error(f"Generation failed: {str(e)}")

    if st.session_state.practice_questions:
        st.markdown("---")
        st.subheader("Active Practice Set")

        with st.form("practice_form"):
            answers = {}
            for idx, q in enumerate(st.session_state.practice_questions, start=1):
                st.markdown(f"**Q{idx} ({q['difficulty']}): {q['question_text']}**")
                if q["question_type"] == "MCQ" and q.get("options"):
                    answers[q["id"]] = st.radio(f"Answer Q{idx}", q["options"], key=f"prac_{q['id']}", label_visibility="collapsed")
                elif q["question_type"] == "True/False":
                    answers[q["id"]] = st.radio(f"Answer Q{idx}", ["True", "False"], key=f"prac_{q['id']}", label_visibility="collapsed")
                else:
                    answers[q["id"]] = st.text_area(f"Answer Q{idx}", key=f"prac_{q['id']}", height=80)
                st.markdown("---")

            sub_prac = st.form_submit_button("Submit & Grade Practice Set", type="primary", use_container_width=True)

            if sub_prac:
                with st.spinner("Grading answers and updating Mistake Memory..."):
                    for q in st.session_state.practice_questions:
                        stu_ans = answers.get(q["id"], "").strip()
                        eval_res = ai_service.analyze_answer(
                            question_text=q["question_text"],
                            correct_answer=q["correct_answer"],
                            student_answer=stu_ans,
                            question_type=q["question_type"]
                        )

                        is_correct = 1 if eval_res.get("status") == "Correct" else 0
                        score_val = float(eval_res.get("score", 0.0))

                        if not is_correct:
                            mistake_memory.log_student_mistake(
                                student_id=student["id"],
                                subject_id=subject["id"],
                                topic_id=q["topic_id"],
                                question_text=q["question_text"],
                                student_answer=stu_ans,
                                correct_answer=q["correct_answer"]
                            )

                        fb = (
                            f"Result: {eval_res.get('status')}. "
                            f"What was correct: {eval_res.get('what_was_correct', '')}. "
                            f"Missing: {eval_res.get('what_was_missing', '')}. "
                            f"Improvement: {eval_res.get('what_should_be_improved', '')}"
                        )

                        database.record_attempt(
                            student_id=student["id"],
                            question_id=q["id"],
                            student_answer=stu_ans,
                            is_correct=is_correct,
                            score=score_val,
                            feedback=fb,
                            attempt_type="practice"
                        )

                        # Render feedback card
                        if is_correct:
                            st.success(f"✅ Q: {q['question_text']}\n\n{fb}")
                        else:
                            st.error(f"❌ Q: {q['question_text']}\n\n{fb}\n\n**Reference Answer:** {q['correct_answer']}")

                    st.session_state.practice_questions = []
                    st.success("Performance and Mistake Memory updated!")


# -------------------------------------------------------------
# SCREEN 6: TOPIC EXPLANATION & REVISION
# -------------------------------------------------------------
def render_explanation_revision(student: dict, subject: dict):
    st.title("📖 Topic Explanation & Quick Revision")
    topics = database.get_topics_by_subject(subject["id"])
    if not topics:
        st.info("Please upload a syllabus first.")
        return

    topic_map = {f"Unit {t.get('unit_number', 1)}: {t['topic_name']}": t for t in topics}
    selected_label = st.selectbox("Select Topic", list(topic_map.keys()))
    topic = topic_map[selected_label]

    tab1, tab2 = st.tabs(["📚 In-Depth Notes & Explanation", "⚡ Quick Revision & Flashcards"])

    with tab1:
        if st.button("Generate Detailed Notes", type="primary"):
            with st.spinner("Generating structured notes from curriculum..."):
                try:
                    notes = ai_service.explain_topic(
                        topic_name=topic["topic_name"],
                        unit_name=topic.get("unit_name", ""),
                        subject_name=subject["name"]
                    )
                    st.session_state["cached_notes"] = notes
                except Exception as e:
                    st.error(f"Failed to generate notes: {str(e)}")

        if "cached_notes" in st.session_state:
            n = st.session_state["cached_notes"]
            st.markdown(f"### {topic['topic_name']}")
            st.info(f"**Definition:** {n.get('definition', '')}")

            st.markdown("#### 🔑 Key Concepts")
            for c in n.get("key_concepts", []):
                st.markdown(f"- {c}")

            st.markdown("#### 💡 Intuitive Explanation")
            st.write(n.get("simple_explanation", ""))

            st.markdown("#### 🌍 Real-World Examples")
            for ex in n.get("examples", []):
                st.markdown(f"- {ex}")

            st.markdown("#### ⚠️ Exam-Oriented Notes & Pitfalls")
            st.warning(n.get("exam_oriented_notes", ""))

    with tab2:
        if st.button("Generate Revision Flashcards", type="primary"):
            with st.spinner("Generating flashcards and quick formulas..."):
                try:
                    rev = ai_service.generate_revision_materials(
                        topic_name=topic["topic_name"],
                        unit_name=topic.get("unit_name", ""),
                        subject_name=subject["name"]
                    )
                    st.session_state["cached_rev"] = rev
                except Exception as e:
                    st.error(f"Failed to generate revision material: {str(e)}")

        if "cached_rev" in st.session_state:
            r = st.session_state["cached_rev"]

            st.markdown("#### 🃏 Interactive Flashcards")
            flashcards = r.get("flashcards", [])
            for idx, fc in enumerate(flashcards, start=1):
                with st.expander(f"🎴 Card {idx}: {fc.get('front', 'Prompt')}"):
                    st.markdown(f"**Answer / Concept:**\n\n{fc.get('back', '')}")

            st.markdown("#### 📌 Key Definitions")
            for kd in r.get("key_definitions", []):
                st.markdown(f"- **{kd.get('term')}**: {kd.get('definition')}")


# -------------------------------------------------------------
# SCREEN 7: TEXT-BASED AI VIVA
# -------------------------------------------------------------
def render_ai_viva(student: dict, subject: dict):
    st.title("🎙️ AI Viva Examiner (Text-Based Oral Exam)")
    st.markdown("Engage in a rigorous, multi-turn viva where the examiner evaluates your answers and asks dynamic follow-up questions.")

    topics = database.get_topics_by_subject(subject["id"])
    if not topics:
        st.info("Please upload a syllabus first.")
        return

    topic_map = {f"Unit {t.get('unit_number', 1)}: {t['topic_name']}": t for t in topics}
    selected_label = st.selectbox("Select Viva Topic", list(topic_map.keys()))
    topic = topic_map[selected_label]

    if st.session_state.viva_state is None:
        if st.button("Start Viva Session 🚀", type="primary"):
            with st.spinner("Examiner is formulating the opening question..."):
                try:
                    v_state = viva.start_viva_session(student["id"], topic["id"])
                    st.session_state.viva_state = v_state
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to initialize viva: {str(e)}")
        return

    # Active Viva Session
    v_state = st.session_state.viva_state

    # Prior turns
    for t in v_state.get("turns", []):
        st.markdown(f"**👨‍🏫 Examiner (Turn {t['turn']}):** {t['question']}")
        st.markdown(f"**🧑‍🎓 Your Answer:** {t['answer']}")
        st.markdown(f"*Score: {t['score']}/10* | *Feedback: {t['feedback']}*")
        st.markdown("---")

    if not v_state["is_concluded"]:
        st.markdown(f"### 👨‍🏫 Examiner's Current Question (Turn {v_state['turn_count']}/{v_state['max_turns']}):")
        st.info(v_state["current_question"])

        with st.form("viva_answer_form"):
            viva_answer = st.text_area("Your Oral Response (Type your explanation):", height=120)
            submit_turn = st.form_submit_button("Submit Response to Examiner", type="primary")

            if submit_turn:
                if not viva_answer.strip():
                    st.warning("Please type your response before submitting.")
                else:
                    with st.spinner("Examiner is evaluating your answer and formulating follow-up..."):
                        updated_state = viva.process_viva_answer(v_state, viva_answer)
                        st.session_state.viva_state = updated_state
                        st.rerun()
    else:
        st.success(f"🎉 Viva Session Concluded! Overall Examiner Score: {v_state['overall_score']}/10")
        st.info(f"**Examiner Appraisal:** {v_state['final_feedback']}")
        if st.button("Start Another Viva Session"):
            st.session_state.viva_state = None
            st.rerun()


# -------------------------------------------------------------
# SCREEN 8: MOCK TEST (WITH TIMER)
# -------------------------------------------------------------
def render_mock_test(student: dict, subject: dict):
    st.title("⏱️ Full-Length Timed Mock Exam")
    st.markdown("Simulate realistic exam conditions covering your entire uploaded syllabus.")

    if st.session_state.mock_test_state is None:
        col1, col2, col3 = st.columns(3)
        with col1:
            q_count = st.selectbox("Total Questions", [10, 15, 20, 25], index=0)
        with col2:
            difficulty = st.selectbox("Difficulty Mix", ["Mixed", "Easy", "Medium", "Hard"])
        with col3:
            duration_mins = st.selectbox("Time Limit", [15, 30, 45, 60], index=0)

        if st.button("Generate & Begin Mock Exam 📝", type="primary"):
            with st.spinner("Drafting full syllabus exam paper..."):
                try:
                    paper = question_generator.generate_mock_test_paper(
                        subject_id=subject["id"],
                        count=q_count,
                        difficulty=difficulty
                    )
                    st.session_state.mock_test_state = {
                        "paper": paper,
                        "duration_secs": duration_mins * 60,
                        "start_time": time.time(),
                        "submitted": False,
                        "result": None
                    }
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to generate mock test: {str(e)}")
        return

    # Active Test
    m_state = st.session_state.mock_test_state
    if not m_state["submitted"]:
        elapsed = int(time.time() - m_state["start_time"])
        rem_secs = max(0, m_state["duration_secs"] - elapsed)
        mins, secs = divmod(rem_secs, 60)

        st.markdown(f"<div class='timer-banner'>⏳ TIME REMAINING: {mins:02d}:{secs:02d}</div>", unsafe_allow_html=True)

        with st.form("mock_exam_form"):
            answers = {}
            for idx, q in enumerate(m_state["paper"], start=1):
                st.markdown(f"**Q{idx} ({q['difficulty']} | {q['topic_name']}): {q['question_text']}**")
                if q["question_type"] == "MCQ" and q.get("options"):
                    answers[q["id"]] = st.radio(f"Select Q{idx}", q["options"], key=f"mock_{q['id']}", label_visibility="collapsed")
                elif q["question_type"] == "True/False":
                    answers[q["id"]] = st.radio(f"Select Q{idx}", ["True", "False"], key=f"mock_{q['id']}", label_visibility="collapsed")
                else:
                    answers[q["id"]] = st.text_area(f"Write answer Q{idx}", key=f"mock_{q['id']}", height=80)
                st.markdown("---")

            submit_mock = st.form_submit_button("Submit Mock Exam Paper", type="primary", use_container_width=True)

            if submit_mock or rem_secs <= 0:
                with st.spinner("Evaluating mock exam paper..."):
                    score_total = 0.0
                    total_q = len(m_state["paper"])
                    for q in m_state["paper"]:
                        stu_ans = answers.get(q["id"], "").strip()
                        eval_res = ai_service.analyze_answer(q["question_text"], q["correct_answer"], stu_ans, q["question_type"])
                        score_val = float(eval_res.get("score", 0.0))
                        score_total += score_val

                        is_correct = 1 if eval_res.get("status") == "Correct" else 0
                        if not is_correct:
                            mistake_memory.log_student_mistake(
                                student_id=student["id"],
                                subject_id=subject["id"],
                                topic_id=q["topic_id"],
                                question_text=q["question_text"],
                                student_answer=stu_ans,
                                correct_answer=q["correct_answer"]
                            )

                        database.record_attempt(
                            student_id=student["id"],
                            question_id=q["id"],
                            student_answer=stu_ans,
                            is_correct=is_correct,
                            score=score_val,
                            feedback=f"{eval_res.get('status')}: {eval_res.get('what_was_correct', '')}",
                            attempt_type="mock"
                        )

                    acc = round((score_total / total_q) * 100.0, 1)
                    time_spent = int(time.time() - m_state["start_time"])
                    database.save_mock_test_result(student["id"], subject["id"], total_q, score_total, acc, time_spent)

                    m_state["submitted"] = True
                    m_state["result"] = {"score": score_total, "total": total_q, "accuracy": acc, "time_spent": time_spent}
                    st.rerun()
    else:
        res = m_state["result"]
        st.success(f"🎉 Mock Exam Completed! Score: {res['score']}/{res['total']} ({res['accuracy']}%)")
        st.info(f"Time Taken: {res['time_spent'] // 60}m {res['time_spent'] % 60}s")
        if st.button("Take Another Mock Exam"):
            st.session_state.mock_test_state = None
            st.rerun()


# -------------------------------------------------------------
# SCREEN 9: WEAK TOPICS & MISTAKE MEMORY
# -------------------------------------------------------------
def render_mistake_memory_page(student: dict, subject: dict):
    st.title("🧠 Mistake Memory & Targeted Remediation")
    st.markdown("All incorrect answers are logged here with cognitive categorization to prevent repeating errors.")

    analytics = mistake_memory.get_mistake_analytics(student["id"])

    col1, col2 = st.columns([1, 1.2])
    with col1:
        st.plotly_chart(utils.create_mistake_donut_chart(analytics["type_breakdown"]), use_container_width=True)
    with col2:
        st.subheader("Top Repeated Mistake Topics")
        if analytics["repeated_topics"]:
            for rt in analytics["repeated_topics"]:
                st.markdown(f"- **{rt['topic_name']}**: {rt['mistake_count']} error(s) logged")
        else:
            st.success("No repeated errors detected. Excellent retention!")

    st.markdown("---")
    st.subheader("Mistake Ledger")

    mistakes = analytics["recent_mistakes"]
    if not mistakes:
        st.info("No recorded mistakes yet. Complete practice sessions or diagnostic tests to populate.")
        return

    for m in mistakes:
        with st.expander(f"❌ {m['topic_name']} — [{m['mistake_type']}] on {m['created_at'][:10]}"):
            st.markdown(f"**Question:** {m['question_text']}")
            st.markdown(f"**Your Answer:** `{m['student_answer']}`")
            st.markdown(f"**Correct Answer:** `{m['correct_answer']}`")

            if st.button(f"Generate Targeted Fix for #{m['id']}", key=f"rem_{m['id']}"):
                with st.spinner("AI is analyzing the misconception..."):
                    try:
                        rem = mistake_memory.generate_targeted_remediation(m["id"])
                        st.info(f"**Core Misconception:** {rem.get('core_misconception')}")
                        st.success(f"**Rule to Remember:** {rem.get('correct_rule')}")
                        st.markdown(f"**Memory Hook:** {rem.get('memory_hook')}")
                    except Exception as e:
                        st.error(f"Remediation error: {str(e)}")


# -------------------------------------------------------------
# SCREEN 10: PERSONALIZED STUDY PLANNER
# -------------------------------------------------------------
def render_study_planner_page(student: dict, subject: dict):
    st.title("📅 Personalized Study Planner")
    st.markdown("Automated timetable prioritizing weak and high-importance topics based on your remaining days.")

    plan_items = database.get_study_plan_by_student(student["id"])

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Generate / Refresh Study Plan ⚡", type="primary"):
            with st.spinner("Building optimal schedule based on weak topics and exam date..."):
                try:
                    plan_items = study_planner.generate_study_plan(student["id"], subject_id=subject["id"])
                    st.success("Study plan successfully generated!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Planning error: {str(e)}")

    if not plan_items:
        st.info("No study schedule generated yet. Click 'Generate Study Plan' to create your timetable.")
        return

    st.markdown("---")
    st.subheader("Your Dynamic Schedule")

    for item in plan_items:
        status_color = "#10B981" if item["status"] == "completed" else ("#EF4444" if item["status"] == "missed" else "#3B82F6")
        status_label = item["status"].upper()

        with st.container():
            c1, c2, c3 = st.columns([2.5, 1, 1.2])
            with c1:
                st.markdown(f"**{item['plan_date']} | {item['time_slot']}**")
                st.markdown(f"📖 **{item['topic_name']}** — *{item['notes']}*")
            with c2:
                st.markdown(f"<span style='color: {status_color}; font-weight: bold;'>[{status_label}]</span>", unsafe_allow_html=True)
            with c3:
                if item["status"] == "pending":
                    b1, b2 = st.columns(2)
                    with b1:
                        if st.button("✅ Done", key=f"done_{item['id']}"):
                            study_planner.mark_plan_completed(item["id"])
                            st.rerun()
                    with b2:
                        if st.button("⏭️ Missed", key=f"miss_{item['id']}"):
                            next_slot_date = study_planner.reschedule_missed_topic(item["id"])
                            st.warning(f"Slot moved non-destructively to {next_slot_date}")
                            st.rerun()
            st.markdown("---")


# -------------------------------------------------------------
# SCREEN 11: PERFORMANCE & SETTINGS
# -------------------------------------------------------------
def render_performance_page(student: dict, subject: dict):
    st.title("📊 Detailed Performance Analytics")
    perf = performance_analyzer.get_student_performance_summary(student["id"], subject_id=subject["id"])

    st.plotly_chart(utils.create_readiness_gauge(perf["preparation_readiness"]), use_container_width=True)

    trends = performance_analyzer.get_performance_trends(student["id"])
    st.plotly_chart(utils.create_progress_timeline(trends), use_container_width=True)

    all_studied = perf["strong_topics"] + perf["moderate_topics"] + perf["weak_topics"]
    if all_studied:
        st.plotly_chart(utils.create_topic_accuracy_chart(all_studied), use_container_width=True)


def render_settings_page(student: dict, subject: dict):
    st.title("⚙️ Settings & Configuration")

    st.subheader("1. AI Provider & API Key")
    current_cfg = ai_service.get_ai_config()

    with st.form("ai_settings_form"):
        provider = st.selectbox(
            "AI Provider",
            options=["gemini", "openai"],
            index=0 if current_cfg["provider"] == "gemini" else 1
        )
        api_key = st.text_input(
            "AI API Key",
            value=current_cfg["api_key"],
            type="password",
            help="Your key is never hardcoded and is used only during this session or saved in .env"
        )
        save_ai = st.form_submit_button("Save AI Configuration")

        if save_ai:
            os.environ["AI_PROVIDER"] = provider
            os.environ["AI_API_KEY"] = api_key.strip()
            st.success("AI Configuration updated successfully!")

    st.markdown("---")
    st.subheader("2. Student Profile & Exam Schedule")

    with st.form("profile_settings_form"):
        name = st.text_input("Name", value=student["name"])
        course = st.text_input("Course", value=student["course"])
        semester = st.text_input("Semester", value=student["semester"])
        exam_dt = st.date_input("Exam Date", value=datetime.strptime(student["exam_date"], "%Y-%m-%d").date())
        hours = st.slider("Daily Study Hours", 1.0, 12.0, float(student["daily_study_hours"]), 0.5)

        save_prof = st.form_submit_button("Update Profile Details")
        if save_prof:
            database.update_student(student["id"], name, course, semester, exam_dt.strftime("%Y-%m-%d"), hours)
            st.success("Profile updated successfully!")
            st.rerun()

    st.markdown("---")
    st.subheader("3. Reset Preparation Data")
    st.warning("This clears all attempts, performance, mistakes, and mock tests for this student, allowing a clean restart.")
    if st.button("Reset Preparation Data (Clean Slate)", type="secondary"):
        database.reset_student_preparation(student["id"])
        st.success("All attempts and performance data reset to a clean state.")
        st.rerun()


# -------------------------------------------------------------
# MAIN APPLICATION CONTROLLER & NAVIGATION
# -------------------------------------------------------------
def main():
    # If no student is selected or logged in, show login screen
    if st.session_state.current_student_id is None:
        render_student_login()
        return

    student = database.get_student_by_id(st.session_state.current_student_id)
    if not student:
        st.session_state.current_student_id = None
        st.rerun()
        return

    subjects = database.get_subjects_by_student(student["id"])
    if not subjects:
        sub_id = database.create_subject(student["id"], "General Preparation")
        subjects = database.get_subjects_by_student(student["id"])
        st.session_state.current_subject_id = sub_id
    elif st.session_state.current_subject_id is None:
        st.session_state.current_subject_id = subjects[0]["id"]

    subject = next((s for s in subjects if s["id"] == st.session_state.current_subject_id), subjects[0])

    # ---------------- Sidebar Navigation (Section 11) ----------------
    with st.sidebar:
        st.title("🎓 PrepPilot")
        st.markdown(f"**Student:** {student['name']}")
        days_rem = utils.get_days_remaining(student["exam_date"])
        st.markdown(f"⏳ **Days to Exam:** `{days_rem} days`")

        # Subject Switcher
        if len(subjects) > 1:
            subj_dict = {s["name"]: s["id"] for s in subjects}
            selected_s_name = st.selectbox("Current Subject", list(subj_dict.keys()))
            st.session_state.current_subject_id = subj_dict[selected_s_name]

        st.markdown("---")

        nav_pages = [
            "Dashboard",
            "Syllabus",
            "Diagnostic Test",
            "Practice Test",
            "Topic Explanation",
            "AI Viva",
            "Mock Test",
            "Mistake Memory",
            "Study Planner",
            "Performance",
            "Settings"
        ]

        active_page = st.radio(
            "Navigation",
            options=nav_pages,
            index=nav_pages.index(st.session_state.active_nav_page) if st.session_state.active_nav_page in nav_pages else 0
        )
        st.session_state.active_nav_page = active_page

        st.markdown("---")
        if st.button("Log Out / Switch Student", use_container_width=True):
            st.session_state.current_student_id = None
            st.session_state.current_subject_id = None
            st.rerun()

    # Route to selected page
    if active_page == "Dashboard":
        render_dashboard(student, subject)
    elif active_page == "Syllabus":
        render_syllabus_page(student, subject)
    elif active_page == "Diagnostic Test":
        render_diagnostic_test(student, subject)
    elif active_page == "Practice Test":
        render_practice_test(student, subject)
    elif active_page == "Topic Explanation":
        render_explanation_revision(student, subject)
    elif active_page == "AI Viva":
        render_ai_viva(student, subject)
    elif active_page == "Mock Test":
        render_mock_test(student, subject)
    elif active_page == "Mistake Memory":
        render_mistake_memory_page(student, subject)
    elif active_page == "Study Planner":
        render_study_planner_page(student, subject)
    elif active_page == "Performance":
        render_performance_page(student, subject)
    elif active_page == "Settings":
        render_settings_page(student, subject)


if __name__ == "__main__":
    main()
