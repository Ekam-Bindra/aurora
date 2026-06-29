"""Mounts all v1 module routers under a single router."""

from __future__ import annotations

from fastapi import APIRouter

from ..modules.auth.router import router as auth_router
from ..modules.health.router import router as health_router
from ..modules.workspaces.router import router as workspaces_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(workspaces_router)
