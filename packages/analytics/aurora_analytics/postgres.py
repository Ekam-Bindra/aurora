"""Postgres path: build in-process DuckDB mart from the relational session (default)."""

from __future__ import annotations

from typing import List

from aurora_ml.marts import MonthlyFinancialRow, get_mart_rows as _duckdb_mart_rows
from sqlalchemy.orm import Session


def get_mart_rows(session: Session, company_id: str) -> List[MonthlyFinancialRow]:
    return _duckdb_mart_rows(session, company_id)
