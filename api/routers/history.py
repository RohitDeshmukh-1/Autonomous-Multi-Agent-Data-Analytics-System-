"""
api/routers/history.py
GET /api/history/{session_id}  – list query history for a session
DELETE /api/history/{history_id}  – delete a single history record
"""

from typing import Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db.pool import pooled_connection, pooled_cursor

router = APIRouter()


class HistoryRecord(BaseModel):
    id: str
    session_id: str
    user_query: str
    code_type: str
    insight_text: Optional[str]
    latency_ms: Optional[int]
    retry_count: Optional[int]
    created_at: str


@router.get("/{session_id}", response_model=List[HistoryRecord])
async def get_history(session_id: str):
    with pooled_cursor(readonly=True, dict_cursor=True) as (cur, conn):
        cur.execute(
            """
            SELECT id, session_id, user_query, code_type, insight_text,
                   latency_ms, retry_count,
                   TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at
            FROM query_history
            WHERE session_id = %s
            ORDER BY created_at DESC
            """,
            (session_id,),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


@router.get("/record/{history_id}")
async def get_history_record(history_id: str):
    with pooled_cursor(readonly=True, dict_cursor=True) as (cur, conn):
        cur.execute(
            "SELECT * FROM query_history WHERE id = %s",
            (history_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Record not found")
    return dict(row)


@router.delete("/{history_id}")
async def delete_history_record(history_id: str):
    with pooled_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM query_history WHERE id = %s", (history_id,))
            deleted = cur.rowcount > 0
            conn.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"deleted": history_id}
