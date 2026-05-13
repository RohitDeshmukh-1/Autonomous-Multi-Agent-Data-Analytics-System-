"""
tests/conftest.py
Shared fixtures for all test layers.
"""

import json
import os
import sqlite3
import uuid
from io import BytesIO
from typing import Generator
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

# ── Environment setup (before any app imports) ────────────────────────────────
os.environ.setdefault("NEON_DATABASE_URL", "postgresql://test:test@localhost/testdb")
os.environ.setdefault("GROQ_API_KEY", "gsk_test_key")
os.environ.setdefault("GROQ_CODE_MODEL", "llama-3.1-70b-versatile")
os.environ.setdefault("GROQ_REASON_MODEL", "llama-3.1-8b-instant")
os.environ.setdefault("TOGETHER_API_KEY", "test_together_key")
os.environ.setdefault("TOGETHER_EMBED_MODEL", "togethercomputer/m2-bert-80M-8k-retrieval")
os.environ.setdefault("UPSTASH_REDIS_REST_URL", "https://test.upstash.io")
os.environ.setdefault("UPSTASH_REDIS_REST_TOKEN", "test_token")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test_service_key")
os.environ.setdefault("SUPABASE_ANON_KEY", "test_anon_key")
os.environ.setdefault("DEMO_MODE", "true")


# ── Reusable data fixtures ────────────────────────────────────────────────────

@pytest.fixture
def session_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def user_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def sample_csv_bytes() -> bytes:
    return (
        b"order_id,customer,product,amount,region\n"
        b"1,Alice,Widget,99.99,North\n"
        b"2,Bob,Gadget,149.99,South\n"
        b"3,Alice,Widget,99.99,North\n"
        b"4,Carol,Doohickey,49.99,East\n"
        b"5,Bob,Widget,99.99,West\n"
    )


@pytest.fixture
def sample_df(sample_csv_bytes) -> pd.DataFrame:
    return pd.read_csv(BytesIO(sample_csv_bytes))


@pytest.fixture
def sample_schema() -> list:
    return [
        {
            "table": "orders",
            "columns": [
                {"name": "order_id", "type": "integer"},
                {"name": "customer", "type": "text"},
                {"name": "product", "type": "text"},
                {"name": "amount", "type": "numeric"},
                {"name": "region", "type": "text"},
            ],
            "row_count": 5,
        }
    ]


@pytest.fixture
def sample_rows() -> list:
    return [
        {"product": "Widget", "total": 299.97},
        {"product": "Gadget", "total": 149.99},
        {"product": "Doohickey", "total": 49.99},
    ]


@pytest.fixture
def sample_state(session_id, user_id) -> dict:
    return {
        "session_id": session_id,
        "user_id": user_id,
        "user_query": "What are the top products by revenue?",
        "connector_id": "neon:public",
        "intent": "sql",
        "query_plan": {"tables": ["orders"], "approach": "aggregate by product", "complexity": "simple"},
        "relevant_tables": [
            {"table": "orders", "columns": [{"name": "product", "type": "text"}, {"name": "amount", "type": "numeric"}]}
        ],
        "schema_context": "Table: orders | Columns: product (text), amount (numeric)",
        "memory_context": "",
        "generated_code": "SELECT product, SUM(amount) AS total FROM orders GROUP BY product ORDER BY total DESC LIMIT 5",
        "code_type": "sql",
        "sql_dialect": "postgres",
        "execution_result": [{"product": "Widget", "total": 299.97}],
        "execution_error": None,
        "from_cache": False,
        "error_class": None,
        "correction_attempts": 0,
        "max_corrections": 3,
        "insight_text": "",
        "chart_spec": None,
        "history_id": None,
        "latency_ms": None,
        "stream_tokens": [],
    }


# ── In-memory SQLite connector fixture ───────────────────────────────────────

@pytest.fixture
def in_memory_sqlite_connector(sample_csv_bytes):
    """Returns a CsvConnector backed by sample CSV bytes (no network)."""
    from connectors.csv_connector import CsvConnector
    return CsvConnector(supabase_url="http://fake", file_bytes=sample_csv_bytes)


# ── Mock LLM fixture ──────────────────────────────────────────────────────────

@pytest.fixture
def mock_groq(mocker):
    """Patch GroqClient.complete_system to return controlled responses."""
    mock = mocker.patch("llm.groq_client.GroqClient.complete_system")
    mock.return_value = '{"intent": "sql", "reasoning": "needs aggregation"}'
    return mock


@pytest.fixture
def mock_embedder(mocker):
    """Patch TogetherEmbedder to return deterministic 768-dim vectors."""
    vec = [0.01] * 768
    mock = mocker.patch("llm.together_embedder.TogetherEmbedder.embed", return_value=vec)
    mocker.patch("llm.together_embedder.TogetherEmbedder.embed_batch", return_value=[vec])
    return mock


# ── FastAPI test client ───────────────────────────────────────────────────────

@pytest.fixture
def api_client():
    """TestClient with all external calls mocked at the module level."""
    with (
        patch("llm.groq_client.GroqClient._post") as mock_post,
        patch("llm.together_embedder.TogetherEmbedder.embed", return_value=[0.01] * 768),
        patch("llm.together_embedder.TogetherEmbedder.embed_batch", return_value=[[0.01] * 768]),
    ):
        mock_post.return_value = {
            "choices": [{"message": {"content": '{"intent": "sql", "reasoning": "test"}'}}]
        }
        from api.main import app
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
