"""Every sensitive mutation leaves an audit trail the admin console can browse.

Admin user/role mutations audit at the service layer (services/admin.py);
these tests pin the router-layer coverage added for reports approval,
ingestion, and simulations. Agent Q&A is deliberately excluded — the
``ai_interaction`` table is its own complete trail.
"""

from __future__ import annotations

import os
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from aurora.core.config import get_settings
from aurora.main import create_app


@pytest.fixture()
def db_client(tmp_path) -> Iterator[TestClient]:
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'audit.db'}"
    os.environ["DEMO_SEED_SCALE"] = "0.05"
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        yield client
    get_settings.cache_clear()
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("DEMO_SEED_SCALE", None)


def _auth(client: TestClient) -> dict:
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "cfo@nimbus.test", "password": "aurora-demo-2026"},
    )
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _audited_actions(client: TestClient, headers: dict) -> set:
    r = client.get("/api/v1/audit-logs?page_size=100", headers=headers)
    assert r.status_code == 200, r.text
    return {e["action"] for e in r.json()["data"]}


def test_mutations_produce_audit_entries(db_client):
    h = _auth(db_client)

    r = db_client.post(
        "/api/v1/ingestion/uploads",
        files={"file": ("c.csv", b"name,industry,region\nA,Retail,NA\n", "text/csv")},
        data={"target": "customers"},
        headers=h,
    )
    assert r.status_code == 202, r.text

    r = db_client.post(
        "/api/v1/data-sources",
        json={"kind": "accounting", "name": "Audit Probe", "config": {}},
        headers=h,
    )
    assert r.status_code == 201, r.text

    r = db_client.post(
        "/api/v1/scenarios",
        json={
            "name": "Audit scenario",
            "horizon_periods": 6,
            "trials": 500,
            "assumptions": {"shocks": [], "distributions": {}},
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    scenario_id = r.json()["data"]["id"]
    r = db_client.post(f"/api/v1/scenarios/{scenario_id}/run", headers=h)
    assert r.status_code == 202, r.text

    r = db_client.post(
        "/api/v1/board-reports",
        json={"title": "Audit Pack", "sections": ["financial_summary"]},
        headers=h,
    )
    assert r.status_code == 201, r.text
    report_id = r.json()["data"]["id"]
    assert db_client.post(
        f"/api/v1/board-reports/{report_id}/generate", headers=h
    ).status_code == 202
    assert db_client.post(
        f"/api/v1/board-reports/{report_id}/approve", headers=h
    ).status_code == 200

    actions = _audited_actions(db_client, h)
    for expected in (
        "ingestion.upload",
        "data_source.register",
        "scenario.create",
        "simulation.run",
        "board_report.create",
        "board_report.generate",
        "board_report.approve",
    ):
        assert expected in actions, f"missing audit action {expected}; got {sorted(actions)}"
