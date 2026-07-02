"""Ingestion orchestration: file uploads, connector sync, lineage, post-ingestion hooks.

Job status is dual-mode: with a session, jobs persist to the ``ingestion_job``
table with their final state (visible to every API instance — ECS runs more
than one task, and a status poll may hit a different task than the upload);
without one they fall back to the per-process dict used by in-memory tests.
"""

from __future__ import annotations

import csv
import hashlib
import io
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from aurora_db.models.commercial import Customer, Vendor
from aurora_db.models.financial import Expense, Invoice
from aurora_db.models.identity import DataSource
from aurora_db.models.intelligence import IngestionJob
from aurora_db.types import new_uuid
from aurora_ml.marts import refresh_mart
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..connectors import ConnectorResult, get_connector
from ..services.graph import refresh_graph

SUPPORTED_TARGETS = frozenset({"customers", "vendors", "invoices", "expenses"})

_jobs: Dict[str, Dict[str, Any]] = {}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _job_id() -> str:
    return f"job_{uuid.uuid4().hex[:12]}"


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


def _job_row_to_dict(row: IngestionJob) -> Dict[str, Any]:
    return {
        "job_id": str(row.id),
        "company_id": str(row.company_id),
        "target": row.target,
        "source_id": str(row.source_id) if row.source_id else None,
        "filename": row.filename,
        "status": row.status,
        "rows_total": row.rows_total,
        "rows_inserted": row.rows_inserted,
        "rows_updated": row.rows_updated,
        "rows_rejected": row.rows_rejected,
        "errors": list(row.errors or []),
        "lineage_ref": row.lineage_ref,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "ws_channel": f"ingestion:{row.id}",
    }


def _persist_job(session: Session, job: Dict[str, Any]) -> None:
    """Write the job's final state. Called after the pipeline so a failed run can
    roll back partial data inserts and still record the failed job."""
    if job.get("status") == "failed":
        session.rollback()
    session.add(
        IngestionJob(
            id=job["job_id"],
            company_id=job["company_id"],
            target=job["target"],
            source_id=job.get("source_id"),
            filename=job.get("filename"),
            status=job["status"],
            rows_total=job.get("rows_total", 0),
            rows_inserted=job.get("rows_inserted", 0),
            rows_updated=job.get("rows_updated", 0),
            rows_rejected=job.get("rows_rejected", 0),
            errors=job.get("errors", []),
            lineage_ref=job.get("lineage_ref"),
            started_at=_parse_iso(job.get("started_at")),
            finished_at=_parse_iso(job.get("finished_at")),
        )
    )
    session.flush()


def _parse_date(value: Any) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"invalid date '{value}'")


def _parse_int(value: Any, field: str) -> int:
    if value is None or value == "":
        raise ValueError(f"missing {field}")
    try:
        if isinstance(value, float):
            return int(value)
        if isinstance(value, Decimal):
            return int(value)
        text = str(value).strip().replace(",", "").replace("$", "")
        if "." in text:
            return int(float(text))
        return int(text)
    except (ValueError, InvalidOperation) as exc:
        raise ValueError(f"invalid integer for {field}: '{value}'") from exc


def _parse_rows(content: bytes, filename: str) -> List[Dict[str, Any]]:
    lower = filename.lower()
    if lower.endswith(".xlsx"):
        try:
            import openpyxl
        except ImportError as exc:
            raise ValueError("XLSX support requires openpyxl") from exc
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        rows_iter = ws.iter_rows(values_only=True)
        headers = [str(h).strip() if h is not None else "" for h in next(rows_iter)]
        rows: List[Dict[str, Any]] = []
        for row in rows_iter:
            if all(c is None or str(c).strip() == "" for c in row):
                continue
            rows.append({headers[i]: row[i] for i in range(len(headers)) if headers[i]})
        return rows
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    return [dict(r) for r in reader]


def _lineage_ref(source: str, filename: str, content: bytes) -> str:
    digest = hashlib.sha256(content).hexdigest()[:16]
    return f"{source}:{filename}#sha256:{digest}"


def _get_or_create_file_source(session: Session, company_id: str) -> DataSource:
    row = session.execute(
        select(DataSource).where(
            DataSource.company_id == company_id,
            DataSource.kind == "file",
        ).limit(1)
    ).scalar_one_or_none()
    if row is not None:
        return row
    ds = DataSource(
        id=new_uuid(),
        company_id=company_id,
        kind="file",
        name="Manual CSV uploads",
        config={},
        status="connected",
    )
    session.add(ds)
    session.flush()
    return ds


