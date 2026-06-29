"""Global in-memory graph store (rebuilt from SQL on startup)."""

from __future__ import annotations

from typing import Optional

from aurora_graph.memory import InMemoryGraphStore

_store: Optional[InMemoryGraphStore] = None


def get_graph_store() -> InMemoryGraphStore:
    global _store
    if _store is None:
        _store = InMemoryGraphStore()
    return _store


def reset_graph_store() -> None:
    global _store
    _store = None
