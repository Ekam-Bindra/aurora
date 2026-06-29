"""Board report generator — assembles KPIs, forecast, risk, and scenario data."""

from __future__ import annotations

import html
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from .financial import metrics_overview
from .forecast import create_forecast
from .risk import compute_genome
from .simulation import create_scenario, run_scenario

DEFAULT_SECTIONS = [
    "financial_summary",
    "forecast",
    "risk_genome",
    "scenario_comparison",
]

VALID_SECTIONS = frozenset(
    DEFAULT_SECTIONS + ["key_decisions", "concentration", "narrative"]
)

_reports: Dict[str, Dict[str, Any]] = {}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _report_id() -> str:
    return f"br_{uuid.uuid4().hex[:12]}"


def create_report(
    company_id: str,
    *,
    title: str,
    period_start: Optional[date],
    period_end: Optional[date],
    sections: Optional[List[str]],
    created_by: Optional[str],
) -> Dict[str, Any]:
    chosen = sections or list(DEFAULT_SECTIONS)
    unknown = [s for s in chosen if s not in VALID_SECTIONS]
    if unknown:
        raise ValueError(f"unknown sections: {', '.join(unknown)}")

    rid = _report_id()
    payload = {
        "id": rid,
        "company_id": company_id,
        "title": title,
        "period_start": period_start.isoformat() if period_start else None,
        "period_end": period_end.isoformat() if period_end else None,
        "sections": chosen,
        "status": "draft",
        "content": None,
        "export_url": None,
        "created_by": created_by,
        "approved_by": None,
        "created_at": _utcnow(),
        "updated_at": _utcnow(),
        "ws_channel": f"report:{rid}",
    }
    _reports[rid] = payload
    return payload


def get_report(report_id: str) -> Optional[Dict[str, Any]]:
    return _reports.get(report_id)


def list_reports(company_id: str) -> List[Dict[str, Any]]:
    items = [r for r in _reports.values() if r.get("company_id") == company_id]
    return sorted(items, key=lambda r: r.get("created_at", ""), reverse=True)


def _build_section_content(
    session: Session,
    company_id: str,
    section: str,
) -> Dict[str, Any]:
    if section == "financial_summary":
        overview = metrics_overview(session, company_id)
        return {"type": section, "data": overview}

    if section == "forecast":
        fc = create_forecast(session, company_id, metric="revenue", horizon_periods=6)
        return {
            "type": section,
            "data": {
                "forecast_id": fc.get("id"),
                "metric": fc.get("metric"),
                "method": fc.get("method"),
                "horizon_periods": fc.get("horizon_periods"),
                "points": (fc.get("points") or [])[:6],
                "accuracy": fc.get("accuracy"),
            },
        }

    if section == "risk_genome":
        genome = compute_genome(session, company_id)
        highlights = sorted(
            genome.get("dimensions", []),
            key=lambda d: float(d.get("score", 0)),
            reverse=True,
        )[:3]
        return {
            "type": section,
            "data": {
                "overall_score": genome.get("overall_score"),
                "computed_at": genome.get("computed_at"),
                "highlights": highlights,
            },
        }

    if section in ("scenario_comparison", "key_decisions"):
        scenario = create_scenario(
            session,
            company_id,
            name="Board baseline stress",
            assumptions={
                "shocks": [{"type": "revenue_shock", "pct_change": -0.10}],
                "distributions": {},
            },
            horizon_periods=6,
            trials=2000,
        )
        sim = run_scenario(session, company_id, scenario["id"], seed=42)
        results = sim.get("results") or []
        runway_block = next((r for r in results if r.get("metric") == "cash_runway_months"), {})
        runway_summary = runway_block.get("summary") or {}
        revenue_block = next((r for r in results if r.get("metric") == "revenue"), {})
        revenue_summary = revenue_block.get("summary") or {}
        return {
            "type": "scenario_comparison",
            "data": {
                "scenario_id": scenario["id"],
                "simulation_id": sim.get("id"),
                "p50_revenue_cents": revenue_summary.get("p50"),
                "p10_revenue_cents": revenue_summary.get("p10"),
                "p90_revenue_cents": revenue_summary.get("p90"),
                "runway_p50_months": runway_summary.get("p50"),
                "risk_deltas": sim.get("risk_deltas"),
                "recommendations": (sim.get("recommendations") or [])[:3],
            },
        }

    if section == "concentration":
        from .financial import concentration

        return {"type": section, "data": concentration(session, company_id)}

    return {"type": section, "data": {"note": "Section placeholder"}}


