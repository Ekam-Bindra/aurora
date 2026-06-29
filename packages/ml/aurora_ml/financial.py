"""Financial intelligence calculators (docs/architecture/financial-risk-simulation-models.md §2)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple

from .marts import MonthlyFinancialRow


@dataclass
class ConcentrationResult:
    entity_type: str  # customer | vendor | product
    top_share: float
    hhi_normalized: float
    top_entities: List[Dict[str, object]]


class FinancialEngine:
    """Compute metrics from materialised monthly financial rows."""

    def __init__(self, rows: List[MonthlyFinancialRow], *, trailing_window: int = 3) -> None:
        self._rows = sorted(rows, key=lambda r: r.month)
        self._trailing = trailing_window

    @property
    def rows(self) -> List[MonthlyFinancialRow]:
        return list(self._rows)

    @property
    def latest(self) -> Optional[MonthlyFinancialRow]:
        return self._rows[-1] if self._rows else None

    def row_for_month(self, month: date) -> Optional[MonthlyFinancialRow]:
        key = month.replace(day=1)
        for row in self._rows:
            if row.month == key:
                return row
        return None

    def gross_margin(self, row: MonthlyFinancialRow) -> Optional[float]:
        if row.revenue_cents <= 0:
            return None
        return (row.revenue_cents - row.cogs_cents) / row.revenue_cents

    def operating_margin(self, row: MonthlyFinancialRow) -> Optional[float]:
        if row.revenue_cents <= 0:
            return None
        opex = row.expenses_cents - row.cogs_cents
        return (row.revenue_cents - row.cogs_cents - opex) / row.revenue_cents

    def net_burn_cents(self, index: Optional[int] = None) -> int:
        """Trailing average monthly cash consumption (positive = burning cash)."""
        if not self._rows:
            return 0
        idx = index if index is not None else len(self._rows) - 1
        start = max(0, idx - self._trailing + 1)
        window = self._rows[start : idx + 1]
        if not window:
            return 0
        burns = [r.expenses_cents - r.revenue_cents for r in window]
        return int(sum(burns) / len(burns))

    def cash_runway_months(self, index: Optional[int] = None) -> Optional[float]:
        if not self._rows:
            return None
        idx = index if index is not None else len(self._rows) - 1
        row = self._rows[idx]
        burn = self.net_burn_cents(idx)
        if burn <= 0:
            return None  # profitable / infinite — API uses a sentinel or large value
        return row.cash_cents / burn

    def yoy_delta_pct(self, field: str, month: date) -> Optional[float]:
        """Year-over-year % change for revenue or a margin."""
        current = self.row_for_month(month)
        prior_month = date(month.year - 1, month.month, 1)
        prior = self.row_for_month(prior_month)
        if current is None or prior is None:
            return None
        if field == "revenue":
            if prior.revenue_cents == 0:
                return None
            return 100.0 * (current.revenue_cents - prior.revenue_cents) / prior.revenue_cents
        if field == "gross_margin":
            cg, pg = self.gross_margin(current), self.gross_margin(prior)
            if cg is None or pg is None:
                return None
            return 100.0 * (cg - pg)  # percentage-point delta
        if field == "operating_margin":
            co, po = self.operating_margin(current), self.operating_margin(prior)
            if co is None or po is None:
                return None
            return 100.0 * (co - po)
        return None

    def series(self, metric: str) -> List[Tuple[date, float]]:
        out: List[Tuple[date, float]] = []
        for i, row in enumerate(self._rows):
            if metric == "revenue":
                out.append((row.month, float(row.revenue_cents)))
            elif metric == "gross_margin":
                gm = self.gross_margin(row)
                if gm is not None:
                    out.append((row.month, gm))
            elif metric == "cash":
                out.append((row.month, float(row.cash_cents)))
            elif metric == "net_burn":
                out.append((row.month, float(self.net_burn_cents(i))))
        return out

    @staticmethod
    def concentration(shares: List[float], top_k: int = 5) -> Tuple[float, float]:
        """Return (top_k_share, normalized_hhi) from a list of amounts."""
        if not shares:
            return 0.0, 0.0
        total = sum(shares)
        if total <= 0:
            return 0.0, 0.0
        sorted_shares = sorted((s / total for s in shares), reverse=True)
        top_k_share = sum(sorted_shares[:top_k])
        hhi = sum(s * s for s in sorted_shares)
        n = len(shares)
        hhi_norm = (hhi - 1 / n) / (1 - 1 / n) if n > 1 else 1.0
        return top_k_share, max(0.0, min(1.0, hhi_norm))
