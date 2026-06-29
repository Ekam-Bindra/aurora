"""Metric registry — formula metadata for the explainability layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class MetricDefinition:
    id: str
    name: str
    formula: str
    unit: str  # cents | ratio | months | percent
    inputs: List[str]
    formula_version: str = "2026.06"


METRIC_REGISTRY: Dict[str, MetricDefinition] = {
    "revenue": MetricDefinition(
        id="revenue",
        name="Revenue",
        formula="SUM(revenue_record.amount_cents) per period",
        unit="cents",
        inputs=["revenue_record.amount_cents", "revenue_record.period_month"],
    ),
    "gross_margin": MetricDefinition(
        id="gross_margin",
        name="Gross Margin",
        formula="(revenue - cogs) / revenue",
        unit="ratio",
        inputs=["revenue_cents", "cogs_cents"],
    ),
    "operating_margin": MetricDefinition(
        id="operating_margin",
        name="Operating Margin",
        formula="(revenue - cogs - opex) / revenue, where opex = expenses - cogs",
        unit="ratio",
        inputs=["revenue_cents", "cogs_cents", "expenses_cents"],
    ),
    "net_burn": MetricDefinition(
        id="net_burn",
        name="Net Burn",
        formula="mean(expenses - revenue) over trailing k months (k=3); positive = cash consumed",
        unit="cents",
        inputs=["expenses_cents", "revenue_cents", "trailing_window=3"],
    ),
    "cash_runway_months": MetricDefinition(
        id="cash_runway_months",
        name="Cash Runway",
        formula="cash_cents / net_burn_cents when net_burn > 0; else infinite (profitable)",
        unit="months",
        inputs=["cash_cents", "net_burn_cents"],
    ),
    "revenue_mtd": MetricDefinition(
        id="revenue_mtd",
        name="Revenue (month-to-date)",
        formula="revenue_cents for the as_of month",
        unit="cents",
        inputs=["revenue_cents", "as_of_month"],
    ),
}


def get_metric(metric_id: str) -> Optional[MetricDefinition]:
    return METRIC_REGISTRY.get(metric_id)
