"""Cross-instance persistence for board reports, ingestion jobs, and simulations.

ECS runs more than one API task behind the ALB, so an artifact created by one
process must be visible from another. These tests boot the app twice against
the same SQLite file — instance A creates, instance B (a fresh process-worth
of state, seeding disabled) must read — which the pre-0002 in-memory dict
stores fail by construction.
"""

from __future__ import annotations

import os
from typing import Iterator, Tuple

import pytest
from fastapi.testclient import TestClient

from aurora.core.config import get_settings
from aurora.core.security import create_token
from aurora.main import create_app

CSV_CONTENT = b"name,industry,region\nAcme Retail,Retail,NA\nZenith Goods,Wholesale,EU\n"


def _make_client(db_url: str, *, seed: bool) -> TestClient:
    os.environ["DATABASE_URL"] = db_url
    os.environ["DEMO_SEED_SCALE"] = "0.05"
    os.environ["SEED_DEMO_ON_STARTUP"] = "true" if seed else "false"
    get_settings.cache_clear()
    return TestClient(create_app())


@pytest.fixture()
def db_url(tmp_path) -> Iterator[str]:
    yield f"sqlite:///{tmp_path / 'store_persistence.db'}"
    get_settings.cache_clear()
    for var in ("DATABASE_URL", "DEMO_SEED_SCALE", "SEED_DEMO_ON_STARTUP"):
        os.environ.pop(var, None)


