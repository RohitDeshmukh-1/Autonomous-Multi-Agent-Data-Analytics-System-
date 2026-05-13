"""
tests/unit/test_llm_clients.py
Tests for Groq and Together AI HTTP clients with mocked network calls.
"""

import pytest
import requests


# ── GroqClient ────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestGroqClient:
    def test_complete_returns_string(self, mocker):
        mock_post = mocker.patch("llm.groq_client.GroqClient._post")
        mock_post.return_value = {
            "choices": [{"message": {"content": "  Hello World  "}}]
        }
        from llm.groq_client import GroqClient
        client = GroqClient()
        result = client.complete("test prompt")
        assert result == "Hello World"

    def test_complete_system_uses_both_messages(self, mocker):
        mock_post = mocker.patch("llm.groq_client.GroqClient._post")
        mock_post.return_value = {"choices": [{"message": {"content": "ok"}}]}
        from llm.groq_client import GroqClient
        client = GroqClient()
        client.complete_system(system="You are a bot", user="Hello")
        call_body = mock_post.call_args[0][0]
        messages = call_body["messages"]
        roles = [m["role"] for m in messages]
        assert "system" in roles
        assert "user" in roles

    def test_uses_reason_model_by_default(self, mocker):
        mock_post = mocker.patch("llm.groq_client.GroqClient._post")
        mock_post.return_value = {"choices": [{"message": {"content": "ok"}}]}
        from llm.groq_client import GroqClient
        client = GroqClient()
        client.complete("test")
        call_body = mock_post.call_args[0][0]
        assert call_body["model"] == client.reason_model

    def test_rate_limit_raises_after_retries(self, mocker):
        import tenacity
        mock_resp = mocker.MagicMock()
        mock_resp.status_code = 429
        mock_resp.raise_for_status.side_effect = requests.HTTPError(response=mock_resp)
        mocker.patch("requests.post", return_value=mock_resp)
        from llm.groq_client import GroqClient
        client = GroqClient()
        # tenacity wraps the HTTPError in a RetryError after exhausting attempts
        with pytest.raises((requests.HTTPError, tenacity.RetryError)):
            client._post({"model": "test", "messages": []})

    def test_strips_whitespace_from_response(self, mocker):
        mocker.patch("llm.groq_client.GroqClient._post").return_value = {
            "choices": [{"message": {"content": "\n\n  trimmed  \n"}}]
        }
        from llm.groq_client import GroqClient
        assert GroqClient().complete("x") == "trimmed"


# ── TogetherEmbedder ──────────────────────────────────────────────────────────

@pytest.mark.unit
class TestTogetherEmbedder:
    def test_embed_returns_float_list(self, mocker):
        vec = [0.1] * 768
        mocker.patch("requests.post").return_value = mocker.MagicMock(
            **{"json.return_value": {"data": [{"embedding": vec}]},
               "raise_for_status.return_value": None}
        )
        from llm.together_embedder import TogetherEmbedder
        result = TogetherEmbedder().embed("test text")
        assert isinstance(result, list)
        assert len(result) == 768
        assert isinstance(result[0], float)

    def test_embed_batch_returns_list_of_lists(self, mocker):
        vec = [0.1] * 768
        mocker.patch("requests.post").return_value = mocker.MagicMock(
            **{"json.return_value": {"data": [{"embedding": vec}, {"embedding": vec}]},
               "raise_for_status.return_value": None}
        )
        from llm.together_embedder import TogetherEmbedder
        results = TogetherEmbedder().embed_batch(["text1", "text2"])
        assert len(results) == 2
        assert len(results[0]) == 768

    def test_embed_retries_on_error(self, mocker):
        call_count = {"n": 0}
        def side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise requests.ConnectionError("timeout")
            mock = mocker.MagicMock()
            mock.json.return_value = {"data": [{"embedding": [0.0] * 768}]}
            mock.raise_for_status.return_value = None
            return mock
        mocker.patch("requests.post", side_effect=side_effect)
        from llm.together_embedder import TogetherEmbedder
        result = TogetherEmbedder().embed("test")
        assert call_count["n"] == 3
        assert len(result) == 768
