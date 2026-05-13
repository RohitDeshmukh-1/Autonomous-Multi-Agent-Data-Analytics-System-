"""
tests/unit/test_agent_nodes.py
Tests for individual LangGraph nodes with mocked LLM/DB calls.
"""

import json
import pytest
from unittest.mock import patch, MagicMock


# ── Intent Router ──────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestIntentRouter:
    def test_routes_sql_intent(self, sample_state, mocker):
        mocker.patch(
            "agent.nodes.intent_router.get_groq_client"
        ).return_value.complete_system.return_value = json.dumps(
            {"intent": "sql", "reasoning": "needs aggregation"}
        )
        from agent.nodes.intent_router import intent_router
        result = intent_router(sample_state)
        assert result["intent"] == "sql"

    def test_routes_pandas_intent(self, sample_state, mocker):
        mocker.patch(
            "agent.nodes.intent_router.get_groq_client"
        ).return_value.complete_system.return_value = json.dumps(
            {"intent": "pandas", "reasoning": "csv manipulation"}
        )
        from agent.nodes.intent_router import intent_router
        result = intent_router({**sample_state, "connector_id": "csv:http://fake"})
        assert result["intent"] == "pandas"

    def test_routes_unsupported_intent(self, sample_state, mocker):
        mocker.patch(
            "agent.nodes.intent_router.get_groq_client"
        ).return_value.complete_system.return_value = json.dumps(
            {"intent": "unsupported", "reasoning": "out of scope"}
        )
        from agent.nodes.intent_router import intent_router
        result = intent_router({**sample_state, "user_query": "what is the weather?"})
        assert result["intent"] == "unsupported"

    def test_defaults_to_sql_on_bad_json(self, sample_state, mocker):
        mocker.patch(
            "agent.nodes.intent_router.get_groq_client"
        ).return_value.complete_system.return_value = "not json at all"
        from agent.nodes.intent_router import intent_router
        result = intent_router(sample_state)
        assert result["intent"] == "sql"


# ── SQL Generator ─────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestSqlGenerator:
    def test_strips_markdown_fences(self, sample_state, mocker):
        mocker.patch(
            "agent.nodes.sql_generator.get_groq_client"
        ).return_value.complete_system.return_value = (
            "```sql\nSELECT * FROM orders LIMIT 5\n```"
        )
        from agent.nodes.sql_generator import sql_generator
        result = sql_generator(sample_state)
        assert "```" not in result["generated_code"]
        assert "SELECT" in result["generated_code"]

    def test_sets_code_type_to_sql(self, sample_state, mocker):
        mocker.patch(
            "agent.nodes.sql_generator.get_groq_client"
        ).return_value.complete_system.return_value = "SELECT 1"
        from agent.nodes.sql_generator import sql_generator
        result = sql_generator(sample_state)
        assert result["code_type"] == "sql"

    def test_sets_postgres_dialect_for_neon(self, sample_state, mocker):
        mocker.patch(
            "agent.nodes.sql_generator.get_groq_client"
        ).return_value.complete_system.return_value = "SELECT 1"
        from agent.nodes.sql_generator import sql_generator
        result = sql_generator({**sample_state, "connector_id": "neon:public"})
        assert result["sql_dialect"] == "postgres"

    def test_sets_sqlite_dialect_for_csv(self, sample_state, mocker):
        mocker.patch(
            "agent.nodes.sql_generator.get_groq_client"
        ).return_value.complete_system.return_value = "SELECT 1"
        from agent.nodes.sql_generator import sql_generator
        result = sql_generator({**sample_state, "connector_id": "csv:http://fake"})
        assert result["sql_dialect"] == "sqlite"


# ── Pandas Generator ──────────────────────────────────────────────────────────

@pytest.mark.unit
class TestPandasGenerator:
    def test_strips_markdown_fences(self, sample_state, mocker):
        mocker.patch(
            "agent.nodes.pandas_generator.get_groq_client"
        ).return_value.complete_system.return_value = (
            "```python\nresult = df.head(5)\n```"
        )
        from agent.nodes.pandas_generator import pandas_generator
        result = pandas_generator(sample_state)
        assert "```" not in result["generated_code"]
        assert "result" in result["generated_code"]

    def test_sets_code_type_to_pandas(self, sample_state, mocker):
        mocker.patch(
            "agent.nodes.pandas_generator.get_groq_client"
        ).return_value.complete_system.return_value = "result = df"
        from agent.nodes.pandas_generator import pandas_generator
        result = pandas_generator(sample_state)
        assert result["code_type"] == "pandas"


