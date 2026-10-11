"""LLM client for OpenAI-compatible APIs."""

import os
from typing import Callable

import requests
from dotenv import load_dotenv

load_dotenv()


class LLMError(Exception):
    """Raised when an LLM API call fails."""

    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(f"LLM API error: status={status_code}, body={body[:200]}")


class LLMClient:
    """Client for OpenAI-compatible chat completions API."""

    def __init__(self):
        self.base_url = os.getenv("MODEL_BASE_URL", "").rstrip("/")
        self.api_key = os.getenv("MODEL_API_KEY", "")
        self.model_name = os.getenv("MODEL_NAME", "")

        if not self.base_url:
            raise ValueError("MODEL_BASE_URL must be set")
        if not self.api_key:
            raise ValueError("MODEL_API_KEY must be set")
        if not self.model_name:
            raise ValueError("MODEL_NAME must be set")

        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def complete(self, system: str, user: str, json_mode: bool = False) -> str:
        """Call the chat completions endpoint."""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        response = requests.post(url, headers=headers, json=payload, timeout=60)

        if not response.ok:
            raise LLMError(response.status_code, response.text[:200])

        data = response.json()
        content = data["choices"][0]["message"]["content"]

        usage = data.get("usage", {})
        self.calls += 1
        self.prompt_tokens += usage.get("prompt_tokens", 0)
        self.completion_tokens += usage.get("completion_tokens", 0)

        return content


class FakeLLMClient:
    """Fake LLM client for testing."""

    def __init__(self, response: str | Callable[[str, str], str]):
        self._response = response
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def complete(self, system: str, user: str, json_mode: bool = False) -> str:
        self.calls += 1
        if callable(self._response):
            return self._response(system, user)
        return self._response


def get_llm() -> LLMClient | FakeLLMClient:
    """Get the appropriate LLM client based on LLM_MODE."""
    mode = os.getenv("LLM_MODE", "live").lower()
    if mode == "fake":
        return FakeLLMClient("Fake response")
    return LLMClient()