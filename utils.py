"""
utils.py - UI Styling, Helpers, and Plotly Visualizations for PrepPilot
Injects a modern blue-and-white educational theme and generates responsive Plotly charts.
"""

from datetime import datetime
from typing import Dict, Any, List
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st


def get_days_remaining(exam_date_str: str) -> int:
    """Calculates days remaining until exam date (Exam Date - Current Date)."""
    try:
        exam_dt = datetime.strptime(exam_date_str, "%Y-%m-%d").date()
        today = datetime.now().date()
        return (exam_dt - today).days
    except Exception:
        return 0


def inject_custom_css():
    """Injects modern blue-and-white aesthetic styling into Streamlit."""
    st.markdown("""
        <style>
        /* Import clean Inter font */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        /* Top header accent */
        .main-header {
            background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
            color: white;
            padding: 1.5rem 2rem;
            border-radius: 12px;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        }

        /* Clean cards */
        .metric-card {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 10px;
            padding: 1.25rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            transition: transform 0.15s ease-in-out, box-shadow 0.15s ease-in-out;
        }
        .metric-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(30, 58, 138, 0.08);
        }

        /* Action card for Next Best Action */
        .action-card {
            background: linear-gradient(to right, #EFF6FF, #DBEAFE);
            border: 2px solid #3B82F6;
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }

        /* Badges */
        .badge {
            display: inline-block;
            padding: 0.25rem 0.6rem;
            font-size: 0.8rem;
            font-weight: 600;
            border-radius: 9999px;
            text-transform: uppercase;
        }
        .badge-high { background-color: #FEE2E2; color: #DC2626; }
        .badge-med { background-color: #FEF3C7; color: #D97706; }
        .badge-low { background-color: #E0E7FF; color: #4F46E5; }
        .badge-success { background-color: #D1FAE5; color: #059669; }

        /* Tree view formatting */
        .syllabus-tree {
            background-color: #0F172A;
            color: #38BDF8;
            font-family: 'Courier New', Courier, monospace;
            padding: 1.25rem;
            border-radius: 8px;
            white-space: pre-wrap;
            line-height: 1.5;
            font-size: 0.95rem;
            overflow-x: auto;
        }

        /* Flashcard styling */
        .flashcard-box {
            background: white;
            border-left: 5px solid #3B82F6;
            border-radius: 8px;
            padding: 1.2rem;
            margin-bottom: 1rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.06);
        }

        /* Exam timer banner */
        .timer-banner {
            background-color: #1E293B;
            color: #F8FAFC;
            font-weight: 700;
            font-size: 1.3rem;
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            text-align: center;
            letter-spacing: 1px;
            margin-bottom: 1rem;
        }
        </style>
    """, unsafe_allow_html=True)


def create_readiness_gauge(score: float) -> go.Figure:
    """Creates an interactive gauge for Preparation Readiness."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Preparation Readiness", 'font': {'size': 20, 'color': '#1E3A8A'}},
        number={'suffix': "%", 'font': {'size': 36, 'color': '#1E3A8A'}},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "#94A3B8"},
            'bar': {'color': "#2563EB"},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "#E2E8F0",
            'steps': [
                {'range': [0, 50], 'color': '#FEE2E2'},
                {'range': [50, 75], 'color': '#FEF3C7'},
                {'range': [75, 100], 'color': '#D1FAE5'}
            ],
            'threshold': {
                'line': {'color': "#10B981", 'width': 4},
                'thickness': 0.75,
                'value': 85
            }
        }
    ))
    fig.update_layout(
        height=240,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif")
    )
    return fig


def create_topic_accuracy_chart(topic_summaries: List[Dict[str, Any]]) -> go.Figure:
    """Creates a horizontal bar chart displaying topic accuracy with color banding."""
    if not topic_summaries:
        fig = go.Figure()
        fig.add_annotation(text="No topic attempts recorded yet.", showarrow=False, font=dict(size=14))
        fig.update_layout(height=260)
        return fig

    topics = [t["topic_name"] for t in topic_summaries][:15]
    accuracies = [t["accuracy"] for t in topic_summaries][:15]

    colors = []
    for acc in accuracies:
        if acc >= 75.0:
            colors.append("#10B981")  # Green
        elif acc >= 50.0:
            colors.append("#F59E0B")  # Amber
        else:
            colors.append("#EF4444")  # Red

    fig = go.Figure(go.Bar(
        x=accuracies,
        y=topics,
        orientation='h',
        marker=dict(color=colors, line=dict(color='#CBD5E1', width=1)),
        text=[f"{a}%" for a in accuracies],
        textposition="inside"
    ))

    fig.update_layout(
        title="Topic Accuracy Breakdown",
        xaxis=dict(range=[0, 100], title="Accuracy (%)"),
        yaxis=dict(autorange="reversed"),
        height=max(280, len(topics) * 28),
        margin=dict(l=10, r=20, t=40, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )
    return fig


def create_mistake_donut_chart(type_breakdown: List[Dict[str, Any]]) -> go.Figure:
    """Creates a donut chart illustrating distribution of mistake types."""
    filtered = [m for m in type_breakdown if m["count"] > 0]
    if not filtered:
        fig = go.Figure()
        fig.add_annotation(text="No mistakes recorded! Great job.", showarrow=False, font=dict(size=14))
        fig.update_layout(height=240)
        return fig

    labels = [m["type"] for m in filtered]
    values = [m["count"] for m in filtered]

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.55,
        marker=dict(colors=["#EF4444", "#F97316", "#F59E0B", "#8B5CF6", "#06B6D4", "#EC4899"])
    )])

    fig.update_layout(
        title="Mistake Type Distribution",
        height=260,
        margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.0)
    )
    return fig


def create_progress_timeline(trends: List[Dict[str, Any]]) -> go.Figure:
    """Creates a chronological line chart showing accuracy progression."""
    if len(trends) < 2:
        fig = go.Figure()
        fig.add_annotation(text="Complete more practice sessions to plot progress trend.", showarrow=False, font=dict(size=14))
        fig.update_layout(height=240)
        return fig

    dates = [t["attempted_at"] for t in trends]
    # Running accuracy
    running_acc = []
    correct_count = 0
    for idx, t in enumerate(trends, start=1):
        if t.get("is_correct"):
            correct_count += 1
        running_acc.append(round((correct_count / idx) * 100.0, 1))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=running_acc,
        mode='lines+markers',
        name='Cumulative Accuracy',
        line=dict(color='#2563EB', width=3),
        marker=dict(size=6, color='#1E40AF')
    ))

    fig.update_layout(
        title="Accuracy Trend Over Time",
        xaxis_title="Date & Time",
        yaxis_title="Accuracy (%)",
        yaxis=dict(range=[0, 100]),
        height=260,
        margin=dict(l=10, r=20, t=40, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )
    return fig
