"""Anthropic/OpenAI provider adapters — request shape, parsing, and failure modes.

Uses httpx.MockTransport so no network or keys are required; the mock provider
remains the default and is covered by test_agent.py.
"""

from __future__ import annotations

import json

import httpx
import pytest

from aurora.core.config import Settings
from aurora.providers.anthropic import AnthropicAIProvider
from aurora.providers.base import AIProviderError, build_system_prompt
from aurora.providers.mock import MockAIProvider
from aurora.providers.openai import OpenAIProvider
from aurora.services.agent import _get_provider

CONTEXT = {
    "metrics": {"overview": {"kpis": {"cash_runway_months": {"value": 14.2}}}},
    "genome": {
        "overall_score": 42,
        "dimensions": [
            {"dimension": "liquidity", "score": 61, "severity": "high", "drivers": ["x"]}
        ],
    },
    "simulation_result": {
        "id": "sim-1",
        "results": [
            {
                "metric": "cash_runway_months",
                "summary": {"p50": 9.1},
                "distribution": {"bins": [1, 2, 3]},
            }
        ],
        "recommendations": [{"title": "Open credit line"}],
    },
    "simulation_id": "sim-1",
    "simulation_args": {"shock": "revenue_-10%"},
}


def _anthropic_ok(request: httpx.Request) -> httpx.Response:
    assert request.url.path == "/v1/messages"
    assert request.headers["x-api-key"] == "test-key"
    assert request.headers["anthropic-version"]
    payload = json.loads(request.content)
    assert payload["model"] == "claude-sonnet-5"
    assert payload["messages"] == [{"role": "user", "content": "What is my runway?"}]
    assert "cash_runway_months" in payload["system"]
    # Distributions must be trimmed out of the prompt.
    assert "bins" not in payload["system"]
    return httpx.Response(
        200,
        json={
            "model": "claude-sonnet-5",
            "content": [{"type": "text", "text": "Runway is ~14 months."}],
            "usage": {"input_tokens": 210, "output_tokens": 18},
        },
    )


def test_anthropic_success_parses_answer_tokens_and_evidence():
    provider = AnthropicAIProvider(
        "test-key", transport=httpx.MockTransport(_anthropic_ok)
    )
    resp = provider.complete("What is my runway?", context=CONTEXT)
    assert resp.answer == "Runway is ~14 months."
    assert resp.provider == "anthropic"
    assert resp.model == "claude-sonnet-5"
    assert resp.tokens_input == 210 and resp.tokens_output == 18
    refs = {c["ref"] for c in resp.citations}
    assert refs == {"/metrics/overview", "/risk/genome", "/explain/simulation/sim-1"}
    assert {t["tool"] for t in resp.tools_used} == {
        "search_metrics_context",
        "run_simulation",
    }


@pytest.mark.parametrize("status", [401, 429, 500])
def test_anthropic_http_errors_raise(status):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(status, json={"error": {"message": "nope"}})
    )
    provider = AnthropicAIProvider("test-key", transport=transport)
    with pytest.raises(AIProviderError, match=str(status)):
        provider.complete("hi")


def test_anthropic_network_error_raises():
    def _boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out")

    provider = AnthropicAIProvider("test-key", transport=httpx.MockTransport(_boom))
    with pytest.raises(AIProviderError, match="request failed"):
        provider.complete("hi")


def test_anthropic_empty_answer_raises():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"content": [], "usage": {}})
    )
    provider = AnthropicAIProvider("test-key", transport=transport)
    with pytest.raises(AIProviderError, match="empty answer"):
        provider.complete("hi")


def _openai_ok(request: httpx.Request) -> httpx.Response:
    assert request.url.path == "/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer test-key"
    payload = json.loads(request.content)
    assert payload["model"] == "gpt-4o-mini"
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][1] == {"role": "user", "content": "What is my runway?"}
    return httpx.Response(
        200,
        json={
            "model": "gpt-4o-mini",
            "choices": [{"message": {"role": "assistant", "content": "About 14 months."}}],
            "usage": {"prompt_tokens": 190, "completion_tokens": 12},
        },
    )


def test_openai_success_parses_answer_and_tokens():
    provider = OpenAIProvider("test-key", transport=httpx.MockTransport(_openai_ok))
    resp = provider.complete("What is my runway?", context=CONTEXT)
    assert resp.answer == "About 14 months."
    assert resp.provider == "openai"
    assert resp.tokens_input == 190 and resp.tokens_output == 12


def test_openai_http_error_raises():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(429, text="rate limited")
    )
    provider = OpenAIProvider("test-key", transport=transport)
    with pytest.raises(AIProviderError, match="429"):
        provider.complete("hi")


def test_system_prompt_grounds_and_trims():
    prompt = build_system_prompt(CONTEXT)
    assert "never invent" in prompt
    assert "cash_runway_months" in prompt
    assert "bins" not in prompt  # distributions dropped
    assert "drivers" not in prompt  # genome trimmed to dimension/score/severity


def test_factory_selects_provider_by_settings():
    assert isinstance(_get_provider(Settings(ai_provider="mock")), MockAIProvider)
    anthropic = _get_provider(
        Settings(ai_provider="anthropic", anthropic_api_key="k", anthropic_model="m-1")
    )
    assert isinstance(anthropic, AnthropicAIProvider) and anthropic.model == "m-1"
    openai = _get_provider(Settings(ai_provider="openai", openai_api_key="k"))
    assert isinstance(openai, OpenAIProvider)


def test_runtime_validation_rejects_misconfiguration():
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        Settings(ai_provider="anthropic").validate_runtime()
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        Settings(ai_provider="openai").validate_runtime()
    with pytest.raises(RuntimeError, match="not implemented"):
        Settings(ai_provider="bedrock").validate_runtime()
    with pytest.raises(RuntimeError, match="AI_PROVIDER"):
        Settings(ai_provider="grok").validate_runtime()


def test_factory_passes_openai_base_url():
    provider = _get_provider(
        Settings(
            ai_provider="openai",
            openai_api_key="k",
            openai_base_url="https://api.groq.com/openai",
        )
    )
    assert provider._base_url == "https://api.groq.com/openai"
