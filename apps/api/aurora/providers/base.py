"""AI provider abstraction (Architecture §8)."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


class AIProviderError(RuntimeError):
    """Upstream AI provider failure (network, auth, rate limit, bad response)."""


@dataclass
class AgentResponse:
    answer: str
    tools_used: List[Dict[str, Any]] = field(default_factory=list)
    citations: List[Dict[str, str]] = field(default_factory=list)
    provider: str = "mock"
    model: str = "aurora-mock-1"
    tokens_input: int = 0
    tokens_output: int = 0


class AIProvider(ABC):
    @abstractmethod
    def complete(
        self,
        message: str,
        *,
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        ...


SYSTEM_PREAMBLE = (
    "You are AURORA, the executive finance copilot for a multi-tenant decision-intelligence "
    "platform. Answer the CFO's question using ONLY the tenant data provided below. Be concise "
    "(2-5 sentences), lead with the number, state units (months, USD, %), and never invent "
    "figures — if the data below cannot answer the question, say so explicitly. Monetary values "
    "in the data are in cents unless a field name says otherwise."
)


def _compact_context(context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Trim the tool context to what a prompt needs (drop distributions/histograms)."""
    ctx = context or {}
    out: Dict[str, Any] = {}
    if ctx.get("metrics"):
        out["metrics"] = ctx["metrics"]
    genome = ctx.get("genome")
    if genome:
        out["risk_genome"] = {
            "overall_score": genome.get("overall_score"),
            "dimensions": [
                {k: d.get(k) for k in ("dimension", "score", "severity")}
                for d in (genome.get("dimensions") or [])
            ],
        }
    sim = ctx.get("simulation_result")
    if sim:
        out["simulation"] = {
            "id": sim.get("id"),
            "results": [
                {"metric": r.get("metric"), "summary": r.get("summary")}
                for r in (sim.get("results") or [])
            ],
            "risk_deltas": sim.get("risk_deltas"),
            "recommendations": (sim.get("recommendations") or [])[:3],
        }
    return out


def build_system_prompt(context: Optional[Dict[str, Any]]) -> str:
    data = _compact_context(context)
    return f"{SYSTEM_PREAMBLE}\n\nTenant data (JSON):\n{json.dumps(data, default=str)}"


def context_evidence(
    context: Optional[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """Deterministic tools_used/citations mirroring the context the agent assembled,
    so real-provider answers carry the same evidence trail the UI renders for mock."""
    ctx = context or {}
    tools: List[Dict[str, Any]] = []
    citations: List[Dict[str, str]] = []
    if ctx.get("metrics"):
        tools.append({"tool": "search_metrics_context", "args": {}})
        citations.append({"type": "metric", "ref": "/metrics/overview"})
    if ctx.get("genome"):
        citations.append({"type": "risk", "ref": "/risk/genome"})
    if ctx.get("simulation_result"):
        tools.append(
            {"tool": "run_simulation", "args": ctx.get("simulation_args") or {}}
        )
        sim_id = ctx.get("simulation_id")
        if sim_id:
            citations.append(
                {"type": "simulation", "ref": f"/explain/simulation/{sim_id}"}
            )
    return tools, citations
