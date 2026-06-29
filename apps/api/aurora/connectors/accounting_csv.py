"""Demo accounting CSV connector — reads bundled sample or tenant-configured path."""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List

from .base import ConnectorResult, DataConnector

_SAMPLE_INVOICES = """invoice_number,customer_name,issue_date,due_date,total_cents,currency,status
ACCT-9001,Continental Mercantile Group,2026-05-01,2026-06-01,125000000,USD,issued
ACCT-9002,Continental Mercantile Group,2026-05-15,2026-06-15,89000000,USD,paid
ACCT-9003,Unknown Corp,2026-05-20,2026-06-20,50000000,USD,issued
"""

_SAMPLE_CUSTOMERS = """name,segment,region,industry,status
Continental Motors,enterprise,NA,Automotive,active
Skyline Retail,mid-market,NA,Retail,active
"""


class AccountingCsvConnector(DataConnector):
    """Accounting-system CSV adapter (demo: bundled samples or local file path in config)."""

    connector_type = "accounting_csv"

    def pull(
        self,
        *,
        company_id: str,
        config: Dict[str, Any],
        target: str,
    ) -> ConnectorResult:
        del company_id  # tenant scoping enforced by caller
        path = config.get("file_path")
        if path:
            text = Path(path).read_text(encoding="utf-8")
            lineage = f"connector:accounting_csv#{Path(path).name}"
        elif target == "customers":
            text = _SAMPLE_CUSTOMERS
            lineage = "connector:accounting_csv#sample_customers.csv"
        elif target == "invoices":
            text = _SAMPLE_INVOICES
            lineage = "connector:accounting_csv#sample_invoices.csv"
        else:
            return ConnectorResult(
                rows=[],
                target=target,
                lineage_ref=f"connector:accounting_csv#{target}",
                errors=[
                    {"row": 0, "issue": f"unsupported target '{target}'", "action": "rejected"},
                ],
            )

        reader = csv.DictReader(StringIO(text))
        rows: List[Dict[str, Any]] = [dict(r) for r in reader]
        return ConnectorResult(rows=rows, target=target, lineage_ref=lineage, rows_total=len(rows))

    def health(self, config: Dict[str, Any]) -> Dict[str, Any]:
        path = config.get("file_path")
        if path and not Path(path).exists():
            return {"status": "error", "detail": f"file not found: {path}"}
        return {"status": "connected", "detail": "accounting_csv demo connector"}
