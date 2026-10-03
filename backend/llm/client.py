"""Provider-agnostic LLM client for an OpenAI-compatible chat endpoint (FR-701).

Configuration comes entirely from environment variables (.env):
LLM_BASE_URL, LLM_API_KEY, LLM_MODEL.
"""
from __future__ import annotations

import httpx

from backend.config import Settings


class LLMUnavailableError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, settings: Settings, timeout: float = 60.0):
        self.base_url = (settings.llm_base_url or "").rstrip("/")
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)

    def chat(self, messages: list[dict]) -> str:
        if not self.available:
            raise LLMUnavailableError("LLM not configured (LLM_BASE_URL/LLM_API_KEY/LLM_MODEL missing)")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            resp = httpx.post(
                self.base_url + "/chat/completions",
                json={"model": self.model, "messages": messages},
                headers=headers,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except LLMUnavailableError:
            raise
        except Exception as e:
            raise LLMUnavailableError(f"LLM call failed: {e}") from e
