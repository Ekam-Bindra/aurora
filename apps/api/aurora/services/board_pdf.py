"""Board report PDF renderer — multi-page reportlab layout for exported packs.

Input is the report dict from ``board_reports`` (``content`` holds title,
period, generated_at and a list of {type, data} sections). Every accessor
tolerates missing/None fields so a sparse or partially generated report
still renders instead of crashing the export endpoint.
"""

from __future__ import annotations

from datetime import datetime
from html import escape
from io import BytesIO
from typing import Any, Callable, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_INK = colors.HexColor("#0f172a")
_MUTED = colors.HexColor("#475569")
_RULE = colors.HexColor("#cbd5e1")
_ROW_ALT = colors.HexColor("#f1f5f9")

_ACRONYMS = {"Mtd": "MTD", "Yoy": "YoY", "Hhi": "HHI", "Kpi": "KPI", "Arr": "ARR", "Id": "ID"}


def _label(key: Any) -> str:
    words = str(key or "").replace("_", " ").title().split()
    return " ".join(_ACRONYMS.get(w, w) for w in words) or "Section"


def _fmt_cents(value: Any) -> str:
    try:
        dollars = float(value) / 100.0
    except (TypeError, ValueError):
        return "—"
    sign = "-" if dollars < 0 else ""
    return f"{sign}${abs(dollars):,.2f}"


def _fmt_pct(value: Any, scale: float = 1.0, signed: bool = False) -> str:
    try:
        pct = float(value) * scale
    except (TypeError, ValueError):
        return "—"
    return f"{pct:+.1f}%" if signed else f"{pct:.1f}%"


def _fmt_num(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):,.1f}"
    except (TypeError, ValueError):
        return str(value)


def _styles() -> Dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "brand": ParagraphStyle(
            "brand", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=13, textColor=_INK, spaceAfter=2,
        ),
        "tagline": ParagraphStyle(
            "tagline", parent=base["Normal"], fontSize=9, textColor=_MUTED, spaceAfter=18,
        ),
        "cover_title": ParagraphStyle(
            "cover_title", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=26, leading=32, textColor=_INK, alignment=0, spaceAfter=10,
        ),
        "heading": ParagraphStyle(
            "heading", parent=base["Heading1"], fontName="Helvetica-Bold",
            fontSize=15, textColor=_INK, spaceBefore=0, spaceAfter=4,
        ),
        "sub": ParagraphStyle(
            "sub", parent=base["Normal"], fontSize=10, leading=14,
            textColor=_MUTED, spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], fontSize=9.5, leading=13, textColor=_INK,
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["Normal"], fontSize=9.5, leading=13,
            textColor=_INK, leftIndent=14, bulletIndent=4, spaceAfter=3,
        ),
    }


def _table(rows: List[List[Any]], col_widths: Optional[List[float]] = None) -> Table:
    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _INK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, _RULE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _ROW_ALT]),
    ])
    return Table(rows, colWidths=col_widths, hAlign="LEFT", repeatRows=1, style=style)


def _note(text: str, s: Dict[str, ParagraphStyle]) -> List[Any]:
    return [Paragraph(escape(text), s["sub"])]


def _kpi_value(name: str, kpi: Dict[str, Any]) -> str:
    if "value_cents" in kpi:
        return _fmt_cents(kpi.get("value_cents"))
    value = kpi.get("value")
    if "margin" in name:
        # Margins arrive as fractions (0-1); YoY deltas are already percent numbers.
        return _fmt_pct(value, scale=100.0)
    if "months" in name or "runway" in name:
        return f"{_fmt_num(value)} mo" if value is not None else "—"
    return _fmt_num(value)


def _render_financial_summary(data: Dict[str, Any], s: Dict[str, ParagraphStyle]) -> List[Any]:
    flow: List[Any] = []
    if data.get("as_of"):
        flow.append(Paragraph(f"As of {escape(str(data['as_of']))}", s["sub"]))
    kpis = data.get("kpis")
    if not isinstance(kpis, dict) or not kpis:
        return flow + _note("No KPI data available for this period.", s)
    rows: List[List[Any]] = [["KPI", "Value", "YoY Change"]]
    for name, kpi in kpis.items():
        kpi = kpi if isinstance(kpi, dict) else {"value": kpi}
        rows.append([
            _label(name),
            _kpi_value(str(name), kpi),
            _fmt_pct(kpi.get("delta_pct_yoy"), signed=True),
        ])
    flow.append(_table(rows, [2.6 * inch, 1.9 * inch, 1.4 * inch]))
    return flow