def list_data_sources(session: Session, company_id: str) -> List[Dict[str, Any]]:
    rows = session.execute(
        select(DataSource).where(DataSource.company_id == company_id).order_by(DataSource.name)
    ).scalars().all()
    items: List[Dict[str, Any]] = []
    for ds in rows:
        health = {"status": ds.status, "last_synced_at": ds.last_synced_at}
        connector_type = ds.config.get("connector_type") if ds.config else None
        if connector_type:
            try:
                health = get_connector(connector_type).health(ds.config or {})
            except KeyError:
                health = {"status": "error", "detail": f"unknown connector {connector_type}"}
        items.append(
            {
                "id": ds.id,
                "kind": ds.kind,
                "name": ds.name,
                "status": ds.status,
                "config": {k: v for k, v in (ds.config or {}).items() if k != "secret_ref"},
                "last_synced_at": ds.last_synced_at.isoformat() if ds.last_synced_at else None,
                "health": health,
                "created_at": ds.created_at.isoformat() if ds.created_at else None,
            }
        )
    return items


def register_data_source(
    session: Session,
    company_id: str,
    *,
    kind: str,
    name: str,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    ds = DataSource(
        id=new_uuid(),
        company_id=company_id,
        kind=kind,
        name=name,
        config=config or {},
        status="connected",
    )
    session.add(ds)
    session.flush()
    return {
        "id": ds.id,
        "kind": ds.kind,
        "name": ds.name,
        "status": ds.status,
        "config": ds.config,
    }


def get_data_source(session: Session, company_id: str, source_id: str) -> Optional[DataSource]:
    return session.execute(
        select(DataSource).where(
            DataSource.id == source_id,
            DataSource.company_id == company_id,
        )
    ).scalar_one_or_none()


def _lookup_customer(session: Session, company_id: str, name: str) -> Optional[Customer]:
    return session.execute(
        select(Customer).where(
            Customer.company_id == company_id,
            Customer.name == name,
        ).limit(1)
    ).scalar_one_or_none()


def _lookup_vendor(session: Session, company_id: str, name: str) -> Optional[Vendor]:
    return session.execute(
        select(Vendor).where(
            Vendor.company_id == company_id,
            Vendor.name == name,
        ).limit(1)
    ).scalar_one_or_none()


def _mapped_col(mapping: Optional[Dict[str, str]], key: str, default: str) -> str:
    return (mapping or {}).get(key, default)


def _ingest_customers(
    session: Session,
    company_id: str,
    rows: List[Dict[str, Any]],
    *,
    data_source_id: str,
    lineage_ref: str,
    mapping: Optional[Dict[str, str]] = None,
) -> Tuple[int, int, int, List[Dict[str, Any]]]:
    inserted = updated = rejected = 0
    errors: List[Dict[str, Any]] = []

    for idx, raw in enumerate(rows, start=2):
        name = str(raw.get(_mapped_col(mapping, "name", "name"), "")).strip()
        if not name:
            rejected += 1
            errors.append({"row": idx, "issue": "missing customer name", "action": "rejected"})
            continue
        existing = _lookup_customer(session, company_id, name)
        payload = {
            "segment": str(
                raw.get(_mapped_col(mapping, "segment", "segment"), "") or ""
            ).strip() or None,
            "region": str(
                raw.get(_mapped_col(mapping, "region", "region"), "") or ""
            ).strip() or None,
            "industry": str(
                raw.get(_mapped_col(mapping, "industry", "industry"), "") or ""
            ).strip() or None,
            "status": str(
                raw.get(_mapped_col(mapping, "status", "status"), "active") or "active"
            ).strip(),
            "data_source_id": data_source_id,
        }
        if existing:
            for k, v in payload.items():
                setattr(existing, k, v)
            updated += 1
        else:
            session.add(
                Customer(
                    id=new_uuid(),
                    company_id=company_id,
                    name=name,
                    **payload,
                )
            )
            inserted += 1
    session.flush()
    return inserted, updated, rejected, errors


def _ingest_vendors(
    session: Session,
    company_id: str,
    rows: List[Dict[str, Any]],
    *,
    data_source_id: str,
    lineage_ref: str,
    mapping: Optional[Dict[str, str]] = None,
) -> Tuple[int, int, int, List[Dict[str, Any]]]:
    inserted = updated = rejected = 0
    errors: List[Dict[str, Any]] = []

    for idx, raw in enumerate(rows, start=2):
        name = str(raw.get(_mapped_col(mapping, "name", "name"), "")).strip()
        if not name:
            rejected += 1
            errors.append({"row": idx, "issue": "missing vendor name", "action": "rejected"})
            continue
        existing = _lookup_vendor(session, company_id, name)
        payload = {
            "category": str(
                raw.get(_mapped_col(mapping, "category", "category"), "") or ""
            ).strip() or None,
            "region": str(
                raw.get(_mapped_col(mapping, "region", "region"), "") or ""
            ).strip() or None,
            "criticality": str(
                raw.get(_mapped_col(mapping, "criticality", "criticality"), "standard")
                or "standard"
            ),
            "status": str(
                raw.get(_mapped_col(mapping, "status", "status"), "active") or "active"
            ).strip(),
            "data_source_id": data_source_id,
        }
        if existing:
            for k, v in payload.items():
                setattr(existing, k, v)
            updated += 1
        else:
            session.add(
                Vendor(
                    id=new_uuid(),
                    company_id=company_id,
                    name=name,
                    **payload,
                )
            )
            inserted += 1
    session.flush()
    return inserted, updated, rejected, errors


def _ingest_invoices(
    session: Session,
    company_id: str,
    rows: List[Dict[str, Any]],
    *,
    data_source_id: str,
    lineage_ref: str,
    mapping: Optional[Dict[str, str]] = None,
) -> Tuple[int, int, int, List[Dict[str, Any]]]:
    inserted = updated = rejected = 0
    errors: List[Dict[str, Any]] = []

    for idx, raw in enumerate(rows, start=2):
        inv_num = str(raw.get(_mapped_col(mapping, "invoice_number", "invoice_number"), "")).strip()
        cust_name = str(raw.get(_mapped_col(mapping, "customer_name", "customer_name"), "")).strip()
        if not inv_num:
            rejected += 1
            errors.append({"row": idx, "issue": "missing invoice_number", "action": "rejected"})
            continue
        if not cust_name:
            rejected += 1
            errors.append({"row": idx, "issue": "missing customer_name", "action": "rejected"})
            continue
        customer = _lookup_customer(session, company_id, cust_name)
        if customer is None:
            rejected += 1
            errors.append(
                {"row": idx, "issue": f"unknown customer '{cust_name}'", "action": "rejected"}
            )
            continue
        try:
            issue_date = _parse_date(raw.get(_mapped_col(mapping, "issue_date", "issue_date")))
            if issue_date is None:
                raise ValueError("missing issue_date")
            due_date = _parse_date(raw.get(_mapped_col(mapping, "due_date", "due_date")))
            total_cents = _parse_int(
                raw.get(_mapped_col(mapping, "total_cents", "total_cents")),
                "total_cents",
            )
        except ValueError as exc:
            rejected += 1
            errors.append({"row": idx, "issue": str(exc), "action": "rejected"})
            continue

        row_lineage = f"{lineage_ref}#row:{idx}"
        existing = session.execute(
            select(Invoice).where(
                Invoice.company_id == company_id,
                Invoice.invoice_number == inv_num,
            ).limit(1)
        ).scalar_one_or_none()
        payload = {
            "customer_id": customer.id,
            "issue_date": issue_date,
            "due_date": due_date,
            "total_cents": total_cents,
            "subtotal_cents": total_cents,
            "currency": str(
                raw.get(_mapped_col(mapping, "currency", "currency"), "USD") or "USD"
            ).strip(),
            "status": str(
                raw.get(_mapped_col(mapping, "status", "status"), "issued") or "issued"
            ).strip(),
            "data_source_id": data_source_id,
            "lineage_ref": row_lineage,
        }
        if existing:
            for k, v in payload.items():
                setattr(existing, k, v)
            updated += 1
        else:
            session.add(
                Invoice(
                    id=new_uuid(),
                    company_id=company_id,
                    invoice_number=inv_num,
                    **payload,
                )
            )
            inserted += 1
    session.flush()
    return inserted, updated, rejected, errors


def _ingest_expenses(
    session: Session,
    company_id: str,
    rows: List[Dict[str, Any]],
    *,
    data_source_id: str,
    lineage_ref: str,
    mapping: Optional[Dict[str, str]] = None,
) -> Tuple[int, int, int, List[Dict[str, Any]]]:
    inserted = updated = rejected = 0
    errors: List[Dict[str, Any]] = []

    for idx, raw in enumerate(rows, start=2):
        category = str(raw.get(_mapped_col(mapping, "category", "category"), "")).strip()
        if not category:
            rejected += 1
            errors.append({"row": idx, "issue": "missing category", "action": "rejected"})
            continue
        try:
            expense_date = _parse_date(
                raw.get(_mapped_col(mapping, "expense_date", "expense_date"))
            )
            if expense_date is None:
                raise ValueError("missing expense_date")
            amount_cents = _parse_int(
                raw.get(_mapped_col(mapping, "amount_cents", "amount_cents")),
                "amount_cents",
            )
        except ValueError as exc:
            rejected += 1
            errors.append({"row": idx, "issue": str(exc), "action": "rejected"})
            continue

        vendor_name = str(
            raw.get(_mapped_col(mapping, "vendor_name", "vendor_name"), "") or ""
        ).strip()
        vendor_id = None
        if vendor_name:
            vendor = _lookup_vendor(session, company_id, vendor_name)
            if vendor is None:
                rejected += 1
                errors.append(
                    {"row": idx, "issue": f"unknown vendor '{vendor_name}'", "action": "rejected"}
                )
                continue
            vendor_id = vendor.id

        row_lineage = f"{lineage_ref}#row:{idx}"
        existing = session.execute(
            select(Expense).where(
                Expense.company_id == company_id,
                Expense.lineage_ref == row_lineage,
            ).limit(1)
        ).scalar_one_or_none()
        payload = {
            "vendor_id": vendor_id,
            "category": category,
            "description": str(
                raw.get(_mapped_col(mapping, "description", "description"), "") or ""
            ).strip() or None,
            "amount_cents": amount_cents,
            "currency": str(
                raw.get(_mapped_col(mapping, "currency", "currency"), "USD") or "USD"
            ).strip(),
            "expense_date": expense_date,
            "data_source_id": data_source_id,
            "lineage_ref": row_lineage,
        }
        if existing:
            for k, v in payload.items():
                setattr(existing, k, v)
            updated += 1
        else:
            session.add(Expense(id=new_uuid(), company_id=company_id, **payload))
            inserted += 1
    session.flush()
    return inserted, updated, rejected, errors


def _run_pipeline(
    session: Session,
    company_id: str,
    *,
    target: str,
    rows: List[Dict[str, Any]],
    data_source_id: str,
    lineage_ref: str,
    mapping: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    if target not in SUPPORTED_TARGETS:
        raise ValueError(f"Unsupported target: {target}")

    dispatch = {
        "customers": _ingest_customers,
        "vendors": _ingest_vendors,
        "invoices": _ingest_invoices,
        "expenses": _ingest_expenses,
    }
    inserted, updated, rejected, errors = dispatch[target](
        session,
        company_id,
        rows,
        data_source_id=data_source_id,
        lineage_ref=lineage_ref,
        mapping=mapping,
    )

    refresh_mart(session, company_id)
    refresh_graph(session, company_id)

    ds = session.get(DataSource, data_source_id)
    if ds is not None:
        ds.status = "connected"
        ds.last_synced_at = datetime.now(timezone.utc)

    return {
        "rows_total": len(rows),
        "rows_inserted": inserted,
        "rows_updated": updated,
        "rows_rejected": rejected,
        "errors": errors[:100],
        "lineage_ref": lineage_ref,
    }


def _create_job(
    company_id: str,
    *,
    target: str,
    source_id: Optional[str] = None,
    filename: Optional[str] = None,
    persistent: bool = False,
) -> Dict[str, Any]:
    jid = new_uuid() if persistent else _job_id()
    payload = {
        "job_id": jid,
        "company_id": company_id,
        "target": target,
        "source_id": source_id,
        "filename": filename,
        "status": "queued",
        "rows_total": 0,
        "rows_inserted": 0,
        "rows_updated": 0,
        "rows_rejected": 0,
        "errors": [],
        "lineage_ref": None,
        "started_at": None,
        "finished_at": None,
        "ws_channel": f"ingestion:{jid}",
    }
    if not persistent:
        _jobs[jid] = payload
    return payload


def get_job(
    job_id: str,
    *,
    session: Optional[Session] = None,
    company_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if session is not None:
        stmt = select(IngestionJob).where(IngestionJob.id == job_id)
        if company_id is not None:
            stmt = stmt.where(IngestionJob.company_id == company_id)
        row = session.execute(stmt).scalar_one_or_none()
        return _job_row_to_dict(row) if row is not None else None
    return _jobs.get(job_id)


def list_jobs(
    company_id: str,
    limit: int = 50,
    *,
    session: Optional[Session] = None,
) -> List[Dict[str, Any]]:
    if session is not None:
        rows = session.execute(
            select(IngestionJob)
            .where(IngestionJob.company_id == company_id)
            .order_by(IngestionJob.created_at.desc())
            .limit(limit)
        ).scalars().all()
        return [_job_row_to_dict(r) for r in rows]
    items = [j for j in _jobs.values() if j.get("company_id") == company_id]
    items.sort(key=lambda j: j.get("started_at") or "", reverse=True)
    return items[:limit]


def process_upload(
    session: Session,
    company_id: str,
    *,
    content: bytes,
    filename: str,
    target: str,
    mapping: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    if target not in SUPPORTED_TARGETS:
        raise ValueError(f"Unsupported target: {target}")

    persistent = session is not None
    job = _create_job(company_id, target=target, filename=filename, persistent=persistent)
    job["status"] = "running"
    job["started_at"] = _utcnow()

    try:
        rows = _parse_rows(content, filename)
        file_source = _get_or_create_file_source(session, company_id)
        lineage = _lineage_ref("upload", filename, content)
        result = _run_pipeline(
            session,
            company_id,
            target=target,
            rows=rows,
            data_source_id=file_source.id,
            lineage_ref=lineage,
            mapping=mapping,
        )
        job.update(result)
        job["status"] = "completed"
        job["source_id"] = file_source.id
    except Exception as exc:
        job["status"] = "failed"
        job["errors"] = [{"row": 0, "issue": str(exc), "action": "failed"}]
    finally:
        job["finished_at"] = _utcnow()
        if persistent:
            _persist_job(session, job)

    return job


def process_connector_sync(
    session: Session,
    company_id: str,
    source_id: str,
    *,
    target: Optional[str] = None,
) -> Dict[str, Any]:
    ds = get_data_source(session, company_id, source_id)
    if ds is None:
        raise KeyError("Data source not found")

    connector_type = (ds.config or {}).get("connector_type")
    if not connector_type:
        raise ValueError("Data source has no connector_type configured")

    sync_target = target or (ds.config or {}).get("default_target", "invoices")
    persistent = session is not None
    job = _create_job(
        company_id, target=sync_target, source_id=source_id, persistent=persistent
    )
    job["status"] = "running"
    job["started_at"] = _utcnow()
    ds.status = "syncing"

    try:
        connector = get_connector(connector_type)
        pull: ConnectorResult = connector.pull(
            company_id=company_id,
            config=ds.config or {},
            target=sync_target,
        )
        result = _run_pipeline(
            session,
            company_id,
            target=sync_target,
            rows=pull.rows,
            data_source_id=ds.id,
            lineage_ref=pull.lineage_ref,
        )
        if pull.errors:
            result["errors"] = pull.errors + result.get("errors", [])
            result["rows_rejected"] = result.get("rows_rejected", 0) + len(pull.errors)
        job.update(result)
        job["status"] = "completed"
    except Exception as exc:
        job["status"] = "failed"
        job["errors"] = [{"row": 0, "issue": str(exc), "action": "failed"}]
    finally:
        job["finished_at"] = _utcnow()
        if persistent:
            _persist_job(session, job)
            if job["status"] == "failed":
                # _persist_job rolled the session back, discarding the pre-failure
                # ds.status="syncing" write; re-mark the source as errored.
                ds = get_data_source(session, company_id, source_id)
                if ds is not None:
                    ds.status = "error"
                    session.flush()
        elif job["status"] == "failed":
            ds.status = "error"

    return job
