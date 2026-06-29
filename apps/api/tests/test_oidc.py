"""OIDC configuration parsing tests (Phase 9)."""

from __future__ import annotations

import pytest

from aurora.core.config import Settings
from aurora.core.oidc import OidcConfig, parse_oidc_config


def test_oidc_disabled_returns_none():
    assert parse_oidc_config(
        enabled=False,
        issuer="https://example.auth0.com",
        client_id="abc",
        client_secret="secret",
        redirect_uri="http://localhost/callback",
        scopes_raw="openid email",
    ) is None


def test_oidc_enabled_requires_fields():
    with pytest.raises(ValueError, match="OIDC enabled but missing"):
        parse_oidc_config(
            enabled=True,
            issuer=None,
            client_id="abc",
            client_secret="secret",
            redirect_uri="http://localhost/callback",
            scopes_raw=None,
        )


def test_oidc_config_builds_authorization_url():
    config = parse_oidc_config(
        enabled=True,
        issuer="https://tenant.auth0.com",
        client_id="client123",
        client_secret="secret",
        redirect_uri="http://localhost:8000/api/v1/auth/oidc/callback",
        scopes_raw="openid profile email",
    )
    assert isinstance(config, OidcConfig)
    url = config.authorization_url(state="state123", nonce="nonce456")
    assert "client_id=client123" in url
    assert "state=state123" in url
    assert "nonce=nonce456" in url


def test_settings_oidc_config_when_disabled():
    settings = Settings(oidc_enabled=False)
    assert settings.oidc_config() is None


def test_oidc_config_endpoint_when_disabled(client):
    resp = client.get("/api/v1/auth/oidc/config")
    assert resp.status_code == 200
    assert resp.json()["data"]["enabled"] is False


def test_oidc_login_disabled_returns_422(client):
    resp = client.get("/api/v1/auth/oidc/login", follow_redirects=False)
    assert resp.status_code == 422
