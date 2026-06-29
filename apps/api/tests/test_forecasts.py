"""Forecast API tests."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from aurora.core.config import get_settings
from aurora.main import create_app


@pytest.fixture()
def db_client(tmp_path):
    db_file = tmp_path / "forecast_test.db"
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


def test_create_and_get_forecast(db_client: TestClient):
    token = _login(db_client)
    r = db_client.post(
        "/api/v1/forecasts",
        json={"metric": "revenue", "horizon_periods": 6, "method": "baseline"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 202
    fc_id = r.json()["data"]["id"]

    r2 = db_client.get(
        f"/api/v1/forecasts/{fc_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    body = r2.json()["data"]
    assert body["metric"] == "revenue"
    assert len(body["points"]) == 6
    assert body["accuracy"]["mape"] >= 0


def test_list_forecasts(db_client: TestClient):
    token = _login(db_client)
    db_client.post(
        "/api/v1/forecasts",
        json={"metric": "revenue", "horizon_periods": 3},
        headers={"Authorization": f"Bearer {token}"},
    )
    r = db_client.get(
        "/api/v1/forecasts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert len(r.json()["data"]["forecasts"]) >= 1
