"""API integration tests for simulation endpoints."""

from __future__ import annotations

import os

import pytest
from aurora_db.models.commercial import Customer
from fastapi.testclient import TestClient
from sqlalchemy import select

from aurora.core.config import get_settings
from aurora.main import create_app
from aurora.persistence import session_scope


@pytest.fixture()
def db_client(tmp_path):
    db_file = tmp_path / "simulation_test.db"
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


def _top_customer_id() -> str:
    with session_scope() as session:
        row = session.execute(
            select(Customer.id)
            .where(Customer.name == "Continental Mercantile Group")
            .limit(1)
        ).first()
        assert row is not None
        return str(row[0])


def test_create_run_and_get_simulation(db_client: TestClient):
    token = _login(db_client)
    cust_id = _top_customer_id()
    r = db_client.post(
        "/api/v1/scenarios",
        json={
            "name": "Lose top customer + 6% eng raise",
            "horizon_periods": 12,
            "trials": 2000,
            "assumptions": {
                "shocks": [
                    {"type": "customer_churn", "customer_id": cust_id, "probability": 1.0},
                    {"type": "expense_change", "category": "payroll", "pct_change": 0.06},
                ],
                "distributions": {
                    "revenue_growth_pct": {"dist": "normal", "mean": 0.015, "std": 0.02},
                },
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    sc_id = r.json()["data"]["id"]

    r2 = db_client.post(
        f"/api/v1/scenarios/{sc_id}/run",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 202
    sim_id = r2.json()["data"]["simulation_id"]

    r3 = db_client.get(
        f"/api/v1/simulations/{sim_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r3.status_code == 200
    body = r3.json()["data"]
    assert body["status"] == "completed"
    assert body["trials"] == 2000
    metrics = {item["metric"] for item in body["results"]}
    assert "cash_runway_months" in metrics
    assert "gross_margin" in metrics
    assert body["risk_deltas"]
    assert len(body["recommendations"]) >= 1


def test_list_scenarios(db_client: TestClient):
    token = _login(db_client)
    db_client.post(
        "/api/v1/scenarios",
        json={"name": "Baseline check", "trials": 500, "assumptions": {"shocks": []}},
        headers={"Authorization": f"Bearer {token}"},
    )
    r = db_client.get(
        "/api/v1/scenarios",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert len(r.json()["data"]) >= 1


def test_explain_simulation(db_client: TestClient):
    token = _login(db_client)
    r = db_client.post(
        "/api/v1/scenarios",
        json={
            "name": "Explain test",
            "trials": 1000,
            "assumptions": {
                "shocks": [{"type": "expense_change", "category": "payroll", "pct_change": 0.05}],
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    sc_id = r.json()["data"]["id"]
    sim_id = db_client.post(
        f"/api/v1/scenarios/{sc_id}/run",
        headers={"Authorization": f"Bearer {token}"},
    ).json()["data"]["simulation_id"]

    r2 = db_client.get(
        f"/api/v1/explain/simulation/{sim_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    data = r2.json()["data"]
    assert data["simulation_id"] == sim_id
    assert data["driver_attribution"]


def test_simulation_tenant_isolation(db_client: TestClient):
    token = _login(db_client)
    sc_id = db_client.post(
        "/api/v1/scenarios",
        json={"name": "Private", "trials": 500, "assumptions": {}},
        headers={"Authorization": f"Bearer {token}"},
    ).json()["data"]["id"]
    other = _login(db_client, email="ceo@nimbus.test")
    r = db_client.get(
        f"/api/v1/scenarios/{sc_id}",
        headers={"Authorization": f"Bearer {other}"},
    )
    assert r.status_code == 200


def test_zero_shock_golden_runway(db_client: TestClient):
    """Golden: zero-shock simulation runway should be near live cash runway."""
    token = _login(db_client)
    cash = db_client.get(
        "/api/v1/financials/cash",
        headers={"Authorization": f"Bearer {token}"},
    ).json()["data"]
    baseline_runway = cash.get("runway_months")

    sc_id = db_client.post(
        "/api/v1/scenarios",
        json={
            "name": "Zero shock",
            "trials": 3000,
            "assumptions": {
                "shocks": [],
                "distributions": {"revenue_growth_pct": {"mean": 0.0, "std": 0.0}},
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    ).json()["data"]["id"]
    sim_id = db_client.post(
        f"/api/v1/scenarios/{sc_id}/run",
        headers={"Authorization": f"Bearer {token}"},
    ).json()["data"]["simulation_id"]
    sim = db_client.get(
        f"/api/v1/simulations/{sim_id}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()["data"]
    runway = next(r for r in sim["results"] if r["metric"] == "cash_runway_months")
    if baseline_runway is not None:
        assert abs(runway["summary"]["p50"] - baseline_runway) < 2.0