def _render_forecast(data: Dict[str, Any], s: Dict[str, ParagraphStyle]) -> List[Any]:
    flow: List[Any] = []
    meta = (
        f"Metric: {_label(data.get('metric') or 'revenue')} · "
        f"Method: {escape(str(data.get('method') or 'n/a'))} · "
        f"Horizon: {escape(str(data.get('horizon_periods') or '—'))} periods"
    )
    flow.append(Paragraph(meta, s["sub"]))
    accuracy = data.get("accuracy")
    if isinstance(accuracy, dict):
        flow.append(Paragraph(
            f"Backtest accuracy — MAPE {_fmt_pct(accuracy.get('mape'), scale=100.0)} · "
            f"windows: {accuracy.get('backtest_windows', '—')} · "
            f"80% interval coverage: {_fmt_pct(accuracy.get('interval_coverage'), scale=100.0)}",
            s["sub"],
        ))
    points = data.get("points")
    if not isinstance(points, list) or not points:
        return flow + _note("No forecast points available.", s)
    rows: List[List[Any]] = [["Period", "Forecast", "Lower Bound", "Upper Bound"]]
    for point in points:
        point = point if isinstance(point, dict) else {}
        rows.append([
            str(point.get("period") or "—"),
            _fmt_cents(point.get("yhat_cents")),
            _fmt_cents(point.get("lower_cents")),
            _fmt_cents(point.get("upper_cents")),
        ])
    flow.append(_table(rows, [1.4 * inch, 1.7 * inch, 1.7 * inch, 1.7 * inch]))
    return flow


def _render_risk_genome(data: Dict[str, Any], s: Dict[str, ParagraphStyle]) -> List[Any]:
    flow: List[Any] = []
    overall = data.get("overall_score")
    if overall is not None:
        flow.append(Paragraph(f"Overall risk score: <b>{_fmt_num(overall)}</b> / 100", s["body"]))
    if data.get("computed_at"):
        flow.append(Paragraph(f"Computed {escape(str(data['computed_at']))}", s["sub"]))
    flow.append(Spacer(1, 4))
    highlights = data.get("highlights")
    if not isinstance(highlights, list) or not highlights:
        return flow + _note("No risk highlights available.", s)
    rows: List[List[Any]] = [["Dimension", "Score", "Severity"]]
    for item in highlights:
        item = item if isinstance(item, dict) else {}
        rows.append([
            _label(item.get("dimension") or "unknown"),
            _fmt_num(item.get("score")),
            _label(item.get("severity") or "—"),
        ])
    flow.append(_table(rows, [2.8 * inch, 1.4 * inch, 1.7 * inch]))
    return flow


def _render_scenario_comparison(data: Dict[str, Any], s: Dict[str, ParagraphStyle]) -> List[Any]:
    flow: List[Any] = [
        _table(
            [
                ["Metric", "P10", "P50", "P90"],
                [
                    "Revenue (simulated)",
                    _fmt_cents(data.get("p10_revenue_cents")),
                    _fmt_cents(data.get("p50_revenue_cents")),
                    _fmt_cents(data.get("p90_revenue_cents")),
                ],
            ],
            [2.2 * inch, 1.6 * inch, 1.6 * inch, 1.6 * inch],
        ),
        Spacer(1, 8),
    ]
    runway = data.get("runway_p50_months")
    if runway is not None:
        flow.append(Paragraph(
            f"Median cash runway under scenario: <b>{_fmt_num(runway)} months</b>", s["body"]
        ))
    deltas = data.get("risk_deltas")
    if isinstance(deltas, dict) and deltas:
        rendered = " · ".join(
            f"{_label(k)}: {_fmt_num(v)}" for k, v in deltas.items()
        )
        flow.append(Paragraph(f"Risk deltas — {rendered}", s["sub"]))
    recommendations = data.get("recommendations")
    if isinstance(recommendations, list) and recommendations:
        flow.append(Spacer(1, 6))
        flow.append(Paragraph("Top recommendations", s["body"]))
        for rec in recommendations:
            if isinstance(rec, dict):
                text = escape(str(rec.get("title") or "Recommendation"))
                if rec.get("priority") is not None:
                    text += f" (priority {escape(str(rec['priority']))})"
                impact = rec.get("expected_impact")
                if isinstance(impact, dict) and impact.get("magnitude"):
                    text += f" — expected impact {escape(str(impact['magnitude']))}"
            else:
                text = escape(str(rec))
            flow.append(Paragraph(text, s["bullet"], bulletText="•"))
    return flow


