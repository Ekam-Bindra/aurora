"""Executive AI agent API routes (Phase 6)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.errors import NotFound, Unprocessable
from ...core.logging import get_request_id
from ...core.rbac import AuthContext, Permission
from ...deps import get_db_session, require_permission
from ...services.agent import get_session, list_sessions, send_message

router = APIRouter(tags=["agent"])


def _require_db(session: Optional[Session] = Depends(get_db_session)) -> Session:
    if session is None:
        raise Unprocessable(
            "AI agent requires DATABASE_URL (SQLite or Postgres). "
            "Set DATABASE_URL and restart, or use ./scripts/local-run.sh."
        )
    return session


class AgentMessage(BaseModel):
    session_id: Optional[str] = None
    message: str


@router.post("/agent/messages")
def post_agent_message(
    body: AgentMessage,
    context: AuthContext = Depends(require_permission(Permission.USE_AI_AGENT)),
    session: Session = Depends(_require_db),
) -> dict:
    data = send_message(
        session,
        context.tenant_id,
        context.user_id,
        message=body.message,
        session_id=body.session_id,
    )
    return {"data": data, "meta": {"request_id": get_request_id()}}


@router.get("/agent/sessions/{session_id}")
def get_agent_session(
    session_id: str,
    context: AuthContext = Depends(require_permission(Permission.USE_AI_AGENT)),
    session: Optional[Session] = Depends(get_db_session),
) -> dict:
    data = get_session(session_id, context.tenant_id, session=session)
    if data is None:
        raise NotFound("Session not found")
    return {"data": data, "meta": {"request_id": get_request_id()}}


@router.get("/agent/sessions")
def list_agent_sessions(
    context: AuthContext = Depends(require_permission(Permission.USE_AI_AGENT)),
    session: Optional[Session] = Depends(get_db_session),
) -> dict:
    items = list_sessions(context.tenant_id, user_id=context.user_id, session=session)
    return {"data": items, "meta": {"request_id": get_request_id()}}
