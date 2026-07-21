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


def test_ready_reports_memory_store_without_database(client):
    resp = client.get("/api/v1/ready")
    assert resp.json()["checks"] == {"store": "memory"}


def test_ready_returns_503_when_database_unreachable(client, monkeypatch):
    """Degradation contract: DB down -> 503 -> ALB removes the task from rotation."""
    from contextlib import contextmanager

    from aurora.modules.health import router as health_router

    @contextmanager
    def _broken_session_scope():
        raise RuntimeError("connection refused")
        yield  # pragma: no cover

    monkeypatch.setattr(health_router, "is_database_enabled", lambda: True)
    monkeypatch.setattr(health_router, "session_scope", _broken_session_scope)

    resp = client.get("/api/v1/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["database"].startswith("error:")


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
