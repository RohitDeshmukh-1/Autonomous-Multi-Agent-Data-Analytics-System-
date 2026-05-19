"""
api/routers/upload.py
POST /api/upload/file  – upload CSV or SQLite, store in Supabase, ingest schema
"""

import io
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from storage.supabase_storage import upload_file
from schema.ingestor import ingest_schema

router = APIRouter()

ALLOWED_TYPES = {
    "text/csv": ("csv", "text/csv"),
    "application/x-sqlite3": ("sqlite", "application/x-sqlite3"),
}

# Extensions that map to sqlite even with a generic content-type
_SQLITE_EXTENSIONS = (".sqlite", ".db")
_CSV_EXTENSIONS = (".csv",)

MAX_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


class UploadResponse(BaseModel):
    connector_id: str
    public_url: str
    file_type: str
    tables_ingested: int


@router.post("/file", response_model=UploadResponse)
async def upload_data_file(
    file: UploadFile = File(...),
    user_id: str = Form(default="anonymous"),
):
    content_type = file.content_type or "application/octet-stream"
    fname = (file.filename or "").lower()

    # Override content-type by extension (browsers often send generic type)
    if fname.endswith(".csv"):
        content_type = "text/csv"
    elif fname.endswith(".sqlite") or fname.endswith(".db"):
        content_type = "application/x-sqlite3"

    if content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {content_type}. Supported: CSV, SQLite",
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 50 MB limit")

    file_kind, mime = ALLOWED_TYPES[content_type]

    # Upload to Supabase Storage
    public_url = upload_file(
        file_bytes=file_bytes,
        filename=fname or f"upload.{file_kind}",
        content_type=mime,
    )

    connector_id = f"{file_kind}:{public_url}"

    # Ingest schema into pgvector
    try:
        n = ingest_schema(connector_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Schema ingestion failed: {exc}")

    return UploadResponse(
        connector_id=connector_id,
        public_url=public_url,
        file_type=file_kind,
        tables_ingested=n,
    )


class DatabaseConnectionRequest(BaseModel):
    url: str
    schema_name: str = "public"


class DatabaseConnectionResponse(BaseModel):
    connector_id: str
    tables_ingested: int
    status: str


@router.post("/connect-db", response_model=DatabaseConnectionResponse)
async def connect_database(req: DatabaseConnectionRequest):
    url = req.url.strip()
    if not url.startswith(("postgresql://", "postgres://")):
        raise HTTPException(
            status_code=400,
            detail="Unsupported protocol. Only standard PostgreSQL/Postgres URIs are supported."
        )

    # Validate connectivity in an isolated read-only cursor
    from connectors.crypto import encrypt_connection_string
    from connectors.neon_connector import NeonConnector

    try:
        connector = NeonConnector(schema=req.schema_name, db_url=url)
        # Test schema fetch to ensure credentials work
        connector.get_schema()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Database connection failed: {e}. Please ensure your database is publicly accessible and credentials are correct."
        )

    encrypted_url = encrypt_connection_string(url)
    connector_id = f"postgres-enc:{encrypted_url}:{req.schema_name}"

    # Ingest schema metadata into the vector search memory safely
    try:
        n = ingest_schema(connector_id)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to index database schemas: {exc}"
        )

    return DatabaseConnectionResponse(
        connector_id=connector_id,
        tables_ingested=n,
        status="connected",
    )
