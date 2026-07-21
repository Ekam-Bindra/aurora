"""Board report response schemas (mirrors board_reports serializer output)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class BoardReportOut(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    company_id: str
    title: str
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    sections: List[str]
    status: str
    content: Optional[Dict[str, Any]] = None
    export_url: Optional[str] = None
    created_by: Optional[str] = None
    approved_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    ws_channel: Optional[str] = None


class BoardReportRef(BaseModel):
    """Minimal payload returned by create/generate/approve."""

    model_config = ConfigDict(extra="allow")

    id: str
    status: str
    ws_channel: Optional[str] = None
    approved_by: Optional[str] = None
