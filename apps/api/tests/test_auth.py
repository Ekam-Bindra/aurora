"""Authentication flows: login, me, refresh, and the consistent error envelope."""

from __future__ import annotations

from tests.conftest import DEMO_PASSWORD, auth_header, login


def test_login_success_returns_tokens_and_user(client):
    resp = login(client, "cfo@nimbus.test")
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "cfo@nimbus.test"
    assert "CFO" in body["user"]["roles"]
    assert "read:financials" in body["user"]["permissions"]


def test_login_wrong_password_is_401_with_envelope(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "cfo@nimbus.test", "password": "wrong"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


def test_login_unknown_user_is_401(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@nimbus.test", "password": DEMO_PASSWORD},
    )
    assert resp.status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_returns_current_user(client):
    resp = client.get("/api/v1/auth/me", headers=auth_header(client, "ceo@nimbus.test"))
    assert resp.status_code == 200
    assert resp.json()["email"] == "ceo@nimbus.test"


def test_refresh_issues_new_access_token(client):
    refresh_token = login(client, "cfo@nimbus.test").json()["refresh_token"]
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_refresh_rejects_access_token(client):
    access = login(client, "cfo@nimbus.test").json()["access_token"]
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": access})
    assert resp.status_code == 401


def test_protected_workspace_endpoint(client):
    resp = client.get(
        "/api/v1/workspaces/current", headers=auth_header(client, "cfo@nimbus.test")
    )
    assert resp.status_code == 200
    assert resp.json()["slug"] == "nimbus"
