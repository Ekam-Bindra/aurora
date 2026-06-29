"""Auth endpoints: login, refresh, logout, me."""

from __future__ import annotations

import jwt
from fastapi import APIRouter, Depends, Response, status

from ...core.config import Settings, get_settings
from ...core.errors import Unauthorized
from ...core.rbac import AuthContext, permissions_for_roles
from ...core.security import create_token, decode_token, verify_password
from ...deps import get_auth_context, get_user_store
from ...repositories.facade import UserStore
from .schemas import (
    AccessTokenResponse,
    AuthUser,
    CompanyClaim,
    LoginRequest,
    LoginResponse,
    RefreshRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_access(user_id: str, tenant_id: str, email: str, roles, settings: Settings) -> str:
    return create_token(
        subject=user_id,
        token_type="access",
        secret=settings.secret_key,
        ttl_seconds=settings.access_token_ttl_seconds,
        algorithm=settings.jwt_algorithm,
        claims={"tenant_id": tenant_id, "email": email, "roles": roles},
    )


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    store: UserStore = Depends(get_user_store),
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    user = store.get_user_by_email(body.email)
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        # Same response whether the user is missing or the password is wrong.
        raise Unauthorized("Invalid email or password.")

    company = store.get_company(user.company_id)
    access = _issue_access(user.id, user.company_id, user.email, user.roles, settings)
    refresh = create_token(
        subject=user.id,
        token_type="refresh",
        secret=settings.secret_key,
        ttl_seconds=settings.refresh_token_ttl_seconds,
        algorithm=settings.jwt_algorithm,
        claims={"tenant_id": user.company_id, "email": user.email, "roles": user.roles},
    )
    return LoginResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.access_token_ttl_seconds,
        user=AuthUser(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            title=user.title,
            company=CompanyClaim(
                id=company.id if company else "",
                name=company.name if company else "",
                slug=company.slug if company else "",
            ),
            roles=user.roles,
            permissions=sorted(permissions_for_roles(user.roles)),
        ),
    )


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(
    body: RefreshRequest,
    settings: Settings = Depends(get_settings),
) -> AccessTokenResponse:
    try:
        payload = decode_token(
            body.refresh_token,
            secret=settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise Unauthorized("Refresh token has expired.") from exc
    except jwt.PyJWTError as exc:
        raise Unauthorized("Invalid refresh token.") from exc

    if payload.get("type") != "refresh":
        raise Unauthorized("A valid refresh token is required.")

    access = _issue_access(
        payload.get("sub", ""),
        payload.get("tenant_id", ""),
        payload.get("email", ""),
        payload.get("roles", []),
        settings,
    )
    return AccessTokenResponse(access_token=access, expires_in=settings.access_token_ttl_seconds)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(_: AuthContext = Depends(get_auth_context)) -> Response:
    # Tokens are stateless in Phase 1; the client discards them. Server-side refresh-token
    # revocation is added with the persistence layer in Phase 2.
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=AuthUser)
def me(
    context: AuthContext = Depends(get_auth_context),
    store: UserStore = Depends(get_user_store),
) -> AuthUser:
    user = store.get_user(context.tenant_id, context.user_id)
    company = store.get_company(context.tenant_id)
    if user is None:
        raise Unauthorized("User no longer exists.")
    return AuthUser(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        title=user.title,
        company=CompanyClaim(
            id=company.id if company else "",
            name=company.name if company else "",
            slug=company.slug if company else "",
        ),
        roles=user.roles,
        permissions=sorted(context.permissions),
    )
