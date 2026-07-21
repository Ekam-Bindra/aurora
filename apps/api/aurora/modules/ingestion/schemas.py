"""Ingestion response schemas (mirror the service serializers)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class SourceHealth(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: Optional[str] = None
    # Connector health payloads vary; last_synced_at may be datetime or ISO string.
    last_synced_at: Optional[Any] = None
    detail: Optional[str] = None


class DataSourceOut(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    kind: str
    name: str
    status: str
    config: Dict[str, Any]
    last_synced_at: Optional[str] = None
    health: Optional[SourceHealth] = None
    created_at: Optional[str] = None


class IngestionJobOut(BaseModel):
    model_config = ConfigDict(extra="allow")

    job_id: str
    company_id: str
    target: str
    status: str
    source_id: Optional[str] = None
    filename: Optional[str] = None
    rows_total: int = 0
    rows_inserted: int = 0
    rows_updated: int = 0
    rows_rejected: int = 0
    errors: List[Dict[str, Any]] = []
    lineage_ref: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    ws_channel: Optional[str] = None


class IngestionJobRef(BaseModel):
    """Minimal payload returned by upload/sync accept responses."""

    model_config = ConfigDict(extra="allow")

    job_id: str
    status: str
    target: str
    ws_channel: Optional[str] = None
