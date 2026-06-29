"""AI agent API tests."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from aurora.core.config import get_settings
from aurora.main import create_app


@pytest.fixture()
def db_client(tmp_path):
    db_file = tmp_path / "agent_test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"
    os.environ["DEMO_SEED_SCALE"] = "0.05"
    os.environ["AI_PROVIDER"] = "mock"
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        yield client
    get_settings.cache_clear()
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("DEMO_SEED_SCALE", None)
    os.environ.pop("AI_PROVIDER", None)


def _login(client: TestClient, email: str = "cfo@nimbus.test") -> str:
    r = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "aurora-demo-2026"},
    )
    assert r.status_code == 200
    return r.json()["access_token"]


def test_agent_mock_revenue_shock(db_client: TestClient):
    token = _login(db_client)
    r = db_client.post(
        "/api/v1/agent/messages",
        json={
            "message": (
                "What's our cash runway if revenue drops 15% next quarter, "
                "and what should we do?"
            ),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["provider"] == "mock"
    assert data["session_id"]
    assert data["interaction_id"]
    assert "runway" in data["answer"].lower()
    assert len(data["tools_used"]) >= 1
    assert any(t["tool"] == "run_simulation" for t in data["tools_used"])


def test_agent_cash_question(db_client: TestClient):
    token = _login(db_client)
    r = db_client.post(
        "/api/v1/agent/messages",
        json={"message": "What is our current cash runway?"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["provider"] == "mock"
    assert "runway" in r.json()["data"]["answer"].lower()


def test_agent_session_history(db_client: TestClient):
    token = _login(db_client)
    r1 = db_client.post(
        "/api/v1/agent/messages",
        json={"message": "Summarize liquidity risk"},
        headers={"Authorization": f"Bearer {token}"},
    )
    sid = r1.json()["data"]["session_id"]
    r2 = db_client.get(
        f"/api/v1/agent/sessions/{sid}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    assert len(r2.json()["data"]["messages"]) >= 1

    r3 = db_client.get(
        "/api/v1/agent/sessions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r3.status_code == 200
    assert len(r3.json()["data"]) >= 1


def test_agent_requires_permission(db_client: TestClient):
    token = _login(db_client, email="admin@nimbus.test")
    r = db_client.post(
        "/api/v1/agent/messages",
        json={"message": "Hello"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
