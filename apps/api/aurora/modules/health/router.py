"""Liveness and readiness endpoints.

Liveness (``/health``) answers "is the process up" — ECS restarts the task on
failure, so it must not depend on downstream systems. Readiness (``/ready``)
answers "can this task serve real traffic" — the ALB target group probes it,
so a task with an unreachable database leaves rotation (HTTP 503) instead of
serving errors, and rejoins automatically when the dependency recovers.
"""

from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, Response, status
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
def ready(response: Response) -> dict:
    """Readiness: dependencies are reachable. 503 removes the task from rotation."""
    checks: Dict[str, str] = {}
    if is_database_enabled():
        try:
            with session_scope() as session:
                session.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as exc:
            checks["database"] = f"error: {type(exc).__name__}"
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "not_ready", "checks": checks}
    else:
        checks["store"] = "memory"

    return {"status": "ready", "checks": checks}
