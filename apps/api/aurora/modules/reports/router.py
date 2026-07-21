"""Board report API routes (Phase 8)."""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.errors import NotFound, Unprocessable, ValidationError
from ...core.logging import get_request_id
from ...core.rbac import AuthContext, Permission
from ...core.schemas import Envelope
from ...deps import get_db_session, require_any_permission, require_permission
from ...services.audit import record_audit
from ...services.board_reports import (
    approve_report,
    create_report,
    export_report,
    generate_report,
    get_report,
    list_reports,
)
from .schemas import BoardReportOut, BoardReportRef

router = APIRouter(prefix="/board-reports", tags=["board-reports"])


def _require_db(session: Optional[Session] = Depends(get_db_session)) -> Session:
    if session is None:
        raise Unprocessable(
            "Board reports require DATABASE_URL (SQLite or Postgres). "
            "Set DATABASE_URL and restart, or use ./scripts/local-run.sh."
        )
    return session


class BoardReportCreate(BaseModel):
    title: str
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    sections: List[str] = Field(default_factory=list)
    # Advisory client-side preset name; sections above are what the server uses.
    # Declared so the schema matches what the web client actually sends.
    template: Optional[str] = None


@router.post("", status_code=status.HTTP_201_CREATED, response_model=Envelope[BoardReportRef])
def post_board_report(
    body: BoardReportCreate,
    context: AuthContext = Depends(require_permission(Permission.CREATE_BOARD_REPORT)),
    session: Session = Depends(_require_db),
) -> dict:
    try:
        data = create_report(
            context.tenant_id,
            title=body.title,
            period_start=body.period_start,
            period_end=body.period_end,
            sections=body.sections or None,
            created_by=context.user_id,
            session=session,
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    record_audit(
        session,
        context.tenant_id,
        user_id=context.user_id,
        action="board_report.create",
        resource_type="board_report",
        resource_id=data["id"],
        after={"title": body.title},
    )
    return {
        "data": {"id": data["id"], "status": data["status"]},
        "meta": {"request_id": get_request_id()},
    }


@router.get("", response_model=Envelope[List[BoardReportOut]])
def get_board_reports(
    context: AuthContext = Depends(require_permission(Permission.READ_FINANCIALS)),
    session: Optional[Session] = Depends(get_db_session),
) -> dict:
    items = list_reports(context.tenant_id, session=session)
    return {"data": items, "meta": {"request_id": get_request_id()}}


@router.get("/{report_id}", response_model=Envelope[BoardReportOut])
def get_board_report(
    report_id: str,
    context: AuthContext = Depends(require_permission(Permission.READ_FINANCIALS)),
    session: Optional[Session] = Depends(get_db_session),
) -> dict:
    data = get_report(report_id, session=session, company_id=context.tenant_id)
    if data is None or data.get("company_id") != context.tenant_id:
        raise NotFound("Board report not found")
    return {"data": data, "meta": {"request_id": get_request_id()}}


@router.post(
    "/{report_id}/generate",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=Envelope[BoardReportRef],
)
def post_generate_board_report(
    report_id: str,
    context: AuthContext = Depends(require_permission(Permission.CREATE_BOARD_REPORT)),
    session: Session = Depends(_require_db),
) -> dict:
    report = get_report(report_id, session=session, company_id=context.tenant_id)
    if report is None or report.get("company_id") != context.tenant_id:
        raise NotFound("Board report not found")
    try:
        data = generate_report(session, context.tenant_id, report_id)
    except KeyError as exc:
        raise NotFound("Board report not found") from exc
    record_audit(
        session,
        context.tenant_id,
        user_id=context.user_id,
        action="board_report.generate",
        resource_type="board_report",
        resource_id=report_id,
    )
    return {
        "data": {
            "id": data["id"],
            "status": data["status"],
            "ws_channel": data.get("ws_channel"),
        },
        "meta": {"request_id": get_request_id()},
    }


@router.post("/{report_id}/approve", response_model=Envelope[BoardReportRef])
def post_approve_board_report(
    report_id: str,
    context: AuthContext = Depends(require_permission(Permission.APPROVE_BOARD_REPORT)),
    session: Optional[Session] = Depends(get_db_session),
) -> dict:
    report = get_report(report_id, session=session, company_id=context.tenant_id)
    if report is None or report.get("company_id") != context.tenant_id:
        raise NotFound("Board report not found")
    try:
        data = approve_report(context.tenant_id, report_id, context.user_id, session=session)
    except KeyError as exc:
        raise NotFound("Board report not found") from exc
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    record_audit(
        session,
        context.tenant_id,
        user_id=context.user_id,
        action="board_report.approve",
        resource_type="board_report",
        resource_id=report_id,
        after={"status": data["status"]},
    )
    return {
        "data": {"id": data["id"], "status": data["status"], "approved_by": data["approved_by"]},
        "meta": {"request_id": get_request_id()},
    }


@router.get("/{report_id}/export")
def get_board_report_export(
    report_id: str,
    format: str = Query("html", alias="format"),
    context: AuthContext = Depends(require_any_permission(
        Permission.READ_FINANCIALS, Permission.CREATE_BOARD_REPORT
    )),
    session: Optional[Session] = Depends(get_db_session),
) -> Response:
    report = get_report(report_id, session=session, company_id=context.tenant_id)
    if report is None or report.get("company_id") != context.tenant_id:
        raise NotFound("Board report not found")
    exported = export_report(report_id, fmt=format, session=session, company_id=context.tenant_id)
    if exported is None:
        raise NotFound("Report content not generated yet")
    body, media_type, filename = exported
    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
