"""Risk genome tests."""

from datetime import date

from aurora_ml.financial import FinancialEngine
from aurora_ml.marts import MonthlyFinancialRow
from aurora_ml.risk import RISK_DIMENSIONS, RiskGenomeEngine, RiskOperationalContext


def _sample_rows() -> list:
    rows = []
    cash = 500_000_00
    for i in range(24):
        month = date(2024, (i % 12) + 1, 1)
        rev = 4_000_000_00
        exp = 3_800_000_00
        cash += rev - exp
        rows.append(
            MonthlyFinancialRow(
                company_id="co1",
                month=month,
                revenue_cents=rev,
                cogs_cents=int(rev * 0.55),
                expenses_cents=exp,
                payroll_cents=int(exp * 0.4),
                cash_cents=cash,
            )
        )
    return rows


def test_risk_genome_eight_dimensions():
    fin = FinancialEngine(_sample_rows())
    engine = RiskGenomeEngine(
        fin,
        customer_concentration={"top_5_share": 0.45, "top": [{"amount_cents": 560_000_00}]},
        vendor_concentration={"top_5_share": 0.40},
    )
    genome = engine.compute()
    assert len(genome.dimensions) == 8
    dims = {d.dimension for d in genome.dimensions}
    assert dims == set(RISK_DIMENSIONS)
    assert 0 <= genome.overall_score <= 100
    for d in genome.dimensions:
        assert d.signal_id.startswith("rs_")


def test_liquidity_elevated_on_low_runway():
    rows = _sample_rows()
    rows[-1] = MonthlyFinancialRow(
        company_id="co1",
        month=rows[-1].month,
        revenue_cents=rows[-1].revenue_cents,
        cogs_cents=rows[-1].cogs_cents,
        expenses_cents=rows[-1].expenses_cents + 2_000_000_00,
        payroll_cents=rows[-1].payroll_cents,
        cash_cents=200_000_00,
    )
    fin = FinancialEngine(rows)
    ctx = RiskOperationalContext(overdue_ar_ratio=0.11)
    engine = RiskGenomeEngine(fin, context=ctx)
    genome = engine.compute()
    liquidity = next(d for d in genome.dimensions if d.dimension == "liquidity")
    assert liquidity.severity in ("high", "critical")
    assert liquidity.score >= 51


def test_customer_concentration_elevated():
    fin = FinancialEngine(_sample_rows())
    engine = RiskGenomeEngine(
        fin,
        customer_concentration={
            "top_5_share": 0.52,
            "top": [
                {"amount_cents": 560_000_00},
                {"amount_cents": 200_000_00},
                {"amount_cents": 150_000_00},
            ],
        },
    )
    genome = engine.compute()
    cc = next(d for d in genome.dimensions if d.dimension == "customer_concentration")
    assert cc.severity in ("moderate", "high", "critical")
    assert cc.score >= 40


def test_explain_dimension():
    fin = FinancialEngine(_sample_rows())
    engine = RiskGenomeEngine(fin)
    genome = engine.compute()
    signal_id = genome.dimensions[0].signal_id
    explain = engine.explain_dimension(genome, signal_id)
    assert explain is not None
    assert explain["signal_id"] == signal_id
    assert len(explain["driver_attribution"]) >= 1
