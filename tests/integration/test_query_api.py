"""
tests/integration/test_query_api.py
FastAPI integration tests — agent graph is fully mocked so no LLM/DB calls happen.
Uses TestClient (synchronous ASGI runner).
"""

import json
import uuid
import pytest
from unittest.mock import patch, MagicMock


def _make_final_state(session_id: str) -> dict:
    return {
        "session_id": session_id,
        "user_id": "test",
        "user_query": "top products",
        "connector_id": "neon:public",
        "intent": "sql",
        "query_plan": {},
        "relevant_tables": [],
        "schema_context": "",
        "memory_context": "",
        "generated_code": "SELECT product, SUM(amount) FROM orders GROUP BY product",
        "code_type": "sql",
        "sql_dialect": "postgres",
        "execution_result": [{"product": "Widget", "total": 299.97}],
        "execution_error": None,
        "from_cache": False,
        "error_class": None,
        "correction_attempts": 0,
        "max_corrections": 3,
        "insight_text": "Widget is the top product with $300 in revenue.",
        "chart_spec": {
            "type": "bar",
            "plotly_json": {
                "data": [{"type": "bar", "x": ["Widget"], "y": [299.97]}],
                "layout": {"title": "top products"},
            },
        },
        "history_id": str(uuid.uuid4()),
        "latency_ms": 850,
        "stream_tokens": [],
    }


@pytest.fixture
def mocked_graph(session_id):
    """Patch get_graph() to return a mock that returns controlled state."""
    state = _make_final_state(session_id)
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = state
    with patch("api.routers.query.get_graph", return_value=mock_graph):
        yield mock_graph, state


@pytest.mark.integration
class TestQueryRunEndpoint:
    def test_returns_200(self, api_client, mocked_graph, session_id):
        resp = api_client.post("/api/query/run", json={
            "user_query": "top products",
            "connector_id": "neon:public",
            "session_id": session_id,
        })
        assert resp.status_code == 200

    def test_response_has_required_fields(self, api_client, mocked_graph, session_id):
        resp = api_client.post("/api/query/run", json={
            "user_query": "top products",
            "connector_id": "neon:public",
            "session_id": session_id,
        })
        body = resp.json()
        required = ["session_id", "intent", "generated_code", "execution_result",
                    "insight_text", "chart_spec", "from_cache", "latency_ms"]
        for field in required:
            assert field in body, f"Missing field: {field}"

    def test_insight_text_returned(self, api_client, mocked_graph, session_id):
        resp = api_client.post("/api/query/run", json={
            "user_query": "top products",
            "connector_id": "neon:public",
            "session_id": session_id,
        })
        assert resp.json()["insight_text"] == "Widget is the top product with $300 in revenue."

    def test_chart_spec_returned(self, api_client, mocked_graph, session_id):
        resp = api_client.post("/api/query/run", json={
            "user_query": "top products",
            "connector_id": "neon:public",
            "session_id": session_id,
        })
        chart = resp.json()["chart_spec"]
        assert chart is not None
        assert chart["type"] == "bar"

    def test_empty_query_rejected(self, api_client):
        resp = api_client.post("/api/query/run", json={
            "user_query": "",
            "connector_id": "neon:public",
        })
        assert resp.status_code == 422

    def test_missing_connector_id_rejected(self, api_client):
        resp = api_client.post("/api/query/run", json={"user_query": "test"})
        assert resp.status_code == 422

    def test_session_id_auto_generated_when_absent(self, api_client, mocked_graph):
        resp = api_client.post("/api/query/run", json={
            "user_query": "top products",
            "connector_id": "neon:public",
        })
        assert resp.status_code == 200
        assert resp.json()["session_id"]

    def test_graph_invoke_called_once(self, api_client, mocked_graph, session_id):
        mock_graph, _ = mocked_graph
        api_client.post("/api/query/run", json={
            "user_query": "top products",
            "connector_id": "neon:public",
            "session_id": session_id,
        })
        mock_graph.invoke.assert_called_once()

    def test_graph_exception_returns_500(self, api_client, session_id):
        mock_graph = MagicMock()
        mock_graph.invoke.side_effect = RuntimeError("LLM timeout")
        with patch("api.routers.query.get_graph", return_value=mock_graph):
            resp = api_client.post("/api/query/run", json={
                "user_query": "top products",
                "connector_id": "neon:public",
                "session_id": session_id,
            })
        assert resp.status_code == 500


@pytest.mark.integration
class TestHealthEndpoint:
    def test_health_returns_ok(self, api_client):
        resp = api_client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


@pytest.mark.integration
class TestStreamEndpoint:
    def test_stream_returns_200(self, api_client, mocked_graph, session_id):
        resp = api_client.post("/api/query/stream", json={
            "user_query": "top products",
            "connector_id": "neon:public",
            "session_id": session_id,
        })
        assert resp.status_code == 200

    def test_stream_content_type_is_event_stream(self, api_client, mocked_graph, session_id):
        resp = api_client.post("/api/query/stream", json={
            "user_query": "top products",
            "connector_id": "neon:public",
            "session_id": session_id,
        })
        assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_stream_contains_done_event(self, api_client, mocked_graph, session_id):
        resp = api_client.post("/api/query/stream", json={
            "user_query": "top products",
            "connector_id": "neon:public",
            "session_id": session_id,
        })
        raw = resp.text
        events = [
            json.loads(line[len("data: "):])
            for line in raw.split("\n")
            if line.startswith("data: ")
        ]
        done_events = [e for e in events if e.get("done")]
        assert len(done_events) == 1

    def test_stream_emits_token_events(self, api_client, mocked_graph, session_id):
        resp = api_client.post("/api/query/stream", json={
            "user_query": "top products",
            "connector_id": "neon:public",
            "session_id": session_id,
        })
        raw = resp.text
        events = [
            json.loads(line[len("data: "):])
            for line in raw.split("\n")
            if line.startswith("data: ")
        ]
        token_events = [e for e in events if "token" in e]
        assert len(token_events) > 0
