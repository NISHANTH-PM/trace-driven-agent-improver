"""Tests for the LLM client."""

import os
from unittest.mock import Mock, patch

import pytest

from app.llm import FakeLLMClient, LLMClient, LLMError, get_llm


class TestFakeLLMClient:
    """Tests for FakeLLMClient."""

    def test_fake_client_returns_static_response(self):
        client = FakeLLMClient("Static response")
        result = client.complete("system prompt", "user prompt")
        assert result == "Static response"
        assert client.calls == 1

    def test_fake_client_returns_callable_response(self):
        def responder(system: str, user: str) -> str:
            return f"System: {system}, User: {user}"

        client = FakeLLMClient(responder)
        result = client.complete("sys", "usr")
        assert result == "System: sys, User: usr"
        assert client.calls == 1

    def test_fake_client_tracks_calls(self):
        client = FakeLLMClient("response")
        client.complete("sys", "usr")
        client.complete("sys", "usr")
        assert client.calls == 2

    def test_fake_client_json_mode_ignored(self):
        client = FakeLLMClient("response")
        result = client.complete("sys", "usr", json_mode=True)
        assert result == "response"


class TestLLMClient:
    """Tests for LLMClient (mocked, no real network calls)."""

    @patch.dict(os.environ, {
        "MODEL_BASE_URL": "https://api.example.com",
        "MODEL_API_KEY": "test-key",
        "MODEL_NAME": "test-model",
    })
    def test_client_initialization(self):
        client = LLMClient()
        assert client.base_url == "https://api.example.com"
        assert client.api_key == "test-key"
        assert client.model_name == "test-model"
        assert client.calls == 0
        assert client.prompt_tokens == 0
        assert client.completion_tokens == 0

    @patch.dict(os.environ, {
        "MODEL_BASE_URL": "https://api.example.com",
        "MODEL_API_KEY": "test-key",
        "MODEL_NAME": "test-model",
    })
    @patch("requests.post")
    def test_successful_completion(self, mock_post):
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello world"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_post.return_value = mock_response

        client = LLMClient()
        result = client.complete("You are helpful", "Say hello")

        assert result == "Hello world"
        assert client.calls == 1
        assert client.prompt_tokens == 10
        assert client.completion_tokens == 5
        mock_post.assert_called_once()

    @patch.dict(os.environ, {
        "MODEL_BASE_URL": "https://api.example.com",
        "MODEL_API_KEY": "test-key",
        "MODEL_NAME": "test-model",
    })
    @patch("requests.post")
    def test_successful_completion_no_usage(self, mock_post):
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello world"}}],
        }
        mock_post.return_value = mock_response

        client = LLMClient()
        result = client.complete("You are helpful", "Say hello")

        assert result == "Hello world"
        assert client.calls == 1
        assert client.prompt_tokens == 0
        assert client.completion_tokens == 0

    @patch.dict(os.environ, {
        "MODEL_BASE_URL": "https://api.example.com",
        "MODEL_API_KEY": "test-key",
        "MODEL_NAME": "test-model",
    })
    @patch("requests.post")
    def test_http_error_raises_llm_error(self, mock_post):
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 401
        mock_response.text = "Unauthorized: invalid API key"
        mock_post.return_value = mock_response

        client = LLMClient()
        with pytest.raises(LLMError) as exc_info:
            client.complete("sys", "usr")

        assert exc_info.value.status_code == 401
        assert "401" in str(exc_info.value)
        assert "Unauthorized" in str(exc_info.value)
        assert "test-key" not in str(exc_info.value)

    @patch.dict(os.environ, {
        "MODEL_BASE_URL": "https://api.example.com",
        "MODEL_API_KEY": "test-key",
        "MODEL_NAME": "test-model",
    })
    @patch("requests.post")
    def test_error_body_truncated_to_200_chars(self, mock_post):
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 500
        mock_response.text = "x" * 300
        mock_post.return_value = mock_response

        client = LLMClient()
        with pytest.raises(LLMError) as exc_info:
            client.complete("sys", "usr")

        assert len(exc_info.value.body) == 200

    @patch.dict(os.environ, {
        "MODEL_BASE_URL": "https://api.example.com",
        "MODEL_API_KEY": "test-key",
        "MODEL_NAME": "test-model",
    })
    @patch("requests.post")
    def test_json_mode_adds_response_format(self, mock_post):
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"key": "value"}'}}],
            "usage": {},
        }
        mock_post.return_value = mock_response

        client = LLMClient()
        client.complete("sys", "usr", json_mode=True)

        call_args = mock_post.call_args
        payload = call_args.kwargs["json"]
        assert payload["response_format"] == {"type": "json_object"}

    @patch.dict(os.environ, {
        "MODEL_BASE_URL": "https://api.example.com",
        "MODEL_API_KEY": "test-key",
        "MODEL_NAME": "test-model",
    })
    @patch("requests.post")
    def test_request_timeout_60s(self, mock_post):
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {},
        }
        mock_post.return_value = mock_response

        client = LLMClient()
        client.complete("sys", "usr")

        call_args = mock_post.call_args
        assert call_args.kwargs["timeout"] == 60

    @patch.dict(os.environ, {
        "MODEL_BASE_URL": "https://api.example.com",
        "MODEL_API_KEY": "test-key",
        "MODEL_NAME": "test-model",
    })
    @patch("requests.post")
    def test_accumulates_tokens_across_calls(self, mock_post):
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3},
        }
        mock_post.return_value = mock_response

        client = LLMClient()
        client.complete("sys", "usr1")
        client.complete("sys", "usr2")
        client.complete("sys", "usr3")

        assert client.calls == 3
        assert client.prompt_tokens == 15
        assert client.completion_tokens == 9

    def test_missing_env_raises_value_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="MODEL_BASE_URL must be set"):
                LLMClient()

    def test_missing_api_key_raises_value_error(self):
        with patch.dict(os.environ, {
            "MODEL_BASE_URL": "https://api.example.com",
            "MODEL_NAME": "test-model",
        }, clear=True):
            with pytest.raises(ValueError, match="MODEL_API_KEY must be set"):
                LLMClient()

    def test_missing_model_name_raises_value_error(self):
        with patch.dict(os.environ, {
            "MODEL_BASE_URL": "https://api.example.com",
            "MODEL_API_KEY": "test-key",
        }, clear=True):
            with pytest.raises(ValueError, match="MODEL_NAME must be set"):
                LLMClient()


class TestGetLLM:
    """Tests for get_llm factory function."""

    @patch.dict(os.environ, {"LLM_MODE": "fake"}, clear=True)
    def test_get_llm_fake_mode(self):
        client = get_llm()
        assert isinstance(client, FakeLLMClient)

    @patch.dict(os.environ, {"LLM_MODE": "live"}, clear=True)
    @patch.dict(os.environ, {
        "MODEL_BASE_URL": "https://api.example.com",
        "MODEL_API_KEY": "test-key",
        "MODEL_NAME": "test-model",
    }, clear=False)
    def test_get_llm_live_mode(self):
        client = get_llm()
        assert isinstance(client, LLMClient)

    @patch.dict(os.environ, {}, clear=True)
    def test_get_llm_defaults_to_live(self):
        with patch.dict(os.environ, {
            "MODEL_BASE_URL": "https://api.example.com",
            "MODEL_API_KEY": "test-key",
            "MODEL_NAME": "test-model",
        }, clear=False):
            client = get_llm()
            assert isinstance(client, LLMClient)