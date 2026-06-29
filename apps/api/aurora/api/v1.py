"""Mounts all v1 module routers under a single router."""

from __future__ import annotations

from fastapi import APIRouter

from ..modules.admin.router import router as admin_router
from ..modules.agent.router import router as agent_router
from ..modules.auth.oidc_router import router as oidc_router
from ..modules.auth.router import router as auth_router
from ..modules.forecasts.router import router as forecasts_router
from ..modules.graph.router import router as graph_router
from ..modules.health.router import router as health_router
from ..modules.ingestion.router import router as ingestion_router
from ..modules.metrics.router import router as metrics_router
from ..modules.reports.router import router as reports_router
from ..modules.risk.router import router as risk_router
from ..modules.simulation.router import router as simulation_router
from ..modules.workspaces.router import router as workspaces_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(oidc_router)
api_router.include_router(admin_router)
api_router.include_router(metrics_router)
api_router.include_router(graph_router)
api_router.include_router(forecasts_router)
api_router.include_router(risk_router)
api_router.include_router(simulation_router)
api_router.include_router(agent_router)
api_router.include_router(ingestion_router)
api_router.include_router(reports_router)
api_router.include_router(workspaces_router)
