"""OpenAI Chat Completions provider (https://platform.openai.com/docs)."""

from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from .base import (
    AgentResponse,
    AIProvider,
    AIProviderError,
    build_system_prompt,
    context_evidence,
)


class OpenAIProvider(AIProvider):
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        *,
        timeout_seconds: float = 30.0,
        max_tokens: int = 1024,
        base_url: str = "https://api.openai.com",
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        if not api_key:
            raise AIProviderError("OpenAI API key is not configured.")
        self._api_key = api_key
        self.model = model
        self._timeout = timeout_seconds
        self._max_tokens = max_tokens
        self._base_url = base_url
        self._transport = transport

    def complete(
        self,
        message: str,
        *,
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        payload = {
            "model": self.model,
            "max_tokens": self._max_tokens,
            "messages": [
                {"role": "system", "content": build_system_prompt(context)},
                {"role": "user", "content": message},
            ],
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            with httpx.Client(
                base_url=self._base_url,
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                resp = client.post("/v1/chat/completions", json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise AIProviderError(f"OpenAI request failed: {exc}") from exc

        if resp.status_code != 200:
            raise AIProviderError(
                f"OpenAI API returned {resp.status_code}: {resp.text[:200]}"
            )

        try:
            body = resp.json()
            choices = body.get("choices") or []
            first = (choices[0].get("message") or {}) if choices else {}
            answer = (first.get("content") or "").strip()
            usage = body.get("usage") or {}
        except ValueError as exc:
            raise AIProviderError("OpenAI API returned malformed JSON.") from exc

        if not answer:
            raise AIProviderError("OpenAI API returned an empty answer.")

        tools, citations = context_evidence(context)
        return AgentResponse(
            answer=answer,
            tools_used=tools,
            citations=citations,
            provider="openai",
            model=body.get("model", self.model),
            tokens_input=int(usage.get("prompt_tokens") or 0),
            tokens_output=int(usage.get("completion_tokens") or 0),
        )
