"""Deterministic mock AI provider — no external keys required (MVP default)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .base import AgentResponse, AIProvider


class MockAIProvider(AIProvider):
    """Pattern-matches common CFO questions and invokes simulation/metric tools via context."""

    MODEL = "aurora-mock-1"

    def complete(
        self,
        message: str,
        *,
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        ctx = context or {}
        msg = message.lower()
        tools: List[Dict[str, Any]] = []
        citations: List[Dict[str, str]] = []

        metrics = ctx.get("metrics") or {}
        cash = metrics.get("cash") or {}
        overview = metrics.get("overview") or {}
        kpis = overview.get("kpis") or {}
        runway_kpi = kpis.get("cash_runway_months") or {}
        baseline_runway = runway_kpi.get("value")

        sim_result = ctx.get("simulation_result")
        sim_id = ctx.get("simulation_id")

        if sim_result and sim_id:
            runway_summary = next(
                (
                    r["summary"]
                    for r in sim_result.get("results", [])
                    if r["metric"] == "cash_runway_months"
                ),
                {},
            )
            p50 = runway_summary.get("p50", baseline_runway)
            p5 = runway_summary.get("p5", p50 * 0.5)
            recs = sim_result.get("recommendations") or []
            actions = "; ".join(
                f"({i + 1}) {r['title']}" for i, r in enumerate(recs[:3])
            )
            answer = (
                f"At the requested shock, projected cash runway falls to ~{p50:.1f} months "
                f"(p50; p5 ≈ {p5:.1f}). "
                f"The main driver is reduced collections against fixed payroll. "
                f"Top actions: {actions or '(1) review burn, (2) accelerate AR'}. "
                f"See the simulation for the full distribution."
            )
            tools.append(
                {
                    "tool": "run_simulation",
                    "args": ctx.get("simulation_args") or {},
                    "result_ref": f"/simulations/{sim_id}",
                }
            )
            citations.extend(
                [
                    {"type": "metric", "ref": "/financials/cash"},
                    {"type": "simulation", "ref": f"/simulations/{sim_id}"},
                ]
            )
        elif "runway" in msg or "cash" in msg:
            rw = baseline_runway if baseline_runway is not None else 8.0
            burn = cash.get("net_burn_cents", 0)
            answer = (
                f"Current cash runway is approximately {rw:.1f} months based on trailing net burn "
                f"of ${abs(burn) / 100:,.0f}/month. "
                f"Ask me to simulate a revenue or expense shock for a full distribution."
            )
            tools.append({"tool": "get_metric", "args": {"metric": "cash_runway_months"}})
            citations.append({"type": "metric", "ref": "/financials/cash"})
        elif "risk" in msg or "genome" in msg:
            genome = ctx.get("genome") or {}
            dims = genome.get("dimensions") or []
            top = sorted(dims, key=lambda d: d.get("score", 0), reverse=True)[:2]
            dim_text = ", ".join(
                f"{d.get('dimension', '?')} ({d.get('severity', '?')})" for d in top
            )
            answer = (
                f"The enterprise risk genome highlights: "
                f"{dim_text or 'liquidity and concentration'}. "
                f"Overall score is {genome.get('overall_score', 'N/A')}. "
                f"See /risk/genome for full drivers and recommended actions."
            )
            tools.append({"tool": "get_risk_genome", "args": {}})
            citations.append({"type": "risk", "ref": "/risk/genome"})
        else:
            answer = (
                "I can help with cash runway, revenue shocks, expense scenarios, and risk drivers. "
                "Try: 'What's our cash runway if revenue drops 15% next quarter?'"
            )

        tokens_in = max(100, len(message.split()) * 12)
        tokens_out = max(80, len(answer.split()) * 10)
        return AgentResponse(
            answer=answer,
            tools_used=tools,
            citations=citations,
            provider="mock",
            model=self.MODEL,
            tokens_input=tokens_in,
            tokens_output=tokens_out,
        )

    @staticmethod
    def detect_revenue_shock_pct(message: str) -> Optional[float]:
        """Extract a revenue drop/rise percentage from natural language."""
        msg = message.lower()
        patterns = [
            r"(?:drop|decline|decrease|fall|down)\s*(?:of\s*)?(\d+(?:\.\d+)?)\s*%",
            r"(\d+(?:\.\d+)?)\s*%\s*(?:drop|decline|decrease|fall)",
            r"revenue\s*(?:drop|decline|decrease|fall)\s*(?:of\s*)?(\d+(?:\.\d+)?)",
        ]
        for pat in patterns:
            m = re.search(pat, msg)
            if m:
                return -float(m.group(1))
        if "15" in msg and ("drop" in msg or "decline" in msg or "down" in msg):
            return -15.0
        return None
