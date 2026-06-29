"""Build analytics marts from the canonical relational store.

Phase 3 materialises ``fct_financials_monthly`` (docs/data-model/data-model.md §6) into
DuckDB for fast metric queries. Amounts are stored in **cents** (integer).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List

import duckdb
from aurora_db.models import Expense, RevenueRecord
from sqlalchemy import func, select
from sqlalchemy.orm import Session

# Matches Nimbus seeder (packages/database/aurora_db/seed/nimbus.py).
START_CASH_CENTS = int(6_500_000 * 100)


@dataclass(frozen=True)
class MonthlyFinancialRow:
    company_id: str
    month: date
    revenue_cents: int
    cogs_cents: int
    expenses_cents: int
    payroll_cents: int
    cash_cents: int

    @property
    def gross_profit_cents(self) -> int:
        return self.revenue_cents - self.cogs_cents

    @property
    def net_profit_cents(self) -> int:
        return self.revenue_cents - self.expenses_cents

    @property
    def opex_cents(self) -> int:
        return self.expenses_cents - self.cogs_cents


class FinancialMartBuilder:
    """Extract monthly financial facts from PostgreSQL / SQLite via SQLAlchemy."""

    def build(self, session: Session, company_id: str) -> List[MonthlyFinancialRow]:
        revenue_by_month: Dict[date, int] = {
            row[0]: int(row[1] or 0)
            for row in session.execute(
                select(RevenueRecord.period_month, func.sum(RevenueRecord.amount_cents))
                .where(RevenueRecord.company_id == company_id)
                .group_by(RevenueRecord.period_month)
                .order_by(RevenueRecord.period_month)
            )
        }

        expense_rows = session.execute(
            select(
                Expense.expense_date,
                Expense.category,
                func.sum(Expense.amount_cents),
            )
            .where(Expense.company_id == company_id)
            .group_by(Expense.expense_date, Expense.category)
            .order_by(Expense.expense_date)
        ).all()

        expenses_by_month: Dict[date, int] = {}
        cogs_by_month: Dict[date, int] = {}
        payroll_by_month: Dict[date, int] = {}
        for exp_date, category, total in expense_rows:
            month = exp_date.replace(day=1) if hasattr(exp_date, "replace") else exp_date
            amt = int(total or 0)
            expenses_by_month[month] = expenses_by_month.get(month, 0) + amt
            if category == "cogs":
                cogs_by_month[month] = cogs_by_month.get(month, 0) + amt
            if category == "payroll":
                payroll_by_month[month] = payroll_by_month.get(month, 0) + amt

        months = sorted(set(revenue_by_month) | set(expenses_by_month))
        cash_cents = START_CASH_CENTS
        rows: List[MonthlyFinancialRow] = []
        disbursements: List[int] = []

        for month in months:
            rev = revenue_by_month.get(month, 0)
            exp = expenses_by_month.get(month, 0)
            cogs = cogs_by_month.get(month, 0)
            payroll = payroll_by_month.get(month, 0)
            disbursements.append(exp)
            # Cash-basis approximation (matches Nimbus verify logic).
            cash_cents += rev - exp
            rows.append(
                MonthlyFinancialRow(
                    company_id=company_id,
                    month=month,
                    revenue_cents=rev,
                    cogs_cents=cogs,
                    expenses_cents=exp,
                    payroll_cents=payroll,
                    cash_cents=cash_cents,
                )
            )
        return rows


class DuckDBMartStore:
    """In-process DuckDB cache of ``fct_financials_monthly``."""

    def __init__(self, path: str = ":memory:") -> None:
        self._con = duckdb.connect(path)
        self._con.execute(
            """
            CREATE TABLE IF NOT EXISTS fct_financials_monthly (
                company_id VARCHAR,
                month DATE,
                revenue_cents BIGINT,
                cogs_cents BIGINT,
                expenses_cents BIGINT,
                payroll_cents BIGINT,
                cash_cents BIGINT
            )
            """
        )

    def refresh(self, company_id: str, rows: List[MonthlyFinancialRow]) -> None:
        self._con.execute("DELETE FROM fct_financials_monthly WHERE company_id = ?", [company_id])
        if not rows:
            return
        self._con.executemany(
            "INSERT INTO fct_financials_monthly VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    r.company_id,
                    r.month,
                    r.revenue_cents,
                    r.cogs_cents,
                    r.expenses_cents,
                    r.payroll_cents,
                    r.cash_cents,
                )
                for r in rows
            ],
        )

    def fetch_rows(self, company_id: str) -> List[MonthlyFinancialRow]:
        result = self._con.execute(
            """
            SELECT company_id, month, revenue_cents, cogs_cents, expenses_cents,
                   payroll_cents, cash_cents
            FROM fct_financials_monthly
            WHERE company_id = ?
            ORDER BY month
            """,
            [company_id],
        ).fetchall()
        return [
            MonthlyFinancialRow(
                company_id=row[0],
                month=row[1],
                revenue_cents=int(row[2]),
                cogs_cents=int(row[3]),
                expenses_cents=int(row[4]),
                payroll_cents=int(row[5]),
                cash_cents=int(row[6]),
            )
            for row in result
        ]

    def close(self) -> None:
        self._con.close()


# Process-wide mart cache keyed by company_id (Phase 3 laptop scale).
_mart_stores: Dict[str, DuckDBMartStore] = {}


def get_mart_store(company_id: str) -> DuckDBMartStore:
    if company_id not in _mart_stores:
        _mart_stores[company_id] = DuckDBMartStore()
    return _mart_stores[company_id]


def refresh_mart(session: Session, company_id: str) -> List[MonthlyFinancialRow]:
    builder = FinancialMartBuilder()
    rows = builder.build(session, company_id)
    store = get_mart_store(company_id)
    store.refresh(company_id, rows)
    return rows


def get_mart_rows(session: Session, company_id: str) -> List[MonthlyFinancialRow]:
    store = get_mart_store(company_id)
    rows = store.fetch_rows(company_id)
    if rows:
        return rows
    return refresh_mart(session, company_id)
