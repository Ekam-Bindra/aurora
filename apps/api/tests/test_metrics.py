"""Metrics API tests (require DATABASE_URL + seeded Nimbus)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from aurora.core.config import get_settings
from aurora.main import create_app
from aurora.repositories.memory import get_store
from aurora.seed.demo import seed_demo
from tests.conftest import login


@pytest.fixture()
def db_client(tmp_path):
    db_file = tmp_path / "metrics_test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"
    os.environ["DEMO_SEED_SCALE"] = "0.05"
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        yield client
    get_settings.cache_clear()
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("DEMO_SEED_SCALE", None)


def _login(client: TestClient, email: str = "cfo@nimbus.test") -> str:
    r = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "aurora-demo-2026"},
    )
    assert r.status_code == 200
    return r.json()["access_token"]


def test_metrics_overview(db_client: TestClient):
    token = _login(db_client)
    r = db_client.get(
        "/api/v1/metrics/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["as_of"]
    kpis = data["kpis"]
    assert kpis["revenue_mtd"]["value_cents"] > 0
    assert kpis["gross_margin"]["value"] is not None
    assert kpis["cash_runway_months"]["value"] > 0


def test_metric_series(db_client: TestClient):
    token = _login(db_client)
    r = db_client.get(
        "/api/v1/metrics/revenue/series",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    points = r.json()["data"]["points"]
    assert len(points) >= 3


def test_explain_metric(db_client: TestClient):
    token = _login(db_client)
    r = db_client.get(
        "/api/v1/explain/metric/gross_margin",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["formula"]
    assert "revenue_cents" in body["inputs"]


def test_metrics_require_database():
    os.environ.pop("DATABASE_URL", None)
    get_settings.cache_clear()
    seed_demo(get_store(), "test-password-123", force=True)
    with TestClient(create_app()) as client:
        token = login(client, "cfo@nimbus.test").json()["access_token"]
        r = client.get(
            "/api/v1/metrics/overview",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 422
