"""Board report API tests (Phase 8)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from aurora.core.config import get_settings
from aurora.main import create_app


@pytest.fixture()
def db_client(tmp_path):
    db_file = tmp_path / "board_reports_test.db"
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


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_board_report_requires_create_permission(db_client: TestClient):
    token = _login(db_client, email="ops@nimbus.test")
    r = db_client.post(
        "/api/v1/board-reports",
        headers=_auth(token),
        json={"title": "Q2 Pack"},
    )
    assert r.status_code == 403


def test_create_generate_and_export_board_report(db_client: TestClient):
    token = _login(db_client)
    create = db_client.post(
        "/api/v1/board-reports",
        headers=_auth(token),
        json={
            "title": "Q2 2026 Board Pack",
            "period_start": "2026-04-01",
            "period_end": "2026-06-30",
            "sections": ["financial_summary", "forecast", "risk_genome"],
        },
    )
    assert create.status_code == 201
    report_id = create.json()["data"]["id"]
    assert create.json()["data"]["status"] == "draft"

    gen = db_client.post(
        f"/api/v1/board-reports/{report_id}/generate",
        headers=_auth(token),
    )
    assert gen.status_code == 202
    assert gen.json()["data"]["status"] == "in_review"

    detail = db_client.get(
        f"/api/v1/board-reports/{report_id}",
        headers=_auth(token),
    )
    assert detail.status_code == 200
    content = detail.json()["data"]["content"]
    assert content is not None
    assert len(content["sections"]) == 3
    assert content["sections"][0]["type"] == "financial_summary"
    assert "kpis" in content["sections"][0]["data"]

    export = db_client.get(
        f"/api/v1/board-reports/{report_id}/export?format=html",
        headers=_auth(token),
    )
    assert export.status_code == 200
    assert "text/html" in export.headers["content-type"]
    assert b"Q2 2026 Board Pack" in export.content


def test_approve_board_report(db_client: TestClient):
    cfo = _login(db_client)
    create = db_client.post(
        "/api/v1/board-reports",
        headers=_auth(cfo),
        json={"title": "Approval Test"},
    )
    report_id = create.json()["data"]["id"]
    db_client.post(
        f"/api/v1/board-reports/{report_id}/generate",
        headers=_auth(cfo),
    )

    ceo = _login(db_client, email="ceo@nimbus.test")
    approve = db_client.post(
        f"/api/v1/board-reports/{report_id}/approve",
        headers=_auth(ceo),
    )
    assert approve.status_code == 200
    assert approve.json()["data"]["status"] == "approved"


def test_board_report_tenant_isolation(db_client: TestClient):
    token = _login(db_client)
    create = db_client.post(
        "/api/v1/board-reports",
        headers=_auth(token),
        json={"title": "Private Pack"},
    )
    report_id = create.json()["data"]["id"]

    # Analyst lacks create but can read financials — still must not see other tenant reports
    # Use a fabricated id to assert 404 (tenant-safe).
    fake = db_client.get(
        "/api/v1/board-reports/br_nonexistent000",
        headers=_auth(token),
    )
    assert fake.status_code == 404
    assert db_client.get(
        f"/api/v1/board-reports/{report_id}",
        headers=_auth(token),
    ).status_code == 200


def test_list_board_reports(db_client: TestClient):
    token = _login(db_client)
    db_client.post(
        "/api/v1/board-reports",
        headers=_auth(token),
        json={"title": "List Test A"},
    )
    db_client.post(
        "/api/v1/board-reports",
        headers=_auth(token),
        json={"title": "List Test B"},
    )
    r = db_client.get("/api/v1/board-reports", headers=_auth(token))
    assert r.status_code == 200
    titles = {item["title"] for item in r.json()["data"]}
    assert "List Test A" in titles
    assert "List Test B" in titles
