"""
tests/unit/test_error_classifier.py
Tests for the error classifier node and LangGraph routing conditions.
"""

import json
import pytest


# ── Error Classifier ──────────────────────────────────────────────────────────

@pytest.mark.unit
class TestErrorClassifier:
    def test_classifies_nonexistent_column(self, sample_state, mocker):
        mocker.patch(
            "agent.nodes.error_classifier.get_groq_client"
        ).return_value.complete_system.return_value = json.dumps(
            {"error_class": "nonexistent_column", "hint": "use exact column name"}
        )
        from agent.nodes.error_classifier import error_classifier
        state = {**sample_state, "execution_error": 'column "revenue" does not exist'}
        result = error_classifier(state)
        assert result["error_class"] == "nonexistent_column"

    def test_classifies_syntax_error(self, sample_state, mocker):
        mocker.patch(
            "agent.nodes.error_classifier.get_groq_client"
        ).return_value.complete_system.return_value = json.dumps(
            {"error_class": "syntax", "hint": "fix syntax near WHERE"}
        )
        from agent.nodes.error_classifier import error_classifier
        state = {**sample_state, "execution_error": "syntax error at or near WHERE"}
        result = error_classifier(state)
        assert result["error_class"] == "syntax"

    def test_defaults_to_unknown_on_bad_json(self, sample_state, mocker):
        mocker.patch(
            "agent.nodes.error_classifier.get_groq_client"
        ).return_value.complete_system.return_value = "not json"
        from agent.nodes.error_classifier import error_classifier
        state = {**sample_state, "execution_error": "some error"}
        result = error_classifier(state)
        assert result["error_class"] == "unknown"

    def test_no_error_returns_state_unchanged(self, sample_state):
        from agent.nodes.error_classifier import error_classifier
        state = {**sample_state, "execution_error": None}
        result = error_classifier(state)
        # Should not have changed error_class
        assert result.get("error_class") == sample_state.get("error_class")

    def test_classifies_type_mismatch(self, sample_state, mocker):
        mocker.patch(
            "agent.nodes.error_classifier.get_groq_client"
        ).return_value.complete_system.return_value = json.dumps(
            {"error_class": "type_mismatch", "hint": "cast the column"}
        )
        from agent.nodes.error_classifier import error_classifier
        state = {**sample_state, "execution_error": "cannot compare integer with text"}
        result = error_classifier(state)
        assert result["error_class"] == "type_mismatch"


# ── Graph routing conditions ──────────────────────────────────────────────────

@pytest.mark.unit
class TestGraphRouting:
    def test_route_intent_sql(self, sample_state):
        from agent.graph import route_intent
        assert route_intent({**sample_state, "intent": "sql"}) == "sql"

    def test_route_intent_pandas(self, sample_state):
        from agent.graph import route_intent
        assert route_intent({**sample_state, "intent": "pandas"}) == "pandas"

    def test_route_intent_unsupported(self, sample_state):
        from agent.graph import route_intent
        from langgraph.graph import END
        assert route_intent({**sample_state, "intent": "unsupported"}) == "unsupported"

    def test_route_intent_insight_only(self, sample_state):
        from agent.graph import route_intent
        assert route_intent({**sample_state, "intent": "insight"}) == "insight_only"

    def test_route_after_execution_success(self, sample_state):
        from agent.graph import route_after_execution
        state = {**sample_state, "execution_error": None, "execution_result": [{"x": 1}]}
        assert route_after_execution(state) == "success"

    def test_route_after_execution_corrects_on_error(self, sample_state):
        from agent.graph import route_after_execution
        state = {**sample_state, "execution_error": "column missing", "correction_attempts": 0, "max_corrections": 3}
        assert route_after_execution(state) == "correct"

    def test_route_after_execution_gives_up_at_max(self, sample_state):
        from agent.graph import route_after_execution
        state = {**sample_state, "execution_error": "still broken", "correction_attempts": 3, "max_corrections": 3}
        assert route_after_execution(state) == "give_up"

    def test_route_after_validation_passes_safe_code(self, sample_state):
        from agent.graph import route_after_validation
        state = {**sample_state, "execution_error": None}
        assert route_after_validation(state) == "execute"

    def test_route_after_validation_blocks_unsafe_code(self, sample_state):
        from agent.graph import route_after_validation
        state = {**sample_state, "execution_error": "SAFETY_BLOCK: Drop operation"}
        assert route_after_validation(state) == "blocked"
