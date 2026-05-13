"""
tests/e2e/test_agent_pipeline.py
End-to-end tests that exercise the full LangGraph agent graph.
All external I/O (LLM, DB, Redis, HTTP) is mocked at boundary level.
Tests verify: correct node sequencing, state propagation, and final output shape.
"""

import json
import uuid
import pytest
from unittest.mock import patch, MagicMock


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _base_state(
    query: str = "top products by revenue",
    connector: str = "neon:public",
) -> dict:
    return {
        "session_id": str(uuid.uuid4()),
        "user_id": "e2e-test",
        "user_query": query,
        "connector_id": connector,
        "intent": "",
        "query_plan": {},
        "relevant_tables": [],
        "schema_context": "",
        "memory_context": "",
        "generated_code": "",
        "code_type": "sql",
        "sql_dialect": "postgres",
        "execution_result": None,
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


def _llm_sequence(*responses):
    """Side-effect function that returns each response in order, then repeats last."""
    responses = list(responses)
    call_count = {"n": -1}

    def _call(*args, **kwargs):
        call_count["n"] += 1
        idx = min(call_count["n"], len(responses) - 1)
        return responses[idx]

    return _call


def _mock_redis():
    m = MagicMock()
    m.get.side_effect = Exception("cache miss")
    m.setex.return_value = True
    return m


def _fake_schema():
    return [
        {
            "table": "orders",
            "columns": [
                {"name": "product", "type": "text"},
                {"name": "amount", "type": "numeric"},
                {"name": "region", "type": "text"},
            ],
            "row_count": 500,
            "similarity": 0.92,
        }
    ]


def _patch_common(mocker, schema=None):
    """Patch embedder, schema retrieval, Redis, and Postgres memory tables."""
    vec = [0.01] * 768
    mocker.patch("llm.together_embedder.TogetherEmbedder.embed", return_value=vec)
    mocker.patch("llm.together_embedder.TogetherEmbedder.embed_batch", return_value=[vec])
    mocker.patch("schema.ingestor.get_relevant_tables", return_value=schema or _fake_schema())
    mocker.patch("agent.nodes.executor.Redis", return_value=_mock_redis())
    mocker.patch("agent.nodes.memory_updater.psycopg2.connect")

    mem_pg = mocker.patch("agent.nodes.memory_retriever.psycopg2.connect")
    mem_pg.return_value.cursor.return_value.__enter__ \
        .return_value.fetchall.return_value = []
    return mem_pg


# ── SQL happy path ─────────────────────────────────────────────────────────────

@pytest.mark.e2e
class TestSqlPipeline:

    def test_full_pipeline_returns_insight(self, mocker):
        _patch_common(mocker)
        mocker.patch(
            "llm.groq_client.GroqClient.complete_system",
            side_effect=_llm_sequence(
                json.dumps({"intent": "sql", "reasoning": "needs aggregation"}),
                json.dumps({"tables": ["orders"], "approach": "group by product",
                            "complexity": "simple", "requires_join": False}),
                "SELECT product, SUM(amount) AS total FROM orders GROUP BY product ORDER BY total DESC LIMIT 5",
                "Widget is the top product with $300 in total revenue.",
            ),
        )
        mock_connector = MagicMock()
        mock_connector.execute_sql.return_value = [
            {"product": "Widget", "total": 300.0},
            {"product": "Gadget", "total": 150.0},
        ]
        mocker.patch("agent.nodes.executor.get_connector", return_value=mock_connector)

        from agent.graph import get_graph
        result = get_graph().invoke(_base_state())

        assert result["intent"] == "sql"
        assert result["execution_error"] is None
        assert len(result["execution_result"]) == 2
        assert result["insight_text"] == "Widget is the top product with $300 in total revenue."

    def test_pipeline_produces_chart_spec(self, mocker):
        _patch_common(mocker)
        mocker.patch(
            "llm.groq_client.GroqClient.complete_system",
            side_effect=_llm_sequence(
                json.dumps({"intent": "sql", "reasoning": "test"}),
                json.dumps({"tables": ["orders"], "approach": "agg",
                            "complexity": "simple", "requires_join": False}),
                "SELECT product, SUM(amount) AS total FROM orders GROUP BY product",
                "Widget leads.",
            ),
        )
        mock_connector = MagicMock()
        mock_connector.execute_sql.return_value = [
            {"product": "Widget", "total": 300.0},
            {"product": "Gadget", "total": 150.0},
        ]
        mocker.patch("agent.nodes.executor.get_connector", return_value=mock_connector)

        from agent.graph import get_graph
        result = get_graph().invoke(_base_state())

        assert result["chart_spec"] is not None
        assert "type" in result["chart_spec"]

    def test_unsupported_query_terminates_early(self, mocker):
        _patch_common(mocker)
        mocker.patch(
            "llm.groq_client.GroqClient.complete_system",
            return_value=json.dumps({"intent": "unsupported", "reasoning": "out of scope"}),
        )
        mock_connector = MagicMock()
        mocker.patch("agent.nodes.executor.get_connector", return_value=mock_connector)

        from agent.graph import get_graph
        result = get_graph().invoke(_base_state("What is the weather in London?"))

        assert result["intent"] == "unsupported"
        assert result["execution_result"] is None
        mock_connector.execute_sql.assert_not_called()

    def test_cache_hit_skips_db_call(self, mocker):
        _patch_common(mocker)

        cached_rows = [{"product": "Widget", "total": 300.0}]
        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps(cached_rows)
        mocker.patch("agent.nodes.executor.Redis", return_value=mock_redis)

        mocker.patch(
            "llm.groq_client.GroqClient.complete_system",
            side_effect=_llm_sequence(
                json.dumps({"intent": "sql", "reasoning": "test"}),
                json.dumps({"tables": ["orders"], "approach": "agg",
                            "complexity": "simple", "requires_join": False}),
                "SELECT product, SUM(amount) AS total FROM orders GROUP BY product",
                "Widget leads from cache.",
            ),
        )
        mock_connector = MagicMock()
        mocker.patch("agent.nodes.executor.get_connector", return_value=mock_connector)

        from agent.graph import get_graph
        result = get_graph().invoke(_base_state())

        assert result["from_cache"] is True
        assert result["execution_result"] == cached_rows
        mock_connector.execute_sql.assert_not_called()

    def test_safety_block_prevents_execution(self, mocker):
        _patch_common(mocker)
        mocker.patch(
            "llm.groq_client.GroqClient.complete_system",
            side_effect=_llm_sequence(
                json.dumps({"intent": "sql", "reasoning": "test"}),
                json.dumps({"tables": ["orders"], "approach": "drop",
                            "complexity": "simple", "requires_join": False}),
                "DROP TABLE orders",   # safety validator will block this
                "Could not answer safely.",
            ),
        )
        mock_connector = MagicMock()
        mocker.patch("agent.nodes.executor.get_connector", return_value=mock_connector)

        from agent.graph import get_graph
        result = get_graph().invoke(_base_state())

        mock_connector.execute_sql.assert_not_called()
        assert result["execution_result"] is None


# ── Self-correction loop ───────────────────────────────────────────────────────

@pytest.mark.e2e
class TestSelfCorrectionPipeline:

    def test_retries_on_first_execution_error(self, mocker):
        _patch_common(mocker)

        call_count = {"n": 0}

        def execute_side(sql):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise Exception('column "revenue" does not exist')
            return [{"product": "Widget", "total": 300.0}]

        mock_connector = MagicMock()
        mock_connector.execute_sql.side_effect = execute_side
        mocker.patch("agent.nodes.executor.get_connector", return_value=mock_connector)

        mocker.patch(
            "llm.groq_client.GroqClient.complete_system",
            side_effect=_llm_sequence(
                json.dumps({"intent": "sql", "reasoning": "test"}),
                json.dumps({"tables": ["orders"], "approach": "agg",
                            "complexity": "simple", "requires_join": False}),
                "SELECT product, SUM(revenue) AS total FROM orders GROUP BY product",
                json.dumps({"error_class": "nonexistent_column", "hint": "use 'amount'"}),
                "SELECT product, SUM(amount) AS total FROM orders GROUP BY product",
                "Widget leads with $300.",
            ),
        )

        from agent.graph import get_graph
        result = get_graph().invoke(_base_state())

        assert result["correction_attempts"] == 1
        assert result["execution_error"] is None
        assert result["execution_result"] == [{"product": "Widget", "total": 300.0}]
        assert result["insight_text"] == "Widget leads with $300."

    def test_gives_up_gracefully_after_max_retries(self, mocker):
        _patch_common(mocker)

        mock_connector = MagicMock()
        mock_connector.execute_sql.side_effect = Exception("persistent db error")
        mocker.patch("agent.nodes.executor.get_connector", return_value=mock_connector)

        mocker.patch(
            "llm.groq_client.GroqClient.complete_system",
            side_effect=_llm_sequence(
                json.dumps({"intent": "sql", "reasoning": "test"}),
                json.dumps({"tables": ["orders"], "approach": "agg",
                            "complexity": "simple", "requires_join": False}),
                "SELECT bad1 FROM orders",
                json.dumps({"error_class": "unknown", "hint": "try again"}),
                "SELECT bad2 FROM orders",
                json.dumps({"error_class": "unknown", "hint": "try again"}),
                "SELECT bad3 FROM orders",
                json.dumps({"error_class": "unknown", "hint": "try again"}),
                "I was unable to answer this question after multiple attempts.",
            ),
        )

        from agent.graph import get_graph
        result = get_graph().invoke(_base_state())

        assert result["correction_attempts"] >= 3
        assert isinstance(result["insight_text"], str)
        assert len(result["insight_text"]) > 0

    def test_correction_attempts_increments_per_cycle(self, mocker):
        _patch_common(mocker)

        call_count = {"n": 0}

        def execute_side(sql):
            call_count["n"] += 1
            if call_count["n"] <= 2:
                raise Exception("column error")
            return [{"x": 1}]

        mock_connector = MagicMock()
        mock_connector.execute_sql.side_effect = execute_side
        mocker.patch("agent.nodes.executor.get_connector", return_value=mock_connector)

        mocker.patch(
            "llm.groq_client.GroqClient.complete_system",
            side_effect=_llm_sequence(
                json.dumps({"intent": "sql", "reasoning": "test"}),
                json.dumps({"tables": ["orders"], "approach": "agg",
                            "complexity": "simple", "requires_join": False}),
                "SELECT bad1 FROM orders",
                json.dumps({"error_class": "nonexistent_column", "hint": "fix"}),
                "SELECT bad2 FROM orders",
                json.dumps({"error_class": "nonexistent_column", "hint": "fix"}),
                "SELECT x FROM orders",
                "Result is x=1.",
            ),
        )

        from agent.graph import get_graph
        result = get_graph().invoke(_base_state())

        assert result["correction_attempts"] == 2
        assert result["execution_result"] is not None


# ── CSV connector pipeline ─────────────────────────────────────────────────────

@pytest.mark.e2e
class TestCsvPipeline:

    def test_csv_connector_uses_sqlite_dialect(self, mocker, sample_csv_bytes):
        csv_schema = [
            {"table": "data", "columns": [
                {"name": "product", "type": "text"},
                {"name": "amount", "type": "REAL"},
            ], "row_count": 5, "similarity": 0.9}
        ]
        _patch_common(mocker, schema=csv_schema)
        # Also patch at the module level where query_planner imports it
        mocker.patch("agent.nodes.query_planner.get_relevant_tables", return_value=csv_schema)
        mocker.patch(
            "llm.groq_client.GroqClient.complete_system",
            side_effect=_llm_sequence(
                json.dumps({"intent": "sql", "reasoning": "test"}),
                json.dumps({"tables": ["data"], "approach": "aggregate",
                            "complexity": "simple", "requires_join": False}),
                "SELECT product, SUM(amount) AS total FROM data GROUP BY product",
                "Widget is top.",
            ),
        )

        from connectors.csv_connector import CsvConnector
        real_connector = CsvConnector(supabase_url="http://fake", file_bytes=sample_csv_bytes)
        mocker.patch("agent.nodes.executor.get_connector", return_value=real_connector)

        from agent.graph import get_graph
        result = get_graph().invoke(_base_state("top products", connector="csv:http://fake"))

        assert result["sql_dialect"] == "sqlite"
        assert result["execution_result"] is not None
        assert len(result["execution_result"]) > 0

    def test_csv_real_sql_aggregation_correct(self, mocker, sample_csv_bytes):
        csv_schema = [
            {"table": "data", "columns": [
                {"name": "product", "type": "text"},
                {"name": "amount", "type": "REAL"},
            ], "row_count": 5, "similarity": 0.9}
        ]
        _patch_common(mocker, schema=csv_schema)
        mocker.patch("agent.nodes.query_planner.get_relevant_tables", return_value=csv_schema)
        mocker.patch(
            "llm.groq_client.GroqClient.complete_system",
            side_effect=_llm_sequence(
                json.dumps({"intent": "sql", "reasoning": "test"}),
                json.dumps({"tables": ["data"], "approach": "aggregate",
                            "complexity": "simple", "requires_join": False}),
                "SELECT product, SUM(amount) AS total FROM data GROUP BY product ORDER BY total DESC",
                "Widget is the top seller.",
            ),
        )

        from connectors.csv_connector import CsvConnector
        real_connector = CsvConnector(supabase_url="http://fake", file_bytes=sample_csv_bytes)
        mocker.patch("agent.nodes.executor.get_connector", return_value=real_connector)

        from agent.graph import get_graph
        result = get_graph().invoke(_base_state("top products", connector="csv:http://fake"))

        assert result["execution_result"] is not None
        products = [r["product"] for r in result["execution_result"]]
        assert "Widget" in products


# ── State integrity ────────────────────────────────────────────────────────────

@pytest.mark.e2e
class TestStateIntegrity:

    def test_session_id_preserved_end_to_end(self, mocker):
        _patch_common(mocker)
        mocker.patch(
            "llm.groq_client.GroqClient.complete_system",
            side_effect=_llm_sequence(
                json.dumps({"intent": "sql", "reasoning": "test"}),
                json.dumps({"tables": ["orders"], "approach": "agg",
                            "complexity": "simple", "requires_join": False}),
                "SELECT product, SUM(amount) AS total FROM orders GROUP BY product",
                "Widget leads.",
            ),
        )
        mock_connector = MagicMock()
        mock_connector.execute_sql.return_value = [{"product": "Widget", "total": 300.0}]
        mocker.patch("agent.nodes.executor.get_connector", return_value=mock_connector)

        state = _base_state()
        original_session = state["session_id"]
        from agent.graph import get_graph
        result = get_graph().invoke(state)

        assert result["session_id"] == original_session

    def test_latency_ms_populated(self, mocker):
        _patch_common(mocker)
        mocker.patch(
            "llm.groq_client.GroqClient.complete_system",
            side_effect=_llm_sequence(
                json.dumps({"intent": "sql", "reasoning": "test"}),
                json.dumps({"tables": ["orders"], "approach": "agg",
                            "complexity": "simple", "requires_join": False}),
                "SELECT product, SUM(amount) AS total FROM orders GROUP BY product",
                "Widget leads.",
            ),
        )
        mock_connector = MagicMock()
        mock_connector.execute_sql.return_value = [{"product": "Widget", "total": 300.0}]
        mocker.patch("agent.nodes.executor.get_connector", return_value=mock_connector)

        from agent.graph import get_graph
        result = get_graph().invoke(_base_state())

        assert result["latency_ms"] is not None
        assert isinstance(result["latency_ms"], int)
        assert result["latency_ms"] >= 0

    def test_memory_updater_commits_on_success(self, mocker):
        _patch_common(mocker)

        mock_pg = mocker.patch("agent.nodes.memory_updater.psycopg2.connect")
        mock_conn = mock_pg.return_value
        mock_conn.cursor.return_value.__enter__ = lambda s: s
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.commit = MagicMock()
        mock_conn.close = MagicMock()

        mocker.patch(
            "llm.groq_client.GroqClient.complete_system",
            side_effect=_llm_sequence(
                json.dumps({"intent": "sql", "reasoning": "test"}),
                json.dumps({"tables": ["orders"], "approach": "agg",
                            "complexity": "simple", "requires_join": False}),
                "SELECT product, SUM(amount) AS total FROM orders GROUP BY product",
                "Widget leads.",
            ),
        )
        mock_connector = MagicMock()
        mock_connector.execute_sql.return_value = [{"product": "Widget", "total": 300.0}]
        mocker.patch("agent.nodes.executor.get_connector", return_value=mock_connector)

        from agent.graph import get_graph
        get_graph().invoke(_base_state())

        mock_pg.assert_called()
        mock_conn.commit.assert_called()
