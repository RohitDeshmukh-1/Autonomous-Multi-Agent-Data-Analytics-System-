"""
api/routers/dashboard.py
CRUD for dashboards and panels.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from dashboard.storage import (
    create_dashboard,
    list_dashboards,
    save_panel,
    list_panels,
    delete_panel,
)

router = APIRouter()


class DashboardCreate(BaseModel):
    user_id: str
    name: str


class PanelCreate(BaseModel):
    user_id: str
    session_id: str
    title: str
    chart_spec: Dict[str, Any]
    query: str
    dashboard_id: Optional[str] = None


@router.post("/")
async def create_dashboard_endpoint(body: DashboardCreate):
    dash_id = create_dashboard(user_id=body.user_id, name=body.name)
    return {"dashboard_id": dash_id}


@router.get("/{user_id}")
async def list_dashboards_endpoint(user_id: str):
    return list_dashboards(user_id=user_id)


@router.post("/panel")
async def add_panel(body: PanelCreate):
    panel_id = save_panel(
        user_id=body.user_id,
        session_id=body.session_id,
        title=body.title,
        chart_spec=body.chart_spec,
        query=body.query,
        dashboard_id=body.dashboard_id,
    )
    return {"panel_id": panel_id}


@router.get("/panel/{user_id}")
async def list_panels_endpoint(user_id: str, dashboard_id: Optional[str] = None):
    return list_panels(user_id=user_id, dashboard_id=dashboard_id)


@router.delete("/panel/{panel_id}")
async def delete_panel_endpoint(panel_id: str, user_id: str):
    ok = delete_panel(panel_id=panel_id, user_id=user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Panel not found")
    return {"deleted": panel_id}
