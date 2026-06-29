"""Enterprise Risk Genome scorers (Phase 5 foundation).

Computes all 8 dimensions with normalized sub-factors per
docs/architecture/financial-risk-simulation-models.md §4. Full driver libraries and
graph-coupled scorers deepen in later P5 iterations.
"""

from __future__ import annotations

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


@dataclass
class RiskGenome:
    computed_at: str
    overall_score: float
    dimensions: List[RiskDimension]


class RiskGenomeEngine:
    """Compute the 8-dimension risk genome from financial + concentration inputs."""

    def __init__(
        self,
        engine: FinancialEngine,
        *,
        customer_concentration: Optional[Dict[str, Any]] = None,
        vendor_concentration: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._engine = engine
        self._customer_conc = customer_concentration or {}
        self._vendor_conc = vendor_concentration or {}

    def compute(self) -> RiskGenome:
        dims = [
            self._financial(),
            self._customer_concentration(),
            self._vendor_supply(),
            self._operational(),
            self._liquidity(),
            self._talent(),
            self._compliance(),
            self._market(),
        ]
        overall = sum(d.score * DIMENSION_WEIGHTS.get(d.dimension, 0.125) for d in dims)
        return RiskGenome(
            computed_at=datetime.now(timezone.utc).isoformat(),
            overall_score=round(overall, 1),
            dimensions=dims,
        )

    def _financial(self) -> RiskDimension:
        latest = self._engine.latest
        gm = self._engine.gross_margin(latest) if latest else None
        om = self._engine.operating_margin(latest) if latest else None
        gm_risk = _threshold_linear(gm or 0.35, 0.20, 0.50)
        om_risk = _threshold_linear(0.50 - (om or 0.05), 0.0, 0.30)
        score = 100 * (0.55 * gm_risk + 0.45 * om_risk)
        drivers = [
            RiskDriver("gross_margin", gm or 0.0, 0.55 * gm_risk),
            RiskDriver("operating_margin", om or 0.0, 0.45 * om_risk),
        ]
        return RiskDimension(
            dimension="financial",
            score=round(score, 1),
            severity=_severity(score),
            drivers=drivers,
            explanation="Margin levels vs. historical targets.",
            recommended_actions=["Review product mix margin", "Audit discretionary spend"],
        )

    def _customer_concentration(self) -> RiskDimension:
        top_share = float(self._customer_conc.get("top_5_share") or 0.35)
        top_customer = 0.0
        top_list = self._customer_conc.get("top") or []
        if top_list:
            total = sum(x.get("amount_cents", 0) for x in top_list) or 1
            top_customer = top_list[0].get("amount_cents", 0) / total if total else 0.0
        hhi_risk = _clip(top_share)
        top_risk = _clip(top_customer / 0.20)
        score = 100 * (0.5 * hhi_risk + 0.5 * top_risk)
        return RiskDimension(
            dimension="customer_concentration",
            score=round(score, 1),
            severity=_severity(score),
            drivers=[
                RiskDriver("top_5_share", top_share, 0.5 * hhi_risk),
                RiskDriver("top_customer_share", top_customer, 0.5 * top_risk),
            ],
            explanation="Revenue concentration among top customers.",
            recommended_actions=["Diversify pipeline", "Negotiate multi-year retention contracts"],
        )

    def _vendor_supply(self) -> RiskDimension:
        top_share = float(self._vendor_conc.get("top_5_share") or 0.30)
        score = 100 * _clip(top_share * 1.2)
        return RiskDimension(
            dimension="vendor_supply",
            score=round(score, 1),
            severity=_severity(score),
            drivers=[RiskDriver("top_5_vendor_share", top_share, _clip(top_share))],
            explanation="Spend concentration and critical vendor exposure.",
            recommended_actions=["Qualify alternate logistics vendors", "Increase safety stock"],
        )

    def _operational(self) -> RiskDimension:
        score = 45.0
        return RiskDimension(
            dimension="operational",
            score=score,
            severity=_severity(score),
            drivers=[RiskDriver("red_project_ratio", 0.15, 0.45)],
            explanation="Project health and budget variance (stub — full scorer in P5).",
            recommended_actions=["Review red projects", "Reconcile budget variance"],
        )

    def _liquidity(self) -> RiskDimension:
        runway = self._engine.cash_runway_months()
        burn = self._engine.net_burn_cents()
        runway_risk = _threshold_linear(runway or 12.0, 3.0, 18.0)
        burn_risk = _clip(burn / max(self._engine.latest.revenue_cents, 1) if self._engine.latest else 0.0)
        score = 100 * (0.70 * runway_risk + 0.30 * burn_risk)
        return RiskDimension(
            dimension="liquidity",
            score=round(score, 1),
            severity=_severity(score),
            drivers=[
                RiskDriver("cash_runway_months", runway or 0.0, 0.70 * runway_risk),
                RiskDriver("net_burn_cents", float(burn), 0.30 * burn_risk),
            ],
            explanation="Cash runway and burn trend.",
            recommended_actions=["Open revolving credit line", "Tighten AR terms"],
        )

    def _talent(self) -> RiskDimension:
        score = 38.0
        return RiskDimension(
            dimension="talent",
            score=score,
            severity=_severity(score),
            drivers=[RiskDriver("key_person_allocation", 0.80, 0.38)],
            explanation="Key-person dependency (stub — graph-coupled scorer in P5).",
            recommended_actions=["Document succession plans", "Cross-train critical roles"],
        )

    def _compliance(self) -> RiskDimension:
        score = 28.0
        return RiskDimension(
            dimension="compliance",
            score=score,
            severity=_severity(score),
            drivers=[RiskDriver("expiring_contracts", 2.0, 0.28)],
            explanation="Contract and audit posture (stub).",
            recommended_actions=["Renew expiring vendor contracts"],
        )

    def _market(self) -> RiskDimension:
        latest = self._engine.latest
        yoy = self._engine.yoy_delta_pct("revenue", latest.month) if latest else None
        gap_risk = _clip(abs(yoy or 0) / 0.25 if yoy is not None else 0.15)
        score = 100 * gap_risk
        return RiskDimension(
            dimension="market",
            score=round(score, 1),
            severity=_severity(score),
            drivers=[RiskDriver("revenue_yoy_delta_pct", yoy or 0.0, gap_risk)],
            explanation="Revenue vs. seasonal expectation.",
            recommended_actions=["Review demand forecast", "Adjust inventory levels"],
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
                        {"factor": dr.factor, "value": dr.value, "contribution": round(dr.contribution, 2)}
                        for dr in d.drivers
                    ],
                    "explanation": d.explanation,
                    "recommended_actions": d.recommended_actions,
                }
                for d in genome.dimensions
            ],
        }
