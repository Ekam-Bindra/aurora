"""ClickHouse analytics mart backend (optional; requires clickhouse-connect)."""

from __future__ import annotations

from typing import List, Optional

from aurora_ml.marts import FinancialMartBuilder, MonthlyFinancialRow
from sqlalchemy.orm import Session

_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS fct_financials_monthly (
    company_id String,
    month Date,
    revenue_cents Int64,
    cogs_cents Int64,
    expenses_cents Int64,
    payroll_cents Int64,
    cash_cents Int64
) ENGINE = MergeTree()
ORDER BY (company_id, month)
"""


def _parse_clickhouse_url(url: str) -> tuple[str, int, str, str, str]:
    """Parse ``http://host:8123`` or ``clickhouse://user:pass@host:8123/default``."""
    if not url:
        raise ValueError("CLICKHOUSE_URL is required when ANALYTICS_BACKEND=clickhouse")
    if url.startswith("clickhouse://"):
        from urllib.parse import urlparse

        parsed = urlparse(url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 8123
        user = parsed.username or "default"
        password = parsed.password or ""
        database = (parsed.path or "/default").lstrip("/") or "default"
        return host, port, user, password, database
    if url.startswith("http://") or url.startswith("https://"):
        from urllib.parse import urlparse

        parsed = urlparse(url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 8123
        return host, port, "default", "", "default"
    return url, 8123, "default", "", "default"


def _client(clickhouse_url: str):
    try:
        import clickhouse_connect
    except ImportError as exc:
        raise RuntimeError(
            "clickhouse-connect is required for ANALYTICS_BACKEND=clickhouse. "
            "Install with: pip install aurora-analytics[clickhouse]"
        ) from exc

    host, port, user, password, database = _parse_clickhouse_url(clickhouse_url)
    return clickhouse_connect.get_client(
        host=host,
        port=port,
        username=user,
        password=password,
        database=database,
    )


def _ensure_table(client) -> None:
    client.command(_TABLE_DDL)


def _refresh_clickhouse(
    session: Session, company_id: str, clickhouse_url: str
) -> List[MonthlyFinancialRow]:
    rows = FinancialMartBuilder().build(session, company_id)
    client = _client(clickhouse_url)
    _ensure_table(client)
    client.command(
        "ALTER TABLE fct_financials_monthly DELETE WHERE company_id = %(cid)s",
        parameters={"cid": company_id},
    )
    if rows:
        client.insert(
            "fct_financials_monthly",
            [
                [
                    r.company_id,
                    r.month,
                    r.revenue_cents,
                    r.cogs_cents,
                    r.expenses_cents,
                    r.payroll_cents,
                    r.cash_cents,
                ]
                for r in rows
            ],
            column_names=[
                "company_id",
                "month",
                "revenue_cents",
                "cogs_cents",
                "expenses_cents",
                "payroll_cents",
                "cash_cents",
            ],
        )
    return rows


def get_mart_rows(
    session: Session,
    company_id: str,
    *,
    clickhouse_url: Optional[str] = None,
) -> List[MonthlyFinancialRow]:
    url = clickhouse_url or ""
    client = _client(url)
    _ensure_table(client)
    result = client.query(
        """
        SELECT company_id, month, revenue_cents, cogs_cents, expenses_cents,
               payroll_cents, cash_cents
        FROM fct_financials_monthly
        WHERE company_id = %(cid)s
        ORDER BY month
        """,
        parameters={"cid": company_id},
    )
    if result.result_rows:
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
            for row in result.result_rows
        ]
    return _refresh_clickhouse(session, company_id, url)
