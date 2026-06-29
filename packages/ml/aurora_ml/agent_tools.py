"""Agent tool helpers — lightweight RAG over metrics and graph context (Phase 6)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session


def search_metrics_context(
    session: Session,
    company_id: str,
    *,
    financial_service: Any,
) -> Dict[str, Any]:
    """Gather KPI snapshot for agent RAG context."""
    overview = financial_service.metrics_overview(session, company_id)
    cash = financial_service.cash_summary(session, company_id)
    return {
        "overview": overview,
        "cash": cash,
    }


def format_metric_citations(context: Dict[str, Any]) -> List[Dict[str, str]]:
    return [
        {"type": "metric", "ref": "/metrics/overview"},
        {"type": "metric", "ref": "/financials/cash"},
    ]


def build_revenue_shock_scenario(
    pct_change: float,
    *,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Build scenario assumptions for a revenue shock (used by mock agent)."""
    pct = pct_change / 100.0 if abs(pct_change) > 1 else pct_change
    return {
        "name": name or f"Revenue change {pct_change:+.0f}%",
        "horizon_periods": 12,
        "trials": 5000,
        "assumptions": {
            "shocks": [{"type": "revenue_change", "pct_change": pct}],
            "distributions": {
                "revenue_growth_pct": {"dist": "normal", "mean": 0.0, "std": 0.015},
            },
        },
    }
