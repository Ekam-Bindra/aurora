"""Offset pagination helpers matching docs/api/api-specification.md §4."""

from __future__ import annotations

from typing import Any, List

from fastapi import Query
from pydantic import BaseModel

from .logging import get_request_id

MAX_PAGE_SIZE = 200


class PaginationParams:
    def __init__(
        self,
        page: int = Query(1, ge=1, description="1-indexed page number"),
        page_size: int = Query(50, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    ) -> None:
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PageMeta(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int


def paginate(items: List[Any], params: PaginationParams) -> dict:
    total = len(items)
    total_pages = (total + params.page_size - 1) // params.page_size if total else 0
    window = items[params.offset : params.offset + params.page_size]
    return {
        "data": window,
        "pagination": {
            "page": params.page,
            "page_size": params.page_size,
            "total_items": total,
            "total_pages": total_pages,
        },
        "meta": {"request_id": get_request_id()},
    }
