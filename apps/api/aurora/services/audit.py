"""Audit log helper — append-only records for admin console."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.logging import get_request_id
from ..repositories.memory import get_store

_DEMO_AUDIT_SEEDED: set = set()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def record_audit(
    session: Optional[Session],
    company_id: str,
    *,
    user_id: Optional[str],
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Write an audit entry (DB when session is available, otherwise in-memory)."""
    request_id = get_request_id()
    if session is not None:
        from aurora_db.models import AuditLog

        entry = AuditLog(
            company_id=company_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=request_id,
            before=before,
            after=after,
        )
        session.add(entry)
        session.flush()
        return _serialize_db_entry(entry)

    return get_store().append_audit_log(
        company_id=company_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        request_id=request_id,
        before=before,
        after=after,
    )


def list_audit_logs(
    session: Optional[Session],
    company_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
    action: Optional[str] = None,
) -> List[Dict[str, Any]]:
    _ensure_demo_audit(session, company_id)
    if session is not None:
        from aurora_db.models import AuditLog

        stmt = (
            select(AuditLog)
            .where(AuditLog.company_id == company_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if action:
            stmt = stmt.where(AuditLog.action == action)
        rows = session.scalars(stmt).all()
        return [_serialize_db_entry(r) for r in rows]

    return get_store().list_audit_logs(
        company_id, limit=limit, offset=offset, action=action
    )


def count_audit_logs(
    session: Optional[Session],
    company_id: str,
    *,
    action: Optional[str] = None,
) -> int:
    _ensure_demo_audit(session, company_id)
    if session is not None:
        from aurora_db.models import AuditLog

        stmt = select(AuditLog).where(AuditLog.company_id == company_id)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        return len(session.scalars(stmt).all())

    return get_store().count_audit_logs(company_id, action=action)


def _serialize_db_entry(entry) -> Dict[str, Any]:
    return {
        "id": str(entry.id),
        "user_id": entry.user_id,
        "action": entry.action,
        "resource_type": entry.resource_type,
        "resource_id": entry.resource_id,
        "request_id": entry.request_id,
        "before": entry.before,
        "after": entry.after,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


def _audit_exists(session: Optional[Session], company_id: str) -> bool:
    if session is not None:
        from aurora_db.models import AuditLog

        row = session.scalars(
            select(AuditLog.id).where(AuditLog.company_id == company_id).limit(1)
        ).first()
        return row is not None
    return get_store().count_audit_logs(company_id) > 0


def _ensure_demo_audit(session: Optional[Session], company_id: str) -> None:
    """Seed a handful of demo audit rows once per tenant (pilot UX)."""
    if company_id in _DEMO_AUDIT_SEEDED:
        return
    if _audit_exists(session, company_id):
        _DEMO_AUDIT_SEEDED.add(company_id)
        return

    demos = [
        ("user.login", "auth", None),
        ("data_source.sync", "data_source", None),
        ("forecast.run", "forecast", None),
        ("simulation.run", "simulation", None),
        ("board_report.generate", "board_report", None),
    ]
    for act, rtype, rid in demos:
        record_audit(
            session,
            company_id,
            user_id=None,
            action=act,
            resource_type=rtype,
            resource_id=rid,
            after={"demo": True},
        )
    _DEMO_AUDIT_SEEDED.add(company_id)
