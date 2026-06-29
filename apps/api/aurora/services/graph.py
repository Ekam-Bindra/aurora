"""Knowledge graph service."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from aurora_graph.sync import sync_company_graph

from ..graph_store import get_graph_store


def refresh_graph(session: Session, company_id: str) -> None:
    snapshot = sync_company_graph(session, company_id)
    get_graph_store().replace(snapshot)


def list_nodes(
    company_id: str,
    label: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    return get_graph_store().list_nodes(company_id, label=label, limit=limit)


def neighbors(company_id: str, node_id: str, depth: int = 1) -> Dict[str, Any]:
    return get_graph_store().neighbors(company_id, node_id, depth=depth)


def impact(
    session: Session,
    company_id: str,
    node_id: str,
    depth: int = 2,
) -> Dict[str, Any]:
    return get_graph_store().impact(company_id, node_id, depth=depth, session=session)


def graph_concentration(company_id: str) -> Dict[str, Any]:
    return get_graph_store().concentration(company_id)
