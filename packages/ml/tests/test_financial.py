"""Financial calculator tests."""

from datetime import date

from aurora_ml.financial import FinancialEngine
from aurora_ml.marts import MonthlyFinancialRow


def _row(month: int, rev: int, exp: int, cogs: int, cash: int) -> MonthlyFinancialRow:
    d = date(2025, month, 1)
    return MonthlyFinancialRow(
        company_id="c1",
        month=d,
        revenue_cents=rev,
        cogs_cents=cogs,
        expenses_cents=exp,
        payroll_cents=exp // 3,
        cash_cents=cash,
    )


def test_gross_margin_and_runway():
    rows = [
        _row(1, 500_000, 900_000, 200_000, 5_000_000_00),
        _row(2, 520_000, 920_000, 210_000, 4_800_000_00),
        _row(3, 540_000, 940_000, 220_000, 4_600_000_00),
    ]
    engine = FinancialEngine(rows)
    gm = engine.gross_margin(rows[-1])
    assert gm is not None
    assert 0.4 < gm < 0.7
    burn = engine.net_burn_cents()
    assert burn > 0
    runway = engine.cash_runway_months()
    assert runway is not None and runway > 0


def test_concentration():
    top, hhi = FinancialEngine.concentration([100, 50, 30, 20, 10, 5])
    assert top > 0.4
    assert 0 <= hhi <= 1
