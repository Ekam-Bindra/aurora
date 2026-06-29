"""Liveness and readiness endpoints (used by Compose/ALB probes)."""

from __future__ import annotations

from fastapi import APIRouter

from ...core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Liveness: the process is up."""
    settings = get_settings()
    return {"status": "ok", "service": settings.project_name, "version": settings.version}


@router.get("/ready")
def ready() -> dict:
    """Readiness: dependencies are reachable.

    Phase 1 runs on the in-memory store, so it is always ready. The structure is in place to
    add Postgres/Neo4j/Redis checks in Phase 2.
    """
    checks = {"store": "ok"}
    return {"status": "ready", "checks": checks}
