"""Connector type registry."""

from __future__ import annotations

from typing import Dict, List, Type

from .base import DataConnector

_registry: Dict[str, Type[DataConnector]] = {}


def register_connector(connector_type: str, cls: Type[DataConnector]) -> None:
    _registry[connector_type] = cls


def get_connector(connector_type: str) -> DataConnector:
    cls = _registry.get(connector_type)
    if cls is None:
        raise KeyError(f"Unknown connector type: {connector_type}")
    return cls()


def list_connector_types() -> List[str]:
    return sorted(_registry.keys())
