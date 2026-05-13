"""
api/routers/schema.py
POST /api/schema/ingest   – manually trigger schema ingestion for a connector
GET  /api/schema/{connector_id} – return schema summary
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from schema.ingestor import ingest_schema
from connectors.base import get_connector

router = APIRouter()


class IngestRequest(BaseModel):
    connector_id: str


@router.post("/ingest")
async def trigger_ingest(req: IngestRequest):
    try:
        n = ingest_schema(req.connector_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"connector_id": req.connector_id, "tables_ingested": n}


@router.get("/{connector_id:path}")
async def get_schema(connector_id: str):
    try:
        connector = get_connector(connector_id)
        schema = connector.get_schema()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"connector_id": connector_id, "tables": schema}
