"""
api/routers/metrics.py
GET /api/metrics – observability dashboard data
"""

from fastapi import APIRouter
from agent.metrics import get_metrics_collector

router = APIRouter()


@router.get("/")
async def get_metrics():
    """Return current system metrics (latency, cache, corrections, errors)."""
    collector = get_metrics_collector()
    return collector.get_metrics()
