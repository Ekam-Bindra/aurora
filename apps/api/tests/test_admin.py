"""Admin console API tests (Phase 8)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from aurora.core.config import get_settings
from aurora.core.rbac import Role
from aurora.main import create_app


@pytest.fixture()
def db_client(tmp_path):
    db_file = tmp_path / "admin_test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"
    os.environ["DEMO_SEED_SCALE"] = "0.05"
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        yield client
    get_settings.cache_clear()
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("DEMO_SEED_SCALE", None)


def _login(client: TestClient, email: str = "admin@nimbus.test") -> str:
    r = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "aurora-demo-2026"},
    )
    assert r.status_code == 200
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_admin_users_requires_permission(db_client: TestClient):
    token = _login(db_client, email="cfo@nimbus.test")
    r = db_client.get("/api/v1/users", headers=_auth(token))
    assert r.status_code == 403


def test_list_users_and_roles(db_client: TestClient):
    token = _login(db_client)
    users = db_client.get("/api/v1/users", headers=_auth(token))
    assert users.status_code == 200
    assert users.json()["pagination"]["total_items"] >= 8

    roles = db_client.get("/api/v1/users", headers=_auth(token))
    assert roles.status_code == 200

    role_list = db_client.get("/api/v1/roles", headers=_auth(token))
    assert role_list.status_code == 200
    names = {r["name"] for r in role_list.json()["data"]}
    assert Role.CFO in names
    assert Role.ADMIN in names


def test_create_and_update_user(db_client: TestClient):
    token = _login(db_client)
    create = db_client.post(
        "/api/v1/users",
        headers=_auth(token),
        json={
            "email": "new.analyst@nimbus.test",
            "full_name": "New Analyst",
            "title": "Finance Analyst",
            "roles": [Role.ANALYST],
            "password": "secure-pass-123",
        },
    )
    assert create.status_code == 201
    user_id = create.json()["data"]["id"]
    assert create.json()["data"]["roles"] == [Role.ANALYST]

    patch = db_client.patch(
        f"/api/v1/users/{user_id}",
        headers=_auth(token),
        json={"title": "Senior Analyst", "is_active": True},
    )
    assert patch.status_code == 200
    assert patch.json()["data"]["title"] == "Senior Analyst"


def test_assign_and_remove_role(db_client: TestClient):
    token = _login(db_client)
    create = db_client.post(
        "/api/v1/users",
        headers=_auth(token),
        json={
            "email": "role.test@nimbus.test",
            "full_name": "Role Tester",
            "roles": [Role.ANALYST],
            "password": "secure-pass-123",
        },
    )
    user_id = create.json()["data"]["id"]

    roles = db_client.get("/api/v1/roles", headers=_auth(token)).json()["data"]
    cfo_role = next(r for r in roles if r["name"] == Role.CFO)

    assign = db_client.post(
        f"/api/v1/users/{user_id}/roles",
        headers=_auth(token),
        json={"role": Role.CFO},
    )
    assert assign.status_code == 201
    assert Role.CFO in assign.json()["data"]["roles"]

    remove = db_client.delete(
        f"/api/v1/users/{user_id}/roles/{cfo_role['id']}",
        headers=_auth(token),
    )
    assert remove.status_code == 200
    assert Role.CFO not in remove.json()["data"]["roles"]


def test_audit_logs(db_client: TestClient):
    admin_token = _login(db_client)
    cfo_token = _login(db_client, email="cfo@nimbus.test")

    denied = db_client.get("/api/v1/audit-logs", headers=_auth(cfo_token))
    # CFO has view:audit_log — should succeed
    assert denied.status_code == 200

    ops_token = _login(db_client, email="ops@nimbus.test")
    denied_ops = db_client.get("/api/v1/audit-logs", headers=_auth(ops_token))
    assert denied_ops.status_code == 403

    logs = db_client.get("/api/v1/audit-logs", headers=_auth(admin_token))
    assert logs.status_code == 200
    assert logs.json()["pagination"]["total_items"] >= 5
    actions = {e["action"] for e in logs.json()["data"]}
    assert "user.login" in actions or "forecast.run" in actions


def test_admin_memory_mode(client: TestClient):
    """Admin endpoints work without DATABASE_URL (in-memory demo tenant)."""
    from tests.conftest import auth_header

    resp = client.get("/api/v1/roles", headers=auth_header(client, "admin@nimbus.test"))
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 8

    audit = client.get("/api/v1/audit-logs", headers=auth_header(client, "admin@nimbus.test"))
    assert audit.status_code == 200
    assert audit.json()["pagination"]["total_items"] >= 5