def _login(client: TestClient) -> str:
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "cfo@nimbus.test", "password": "aurora-demo-2026"},
    )
    assert r.status_code == 200
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_artifacts(client: TestClient, token: str) -> Tuple[str, str, str, str]:
    """Create one board report, one ingestion job, and one scenario + run."""
    r = client.post(
        "/api/v1/board-reports",
        json={"title": "Q2 Board Pack"},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    report_id = r.json()["data"]["id"]

    r = client.post(
        "/api/v1/ingestion/uploads",
        files={"file": ("customers.csv", CSV_CONTENT, "text/csv")},
        data={"target": "customers"},
        headers=_auth(token),
    )
    assert r.status_code == 202, r.text
    job_id = r.json()["data"]["job_id"]

    r = client.post(
        "/api/v1/scenarios",
        json={
            "name": "Persistence smoke",
            "horizon_periods": 6,
            "trials": 500,
            "assumptions": {
                "shocks": [{"type": "revenue_shock", "pct_change": -0.05}],
                "distributions": {},
            },
        },
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    scenario_id = r.json()["data"]["id"]

    r = client.post(f"/api/v1/scenarios/{scenario_id}/run", headers=_auth(token))
    assert r.status_code == 202, r.text
    simulation_id = r.json()["data"]["simulation_id"]

    return report_id, job_id, scenario_id, simulation_id


def test_artifacts_survive_process_restart(db_url):
    with _make_client(db_url, seed=True) as client_a:
        token = _login(client_a)
        report_id, job_id, scenario_id, simulation_id = _create_artifacts(client_a, token)

    # Instance B: same database, fresh process state, no re-seed (a re-seed
    # wipes and recreates the tenant, which is not what a second ECS task does).
    with _make_client(db_url, seed=False) as client_b:
        token = _login(client_b)

        r = client_b.get(f"/api/v1/board-reports/{report_id}", headers=_auth(token))
        assert r.status_code == 200, r.text
        assert r.json()["data"]["title"] == "Q2 Board Pack"

        r = client_b.get(f"/api/v1/ingestion/jobs/{job_id}", headers=_auth(token))
        assert r.status_code == 200, r.text
        assert r.json()["data"]["status"] == "completed"
        assert r.json()["data"]["rows_inserted"] == 2

        r = client_b.get(f"/api/v1/scenarios/{scenario_id}", headers=_auth(token))
        assert r.status_code == 200, r.text
        assert r.json()["data"]["latest_simulation_id"] == simulation_id

        r = client_b.get(f"/api/v1/simulations/{simulation_id}", headers=_auth(token))
        assert r.status_code == 200, r.text
        body = r.json()["data"]
        assert body["status"] == "completed"
        assert {blk["metric"] for blk in body["results"]}
        assert body["seed"] == 42

        r = client_b.get(
            f"/api/v1/explain/simulation/{simulation_id}", headers=_auth(token)
        )
        assert r.status_code == 200, r.text


def test_generate_and_approve_report_across_instances(db_url):
    with _make_client(db_url, seed=True) as client_a:
        token = _login(client_a)
        r = client_a.post(
            "/api/v1/board-reports",
            json={"title": "Lifecycle Pack", "sections": ["financial_summary"]},
            headers=_auth(token),
        )
        assert r.status_code == 201, r.text
        report_id = r.json()["data"]["id"]
        r = client_a.post(
            f"/api/v1/board-reports/{report_id}/generate", headers=_auth(token)
        )
        assert r.status_code == 202, r.text

    with _make_client(db_url, seed=False) as client_b:
        token = _login(client_b)
        r = client_b.post(
            f"/api/v1/board-reports/{report_id}/approve", headers=_auth(token)
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["status"] == "approved"

        r = client_b.get(
            f"/api/v1/board-reports/{report_id}/export?format=html", headers=_auth(token)
        )
        assert r.status_code == 200
        assert b"Lifecycle Pack" in r.content


def test_failed_upload_job_is_persisted(db_url):
    with _make_client(db_url, seed=True) as client_a:
        token = _login(client_a)
        # .xlsx extension with non-xlsx bytes forces a parse failure -> failed job.
        r = client_a.post(
            "/api/v1/ingestion/uploads",
            files={"file": ("broken.xlsx", b"not really a workbook", "application/octet-stream")},
            data={"target": "customers"},
            headers=_auth(token),
        )
        assert r.status_code == 202, r.text
        job_id = r.json()["data"]["job_id"]

    with _make_client(db_url, seed=False) as client_b:
        token = _login(client_b)
        r = client_b.get(f"/api/v1/ingestion/jobs/{job_id}", headers=_auth(token))
        assert r.status_code == 200, r.text
        assert r.json()["data"]["status"] == "failed"
        assert r.json()["data"]["errors"]


def test_agent_chat_history_survives_process_restart(db_url):
    with _make_client(db_url, seed=True) as client_a:
        token = _login(client_a)
        r = client_a.post(
            "/api/v1/agent/messages",
            json={"message": "What is our cash runway?"},
            headers=_auth(token),
        )
        assert r.status_code == 200, r.text
        body = r.json()["data"]
        session_id = body["session_id"]
        assert body["answer"]

        r = client_a.post(
            "/api/v1/agent/messages",
            json={"message": "And our top risks?", "session_id": session_id},
            headers=_auth(token),
        )
        assert r.status_code == 200, r.text

    with _make_client(db_url, seed=False) as client_b:
        token = _login(client_b)

        r = client_b.get("/api/v1/agent/sessions", headers=_auth(token))
        assert r.status_code == 200, r.text
        sessions = r.json()["data"]
        assert any(
            s["id"] == session_id and s["message_count"] == 2 for s in sessions
        ), sessions

        r = client_b.get(f"/api/v1/agent/sessions/{session_id}", headers=_auth(token))
        assert r.status_code == 200, r.text
        messages = r.json()["data"]["messages"]
        assert [m["question"] for m in messages] == [
            "What is our cash runway?",
            "And our top risks?",
        ]
        assert all(m["answer"] for m in messages)
        assert all(m["provider"] == "mock" for m in messages)


def test_persisted_stores_are_tenant_scoped(db_url):
    with _make_client(db_url, seed=True) as client:
        token = _login(client)
        report_id, job_id, scenario_id, simulation_id = _create_artifacts(client, token)
        r = client.post(
            "/api/v1/agent/messages",
            json={"message": "runway?"},
            headers=_auth(token),
        )
        assert r.status_code == 200
        agent_session_id = r.json()["data"]["session_id"]

        settings = get_settings()
        intruder = create_token(
            subject="00000000-0000-4000-8000-000000000001",
            token_type="access",
            secret=settings.secret_key,
            ttl_seconds=300,
            claims={
                "tenant_id": "00000000-0000-4000-8000-000000000002",
                "email": "intruder@other.test",
                "roles": ["CFO"],
            },
        )
        for url in (
            f"/api/v1/board-reports/{report_id}",
            f"/api/v1/ingestion/jobs/{job_id}",
            f"/api/v1/scenarios/{scenario_id}",
            f"/api/v1/simulations/{simulation_id}",
            f"/api/v1/agent/sessions/{agent_session_id}",
        ):
            r = client.get(url, headers=_auth(intruder))
            assert r.status_code == 404, f"{url} leaked across tenants: {r.status_code}"
