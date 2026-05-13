"""
agent/nodes/report_exporter.py
Generates PDF report from session history using WeasyPrint + Jinja2.
"""

from agent.state import AgentState
from reports.generator import generate_pdf


def report_exporter(state: AgentState) -> AgentState:
    pdf_bytes = generate_pdf(
        session_id=state["session_id"],
        user_id=state["user_id"],
    )
    return {**state, "report_pdf": pdf_bytes}
