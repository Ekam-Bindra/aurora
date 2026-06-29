"""Tenant context.

The active tenant is resolved from the authenticated request and stored in a context variable.
Repositories read it (or take it explicitly) so that every data access is scoped to one tenant
— the foundation of AURORA's multi-tenant isolation (docs/architecture/system-architecture.md
§6). In Phase 2 this also drives the SQLAlchemy repository filters / optional Postgres RLS.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

_tenant_ctx: ContextVar[Optional[str]] = ContextVar("tenant_id", default=None)


def set_current_tenant(tenant_id: Optional[str]) -> None:
    _tenant_ctx.set(tenant_id)


def get_current_tenant() -> Optional[str]:
    return _tenant_ctx.get()


def require_current_tenant() -> str:
    tenant_id = _tenant_ctx.get()
    if not tenant_id:
        raise RuntimeError("No tenant in context; this code path must run within a request.")
    return tenant_id
