"""
api/routers/report.py
POST /api/report/generate  – generate and return PDF report for a session
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional

from reports.generator import generate_pdf

router = APIRouter()


class ReportRequest(BaseModel):
    session_id: str
    user_id: str
    title: Optional[str] = None


@router.post("/generate")
async def generate_report(req: ReportRequest):
    try:
        pdf_bytes = generate_pdf(
            session_id=req.session_id,
            user_id=req.user_id,
            title=req.title,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {exc}")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="report-{req.session_id[:8]}.pdf"'
        },
    )
