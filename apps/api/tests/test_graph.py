"""Knowledge graph API tests."""

from __future__ import annotations

import os

import pytest
from aurora_db.seed.nimbus import CRITICAL_VENDOR, TOP_CUSTOMER
from aurora_graph.sync import ELECTRONICS_LINE
from fastapi.testclient import TestClient

from aurora.core.config import get_settings
from aurora.main import create_app


@pytest.fixture()
def db_client(tmp_path):
    db_file = tmp_path / "graph_test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"
    os.environ["DEMO_SEED_SCALE"] = "0.05"
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        yield client
    get_settings.cache_clear()
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("DEMO_SEED_SCALE", None)


def _login(client: TestClient, email: str = "coo@nimbus.test") -> str:
    r = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "aurora-demo-2026"},
    )
    assert r.status_code == 200
    return r.json()["access_token"]


def test_graph_nodes_and_impact(db_client: TestClient):
    token = _login(db_client)
    r = db_client.get(
        "/api/v1/graph/nodes?label=Vendor",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    vendors = r.json()["data"]["nodes"]
    assert len(vendors) > 0
    critical = next(
        (v for v in vendors if v.get("criticality") == "critical"),
        vendors[0],
    )
    r2 = db_client.get(
        f"/api/v1/graph/impact/{critical['id']}?depth=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    body = r2.json()["data"]
    assert body["impact"]["affected_products"]
    assert body["impact"]["estimated_revenue_at_risk_cents"] > 0


def test_graph_neighbors(db_client: TestClient):
    token = _login(db_client)
    nodes = db_client.get(
        "/api/v1/graph/nodes?limit=5",
        headers={"Authorization": f"Bearer {token}"},
    ).json()["data"]["nodes"]
    node_id = nodes[0]["id"]
    r = db_client.get(
        f"/api/v1/graph/neighbors/{node_id}?depth=1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["node"]["id"] == node_id


def test_vanguard_impact_chain_integration(db_client: TestClient):
    """Golden integration test: Vanguard → Electronics → Continental chain via API."""
    token = _login(db_client)
    vendors = db_client.get(
        "/api/v1/graph/nodes?label=Vendor",
        headers={"Authorization": f"Bearer {token}"},
    ).json()["data"]["nodes"]
    critical = next(v for v in vendors if v["name"] == CRITICAL_VENDOR)
    assert critical["criticality"] == "critical"

    r = db_client.get(
        f"/api/v1/graph/impact/{critical['id']}?depth=3",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()["data"]
    impact = body["impact"]

    electronics = [p for p in impact["affected_products"] if p.get("line") == ELECTRONICS_LINE]
    assert len(electronics) >= 1

    customer_names = {c["name"] for c in impact["affected_customers"]}
    assert TOP_CUSTOMER in customer_names

    dept_names = {d["name"] for d in impact["affected_departments"]}
    assert "Supply Chain" in dept_names

    assert impact["estimated_revenue_at_risk_cents"] > 0
