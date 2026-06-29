"""OIDC / SSO endpoints (Auth0, Okta, Cognito-compatible)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse

from ...core.config import Settings, get_settings
from ...core.errors import Unauthorized, Unprocessable
from ...core.oidc import OidcConfig, decode_id_token, exchange_code, fetch_userinfo
from ...core.rbac import permissions_for_roles
from ...core.security import create_token
from ...deps import get_user_store
from ...repositories.facade import UserStore
from .oidc_state import create_state, pop_state
from .router import _issue_access
from .schemas import AuthUser, CompanyClaim, LoginResponse

router = APIRouter(prefix="/auth/oidc", tags=["auth"])


def _require_oidc(settings: Settings = Depends(get_settings)) -> OidcConfig:
    config = settings.oidc_config()
    if config is None:
        raise Unprocessable("OIDC SSO is not enabled.")
    return config


@router.get("/config")
def oidc_config(settings: Settings = Depends(get_settings)) -> dict:
    config = settings.oidc_config()
    return {
        "data": {
            "enabled": config is not None,
            "issuer": config.issuer if config else None,
            "login_path": "/api/v1/auth/oidc/login" if config else None,
        }
    }


@router.get("/login")
def oidc_login(config: OidcConfig = Depends(_require_oidc)) -> RedirectResponse:
    state, nonce = create_state()
    url = config.authorization_url(state=state, nonce=nonce)
    return RedirectResponse(url=url, status_code=302)


@router.get("/callback", response_model=LoginResponse)
def oidc_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    config: OidcConfig = Depends(_require_oidc),
    store: UserStore = Depends(get_user_store),
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    if not code or not state:
        raise Unauthorized("Missing OIDC authorization code or state.")

    nonce = pop_state(state)
    if nonce is None:
        raise Unauthorized("Invalid or expired OIDC state.")

    try:
        tokens = exchange_code(config, code)
    except Exception as exc:
        raise Unauthorized("OIDC token exchange failed.") from exc

    id_token = tokens.get("id_token")
    access_token = tokens.get("access_token")
    email: Optional[str] = None
    if id_token:
        claims = decode_id_token(id_token, config)
        if claims.get("nonce") and claims.get("nonce") != nonce:
            raise Unauthorized("OIDC nonce mismatch.")
        email = claims.get("email")
    if not email and access_token:
        profile = fetch_userinfo(config, access_token)
        email = profile.get("email")
    if not email:
        raise Unauthorized("OIDC profile did not include an email address.")

    user = store.get_user_by_email(email)
    if user is None or not user.is_active:
        raise Unauthorized("No active AURORA user matches this SSO identity.")

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
