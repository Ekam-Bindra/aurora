"""RBAC enforcement and multi-tenant isolation."""

from __future__ import annotations

from tests.conftest import auth_header


def test_admin_can_list_users(client):
    resp = client.get("/api/v1/workspaces/users", headers=auth_header(client, "admin@nimbus.test"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["pagination"]["total_items"] == 8  # the 8 seeded personas


def test_cfo_cannot_list_users(client):
    # CFO lacks manage:users -> 403.
    resp = client.get("/api/v1/workspaces/users", headers=auth_header(client, "cfo@nimbus.test"))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


def test_ops_manager_cannot_run_simulation_permission(client):
    # Sanity: Operations Manager is not granted run:simulation.
    perms = client.post(
        "/api/v1/auth/login",
        json={"email": "ops@nimbus.test", "password": "test-password-123"},
    ).json()["user"]["permissions"]
    assert "run:simulation" not in perms
    assert "read:operations" in perms


def test_users_list_is_tenant_scoped(client, second_tenant):
    other_company, other_user = second_tenant
    resp = client.get("/api/v1/workspaces/users", headers=auth_header(client, "admin@nimbus.test"))
    emails = {u["email"] for u in resp.json()["data"]}
    assert "admin@otherco.test" not in emails
    assert other_user.email not in emails


def test_repository_rejects_cross_tenant_user_access(client, store, second_tenant):
    other_company, other_user = second_tenant
    nimbus = store.get_company  # noqa: F841  (clarity)
    # The nimbus tenant id is the company whose slug is 'nimbus'.
    nimbus_id = next(c.id for c in store._companies.values() if c.slug == "nimbus")  # noqa: SLF001
    # Fetching the other tenant's user while scoped to nimbus must return nothing.
    assert store.get_user(nimbus_id, other_user.id) is None
    # But it is reachable within its own tenant.
    assert store.get_user(other_company.id, other_user.id) is not None
