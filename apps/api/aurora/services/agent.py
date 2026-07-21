"""Executive AI agent service — provider orchestration + tool assembly.

Interaction storage is dual-mode: with a session, Q&A rounds persist to the
``ai_interaction`` table (chat history survives restarts and spans the two
ECS API tasks); without one the per-process dicts back the in-memory test
mode. A "chat session" is the group of interactions sharing a ``session_id``.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from aurora_db.models.intelligence import AIInteraction
from aurora_db.types import new_uuid
from aurora_ml.agent_tools import build_revenue_shock_scenario, search_metrics_context
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.config import Settings, get_settings
from ..core.errors import BadGateway
from ..providers.anthropic import AnthropicAIProvider
from ..providers.base import AgentResponse, AIProviderError
from ..providers.mock import MockAIProvider
from ..providers.openai import OpenAIProvider
from .financial import cash_summary, metrics_overview
from .risk import compute_genome, get_genome
from .simulation import run_inline_simulation

_sessions: Dict[str, Dict[str, Any]] = {}
_interactions: Dict[str, Dict[str, Any]] = {}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_provider(settings: Settings):
    """Provider factory. Unknown/unconfigured values are rejected at startup by
    ``Settings.validate_runtime``; mock remains the keyless default."""
    if settings.ai_provider == "anthropic":
        return AnthropicAIProvider(
            settings.anthropic_api_key,
            settings.anthropic_model,
            timeout_seconds=settings.ai_timeout_seconds,
        )
    if settings.ai_provider == "openai":
        return OpenAIProvider(
            settings.openai_api_key,
            settings.openai_model,
            timeout_seconds=settings.ai_timeout_seconds,
            base_url=settings.openai_base_url,
        )
    return MockAIProvider()


def _interaction_row_to_dict(row: AIInteraction) -> Dict[str, Any]:
    return {
        "id": str(row.id),
        "session_id": str(row.session_id) if row.session_id else None,
        "company_id": str(row.company_id),
        "user_id": str(row.user_id) if row.user_id else None,
        "question": row.question,
        "answer": row.answer,
        "tools_used": list(row.tools_used or []),
        "citations": list(row.citations or []),
        "provider": row.provider,
        "model": row.model,
        "tokens": {"input": row.tokens_input or 0, "output": row.tokens_output or 0},
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def send_message(
    session: Session,
    company_id: str,
    user_id: str,
    *,
    message: str,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    settings = get_settings()
    provider = _get_provider(settings)

    persistent = session is not None
    if persistent:
        sid = session_id or new_uuid()
    else:
        sid = session_id or f"se_{uuid.uuid4().hex[:12]}"
    if not persistent and sid not in _sessions:
        _sessions[sid] = {
            "id": sid,
            "company_id": company_id,
            "user_id": user_id,
            "created_at": _utcnow(),
            "messages": [],
        }

    metrics_ctx = search_metrics_context(
        session, company_id, financial_service=_FinancialFacade()
    )
    genome = get_genome(company_id)
    if genome is None:
        genome = compute_genome(session, company_id)

    ctx: Dict[str, Any] = {
        "metrics": metrics_ctx,
        "genome": genome,
    }

    shock_pct = MockAIProvider.detect_revenue_shock_pct(message)
    sim_result = None
    sim_id = None
    sim_args: Dict[str, Any] = {}
    if shock_pct is not None:
        spec = build_revenue_shock_scenario(shock_pct)
        sim_args = {"shock": f"revenue_{shock_pct:+.0f}%"}
        sim_result = run_inline_simulation(
            session,
            company_id,
            name=spec["name"],
            assumptions=spec["assumptions"],
            horizon_periods=spec["horizon_periods"],
            trials=spec["trials"],
        )
        sim_id = sim_result["id"]
        ctx["simulation_result"] = sim_result
        ctx["simulation_id"] = sim_id
        ctx["simulation_args"] = sim_args

    started = time.monotonic()
    try:
        response: AgentResponse = provider.complete(
            message, session_id=sid, context=ctx
        )
    except AIProviderError as exc:
        raise BadGateway(f"AI provider error: {exc}") from exc
    latency_ms = int((time.monotonic() - started) * 1000)

    if persistent:
        row = AIInteraction(
            id=new_uuid(),
            company_id=company_id,
            user_id=user_id,
            session_id=sid,
            question=message,
            answer=response.answer,
            tools_used=response.tools_used or [],
            citations=response.citations or [],
            provider=response.provider,
            model=response.model,
            tokens_input=response.tokens_input,
            tokens_output=response.tokens_output,
            latency_ms=latency_ms,
        )
        session.add(row)
        session.flush()
        interaction_id = str(row.id)
    else:
        interaction_id = f"ai_{uuid.uuid4().hex[:12]}"
        record = {
            "id": interaction_id,
            "session_id": sid,
            "company_id": company_id,
            "user_id": user_id,
            "question": message,
            "answer": response.answer,
            "tools_used": response.tools_used,
            "citations": response.citations,
            "provider": response.provider,
            "model": response.model,
            "tokens": {"input": response.tokens_input, "output": response.tokens_output},
            "created_at": _utcnow(),
        }
        _interactions[interaction_id] = record
        _sessions[sid]["messages"].append(record)

    return {
        "session_id": sid,
        "interaction_id": interaction_id,
        "answer": response.answer,
        "tools_used": response.tools_used,
        "citations": response.citations,
        "provider": response.provider,
        "model": response.model,
        "tokens": {"input": response.tokens_input, "output": response.tokens_output},
    }


def get_session(
    session_id: str,
    company_id: str,
    *,
    session: Optional[Session] = None,
) -> Optional[Dict[str, Any]]:
    if session is not None:
        rows = session.execute(
            select(AIInteraction)
            .where(
                AIInteraction.company_id == company_id,
                AIInteraction.session_id == session_id,
            )
            .order_by(AIInteraction.created_at)
        ).scalars().all()
        if not rows:
            return None
        return {
            "id": session_id,
            "messages": [_interaction_row_to_dict(r) for r in rows],
            "created_at": rows[0].created_at.isoformat() if rows[0].created_at else None,
        }
    sess = _sessions.get(session_id)
    if sess is None or sess.get("company_id") != company_id:
        return None
    return {
        "id": sess["id"],
        "messages": sess.get("messages", []),
        "created_at": sess.get("created_at"),
    }


def list_sessions(
    company_id: str,
    user_id: Optional[str] = None,
    *,
    session: Optional[Session] = None,
) -> List[Dict[str, Any]]:
    if session is not None:
        stmt = (
            select(
                AIInteraction.session_id,
                func.min(AIInteraction.created_at).label("created_at"),
                func.count().label("message_count"),
            )
            .where(
                AIInteraction.company_id == company_id,
                AIInteraction.session_id.isnot(None),
            )
            .group_by(AIInteraction.session_id)
            .order_by(func.min(AIInteraction.created_at).desc())
        )
        if user_id:
            stmt = stmt.where(AIInteraction.user_id == user_id)
        rows = session.execute(stmt).all()
        return [
            {
                "id": str(sid),
                "created_at": created.isoformat() if created else None,
                "message_count": count,
            }
            for sid, created, count in rows
        ]
    out = []
    for sess in _sessions.values():
        if sess.get("company_id") != company_id:
            continue
        if user_id and sess.get("user_id") != user_id:
            continue
        out.append(
            {
                "id": sess["id"],
                "created_at": sess.get("created_at"),
                "message_count": len(sess.get("messages", [])),
            }
        )
    return sorted(out, key=lambda s: s.get("created_at", ""), reverse=True)


class _FinancialFacade:
    """Thin adapter so agent_tools does not import the service module."""

    @staticmethod
    def metrics_overview(session: Session, company_id: str) -> Dict[str, Any]:
        return metrics_overview(session, company_id)

    @staticmethod
    def cash_summary(session: Session, company_id: str) -> Dict[str, Any]:
        return cash_summary(session, company_id)
