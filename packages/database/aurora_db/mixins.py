"""Reusable mapped mixins: UUID primary keys, timestamps, and tenant scoping.

``TenantScopedMixin`` is the heart of AURORA's multi-tenant isolation: every business table
carries an indexed, FK-backed ``company_id`` (the tenant key), and the repository layer filters
on it for every read (docs/data-model/data-model.md §1).
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from .types import GUID, new_uuid


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UUIDPrimaryKeyMixin:
    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
        nullable=False,
    )


class CreatedAtMixin:
    """For append-only / write-once tables that only need a creation timestamp."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )


class TenantScopedMixin:
    company_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True
    )
