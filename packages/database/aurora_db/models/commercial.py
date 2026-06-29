"""Group C — Commercial entities (docs/data-model/data-model.md §4)."""

from datetime import date
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from ..mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from ..types import GUID


class Customer(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "customer"
    __table_args__ = (
        CheckConstraint(
            "status in ('prospect','active','churned')", name="status_valid"
        ),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    segment: Mapped[Optional[str]] = mapped_column(String(32))
    region: Mapped[Optional[str]] = mapped_column(String(32))
    industry: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    acquired_date: Mapped[Optional[date]] = mapped_column(Date)
    churn_date: Mapped[Optional[date]] = mapped_column(Date)
    data_source_id: Mapped[Optional[str]] = mapped_column(GUID)


class Vendor(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "vendor"
    __table_args__ = (
        CheckConstraint(
            "criticality in ('critical','standard','low')", name="criticality_valid"
        ),
        CheckConstraint("status in ('active','inactive')", name="status_valid"),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(48))
    region: Mapped[Optional[str]] = mapped_column(String(32))
    criticality: Mapped[str] = mapped_column(String(16), nullable=False, default="standard")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    data_source_id: Mapped[Optional[str]] = mapped_column(GUID)


class Product(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "product"
    __table_args__ = (
        CheckConstraint("status in ('active','discontinued')", name="status_valid"),
        UniqueConstraint("company_id", "sku", name="company_id_sku"),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    sku: Mapped[Optional[str]] = mapped_column(String(48))
    line: Mapped[Optional[str]] = mapped_column(String(64))
    unit_price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    unit_cost_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")


class Contract(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "contract"
    __table_args__ = (
        CheckConstraint(
            "party_type in ('customer','vendor')", name="party_type_valid"
        ),
        CheckConstraint(
            "status in ('draft','active','expired','terminated')", name="status_valid"
        ),
    )

    party_type: Mapped[str] = mapped_column(String(16), nullable=False)
    customer_id: Mapped[Optional[str]] = mapped_column(
        GUID, ForeignKey("customer.id", ondelete="CASCADE")
    )
    vendor_id: Mapped[Optional[str]] = mapped_column(
        GUID, ForeignKey("vendor.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    value_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    renewal_type: Mapped[Optional[str]] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
