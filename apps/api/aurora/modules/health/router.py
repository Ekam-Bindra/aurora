"""Liveness and readiness endpoints (used by Compose/ALB probes)."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from ...core.config import get_settings
from ...persistence import is_database_enabled, session_scope

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Liveness: the process is up."""
    settings = get_settings()
    return {"status": "ok", "service": settings.project_name, "version": settings.version}


@router.get("/ready")
def ready() -> dict:
    """Readiness: dependencies are reachable."""
    checks: dict[str, str] = {}
    if is_database_enabled():
        try:
            with session_scope() as session:
                session.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as exc:  # pragma: no cover - surfaced in response
            checks["database"] = f"error: {exc}"
            return {"status": "not_ready", "checks": checks}
    else:
        checks["store"] = "memory"

    return {"status": "ready", "checks": checks}
