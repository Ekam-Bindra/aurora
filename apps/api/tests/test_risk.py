"""Risk genome API tests."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from aurora.core.config import get_settings
from aurora.main import create_app


@pytest.fixture()
def db_client(tmp_path):
    db_file = tmp_path / "risk_test.db"
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


def test_risk_genome_eight_dimensions(db_client: TestClient):
    token = _login(db_client)
    r = db_client.get(
        "/api/v1/risk/genome",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data["dimensions"]) == 8
    assert 0 <= data["overall_score"] <= 100


def test_risk_genome_dimension_detail(db_client: TestClient):
    token = _login(db_client)
    db_client.get("/api/v1/risk/genome", headers={"Authorization": f"Bearer {token}"})
    r = db_client.get(
        "/api/v1/risk/genome/liquidity",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["dimension"] == "liquidity"
    assert "drivers" in r.json()["data"]


def test_risk_recompute(db_client: TestClient):
    token = _login(db_client)
    r = db_client.post(
        "/api/v1/risk/recompute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 202
    assert r.json()["data"]["status"] == "completed"
