"""Tenant-scoped repositories — the primary enforcement point for multi-tenant isolation.

Every read here is filtered by ``company_id`` (the tenant key). The single intentional exception
is :meth:`UserRepository.get_by_email`, used at login before a tenant is established
(docs/architecture/system-architecture.md §7.3).
"""

from typing import Generic, List, Optional, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import (
    AppUser,
    Company,
    Customer,
    Invoice,
    Role,
    UserRole,
    Vendor,
)

ModelT = TypeVar("ModelT")


class CompanyRepository:
    """The tenant root. Not itself tenant-scoped (it *is* the tenant)."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, company_id: str) -> Optional[Company]:
        return self.session.get(Company, company_id)

    def get_by_slug(self, slug: str) -> Optional[Company]:
        return self.session.scalars(select(Company).where(Company.slug == slug)).first()


class TenantScopedRepository(Generic[ModelT]):
    """Base class: all queries are constrained to a single tenant."""

    model: type

    def __init__(self, session: Session, tenant_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id

    def _scoped(self):
        return select(self.model).where(self.model.company_id == self.tenant_id)

    def get(self, entity_id: str) -> Optional[ModelT]:
        obj = self.session.get(self.model, entity_id)
        if obj is None or getattr(obj, "company_id", None) != self.tenant_id:
            return None
        return obj

    def list(self, *, limit: int = 50, offset: int = 0, order_by=None) -> List[ModelT]:
        stmt = self._scoped()
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        stmt = stmt.limit(limit).offset(offset)
        return list(self.session.scalars(stmt))

    def count(self) -> int:
        stmt = (
            select(func.count())
            .select_from(self.model)
            .where(self.model.company_id == self.tenant_id)
        )
        return int(self.session.scalar(stmt) or 0)


class UserRepository(TenantScopedRepository[AppUser]):
    model = AppUser

    def get_by_email(self, email: str) -> Optional[AppUser]:
        """Global lookup (case-insensitive) used only at login, before a tenant is known."""
        normalized = email.strip().lower()
        stmt = select(AppUser).where(func.lower(AppUser.email) == normalized)
        return self.session.scalars(stmt).first()

    def list(self, *, limit: int = 50, offset: int = 0) -> List[AppUser]:
        return super().list(limit=limit, offset=offset, order_by=AppUser.full_name)


class RoleRepository(TenantScopedRepository[Role]):
    model = Role

    def get_by_name(self, name: str) -> Optional[Role]:
        return self.session.scalars(self._scoped().where(Role.name == name)).first()

    def list(self, *, limit: int = 100, offset: int = 0) -> List[Role]:
        return super().list(limit=limit, offset=offset, order_by=Role.name)


class CustomerRepository(TenantScopedRepository[Customer]):
    model = Customer

    def list(self, *, limit: int = 50, offset: int = 0) -> List[Customer]:
        return super().list(limit=limit, offset=offset, order_by=Customer.name)


class VendorRepository(TenantScopedRepository[Vendor]):
    model = Vendor

    def list(self, *, limit: int = 50, offset: int = 0) -> List[Vendor]:
        return super().list(limit=limit, offset=offset, order_by=Vendor.name)


class InvoiceRepository(TenantScopedRepository[Invoice]):
    model = Invoice

    def list(self, *, limit: int = 50, offset: int = 0) -> List[Invoice]:
        return super().list(limit=limit, offset=offset, order_by=Invoice.issue_date.desc())


def role_names_for_user(session: Session, user_id: str) -> List[str]:
    """Return the role names assigned to a user (used to build the JWT/AuthContext)."""
    stmt = (
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
        .order_by(Role.name)
    )
    return list(session.scalars(stmt))
