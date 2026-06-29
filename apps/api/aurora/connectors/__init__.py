"""Connector framework for live data-source sync (Phase 7)."""

from .accounting_csv import AccountingCsvConnector
from .base import ConnectorResult, DataConnector
from .registry import get_connector, list_connector_types, register_connector

register_connector("accounting_csv", AccountingCsvConnector)

__all__ = [
    "AccountingCsvConnector",
    "ConnectorResult",
    "DataConnector",
    "get_connector",
    "list_connector_types",
    "register_connector",
]
