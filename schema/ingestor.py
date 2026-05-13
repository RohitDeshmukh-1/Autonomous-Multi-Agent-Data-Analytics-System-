"""
schema/ingestor.py
Crawls connector schema, compresses it, embeds via local sentence-transformers,
and stores in Neon pgvector schema_embeddings table.
Uses connection pool + Redis caching for performance.
"""

import hashlib
import json
import os
import uuid
from functools import lru_cache
from typing import Any, Dict, List

from connectors.base import get_connector
from db.pool import pooled_connection, pooled_cursor
from llm import get_embedder
from schema.compressor import compress_table_schema

# ── In-memory schema cache ────────────────────────────────────────────────────
_schema_cache: Dict[str, List[Dict[str, Any]]] = {}


def _cache_key(connector_id: str, query: str) -> str:
    raw = f"{connector_id}:{query}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def ingest_schema(connector_id: str) -> int:
    """
    Ingest schema from a connector into Neon pgvector.
    Returns number of table embeddings stored.
    """
    connector = get_connector(connector_id)
    tables = connector.get_schema()
    embedder = get_embedder()

    stored = 0
    with pooled_connection() as conn:
        with conn.cursor() as cur:
            # Clear existing embeddings for this connector
            cur.execute(
                "DELETE FROM schema_embeddings WHERE connector_id = %s",
                (connector_id,),
            )

            texts = [compress_table_schema(t) for t in tables]
            embeddings = embedder.embed_batch(texts)

            for table, text, emb in zip(tables, texts, embeddings):
                cur.execute(
                    """
                    INSERT INTO schema_embeddings
                      (id, connector_id, table_name, column_summary, embedding)
                    VALUES (%s, %s, %s, %s, %s::vector)
                    """,
                    (
                        str(uuid.uuid4()),
                        connector_id,
                        table["table"],
                        text,
                        emb,
                    ),
                )
                stored += 1

            conn.commit()

    # Invalidate cache for this connector
    keys_to_remove = [k for k in _schema_cache if k.startswith(connector_id[:16])]
    for k in keys_to_remove:
        _schema_cache.pop(k, None)

    return stored


def get_relevant_tables(
    connector_id: str,
    query: str,
    top_k: int = 4,
) -> List[Dict[str, Any]]:
    """
    Vector search schema_embeddings to find the most relevant tables.
    Falls back to returning all tables if no embeddings exist yet.
    Caches results in-memory per (connector_id, query) to avoid
    redundant embedding API calls.
    """
    cache_key = _cache_key(connector_id, query)
    if cache_key in _schema_cache:
        return _schema_cache[cache_key]

    embedder = get_embedder()
    query_vec = embedder.embed(query)

    with pooled_cursor(readonly=True, dict_cursor=True) as (cur, conn):
        cur.execute(
            """
            SELECT table_name, column_summary,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM schema_embeddings
            WHERE connector_id = %s
            ORDER BY similarity DESC
            LIMIT %s
            """,
            (query_vec, connector_id, top_k),
        )
        rows = cur.fetchall()

    if not rows:
        # No embeddings yet — ingest on-the-fly and retry once
        ingest_schema(connector_id)
        return get_relevant_tables(connector_id, query, top_k)

    # Parse column_summary back into structured form
    result = []
    for row in rows:
        try:
            parsed = json.loads(row["column_summary"])
        except (json.JSONDecodeError, TypeError):
            parsed = {"table": row["table_name"], "columns": []}
        parsed["similarity"] = float(row["similarity"])
        result.append(parsed)

    # Cache the result
    if len(_schema_cache) < 512:
        _schema_cache[cache_key] = result

    return result
