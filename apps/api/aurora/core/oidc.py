"""OIDC / SSO configuration parsing and token exchange helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx
import jwt


@dataclass(frozen=True)
class OidcConfig:
    enabled: bool
    issuer: str
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: List[str]

    @property
    def authorization_endpoint(self) -> str:
        return f"{self.issuer.rstrip('/')}/authorize"

    @property
    def token_endpoint(self) -> str:
        return f"{self.issuer.rstrip('/')}/oauth/token"

    @property
    def userinfo_endpoint(self) -> str:
        return f"{self.issuer.rstrip('/')}/userinfo"

    @property
    def jwks_uri(self) -> str:
        return f"{self.issuer.rstrip('/')}/.well-known/jwks.json"

    def authorization_url(self, *, state: str, nonce: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.scopes),
            "state": state,
            "nonce": nonce,
        }
        return f"{self.authorization_endpoint}?{urlencode(params)}"


def parse_oidc_config(
    *,
    enabled: bool,
    issuer: Optional[str],
    client_id: Optional[str],
    client_secret: Optional[str],
    redirect_uri: Optional[str],
    scopes_raw: Optional[str],
) -> Optional[OidcConfig]:
    """Parse OIDC settings; returns ``None`` when SSO is disabled."""
    if not enabled:
        return None
    missing = [
        name
        for name, value in [
            ("OIDC_ISSUER", issuer),
            ("OIDC_CLIENT_ID", client_id),
            ("OIDC_CLIENT_SECRET", client_secret),
            ("OIDC_REDIRECT_URI", redirect_uri),
        ]
        if not value
    ]
    if missing:
        raise ValueError(f"OIDC enabled but missing: {', '.join(missing)}")
    scopes = [s for s in (scopes_raw or "openid profile email").split() if s]
    return OidcConfig(
        enabled=True,
        issuer=issuer or "",
        client_id=client_id or "",
        client_secret=client_secret or "",
        redirect_uri=redirect_uri or "",
        scopes=scopes,
    )


def exchange_code(config: OidcConfig, code: str) -> Dict[str, Any]:
    """Exchange authorization code for tokens at the IdP token endpoint."""
    payload = {
        "grant_type": "authorization_code",
        "client_id": config.client_id,
        "client_secret": config.client_secret,
        "code": code,
        "redirect_uri": config.redirect_uri,
    }
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(config.token_endpoint, data=payload)
        resp.raise_for_status()
        return resp.json()


def decode_id_token(id_token: str, config: OidcConfig) -> Dict[str, Any]:
    """Decode OIDC ID token (signature verification skipped for mock/dev IdPs)."""
    return jwt.decode(
        id_token,
        key="",
        options={"verify_signature": False, "verify_aud": False},
        algorithms=["RS256", "HS256"],
    )


def fetch_userinfo(config: OidcConfig, access_token: str) -> Dict[str, Any]:
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(
            config.userinfo_endpoint,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()
