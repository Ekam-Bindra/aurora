"""Security middleware and production settings tests (Phase 9)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aurora.core.config import Settings, get_settings
from aurora.main import create_app


@pytest.fixture()
def security_client(monkeypatch):
    monkeypatch.setenv("SECURITY_HEADERS_ENABLED", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        yield client
    get_settings.cache_clear()


def test_security_headers_present(security_client: TestClient):
    resp = security_client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_auth_rate_limit_returns_429(monkeypatch):
    monkeypatch.setenv("AUTH_RATE_LIMIT_PER_MINUTE", "2")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        for _ in range(2):
            client.post(
                "/api/v1/auth/login",
                json={"email": "cfo@nimbus.test", "password": "wrong"},
            )
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "cfo@nimbus.test", "password": "wrong"},
        )
        assert resp.status_code == 429
        assert resp.json()["error"]["code"] == "rate_limited"
    get_settings.cache_clear()


def test_production_rejects_short_secret():
    settings = Settings(app_env="production", secret_key="too-short")
    with pytest.raises(RuntimeError, match="at least 32 characters"):
        settings.validate_runtime()


def test_production_rejects_default_demo_password_when_seeding():
    settings = Settings(
        app_env="production",
        secret_key="x" * 32,
        demo_password="aurora-demo-2026",
        seed_demo_on_startup=True,
    )
    with pytest.raises(RuntimeError, match="DEMO_PASSWORD"):
        settings.validate_runtime()


def test_clickhouse_requires_url():
    settings = Settings(
        analytics_backend="clickhouse",
        clickhouse_url=None,
    )
    with pytest.raises(RuntimeError, match="CLICKHOUSE_URL"):
        settings.validate_runtime()
