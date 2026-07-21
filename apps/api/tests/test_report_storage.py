"""Board-pack S3 archival: best-effort write-through with presigned sharing."""

from __future__ import annotations

import os

import pytest

from aurora.core.config import get_settings
from aurora.services import report_storage

REPORT = {"id": "rep-1", "company_id": "co-1"}


class FakeS3:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.puts = []

    def put_object(self, **kwargs):
        if self.fail:
            raise RuntimeError("s3 down")
        self.puts.append(kwargs)

    def generate_presigned_url(self, op, Params=None, ExpiresIn=None):
        return f"https://signed.example/{Params['Key']}?ttl={ExpiresIn}"


@pytest.fixture()
def s3_env():
    os.environ["S3_BUCKET"] = "test-bucket"
    get_settings.cache_clear()
    yield
    os.environ.pop("S3_BUCKET", None)
    get_settings.cache_clear()


def test_archives_and_presigns(monkeypatch, s3_env):
    fake = FakeS3()
    monkeypatch.setattr(report_storage, "_s3_client", lambda: fake)

    url = report_storage.archive_export(
        REPORT, body=b"%PDF", media_type="application/pdf", filename="pack.pdf"
    )

    assert url == "https://signed.example/reports/co-1/rep-1/pack.pdf?ttl=3600"
    (put,) = fake.puts
    assert put["Bucket"] == "test-bucket"
    assert put["Key"] == "reports/co-1/rep-1/pack.pdf"
    assert put["Body"] == b"%PDF"
    assert put["ContentType"] == "application/pdf"


def test_noop_without_bucket(monkeypatch):
    get_settings.cache_clear()
    called = []
    monkeypatch.setattr(report_storage, "_s3_client", lambda: called.append(1))

    assert (
        report_storage.archive_export(
            REPORT, body=b"x", media_type="text/html", filename="pack.html"
        )
        is None
    )
    assert not called


def test_s3_failure_never_raises(monkeypatch, s3_env):
    monkeypatch.setattr(report_storage, "_s3_client", lambda: FakeS3(fail=True))

    assert (
        report_storage.archive_export(
            REPORT, body=b"x", media_type="text/html", filename="pack.html"
        )
        is None
    )


def test_export_route_sets_archive_header(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from aurora.main import create_app

    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'archive.db'}"
    os.environ["DEMO_SEED_SCALE"] = "0.05"
    os.environ["S3_BUCKET"] = "test-bucket"
    get_settings.cache_clear()
    monkeypatch.setattr(report_storage, "_s3_client", lambda: FakeS3())
    try:
        with TestClient(create_app()) as client:
            r = client.post(
                "/api/v1/auth/login",
                json={"email": "cfo@nimbus.test", "password": "aurora-demo-2026"},
            )
            headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
            report_id = client.post(
                "/api/v1/board-reports",
                json={"title": "Archive Pack", "sections": ["financial_summary"]},
                headers=headers,
            ).json()["data"]["id"]
            client.post(f"/api/v1/board-reports/{report_id}/generate", headers=headers)

            resp = client.get(
                f"/api/v1/board-reports/{report_id}/export?format=html", headers=headers
            )
            assert resp.status_code == 200
            assert resp.headers["X-Export-Archive-Url"].startswith(
                "https://signed.example/reports/"
            )
            assert report_id in resp.headers["X-Export-Archive-Url"]
    finally:
        for var in ("DATABASE_URL", "DEMO_SEED_SCALE", "S3_BUCKET"):
            os.environ.pop(var, None)
        get_settings.cache_clear()
