"""Board report PDF export tests (real reportlab renderer)."""

from __future__ import annotations

import os
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from aurora.core.config import get_settings
from aurora.main import create_app
from aurora.services.board_pdf import render_pdf


@pytest.fixture()
def db_client(tmp_path):
    db_file = tmp_path / "board_pdf_test.db"
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


def test_pdf_export_full_report(db_client: TestClient):
    token = _login(db_client)
    create = db_client.post(
        "/api/v1/board-reports",
        headers=_auth(token),
        json={
            "title": "Q2 2026 Board Pack",
            "period_start": "2026-04-01",
            "period_end": "2026-06-30",
        },
    )
    assert create.status_code == 201
    report_id = create.json()["data"]["id"]

    gen = db_client.post(
        f"/api/v1/board-reports/{report_id}/generate",
        headers=_auth(token),
    )
    assert gen.status_code == 202

    export = db_client.get(
        f"/api/v1/board-reports/{report_id}/export?format=pdf",
        headers=_auth(token),
    )
    assert export.status_code == 200
    assert "application/pdf" in export.headers["content-type"]
    assert export.content.startswith(b"%PDF")

    reader = PdfReader(BytesIO(export.content))
    assert len(reader.pages) >= 2
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Q2 2026 Board Pack" in text
    assert "Financial Summary" in text
    assert "Risk Genome" in text
    assert "$" in text


def test_render_pdf_sparse_content_does_not_raise():
    report = {
        "title": "Sparse Pack",
        "content": {
            "title": None,
            "period_start": None,
            "period_end": None,
            "generated_at": "not-a-timestamp",
            "sections": [
                {"type": "financial_summary", "data": {}},
                {"type": "forecast"},
                {"type": "risk_genome", "data": {"highlights": None}},
                {"type": "scenario_comparison", "data": {"recommendations": [{}, "raw text"]}},
                {"type": "concentration", "data": {"customers": None}},
                {"type": "narrative", "data": {"note": "Section placeholder"}},
                {"type": "mystery_section", "data": "unstructured payload"},
                {"type": None, "data": None},
                "not-even-a-dict",
            ],
        },
    }
    pdf = render_pdf(report)
    assert pdf.startswith(b"%PDF")
    assert len(PdfReader(BytesIO(pdf)).pages) >= 2

    # Content missing entirely still yields a valid cover-only document.
    assert render_pdf({}).startswith(b"%PDF")
