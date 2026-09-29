"""Provider adapters. NVIDIA, Groq and OpenRouter all expose an OpenAI-compatible
/chat/completions. Errors are classified into failover triggers; raw provider
messages never leave this module toward the client."""
from __future__ import annotations

from dataclasses import dataclass

import httpx

BASE = {
    "nvidia": "https://integrate.api.nvidia.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    # Google AI Studio key via Gemini's OpenAI-compatible endpoint (no GCP/Vertex project).
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
}


@dataclass
class Completion:
    text: str
    finish_reason: str
    tokens: int
    headers: dict


class ProviderError(Exception):
    """kind: rate_limit | auth | not_found | server | timeout | network | bad_request"""
    def __init__(self, kind: str, status: int | None = None):
        super().__init__(kind)
        self.kind, self.status = kind, status


def classify(status: int) -> str:
    if status == 429 or status == 402:
        return "rate_limit"          # 402 = unfunded/quota on OpenRouter
    if status in (401, 403):
        return "auth"
    if status in (404, 410):
        return "not_found"
    if status in (400, 413, 422):
        return "bad_request"
    if status == 408:
        return "timeout"
    return "server"


class OpenAICompatAdapter:
    def __init__(self, keys: dict[str, str], client: httpx.Client | None = None):
        self.keys, self.client = keys, client or httpx.Client()

    def complete(self, provider: str, model: str, messages: list[dict], *, timeout_s: float,
                 json_mode: bool = False, max_tokens: int = 1500) -> Completion:
        key = self.keys.get(provider)
        if not key or provider not in BASE:
            raise ProviderError("auth")
        payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.2}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        extra = {"provider": {"data_collection": "deny"}} if provider == "openrouter" else {}
        try:
            r = self.client.post(f"{BASE[provider]}/chat/completions", json={**payload, **extra},
                                 headers={"Authorization": f"Bearer {key}"}, timeout=timeout_s)
        except httpx.TimeoutException:
            raise ProviderError("timeout")
        except httpx.HTTPError:
            raise ProviderError("network")
        if r.status_code != 200:
            raise ProviderError(classify(r.status_code), r.status_code)
        try:
            d = r.json()
            ch = d["choices"][0]
            return Completion(ch["message"].get("content") or "", ch.get("finish_reason") or "",
                              (d.get("usage") or {}).get("total_tokens", 0), dict(r.headers))
        except (ValueError, KeyError, IndexError, TypeError):
            raise ProviderError("server", r.status_code)
