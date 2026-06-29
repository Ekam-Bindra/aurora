"""Shared FastAPI dependencies: auth-context resolution and permission guards."""

from __future__ import annotations

from typing import Generator, Optional

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .core.config import Settings, get_settings
from .core.errors import Forbidden, Unauthorized
from .core.rbac import AuthContext, permissions_for_roles
from .core.security import decode_token
from .core.tenancy import set_current_tenant
from .persistence import get_session_factory
from .repositories.facade import DatabaseUserStore, MemoryUserStore, UserStore
from .repositories.memory import get_store

_bearer = HTTPBearer(auto_error=False)


def get_db_session() -> Generator[Optional[Session], None, None]:
    """Yield a SQLAlchemy session when the database is enabled; otherwise ``None``."""
    factory = get_session_factory()
    if factory is None:
        yield None
        return
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_user_store(
    settings: Settings = Depends(get_settings),
    session: Optional[Session] = Depends(get_db_session),
) -> UserStore:
    if settings.database_url and session is not None:
        return DatabaseUserStore(session)
    return MemoryUserStore(get_store())


def get_auth_context(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> AuthContext:
    if credentials is None or not credentials.credentials:
        raise Unauthorized("Missing bearer token.")
    try:
        payload = decode_token(
            credentials.credentials,
            secret=settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise Unauthorized("Token has expired.") from exc
    except jwt.PyJWTError as exc:
        raise Unauthorized("Invalid token.") from exc

    if payload.get("type") != "access":
        raise Unauthorized("A valid access token is required.")

    roles = payload.get("roles", [])
    context = AuthContext(
        user_id=payload.get("sub", ""),
        tenant_id=payload.get("tenant_id", ""),
        email=payload.get("email", ""),
        roles=roles,
        permissions=permissions_for_roles(roles),
    )
    set_current_tenant(context.tenant_id)
    return context


def require_permission(permission: str):
    """Dependency factory: 403 unless the caller holds ``permission``."""

    def _guard(context: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if not context.has(permission):
            raise Forbidden(f"Missing required permission: {permission}")
        return context

    return _guard
