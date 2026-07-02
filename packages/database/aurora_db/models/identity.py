"""Group A — Tenancy, identity & access (docs/data-model/data-model.md §2, §4)."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base
from ..mixins import CreatedAtMixin, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from ..types import GUID, JSONB


class Company(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The tenant / workspace root. Owns every other row via ``company_id``."""

    __tablename__ = "company"
    __table_args__ = (
        CheckConstraint(
            "status in ('active','suspended','archived')", name="status_valid"
        ),
        CheckConstraint(
            "fiscal_year_start_month between 1 and 12", name="fiscal_month_valid"
        ),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    industry: Mapped[Optional[str]] = mapped_column(Text)
    fiscal_year_start_month: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=1
    )
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    plan: Mapped[str] = mapped_column(String(32), nullable=False, default="standard")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")

    users: Mapped[List["AppUser"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    roles: Mapped[List["Role"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )


class Role(UUIDPrimaryKeyMixin, TenantScopedMixin, CreatedAtMixin, Base):
    """A named bundle of permissions, scoped to a tenant."""

    __tablename__ = "role"
    # Table-scoped name: PostgreSQL backs unique constraints with schema-global
    # indexes, so this must not collide with department's equivalent constraint.
    __table_args__ = (UniqueConstraint("company_id", "name", name="role_company_name"),)

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    permissions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    company: Mapped["Company"] = relationship(back_populates="roles")
    user_roles: Mapped[List["UserRole"]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )


class AppUser(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """A person who logs in. Email is stored normalized (lower-cased) for case-insensitive login."""

    __tablename__ = "app_user"
    __table_args__ = (UniqueConstraint("company_id", "email", name="company_id_email"),)

    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(Text)
    title: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    company: Mapped["Company"] = relationship(back_populates="users")
    user_roles: Mapped[List["UserRole"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserRole(UUIDPrimaryKeyMixin, TenantScopedMixin, CreatedAtMixin, Base):
    """Assignment of a role to a user, optionally scoped to a department or project."""

    __tablename__ = "user_role"
    __table_args__ = (
        CheckConstraint(
            "scope_type in ('tenant','department','project')", name="scope_valid"
        ),
        UniqueConstraint(
            "user_id", "role_id", "scope_type", "scope_id", name="assignment_unique"
        ),
    )

    user_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("role.id", ondelete="CASCADE"), nullable=False
    )
    scope_type: Mapped[str] = mapped_column(String(16), nullable=False, default="tenant")
    scope_id: Mapped[Optional[str]] = mapped_column(GUID)

    user: Mapped["AppUser"] = relationship(back_populates="user_roles")
    role: Mapped["Role"] = relationship(back_populates="user_roles")


class DataSource(UUIDPrimaryKeyMixin, TenantScopedMixin, CreatedAtMixin, Base):
    """A registered origin of ingested data (file/connector). Lineage references point here."""

    __tablename__ = "data_source"
    __table_args__ = (
        CheckConstraint(
            "kind in ('file','accounting','crm','hris','api')", name="kind_valid"
        ),
        CheckConstraint(
            "status in ('connected','error','syncing','disabled')", name="status_valid"
        ),
    )

    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="connected")
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class AuditLog(TenantScopedMixin, CreatedAtMixin, Base):
    """Immutable, append-only record of significant actions (monotonic BIGINT key)."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[str]] = mapped_column(GUID)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[str] = mapped_column(Text, nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(GUID)
    request_id: Mapped[Optional[str]] = mapped_column(Text)
    before: Mapped[Optional[dict]] = mapped_column(JSONB)
    after: Mapped[Optional[dict]] = mapped_column(JSONB)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
