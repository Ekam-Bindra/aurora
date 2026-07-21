"""Data integration API routes (Phase 7 — ingestion + connectors)."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.errors import NotFound, Unprocessable, ValidationError
from ...core.logging import get_request_id
from ...core.rbac import AuthContext, Permission
from ...core.schemas import Envelope
from ...deps import get_db_session, require_permission
from ...services.audit import record_audit
from ...services.ingestion import (
    get_data_source,
    get_job,
    list_data_sources,
    list_jobs,
    process_connector_sync,
    process_upload,
    register_data_source,
)
from .schemas import DataSourceOut, IngestionJobOut, IngestionJobRef

router = APIRouter(tags=["ingestion"])


def _require_db(session: Optional[Session] = Depends(get_db_session)) -> Session:
    if session is None:
        raise Unprocessable(
            "Ingestion requires DATABASE_URL (SQLite or Postgres). "
            "Set DATABASE_URL and restart, or use ./scripts/local-run.sh."
        )
    return session


class DataSourceCreate(BaseModel):
    kind: str = Field(..., description="file | accounting | crm | hris | api")
    name: str
    config: Dict[str, Any] = Field(default_factory=dict)


@router.get("/data-sources", response_model=Envelope[List[DataSourceOut]])
def get_data_sources(
    context: AuthContext = Depends(require_permission(Permission.MANAGE_DATA_SOURCES)),
    session: Session = Depends(_require_db),
) -> dict:
    items = list_data_sources(session, context.tenant_id)
    return {"data": items, "meta": {"request_id": get_request_id()}}


@router.post(
    "/data-sources",
    status_code=status.HTTP_201_CREATED,
    response_model=Envelope[DataSourceOut],
)
def post_data_source(
    body: DataSourceCreate,
    context: AuthContext = Depends(require_permission(Permission.MANAGE_DATA_SOURCES)),
    session: Session = Depends(_require_db),
) -> dict:
    data = register_data_source(
        session,
        context.tenant_id,
        kind=body.kind,
        name=body.name,
        config=body.config,
    )
    record_audit(
        session,
        context.tenant_id,
        user_id=context.user_id,
        action="data_source.register",
        resource_type="data_source",
        resource_id=data.get("id"),
        after={"kind": body.kind, "name": body.name},
    )
    return {"data": data, "meta": {"request_id": get_request_id()}}


@router.post(
    "/ingestion/uploads",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=Envelope[IngestionJobRef],
)
async def post_ingestion_upload(
    file: UploadFile = File(...),
    target: str = Form(...),
    mapping: Optional[str] = Form(None),
    context: AuthContext = Depends(require_permission(Permission.MANAGE_DATA_SOURCES)),
    session: Session = Depends(_require_db),
) -> dict:
    content = await file.read()
    if not content:
        raise ValidationError("Uploaded file is empty")
    filename = file.filename or "upload.csv"
    parsed_mapping: Optional[Dict[str, str]] = None
    if mapping:
        try:
            parsed_mapping = json.loads(mapping)
        except json.JSONDecodeError as exc:
            raise ValidationError("mapping must be valid JSON") from exc
    try:
        job = process_upload(
            session,
            context.tenant_id,
            content=content,
            filename=filename,
            target=target,
            mapping=parsed_mapping,
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    record_audit(
        session,
        context.tenant_id,
        user_id=context.user_id,
        action="ingestion.upload",
        resource_type="ingestion_job",
        resource_id=job["job_id"],
        after={"target": target, "filename": filename, "status": job["status"]},
    )
    return {
        "data": {
            "job_id": job["job_id"],
            "status": job["status"],
            "target": job["target"],
            "ws_channel": job["ws_channel"],
        },
        "meta": {"request_id": get_request_id()},
    }


@router.post(
    "/ingestion/{source_id}/sync",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=Envelope[IngestionJobRef],
)
def post_ingestion_sync(
    source_id: str,
    target: Optional[str] = None,
    context: AuthContext = Depends(require_permission(Permission.MANAGE_DATA_SOURCES)),
    session: Session = Depends(_require_db),
) -> dict:
    ds = get_data_source(session, context.tenant_id, source_id)
    if ds is None:
        raise NotFound("Data source not found")
    try:
        job = process_connector_sync(session, context.tenant_id, source_id, target=target)
    except KeyError as exc:
        raise NotFound("Data source not found") from exc
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    record_audit(
        session,
        context.tenant_id,
        user_id=context.user_id,
        action="ingestion.sync",
        resource_type="ingestion_job",
        resource_id=job["job_id"],
        after={"source_id": source_id, "target": job["target"], "status": job["status"]},
    )
    return {
        "data": {
            "job_id": job["job_id"],
            "status": job["status"],
            "target": job["target"],
            "ws_channel": job["ws_channel"],
        },
        "meta": {"request_id": get_request_id()},
    }


@router.get("/ingestion/jobs/{job_id}", response_model=Envelope[IngestionJobOut])
def get_ingestion_job(
    job_id: str,
    context: AuthContext = Depends(require_permission(Permission.MANAGE_DATA_SOURCES)),
    session: Optional[Session] = Depends(get_db_session),
) -> dict:
    job = get_job(job_id, session=session, company_id=context.tenant_id)
    if job is None or job.get("company_id") != context.tenant_id:
        raise NotFound("Ingestion job not found")
    return {"data": job, "meta": {"request_id": get_request_id()}}


@router.get("/ingestion/jobs", response_model=Envelope[List[IngestionJobOut]])
def get_ingestion_jobs(
    context: AuthContext = Depends(require_permission(Permission.MANAGE_DATA_SOURCES)),
    session: Optional[Session] = Depends(get_db_session),
) -> dict:
    items = list_jobs(context.tenant_id, session=session)
    return {"data": items, "meta": {"request_id": get_request_id()}}
