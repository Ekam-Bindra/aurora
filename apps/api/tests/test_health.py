"""Health, readiness, and request-id correlation."""

from __future__ import annotations


def test_health_ok(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"]


def test_ready_ok(client):
    resp = client.get("/api/v1/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


def test_request_id_header_present(client):
    resp = client.get("/api/v1/health")
    assert resp.headers.get("X-Request-Id", "").startswith("req_")


def test_inbound_request_id_is_echoed(client):
    resp = client.get("/api/v1/health", headers={"X-Request-Id": "req_test_123"})
    assert resp.headers["X-Request-Id"] == "req_test_123"


def test_root_redirects_to_docs(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"] == "/api/v1/docs"
