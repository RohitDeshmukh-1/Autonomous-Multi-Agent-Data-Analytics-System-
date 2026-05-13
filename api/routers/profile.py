"""
api/routers/profile.py
POST /api/profile – generate data profile for a connector
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent.nodes.data_profiler import profile_connector

router = APIRouter()


class ProfileRequest(BaseModel):
    connector_id: str


@router.post("/")
async def generate_profile(req: ProfileRequest):
    """Generate a comprehensive data profile for a connector."""
    try:
        profile = profile_connector(req.connector_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Profiling failed: {exc}")
    return profile
