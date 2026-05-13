"""
reports/generator.py
Generates a PDF report of a session's query history using WeasyPrint + Jinja2.
Uses connection pool for performance.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from db.pool import pooled_cursor
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

TEMPLATE_DIR = Path(__file__).parent / "templates"


def _fetch_session_history(session_id: str) -> List[Dict[str, Any]]:
    with pooled_cursor(readonly=True, dict_cursor=True) as (cur, conn):
        cur.execute(
            """
            SELECT user_query, generated_code, code_type, insight_text,
                   chart_spec, result_preview, retry_count, latency_ms,
                   created_at
            FROM query_history
            WHERE session_id = %s
            ORDER BY created_at ASC
            """,
            (session_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def generate_pdf(
    session_id: str,
    user_id: str,
    title: Optional[str] = None,
) -> bytes:
    history = _fetch_session_history(session_id)
    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("report.html")

    html_str = template.render(
        title=title or f"Analysis Report — {generated_at}",
        session_id=session_id,
        generated_at=generated_at,
        queries=history,
    )

    return HTML(string=html_str, base_url=str(TEMPLATE_DIR)).write_pdf()
