"""Enterprise Risk Genome scorers (Phase 5).

Computes all 8 dimensions with normalized sub-factors per
docs/architecture/financial-risk-simulation-models.md §4.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .financial import FinancialEngine

RISK_DIMENSIONS = [
    "financial",
    "customer_concentration",
    "vendor_supply",
    "operational",
    "liquidity",
    "talent",
    "compliance",
    "market",
]

DIMENSION_WEIGHTS = {
    "financial": 0.16,
    "customer_concentration": 0.13,
    "vendor_supply": 0.12,
    "operational": 0.12,
    "liquidity": 0.18,
    "talent": 0.10,
    "compliance": 0.09,
    "market": 0.10,
}


def _severity(score: float) -> str:
    if score <= 25:
        return "low"
    if score <= 50:
        return "moderate"
    if score <= 75:
        return "high"
    return "critical"


def _clip(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _threshold_linear(value: float, t_min: float, t_max: float) -> float:
    if t_max <= t_min:
        return 0.0
    return _clip((t_max - value) / (t_max - t_min))


def _logistic(value: float, x0: float = 0.0, k: float = 8.0) -> float:
    return _clip(1.0 / (1.0 + math.exp(-k * (value - x0))))


def _signal_id(dimension: str, computed_at: str) -> str:
    ts = computed_at.replace(":", "").replace("-", "").replace("+", "")[:14]
    return f"rs_{dimension}_{ts}"


@dataclass
class RiskDriver:
    factor: str
    value: float
    contribution: float


@dataclass
class RiskDimension:
    dimension: str
    score: float
    severity: str
    drivers: List[RiskDriver] = field(default_factory=list)
    explanation: str = ""
    recommended_actions: List[str] = field(default_factory=list)
    signal_id: str = ""


@dataclass
class RiskGenome:
    computed_at: str
    overall_score: float
    dimensions: List[RiskDimension]


@dataclass
class RiskOperationalContext:
    """Supplementary inputs gathered from canonical data + graph."""

    red_project_ratio: float = 0.0
    budget_variance_pct: float = 0.0
    dependency_centrality: float = 0.0
    overdue_ar_ratio: float = 0.0
    key_person_max_allocation: float = 0.0
    critical_open_roles: int = 0
    expiring_contracts: int = 0
    expired_critical_contracts: int = 0
    audit_findings: int = 0
    vendor_critical_spo: float = 0.0
    delivery_reliability: float = 0.85
    attrition_rate: float = 0.0


class RiskGenomeEngine:
    """Compute the 8-dimension risk genome from financial + concentration + operational inputs."""

    def __init__(
        self,
        engine: FinancialEngine,
        *,
        customer_concentration: Optional[Dict[str, Any]] = None,
        vendor_concentration: Optional[Dict[str, Any]] = None,
        context: Optional[RiskOperationalContext] = None,
    ) -> None:
        self._engine = engine
        self._customer_conc = customer_concentration or {}
        self._vendor_conc = vendor_concentration or {}
        self._ctx = context or RiskOperationalContext()

    def compute(self) -> RiskGenome:
        computed_at = datetime.now(timezone.utc).isoformat()
        dims = [
            self._financial(computed_at),
            self._customer_concentration(computed_at),
            self._vendor_supply(computed_at),
            self._operational(computed_at),
            self._liquidity(computed_at),
            self._talent(computed_at),
            self._compliance(computed_at),
            self._market(computed_at),
        ]
        overall = sum(d.score * DIMENSION_WEIGHTS.get(d.dimension, 0.125) for d in dims)
        return RiskGenome(
            computed_at=computed_at,
            overall_score=round(overall, 1),
            dimensions=dims,
        )

    def _financial(self, computed_at: str) -> RiskDimension:
        latest = self._engine.latest
        gm = self._engine.gross_margin(latest) if latest else None
        om = self._engine.operating_margin(latest) if latest else None
        gm_risk = _threshold_linear(gm or 0.35, 0.20, 0.50)
        om_risk = _threshold_linear(0.50 - (om or 0.05), 0.0, 0.30)

        earnings_vol = 0.0
        if len(self._engine.rows) >= 6:
            margins = [
                self._engine.operating_margin(r) or 0.0
                for r in self._engine.rows[-6:]
            ]
            mean_m = sum(margins) / len(margins)
            earnings_vol = _clip(
                math.sqrt(sum((m - mean_m) ** 2 for m in margins) / len(margins)) / 0.15
            )

        score = 100 * (0.45 * gm_risk + 0.35 * om_risk + 0.20 * earnings_vol)
        drivers = [
            RiskDriver("gross_margin", gm or 0.0, round(0.45 * gm_risk, 2)),
            RiskDriver("operating_margin", om or 0.0, round(0.35 * om_risk, 2)),
            RiskDriver(
                "earnings_volatility", round(earnings_vol, 3), round(0.20 * earnings_vol, 2)
            ),
        ]
        return RiskDimension(
            dimension="financial",
            score=round(score, 1),
            severity=_severity(score),
            drivers=drivers,
            explanation="Margin levels and earnings volatility vs. historical targets.",
            recommended_actions=["Review product mix margin", "Audit discretionary spend"],
            signal_id=_signal_id("financial", computed_at),
        )

    def _customer_concentration(self, computed_at: str) -> RiskDimension:
        top_list = self._customer_conc.get("top") or []
        amounts = [x.get("amount_cents", 0) for x in top_list]
        if amounts:
            _, hhi_norm = FinancialEngine.concentration(amounts)
            total = sum(amounts) or 1
            top_customer = top_list[0].get("amount_cents", 0) / total
            top_10 = sum(amounts[:10]) / total
        else:
            hhi_norm = float(self._customer_conc.get("top_5_share") or 0.35)
            top_customer = hhi_norm * 0.4
            top_10 = hhi_norm

        hhi_risk = _clip(hhi_norm)
        top_risk = _clip(top_customer / 0.20)
        top10_risk = _clip(top_10 / 0.50)
        score = 100 * (0.40 * hhi_risk + 0.35 * top_risk + 0.25 * top10_risk)
        explanation = (
            f"Top customer is {top_customer * 100:.1f}% of revenue; "
            f"top-5 share is {float(self._customer_conc.get('top_5_share') or top_10) * 100:.0f}%."
        )
        return RiskDimension(
            dimension="customer_concentration",
            score=round(score, 1),
            severity=_severity(score),
            drivers=[
                RiskDriver("normalized_hhi", round(hhi_norm, 3), round(0.40 * hhi_risk, 2)),
                RiskDriver("top_customer_share", round(top_customer, 3), round(0.35 * top_risk, 2)),
                RiskDriver("top_10_share", round(top_10, 3), round(0.25 * top10_risk, 2)),
            ],
            explanation=explanation,
            recommended_actions=[
                "Diversify pipeline",
                "Negotiate multi-year retention contracts",
            ],
            signal_id=_signal_id("customer_concentration", computed_at),
        )

    def _vendor_supply(self, computed_at: str) -> RiskDimension:
        top_share = float(self._vendor_conc.get("top_5_share") or 0.30)
        top_list = self._vendor_conc.get("top") or []
        amounts = [x.get("amount_cents", 0) for x in top_list]
        _, hhi_norm = FinancialEngine.concentration(amounts) if amounts else (top_share, top_share)
        spend_risk = _clip(hhi_norm)
        spo_risk = _clip(self._ctx.vendor_critical_spo or top_share * 1.1)
        reliability_risk = _clip(1.0 - self._ctx.delivery_reliability)
        score = 100 * (0.45 * spend_risk + 0.35 * spo_risk + 0.20 * reliability_risk)
        return RiskDimension(
            dimension="vendor_supply",
            score=round(score, 1),
            severity=_severity(score),
            drivers=[
                RiskDriver("spend_hhi", round(hhi_norm, 3), round(0.45 * spend_risk, 2)),
                RiskDriver("critical_spo", round(spo_risk, 3), round(0.35 * spo_risk, 2)),
                RiskDriver(
                    "delivery_reliability",
                    self._ctx.delivery_reliability,
                    round(0.20 * reliability_risk, 2),
                ),
            ],
            explanation="Spend concentration and critical vendor single-points-of-failure.",
            recommended_actions=[
                "Qualify alternate logistics vendors",
                "Increase safety stock",
            ],
            signal_id=_signal_id("vendor_supply", computed_at),
        )

    def _operational(self, computed_at: str) -> RiskDimension:
        red_risk = _clip(self._ctx.red_project_ratio / 0.25)
        budget_risk = _clip(abs(self._ctx.budget_variance_pct) / 0.20)
        centrality_risk = _clip(self._ctx.dependency_centrality)
        score = 100 * (0.40 * red_risk + 0.35 * budget_risk + 0.25 * centrality_risk)
        return RiskDimension(
            dimension="operational",
            score=round(score, 1),
            severity=_severity(score),
            drivers=[
                RiskDriver(
                    "red_project_ratio",
                    round(self._ctx.red_project_ratio, 3),
                    round(0.40 * red_risk, 2),
                ),
                RiskDriver(
                    "budget_variance_pct",
                    round(self._ctx.budget_variance_pct, 3),
                    round(0.35 * budget_risk, 2),
                ),
                RiskDriver(
                    "dependency_centrality",
                    round(self._ctx.dependency_centrality, 3),
                    round(0.25 * centrality_risk, 2),
                ),
            ],
            explanation="Project health, budget variance, and dependency centrality.",
            recommended_actions=["Review red projects", "Reconcile budget variance"],
            signal_id=_signal_id("operational", computed_at),
        )

    def _liquidity(self, computed_at: str) -> RiskDimension:
        runway = self._engine.cash_runway_months()
        runway_risk = _threshold_linear(runway or 12.0, 3.0, 18.0)

        burn_trend = 0.0
        rows = self._engine.rows
        if len(rows) >= 6:
            recent_burn = self._engine.net_burn_cents(len(rows) - 1)
            prior_burn = self._engine.net_burn_cents(len(rows) - 4)
            if prior_burn != 0:
                burn_trend = (recent_burn - prior_burn) / abs(prior_burn)
        burn_risk = _logistic(burn_trend, x0=0.10, k=6.0)

        overdue_risk = _clip(self._ctx.overdue_ar_ratio / 0.30)
        score = 100 * (0.55 * runway_risk + 0.25 * burn_risk + 0.20 * overdue_risk)

        runway_val = round(runway or 0.0, 1)
        explanation = (
            f"Runway is {runway_val} months"
            + (" (below the 6-month threshold)" if runway_val < 6 else "")
            + f" with {'rising' if burn_trend > 0.05 else 'stable'} burn."
        )
        return RiskDimension(
            dimension="liquidity",
            score=round(score, 1),
            severity=_severity(score),
            drivers=[
                RiskDriver("cash_runway_months", runway_val, round(0.55 * runway_risk, 2)),
                RiskDriver("burn_trend_pct", round(burn_trend, 3), round(0.25 * burn_risk, 2)),
                RiskDriver(
                    "overdue_ar_ratio",
                    round(self._ctx.overdue_ar_ratio, 3),
                    round(0.20 * overdue_risk, 2),
                ),
            ],
            explanation=explanation,
            recommended_actions=[
                "Open a $5M revolving credit line",
                "Tighten AR terms to net-30",
                "Defer non-critical Q4 spend",
            ],
            signal_id=_signal_id("liquidity", computed_at),
        )

    def _talent(self, computed_at: str) -> RiskDimension:
        attrition_risk = _clip(self._ctx.attrition_rate / 0.15)
        key_person_risk = _clip(self._ctx.key_person_max_allocation / 1.0)
        roles_risk = _clip(self._ctx.critical_open_roles / 5.0)
        score = 100 * (0.35 * attrition_risk + 0.45 * key_person_risk + 0.20 * roles_risk)
        return RiskDimension(
            dimension="talent",
            score=round(score, 1),
            severity=_severity(score),
            drivers=[
                RiskDriver(
                    "attrition_rate",
                    round(self._ctx.attrition_rate, 3),
                    round(0.35 * attrition_risk, 2),
                ),
                RiskDriver(
                    "key_person_allocation",
                    round(self._ctx.key_person_max_allocation, 3),
                    round(0.45 * key_person_risk, 2),
                ),
                RiskDriver(
                    "critical_open_roles",
                    float(self._ctx.critical_open_roles),
                    round(0.20 * roles_risk, 2),
                ),
            ],
            explanation="Key-person dependency and attrition exposure.",
            recommended_actions=["Document succession plans", "Cross-train critical roles"],
            signal_id=_signal_id("talent", computed_at),
        )

    def _compliance(self, computed_at: str) -> RiskDimension:
        expiring_risk = _clip(self._ctx.expiring_contracts / 5.0)
        expired_risk = _clip(self._ctx.expired_critical_contracts / 3.0)
        audit_risk = _clip(self._ctx.audit_findings / 5.0)
        score = 100 * (0.45 * expiring_risk + 0.35 * expired_risk + 0.20 * audit_risk)
        return RiskDimension(
            dimension="compliance",
            score=round(score, 1),
            severity=_severity(score),
            drivers=[
                RiskDriver(
                    "expiring_contracts",
                    float(self._ctx.expiring_contracts),
                    round(0.45 * expiring_risk, 2),
                ),
                RiskDriver(
                    "expired_critical_contracts",
                    float(self._ctx.expired_critical_contracts),
                    round(0.35 * expired_risk, 2),
                ),
                RiskDriver(
                    "audit_findings",
                    float(self._ctx.audit_findings),
                    round(0.20 * audit_risk, 2),
                ),
            ],
            explanation="Contract expiry posture and audit findings.",
            recommended_actions=["Renew expiring vendor contracts", "Close open audit items"],
            signal_id=_signal_id("compliance", computed_at),
        )

    def _market(self, computed_at: str) -> RiskDimension:
        latest = self._engine.latest
        yoy = self._engine.yoy_delta_pct("revenue", latest.month) if latest else None
        gap_risk = _clip(abs(yoy or 0) / 25.0 if yoy is not None else 0.15)

        volatility = 0.0
        if len(self._engine.rows) >= 12:
            revs = [r.revenue_cents for r in self._engine.rows[-12:] if r.revenue_cents > 0]
            if len(revs) >= 2:
                mean_r = sum(revs) / len(revs)
                volatility = _clip(
                    math.sqrt(sum((r - mean_r) ** 2 for r in revs) / len(revs)) / mean_r / 0.20
                )

        region_risk = _clip(float(self._customer_conc.get("top_5_share") or 0.0) * 0.5)
        score = 100 * (0.50 * gap_risk + 0.30 * volatility + 0.20 * region_risk)
        return RiskDimension(
            dimension="market",
            score=round(score, 1),
            severity=_severity(score),
            drivers=[
                RiskDriver("revenue_yoy_delta_pct", yoy or 0.0, round(0.50 * gap_risk, 2)),
                RiskDriver("demand_volatility", round(volatility, 3), round(0.30 * volatility, 2)),
                RiskDriver("regional_concentration", region_risk, round(0.20 * region_risk, 2)),
            ],
            explanation="Revenue vs. seasonal expectation and demand volatility.",
            recommended_actions=["Review demand forecast", "Adjust inventory levels"],
            signal_id=_signal_id("market", computed_at),
        )

    def to_dict(self, genome: RiskGenome) -> Dict[str, object]:
        return {
            "computed_at": genome.computed_at,
            "overall_score": genome.overall_score,
            "dimensions": [
                {
                    "dimension": d.dimension,
                    "score": d.score,
                    "severity": d.severity,
                    "drivers": [
                        {
                            "factor": dr.factor,
                            "value": dr.value,
                            "contribution": round(dr.contribution, 2),
                        }
                        for dr in d.drivers
                    ],
                    "explanation": d.explanation,
                    "recommended_actions": d.recommended_actions,
                    "signal_id": d.signal_id,
                    "explain_ref": f"/explain/risk/{d.signal_id}",
                }
                for d in genome.dimensions
            ],
        }

    def explain_dimension(self, genome: RiskGenome, signal_id: str) -> Optional[Dict[str, object]]:
        for d in genome.dimensions:
            if d.signal_id == signal_id:
                ranked = sorted(d.drivers, key=lambda x: -x.contribution)
                return {
                    "signal_id": signal_id,
                    "dimension": d.dimension,
                    "score": d.score,
                    "severity": d.severity,
                    "driver_attribution": [
                        {
                            "factor": dr.factor,
                            "value": dr.value,
                            "contribution": round(dr.contribution, 2),
                            "weight_share": round(
                                dr.contribution / max(sum(x.contribution for x in d.drivers), 0.01),
                                2,
                            ),
                        }
                        for dr in ranked
                    ],
                    "explanation": d.explanation,
                    "recommended_actions": d.recommended_actions,
                    "evidence": [
                        {"type": "metric", "ref": f"/metrics/{dr.factor}"}
                        for dr in ranked[:3]
                    ],
                }
        return None
