"""Group D — Financial facts (docs/data-model/data-model.md §4).

Monetary amounts are integer **minor units (cents)** + a currency code, to avoid float drift.
"""

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from ..mixins import CreatedAtMixin, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from ..types import GUID


class Invoice(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "invoice"
    __table_args__ = (
        CheckConstraint(
            "status in ('draft','issued','paid','overdue','void')", name="status_valid"
        ),
        UniqueConstraint("company_id", "invoice_number", name="company_id_invoice_number"),
        Index("ix_invoice_company_id_issue_date", "company_id", "issue_date"),
    )

    customer_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("customer.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contract_id: Mapped[Optional[str]] = mapped_column(
        GUID, ForeignKey("contract.id", ondelete="SET NULL")
    )
    invoice_number: Mapped[str] = mapped_column(String(48), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    paid_date: Mapped[Optional[date]] = mapped_column(Date)
    subtotal_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tax_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="issued")
    data_source_id: Mapped[Optional[str]] = mapped_column(GUID)
    lineage_ref: Mapped[Optional[str]] = mapped_column(Text)


class InvoiceLineItem(UUIDPrimaryKeyMixin, TenantScopedMixin, CreatedAtMixin, Base):
    __tablename__ = "invoice_line_item"

    invoice_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("invoice.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[Optional[str]] = mapped_column(
        GUID, ForeignKey("product.id", ondelete="SET NULL")
    )
    description: Mapped[Optional[str]] = mapped_column(Text)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("1"))
    unit_price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)


class Expense(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "expense"
    __table_args__ = (
        Index("ix_expense_company_id_expense_date", "company_id", "expense_date"),
        Index("ix_expense_company_id_category", "company_id", "category"),
    )

    vendor_id: Mapped[Optional[str]] = mapped_column(
        GUID, ForeignKey("vendor.id", ondelete="SET NULL")
    )
    department_id: Mapped[Optional[str]] = mapped_column(
        GUID, ForeignKey("department.id", ondelete="SET NULL")
    )
    contract_id: Mapped[Optional[str]] = mapped_column(
        GUID, ForeignKey("contract.id", ondelete="SET NULL")
    )
    category: Mapped[str] = mapped_column(String(48), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_recurring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    data_source_id: Mapped[Optional[str]] = mapped_column(GUID)
    lineage_ref: Mapped[Optional[str]] = mapped_column(Text)


class RevenueRecord(UUIDPrimaryKeyMixin, TenantScopedMixin, CreatedAtMixin, Base):
    __tablename__ = "revenue_record"
    __table_args__ = (
        CheckConstraint(
            "recognition_type in ('point','ratable')", name="recognition_valid"
        ),
        Index("ix_revenue_record_company_id_period_month", "company_id", "period_month"),
    )

    customer_id: Mapped[Optional[str]] = mapped_column(
        GUID, ForeignKey("customer.id", ondelete="SET NULL"), index=True
    )
    product_id: Mapped[Optional[str]] = mapped_column(
        GUID, ForeignKey("product.id", ondelete="SET NULL")
    )
    invoice_id: Mapped[Optional[str]] = mapped_column(
        GUID, ForeignKey("invoice.id", ondelete="SET NULL")
    )
    period_month: Mapped[date] = mapped_column(Date, nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    recognition_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="point"
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
