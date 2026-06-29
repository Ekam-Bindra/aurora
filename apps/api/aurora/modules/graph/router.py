"""Knowledge graph API routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...core.errors import Unprocessable
from ...core.logging import get_request_id
from ...core.rbac import AuthContext, Permission
from ...deps import get_db_session, require_permission
from ...services.graph import graph_concentration, impact, list_nodes, neighbors

router = APIRouter(tags=["graph"])


def _require_db(session: Optional[Session] = Depends(get_db_session)) -> Session:
    if session is None:
        raise Unprocessable(
            "Knowledge graph requires DATABASE_URL (SQLite or Postgres). "
            "Set DATABASE_URL and restart, or use ./scripts/local-run.sh."
        )
    return session


@router.get("/graph/nodes")
def graph_nodes(
    label: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=500),
    context: AuthContext = Depends(require_permission(Permission.READ_GRAPH)),
    session: Session = Depends(_require_db),
) -> dict:
    data = {"nodes": list_nodes(context.tenant_id, label=label, limit=limit)}
    return {"data": data, "meta": {"request_id": get_request_id()}}


@router.get("/graph/neighbors/{node_id}")
def graph_neighbors(
    node_id: str,
    depth: int = Query(1, ge=1, le=4),
    context: AuthContext = Depends(require_permission(Permission.READ_GRAPH)),
    session: Session = Depends(_require_db),
) -> dict:
    data = neighbors(context.tenant_id, node_id, depth=depth)
    return {"data": data, "meta": {"request_id": get_request_id()}}


@router.get("/graph/impact/{node_id}")
def graph_impact(
    node_id: str,
    depth: int = Query(2, ge=1, le=4),
    context: AuthContext = Depends(require_permission(Permission.READ_GRAPH)),
    session: Session = Depends(_require_db),
) -> dict:
    data = impact(session, context.tenant_id, node_id, depth=depth)
    return {"data": data, "meta": {"request_id": get_request_id()}}


@router.get("/graph/concentration")
def graph_concentration_endpoint(
    context: AuthContext = Depends(require_permission(Permission.READ_GRAPH)),
    session: Session = Depends(_require_db),
) -> dict:
    data = graph_concentration(context.tenant_id)
    return {"data": data, "meta": {"request_id": get_request_id()}}
