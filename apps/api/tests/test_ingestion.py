"""Ingestion API tests (Phase 7)."""

from __future__ import annotations

import io
import os

import pytest
from fastapi.testclient import TestClient

from aurora.core.config import get_settings
from aurora.main import create_app


@pytest.fixture()
def db_client(tmp_path):
    db_file = tmp_path / "ingestion_test.db"
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


def test_ingestion_requires_permission(db_client: TestClient):
    token = _login(db_client, email="ceo@nimbus.test")
    r = db_client.get("/api/v1/data-sources", headers=_auth(token))
    assert r.status_code == 403


def test_list_data_sources(db_client: TestClient):
    token = _login(db_client)
    r = db_client.get("/api/v1/data-sources", headers=_auth(token))
    assert r.status_code == 200
    sources = r.json()["data"]
    assert len(sources) >= 2
    kinds = {s["kind"] for s in sources}
    assert "file" in kinds
    assert "accounting" in kinds


def test_register_connector_data_source(db_client: TestClient):
    token = _login(db_client)
    r = db_client.post(
        "/api/v1/data-sources",
        headers=_auth(token),
        json={
            "kind": "accounting",
            "name": "Demo Accounting CSV",
            "config": {"connector_type": "accounting_csv", "default_target": "invoices"},
        },
    )
    assert r.status_code == 201
    body = r.json()["data"]
    assert body["kind"] == "accounting"
    assert body["config"]["connector_type"] == "accounting_csv"


def test_upload_customers_csv(db_client: TestClient):
    token = _login(db_client)
    csv_content = (
        "name,segment,region,industry,status\n"
        "IngestCo Alpha,enterprise,NA,SaaS,active\n"
        "IngestCo Beta,mid-market,EU,Retail,active\n"
    )
    r = db_client.post(
        "/api/v1/ingestion/uploads",
        headers=_auth(token),
        data={"target": "customers"},
        files={"file": ("customers.csv", io.BytesIO(csv_content.encode()), "text/csv")},
    )
    assert r.status_code == 202
    job_id = r.json()["data"]["job_id"]
    assert r.json()["data"]["ws_channel"] == f"ingestion:{job_id}"

    job = db_client.get(f"/api/v1/ingestion/jobs/{job_id}", headers=_auth(token))
    assert job.status_code == 200
    data = job.json()["data"]
    assert data["status"] == "completed"
    assert data["rows_inserted"] == 2
    assert data["rows_rejected"] == 0
    assert data["lineage_ref"].startswith("upload:customers.csv#sha256:")


def test_upload_invoices_with_rejected_rows(db_client: TestClient):
    token = _login(db_client)
    # First seed a customer for a valid row
    db_client.post(
        "/api/v1/ingestion/uploads",
        headers=_auth(token),
        data={"target": "customers"},
        files={
            "file": (
                "cust.csv",
                io.BytesIO(b"name,segment,region,industry,status\nValidCust,enterprise,NA,SaaS,active\n"),
                "text/csv",
            )
        },
    )
    csv_content = (
        "invoice_number,customer_name,issue_date,due_date,total_cents,currency,status\n"
        "ING-1001,ValidCust,2026-05-01,2026-06-01,50000000,USD,issued\n"
        "ING-1002,MissingCustomer,2026-05-01,2026-06-01,10000000,USD,issued\n"
    )
    r = db_client.post(
        "/api/v1/ingestion/uploads",
        headers=_auth(token),
        data={"target": "invoices"},
        files={"file": ("invoices.csv", io.BytesIO(csv_content.encode()), "text/csv")},
    )
    assert r.status_code == 202
    job_id = r.json()["data"]["job_id"]
    data = db_client.get(f"/api/v1/ingestion/jobs/{job_id}", headers=_auth(token)).json()["data"]
    assert data["status"] == "completed"
    assert data["rows_inserted"] == 1
    assert data["rows_rejected"] == 1
    assert any("MissingCustomer" in e["issue"] for e in data["errors"])


