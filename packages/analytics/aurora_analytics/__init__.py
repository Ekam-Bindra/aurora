"""Analytics mart backend selection (Postgres/DuckDB default, optional ClickHouse)."""

from __future__ import annotations

import os
from typing import List, Optional

from aurora_ml.marts import MonthlyFinancialRow
from sqlalchemy.orm import Session

_VALID_BACKENDS = {"postgres", "clickhouse"}


def get_analytics_backend() -> str:
    """Return configured backend: ``postgres`` (default) or ``clickhouse``."""
    raw = os.environ.get("ANALYTICS_BACKEND", "postgres").strip().lower()
    if raw not in _VALID_BACKENDS:
        raise ValueError(
            f"Invalid ANALYTICS_BACKEND={raw!r}; expected one of {sorted(_VALID_BACKENDS)}"
        )
    return raw


def get_mart_rows(
    session: Session,
    company_id: str,
    *,
    backend: Optional[str] = None,
    clickhouse_url: Optional[str] = None,
) -> List[MonthlyFinancialRow]:
    """Fetch monthly financial mart rows using the configured analytics backend."""
    chosen = (backend or get_analytics_backend()).lower()
    if chosen == "postgres":
        from .postgres import get_mart_rows as postgres_rows

        return postgres_rows(session, company_id)
    if chosen == "clickhouse":
        from .clickhouse import get_mart_rows as clickhouse_rows

        return clickhouse_rows(
            session,
            company_id,
            clickhouse_url=clickhouse_url or os.environ.get("CLICKHOUSE_URL", ""),
        )
    raise ValueError(f"Unsupported analytics backend: {chosen}")