# ── Safety Validator ──────────────────────────────────────────────────────────

@pytest.mark.unit
class TestSafetyValidator:
    def test_passes_valid_sql(self, sample_state):
        from agent.nodes.safety_validator import safety_validator
        state = {**sample_state, "generated_code": "SELECT * FROM orders", "code_type": "sql"}
        result = safety_validator(state)
        assert result["execution_error"] is None

    def test_blocks_drop_table(self, sample_state):
        from agent.nodes.safety_validator import safety_validator
        state = {**sample_state, "generated_code": "DROP TABLE orders", "code_type": "sql"}
        result = safety_validator(state)
        assert result["execution_error"] is not None
        assert "SAFETY_BLOCK" in result["execution_error"]

    def test_passes_valid_pandas(self, sample_state):
        from agent.nodes.safety_validator import safety_validator
        state = {**sample_state, "generated_code": "result = df.head()", "code_type": "pandas"}
        result = safety_validator(state)
        assert result["execution_error"] is None

    def test_blocks_os_import_in_pandas(self, sample_state):
        from agent.nodes.safety_validator import safety_validator
        state = {**sample_state, "generated_code": "import os\nresult = df", "code_type": "pandas"}
        result = safety_validator(state)
        assert result["execution_error"] is not None
        assert "SAFETY_BLOCK" in result["execution_error"]


# ── Self Corrector ────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestSelfCorrector:
    def test_increments_correction_attempts(self, sample_state, mocker):
        mocker.patch(
            "agent.nodes.self_corrector.get_groq_client"
        ).return_value.complete_system.return_value = "SELECT 1"
        from agent.nodes.self_corrector import self_corrector
        state = {**sample_state, "execution_error": "column not found", "error_class": "nonexistent_column", "correction_attempts": 0}
        result = self_corrector(state)
        assert result["correction_attempts"] == 1

    def test_clears_execution_error(self, sample_state, mocker):
        mocker.patch(
            "agent.nodes.self_corrector.get_groq_client"
        ).return_value.complete_system.return_value = "SELECT 1"
        from agent.nodes.self_corrector import self_corrector
        state = {**sample_state, "execution_error": "syntax error", "error_class": "syntax", "correction_attempts": 1}
        result = self_corrector(state)
        assert result["execution_error"] is None

    def test_gives_up_at_max_attempts(self, sample_state, mocker):
        mocker.patch("agent.nodes.self_corrector.get_groq_client")
        from agent.nodes.self_corrector import self_corrector
        state = {**sample_state, "execution_error": "err", "error_class": "unknown",
                 "correction_attempts": 3, "max_corrections": 3}
        result = self_corrector(state)
        assert "unable" in result.get("insight_text", "").lower()

    def test_strips_markdown_from_corrected_code(self, sample_state, mocker):
        mocker.patch(
            "agent.nodes.self_corrector.get_groq_client"
        ).return_value.complete_system.return_value = "```sql\nSELECT 1\n```"
        from agent.nodes.self_corrector import self_corrector
        state = {**sample_state, "execution_error": "err", "error_class": "syntax", "correction_attempts": 0}
        result = self_corrector(state)
        assert "```" not in result["generated_code"]


# ── Insight Synthesizer ───────────────────────────────────────────────────────

@pytest.mark.unit
class TestInsightSynthesizer:
    def test_returns_insight_text(self, sample_state, sample_rows, mocker):
        mocker.patch(
            "agent.nodes.insight_synthesizer.get_groq_client"
        ).return_value.complete_system.return_value = "Widget leads with $300 in revenue."
        from agent.nodes.insight_synthesizer import insight_synthesizer
        state = {**sample_state, "execution_result": sample_rows}
        result = insight_synthesizer(state)
        assert result["insight_text"] == "Widget leads with $300 in revenue."

    def test_no_result_returns_no_results_message(self, sample_state):
        from agent.nodes.insight_synthesizer import insight_synthesizer
        state = {**sample_state, "execution_result": None}
        result = insight_synthesizer(state)
        assert "no results" in result["insight_text"].lower()

    def test_empty_result_returns_no_results_message(self, sample_state):
        from agent.nodes.insight_synthesizer import insight_synthesizer
        state = {**sample_state, "execution_result": []}
        result = insight_synthesizer(state)
        assert "no results" in result["insight_text"].lower()
