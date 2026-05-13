"""
llm/groq_client.py
Groq REST API wrapper with exponential-backoff retry for rate-limit (429) responses.
"""

import os
import time
from functools import lru_cache

import requests
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


def _is_rate_limit(exc: Exception) -> bool:
    return isinstance(exc, requests.HTTPError) and exc.response.status_code == 429


class GroqClient:
    def __init__(self):
        self.api_key = os.environ["GROQ_API_KEY"]
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        self.code_model = os.environ.get("GROQ_CODE_MODEL", "llama-3.1-70b-versatile")
        self.reason_model = os.environ.get("GROQ_REASON_MODEL", "llama-3.1-8b-instant")

    @retry(
        retry=retry_if_exception(_is_rate_limit),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        stop=stop_after_attempt(3),
    )
    def _post(self, body: dict) -> dict:
        resp = requests.post(GROQ_API_URL, json=body, headers=self.headers, timeout=60)
        resp.raise_for_status()
        return resp.json()

    def complete(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> str:
        model = model or self.reason_model
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        data = self._post(body)
        return data["choices"][0]["message"]["content"].strip()

    def complete_system(
        self,
        system: str,
        user: str,
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> str:
        model = model or self.reason_model
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        data = self._post(body)
        return data["choices"][0]["message"]["content"].strip()


@lru_cache(maxsize=1)
def get_groq_client() -> GroqClient:
    return GroqClient()
