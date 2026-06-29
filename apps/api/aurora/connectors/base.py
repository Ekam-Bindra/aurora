"""Base connector interface for idempotent data-source sync."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ConnectorResult:
    """Normalized output from a connector pull."""

    rows: List[Dict[str, Any]]
    target: str
    lineage_ref: str
    rows_total: int = 0
    errors: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.rows_total == 0:
            self.rows_total = len(self.rows)


class DataConnector(ABC):
    """Pull remote/tabular data and return rows ready for the ingestion pipeline."""

    connector_type: str = "base"

    @abstractmethod
    def pull(
        self,
        *,
        company_id: str,
        config: Dict[str, Any],
        target: str,
    ) -> ConnectorResult:
        """Fetch rows for ``target`` using connector-specific config (no secrets in repo)."""

    def health(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Return connector health metadata for data-source cards."""
        return {"status": "connected", "detail": f"{self.connector_type} ready"}