def _render_concentration(data: Dict[str, Any], s: Dict[str, ParagraphStyle]) -> List[Any]:
    flow: List[Any] = []
    for group in ("customers", "vendors"):
        block = data.get(group)
        if not isinstance(block, dict):
            continue
        flow.append(Paragraph(_label(group), s["body"]))
        flow.append(Paragraph(
            f"Top-5 share: {_fmt_pct(block.get('top_5_share'), scale=100.0)} · "
            f"HHI (normalized): {_fmt_num(block.get('hhi_normalized'))}",
            s["sub"],
        ))
        top = block.get("top")
        if isinstance(top, list) and top:
            rows: List[List[Any]] = [["Name", "Amount", "Share"]]
            for entry in top:
                entry = entry if isinstance(entry, dict) else {}
                rows.append([
                    str(entry.get("name") or "—"),
                    _fmt_cents(entry.get("amount_cents")),
                    _fmt_pct(entry.get("share"), scale=100.0),
                ])
            flow.append(_table(rows, [3.2 * inch, 1.8 * inch, 1.2 * inch]))
        flow.append(Spacer(1, 10))
    return flow or _note("No concentration data available.", s)


def _render_generic(data: Any, s: Dict[str, ParagraphStyle]) -> List[Any]:
    if isinstance(data, dict) and data:
        if set(data) == {"note"}:
            return _note(str(data["note"]), s)
        rows: List[List[Any]] = [["Field", "Value"]]
        for key, value in data.items():
            text = str(value)
            if len(text) > 160:
                text = text[:157] + "…"
            rows.append([_label(key), Paragraph(escape(text), s["body"])])
        return [_table(rows, [2.0 * inch, 4.4 * inch])]
    if data:
        return [Paragraph(escape(str(data)), s["body"])]
    return _note("No data available for this section.", s)


_SECTION_RENDERERS: Dict[str, Callable[[Dict[str, Any], Dict[str, ParagraphStyle]], List[Any]]] = {
    "financial_summary": _render_financial_summary,
    "forecast": _render_forecast,
    "risk_genome": _render_risk_genome,
    "scenario_comparison": _render_scenario_comparison,
    "concentration": _render_concentration,
}


def _fmt_generated_at(raw: Any) -> Optional[str]:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return parsed.strftime("%B %d, %Y at %H:%M UTC")
    except ValueError:
        return str(raw)


def _cover(content: Dict[str, Any], title: str, s: Dict[str, ParagraphStyle]) -> List[Any]:
    flow: List[Any] = [
        Spacer(1, 1.6 * inch),
        Paragraph("A U R O R A", s["brand"]),
        Paragraph("Enterprise Decision Intelligence", s["tagline"]),
        HRFlowable(width="100%", thickness=1, color=_RULE, spaceAfter=24),
        Paragraph(escape(title), s["cover_title"]),
    ]
    start, end = content.get("period_start"), content.get("period_end")
    if start or end:
        flow.append(Paragraph(
            f"Reporting period: {escape(str(start or '…'))} — {escape(str(end or '…'))}",
            s["sub"],
        ))
    generated = _fmt_generated_at(content.get("generated_at"))
    if generated:
        flow.append(Paragraph(f"Generated {escape(generated)}", s["sub"]))
    flow.append(Spacer(1, 0.4 * inch))
    flow.append(Paragraph("Prepared with AURORA board reporting. Confidential.", s["tagline"]))
    return flow


def _footer(canvas: Any, doc: Any) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(_MUTED)
    canvas.drawString(doc.leftMargin, 0.55 * inch, "AURORA — Confidential")
    page_no = f"Page {canvas.getPageNumber()}"
    canvas.drawRightString(letter[0] - doc.rightMargin, 0.55 * inch, page_no)
    canvas.restoreState()


def render_pdf(report: Dict[str, Any]) -> bytes:
    content = report.get("content") if isinstance(report.get("content"), dict) else {}
    title = str(content.get("title") or report.get("title") or "Board Report")
    s = _styles()

    story: List[Any] = _cover(content, title, s)
    sections = content.get("sections")
    for section in sections if isinstance(sections, list) else []:
        if not isinstance(section, dict):
            continue
        story.append(PageBreak())
        story.append(Paragraph(escape(_label(section.get("type"))), s["heading"]))
        story.append(HRFlowable(width="100%", thickness=0.8, color=_RULE, spaceAfter=10))
        renderer = _SECTION_RENDERERS.get(str(section.get("type")))
        data = section.get("data")
        if renderer is not None and isinstance(data, dict):
            story.extend(renderer(data, s))
        else:
            story.extend(_render_generic(data, s))

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.9 * inch,
        rightMargin=0.9 * inch,
        topMargin=0.9 * inch,
        bottomMargin=0.9 * inch,
        title=title,
        author="AURORA",
    )
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()