def test_upload_idempotent_resync(db_client: TestClient):
    token = _login(db_client)
    csv_content = (
        "name,segment,region,industry,status\n"
        "IdemCo,enterprise,NA,SaaS,active\n"
    )
    for _ in range(2):
        r = db_client.post(
            "/api/v1/ingestion/uploads",
            headers=_auth(token),
            data={"target": "customers"},
            files={"file": ("idem.csv", io.BytesIO(csv_content.encode()), "text/csv")},
        )
        assert r.status_code == 202
        job_id = r.json()["data"]["job_id"]
        job_resp = db_client.get(f"/api/v1/ingestion/jobs/{job_id}", headers=_auth(token))
        data = job_resp.json()["data"]
        assert data["status"] == "completed"

    second = db_client.get(f"/api/v1/ingestion/jobs/{job_id}", headers=_auth(token)).json()["data"]
    assert second["rows_inserted"] == 0
    assert second["rows_updated"] == 1


def test_connector_sync(db_client: TestClient):
    token = _login(db_client)
    reg = db_client.post(
        "/api/v1/data-sources",
        headers=_auth(token),
        json={
            "kind": "accounting",
            "name": "Accounting CSV Sync",
            "config": {"connector_type": "accounting_csv", "default_target": "customers"},
        },
    ).json()["data"]
    source_id = reg["id"]

    sync = db_client.post(
        f"/api/v1/ingestion/{source_id}/sync",
        headers=_auth(token),
    )
    assert sync.status_code == 202
    job_id = sync.json()["data"]["job_id"]
    job = db_client.get(f"/api/v1/ingestion/jobs/{job_id}", headers=_auth(token)).json()["data"]
    assert job["status"] == "completed"
    assert job["rows_inserted"] >= 1
    assert "connector:accounting_csv" in job["lineage_ref"]


def test_connector_sync_invoices_with_known_customer(db_client: TestClient):
    token = _login(db_client)
    # Continental Motors exists in Nimbus seed
    reg = db_client.post(
        "/api/v1/data-sources",
        headers=_auth(token),
        json={
            "kind": "accounting",
            "name": "Accounting Invoice Sync",
            "config": {"connector_type": "accounting_csv"},
        },
    ).json()["data"]

    sync = db_client.post(
        f"/api/v1/ingestion/{reg['id']}/sync?target=invoices",
        headers=_auth(token),
    )
    assert sync.status_code == 202
    job = db_client.get(
        f"/api/v1/ingestion/jobs/{sync.json()['data']['job_id']}",
        headers=_auth(token),
    ).json()["data"]
    assert job["status"] == "completed"
    assert job["rows_inserted"] + job["rows_updated"] >= 1


def test_list_ingestion_jobs(db_client: TestClient):
    token = _login(db_client)
    db_client.post(
        "/api/v1/ingestion/uploads",
        headers=_auth(token),
        data={"target": "customers"},
        files={
            "file": (
                "one.csv",
                io.BytesIO(b"name,segment,region,industry,status\nJobListCo,,,,\n"),
                "text/csv",
            )
        },
    )
    r = db_client.get("/api/v1/ingestion/jobs", headers=_auth(token))
    assert r.status_code == 200
    assert len(r.json()["data"]) >= 1


def test_job_not_found_and_rbac(db_client: TestClient):
    cfo = _login(db_client)
    r = db_client.get("/api/v1/ingestion/jobs/job_nonexistent", headers=_auth(cfo))
    assert r.status_code == 404

    ceo = _login(db_client, email="ceo@nimbus.test")
    r2 = db_client.get("/api/v1/ingestion/jobs", headers=_auth(ceo))
    assert r2.status_code == 403


def test_post_ingestion_refresh_hooks(db_client: TestClient, monkeypatch):
    """Upload triggers mart + graph refresh hooks."""
    calls = {"mart": 0, "graph": 0}

    import aurora.services.ingestion as ingestion_mod

    original_mart = ingestion_mod.refresh_mart
    original_graph = ingestion_mod.refresh_graph

    def _mart(session, company_id):
        calls["mart"] += 1
        return original_mart(session, company_id)

    def _graph(session, company_id):
        calls["graph"] += 1
        return original_graph(session, company_id)

    monkeypatch.setattr(ingestion_mod, "refresh_mart", _mart)
    monkeypatch.setattr(ingestion_mod, "refresh_graph", _graph)

    token = _login(db_client)
    db_client.post(
        "/api/v1/ingestion/uploads",
        headers=_auth(token),
        data={"target": "customers"},
        files={
            "file": (
                "hook.csv",
                io.BytesIO(b"name,segment,region,industry,status\nHookCo,,,,\n"),
                "text/csv",
            )
        },
    )
    assert calls["mart"] >= 1
    assert calls["graph"] >= 1
