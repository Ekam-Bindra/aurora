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
    for dim in data["dimensions"]:
        assert "signal_id" in dim
        assert "explain_ref" in dim


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


def test_explain_risk_signal(db_client: TestClient):
    token = _login(db_client)
    r = db_client.get(
        "/api/v1/risk/genome",
        headers={"Authorization": f"Bearer {token}"},
    )
    liquidity = next(
        d for d in r.json()["data"]["dimensions"] if d["dimension"] == "liquidity"
    )
    signal_id = liquidity["signal_id"]
    r2 = db_client.get(
        f"/api/v1/explain/risk/{signal_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    data = r2.json()["data"]
    assert data["signal_id"] == signal_id
    assert data["dimension"] == "liquidity"
    assert len(data["driver_attribution"]) >= 1


def test_nimbus_liquidity_and_concentration(tmp_path):
    """Golden check: Nimbus demo should show elevated liquidity and customer concentration."""
    db_file = tmp_path / "risk_golden.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"
    os.environ["DEMO_SEED_SCALE"] = "0.5"
    get_settings.cache_clear()
    with TestClient(create_app()) as db_client:
        token = _login(db_client)
        r = db_client.get(
            "/api/v1/risk/genome",
            headers={"Authorization": f"Bearer {token}"},
        )
        dims = {d["dimension"]: d for d in r.json()["data"]["dimensions"]}
        liquidity = dims["liquidity"]
        concentration = dims["customer_concentration"]
        assert liquidity["severity"] == "high"
        assert concentration["severity"] == "high"
        assert liquidity["score"] >= 51
        assert concentration["score"] >= 51
    get_settings.cache_clear()
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("DEMO_SEED_SCALE", None)


def test_risk_genome_history(db_client: TestClient):
    token = _login(db_client)
    db_client.get("/api/v1/risk/genome", headers={"Authorization": f"Bearer {token}"})
    r = db_client.get(
        "/api/v1/risk/genome/history",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert len(r.json()["data"]["history"]) >= 1
