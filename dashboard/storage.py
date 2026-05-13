"""
dashboard/storage.py
Persist and retrieve saved dashboard panels (pinned chart specs) in Neon.
Uses connection pool for performance.
"""

import json
import uuid
from typing import Any, Dict, List, Optional

from db.pool import pooled_connection, pooled_cursor


def save_panel(
    user_id: str,
    session_id: str,
    title: str,
    chart_spec: Dict[str, Any],
    query: str,
    dashboard_id: Optional[str] = None,
) -> str:
    """Pin a chart as a dashboard panel. Returns panel_id."""
    panel_id = str(uuid.uuid4())
    with pooled_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO dashboard_panels
                  (id, user_id, session_id, dashboard_id, title, chart_spec, query)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    panel_id,
                    user_id,
                    session_id,
                    dashboard_id,
                    title,
                    json.dumps(chart_spec),
                    query,
                ),
            )
            conn.commit()
    return panel_id


def list_panels(user_id: str, dashboard_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return all panels for a user, optionally filtered by dashboard."""
    with pooled_cursor(dict_cursor=True) as (cur, conn):
        if dashboard_id:
            cur.execute(
                "SELECT * FROM dashboard_panels WHERE user_id=%s AND dashboard_id=%s ORDER BY created_at DESC",
                (user_id, dashboard_id),
            )
        else:
            cur.execute(
                "SELECT * FROM dashboard_panels WHERE user_id=%s ORDER BY created_at DESC",
                (user_id,),
            )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def delete_panel(panel_id: str, user_id: str) -> bool:
    """Delete a panel. Returns True if deleted."""
    with pooled_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM dashboard_panels WHERE id=%s AND user_id=%s",
                (panel_id, user_id),
            )
            deleted = cur.rowcount > 0
            conn.commit()
    return deleted


def create_dashboard(user_id: str, name: str) -> str:
    """Create a named dashboard container. Returns dashboard_id."""
    dash_id = str(uuid.uuid4())
    with pooled_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO dashboards (id, user_id, name) VALUES (%s, %s, %s)",
                (dash_id, user_id, name),
            )
            conn.commit()
    return dash_id


def list_dashboards(user_id: str) -> List[Dict[str, Any]]:
    with pooled_cursor(dict_cursor=True) as (cur, conn):
        cur.execute(
            "SELECT * FROM dashboards WHERE user_id=%s ORDER BY created_at DESC",
            (user_id,),
        )
        return [dict(r) for r in cur.fetchall()]