def generate_report(session: Session, company_id: str, report_id: str) -> Dict[str, Any]:
    report = _reports.get(report_id)
    if report is None or report.get("company_id") != company_id:
        raise KeyError("Report not found")

    sections_out: List[Dict[str, Any]] = []
    for section in report.get("sections") or []:
        sections_out.append(_build_section_content(session, company_id, section))

    report["content"] = {
        "title": report["title"],
        "period_start": report.get("period_start"),
        "period_end": report.get("period_end"),
        "generated_at": _utcnow(),
        "sections": sections_out,
    }
    report["status"] = "in_review"
    report["updated_at"] = _utcnow()
    report["export_url"] = f"/api/v1/board-reports/{report_id}/export"
    return report


def approve_report(company_id: str, report_id: str, approved_by: str) -> Dict[str, Any]:
    report = _reports.get(report_id)
    if report is None or report.get("company_id") != company_id:
        raise KeyError("Report not found")
    if report.get("content") is None:
        raise ValueError("Report must be generated before approval")
    report["status"] = "approved"
    report["approved_by"] = approved_by
    report["updated_at"] = _utcnow()
    return report


def render_html(report: Dict[str, Any]) -> str:
    content = report.get("content") or {}
    title = html.escape(content.get("title") or report.get("title") or "Board Report")
    parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        f"<title>{title}</title>",
        "<style>body{font-family:system-ui,sans-serif;margin:2rem;color:#111}",
        "h1,h2{color:#0f172a}section{margin:1.5rem 0;padding:1rem;border:1px solid #e2e8f0;",
        "border-radius:8px}pre{background:#f8fafc;padding:1rem;overflow:auto}</style>",
        "</head><body>",
        f"<h1>{title}</h1>",
    ]
    period = content.get("period_start"), content.get("period_end")
    if any(period):
        parts.append(
            f"<p><strong>Period:</strong> {html.escape(str(period[0] or ''))}"
            f" — {html.escape(str(period[1] or ''))}</p>"
        )
    for section in content.get("sections") or []:
        stype = html.escape(str(section.get("type", "section")))
        parts.append(f"<section><h2>{stype.replace('_', ' ').title()}</h2>")
        parts.append(f"<pre>{html.escape(str(section.get('data')))}</pre></section>")
    parts.append("</body></html>")
    return "".join(parts)


def export_report(report_id: str, fmt: str = "html") -> Optional[tuple]:
    """Return (bytes, media_type, filename) for download."""
    report = _reports.get(report_id)
    if report is None or report.get("content") is None:
        return None
    safe_title = (report.get("title") or "board-report").replace(" ", "-")[:40]
    if fmt == "html":
        body = render_html(report).encode("utf-8")
        return body, "text/html", f"{safe_title}.html"
    if fmt == "json":
        import json

        body = json.dumps(report.get("content"), indent=2).encode("utf-8")
        return body, "application/json", f"{safe_title}.json"
    # Minimal PDF stub with real title (no external deps).
    title = report.get("title") or "Board Report"
    pdf = _minimal_pdf(title)
    return pdf, "application/pdf", f"{safe_title}.pdf"


def _minimal_pdf(title: str) -> bytes:
    """Single-page PDF stub carrying the report title (export placeholder)."""
    safe = title.replace("(", "[").replace(")", "]")[:80]
    stream = f"BT /F1 18 Tf 72 720 Td ({safe}) Tj ET"
    objects = [
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n",
        b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n",
        (
            b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj\n"
        ),
        f"4 0 obj<< /Length {len(stream)} >>stream\n{stream}\nendstream endobj\n".encode(),
        b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n",
    ]
    body = b"".join(objects)
    pdf = b"%PDF-1.4\n" + body
    xref_pos = len(pdf)
    xref = b"xref\n0 6\n0000000000 65535 f \n"
    # Simplified xref — use fixed widths for demo stub
    offsets = []
    pos = 9
    for obj in objects:
        offsets.append(pos)
        pos += len(obj)
    for off in offsets:
        xref += f"{off:010d} 00000 n \n".encode()
    trailer = (
        f"trailer<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF"
    ).encode()
    return pdf + xref + trailer
