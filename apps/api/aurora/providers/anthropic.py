"""Anthropic Messages API provider (https://docs.anthropic.com)."""

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

_API_VERSION = "2023-06-01"


class AnthropicAIProvider(AIProvider):
    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-5",
        *,
        timeout_seconds: float = 30.0,
        max_tokens: int = 1024,
        base_url: str = "https://api.anthropic.com",
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        if not api_key:
            raise AIProviderError("Anthropic API key is not configured.")
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
            "system": build_system_prompt(context),
            "messages": [{"role": "user", "content": message}],
        }
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": _API_VERSION,
        }
        try:
            with httpx.Client(
                base_url=self._base_url,
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                resp = client.post("/v1/messages", json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise AIProviderError(f"Anthropic request failed: {exc}") from exc

        if resp.status_code != 200:
            raise AIProviderError(
                f"Anthropic API returned {resp.status_code}: {resp.text[:200]}"
            )

        try:
            body = resp.json()
            answer = "".join(
                block.get("text", "")
                for block in body.get("content", [])
                if block.get("type") == "text"
            ).strip()
            usage = body.get("usage") or {}
        except ValueError as exc:
            raise AIProviderError("Anthropic API returned malformed JSON.") from exc

        if not answer:
            raise AIProviderError("Anthropic API returned an empty answer.")

        tools, citations = context_evidence(context)
        return AgentResponse(
            answer=answer,
            tools_used=tools,
            citations=citations,
            provider="anthropic",
            model=body.get("model", self.model),
            tokens_input=int(usage.get("input_tokens") or 0),
            tokens_output=int(usage.get("output_tokens") or 0),
        )
