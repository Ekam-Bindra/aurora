"""Group B — Organization & people (docs/data-model/data-model.md §4)."""

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from ..mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from ..types import GUID


class Department(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "department"
    # Table-scoped name — see Role: schema-global index namespace on PostgreSQL.
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="department_company_name"),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(16))
    parent_id: Mapped[Optional[str]] = mapped_column(
        GUID, ForeignKey("department.id", ondelete="SET NULL")
    )
    # Soft reference to employee (avoids a department<->employee FK cycle at create time).
    head_employee_id: Mapped[Optional[str]] = mapped_column(GUID)
    annual_budget_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    cost_center: Mapped[Optional[str]] = mapped_column(String(32))


class Employee(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "employee"
    __table_args__ = (
        CheckConstraint(
            "employment_type in ('full_time','part_time','contractor')",
            name="employment_type_valid",
        ),
        CheckConstraint(
            "status in ('active','on_leave','terminated')", name="status_valid"
        ),
    )

    department_id: Mapped[Optional[str]] = mapped_column(
        GUID, ForeignKey("department.id", ondelete="SET NULL"), index=True
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        GUID, ForeignKey("app_user.id", ondelete="SET NULL")
    )
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text)
    employment_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="full_time"
    )
    annual_salary_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    hire_date: Mapped[Optional[date]] = mapped_column(Date)
    termination_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    data_source_id: Mapped[Optional[str]] = mapped_column(GUID)


class Project(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "project"
    __table_args__ = (
        CheckConstraint(
            "status in ('planned','active','on_hold','completed','cancelled')",
            name="status_valid",
        ),
        CheckConstraint("health in ('green','amber','red')", name="health_valid"),
    )

    department_id: Mapped[Optional[str]] = mapped_column(
        GUID, ForeignKey("department.id", ondelete="SET NULL"), index=True
    )
    customer_id: Mapped[Optional[str]] = mapped_column(
        GUID, ForeignKey("customer.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    budget_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    spent_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    health: Mapped[Optional[str]] = mapped_column(String(8))


class ProjectAssignment(UUIDPrimaryKeyMixin, TenantScopedMixin, Base):
    __tablename__ = "project_assignment"
    __table_args__ = (
        UniqueConstraint("project_id", "employee_id", name="project_employee_unique"),
    )

    project_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("employee.id", ondelete="CASCADE"), nullable=False
    )
    allocation_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("100")
    )
    role_on_project: Mapped[Optional[str]] = mapped_column(Text)
