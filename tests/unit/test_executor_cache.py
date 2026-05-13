"""
tests/unit/test_executor_cache.py
Tests for the executor node — cache hit/miss behavior and result capping.
"""

import json
import uuid
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def executor_state(sample_state):
    return {
        **sample_state,
        "generated_code": "SELECT product, SUM(amount) AS total FROM orders GROUP BY product",
        "code_type": "sql",
        "execution_error": None,
    }


@pytest.mark.unit
class TestExecutorCaching:
    def test_cache_hit_returns_cached_result(self, executor_state, mocker):
        cached = [{"product": "Widget", "total": 100.0}]
        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps(cached)
        mocker.patch("agent.nodes.executor.Redis", return_value=mock_redis)

        from agent.nodes.executor import executor
        result = executor(executor_state)

        assert result["from_cache"] is True
        assert result["execution_result"] == cached

    def test_cache_miss_calls_connector(self, executor_state, mocker):
        mock_redis = MagicMock()
        mock_redis.get.side_effect = Exception("miss")
        mocker.patch("agent.nodes.executor.Redis", return_value=mock_redis)

        rows = [{"product": "Widget", "total": 99.0}]
        mock_connector = MagicMock()
        mock_connector.execute_sql.return_value = rows
        mocker.patch("agent.nodes.executor.get_connector", return_value=mock_connector)

        from agent.nodes.executor import executor
        result = executor(executor_state)

        assert result["from_cache"] is False
        assert result["execution_result"] == rows
        mock_connector.execute_sql.assert_called_once()

    def test_cache_write_called_on_miss(self, executor_state, mocker):
        mock_redis = MagicMock()
        mock_redis.get.side_effect = Exception("miss")
        mocker.patch("agent.nodes.executor.Redis", return_value=mock_redis)

        mock_connector = MagicMock()
        mock_connector.execute_sql.return_value = [{"x": 1}]
        mocker.patch("agent.nodes.executor.get_connector", return_value=mock_connector)

        from agent.nodes.executor import executor
        executor(executor_state)

        mock_redis.setex.assert_called_once()
        # TTL should be 3600
        args = mock_redis.setex.call_args[0]
        assert args[1] == 3600

    def test_safety_block_skips_execution(self, executor_state, mocker):
        mock_redis = MagicMock()
        mocker.patch("agent.nodes.executor.Redis", return_value=mock_redis)
        mock_connector = MagicMock()
        mocker.patch("agent.nodes.executor.get_connector", return_value=mock_connector)

        state = {**executor_state, "execution_error": "SAFETY_BLOCK: Drop operation"}
        from agent.nodes.executor import executor
        result = executor(state)

        mock_connector.execute_sql.assert_not_called()
        assert result["execution_error"].startswith("SAFETY_BLOCK")

    def test_result_capped_at_500_rows(self, executor_state, mocker):
        mock_redis = MagicMock()
        mock_redis.get.side_effect = Exception("miss")
        mocker.patch("agent.nodes.executor.Redis", return_value=mock_redis)

        big_result = [{"id": i} for i in range(600)]
        mock_connector = MagicMock()
        mock_connector.execute_sql.return_value = big_result
        mocker.patch("agent.nodes.executor.get_connector", return_value=mock_connector)

        from agent.nodes.executor import executor
        result = executor(executor_state)

        assert len(result["execution_result"]) == 500

    def test_connector_exception_sets_error(self, executor_state, mocker):
        mock_redis = MagicMock()
        mock_redis.get.side_effect = Exception("miss")
        mocker.patch("agent.nodes.executor.Redis", return_value=mock_redis)

        mock_connector = MagicMock()
        mock_connector.execute_sql.side_effect = Exception("relation does not exist")
        mocker.patch("agent.nodes.executor.get_connector", return_value=mock_connector)

        from agent.nodes.executor import executor
        result = executor(executor_state)

        assert result["execution_result"] is None
        assert "relation does not exist" in result["execution_error"]
        assert result["from_cache"] is False

    def test_cache_key_differs_by_query(self, mocker):
        """Two different queries must produce different cache keys."""
        from agent.nodes.executor import _cache_key
        k1 = _cache_key("neon:public", "SELECT 1", "sql")
        k2 = _cache_key("neon:public", "SELECT 2", "sql")
        assert k1 != k2

    def test_cache_key_differs_by_connector(self, mocker):
        from agent.nodes.executor import _cache_key
        k1 = _cache_key("neon:public", "SELECT 1", "sql")
        k2 = _cache_key("csv:http://foo", "SELECT 1", "sql")
        assert k1 != k2

    def test_latency_ms_recorded(self, executor_state, mocker):
        mock_redis = MagicMock()
        mock_redis.get.side_effect = Exception("miss")
        mocker.patch("agent.nodes.executor.Redis", return_value=mock_redis)

        mock_connector = MagicMock()
        mock_connector.execute_sql.return_value = [{"x": 1}]
        mocker.patch("agent.nodes.executor.get_connector", return_value=mock_connector)

        from agent.nodes.executor import executor
        result = executor(executor_state)

        assert result["latency_ms"] is not None
        assert result["latency_ms"] >= 0
