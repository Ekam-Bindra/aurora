"""Repository facade — one interface for in-memory (Phase 1) and SQLAlchemy (Phase 2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Protocol

from aurora_db.repositories import CompanyRepository, UserRepository, role_names_for_user
from sqlalchemy.orm import Session

from .memory import InMemoryStore, StoredCompany, StoredUser


@dataclass(frozen=True)
class CompanyRecord:
    id: str
    name: str
    slug: str
    industry: str
    base_currency: str


@dataclass(frozen=True)
class UserRecord:
    id: str
    company_id: str
    email: str
    full_name: str
    title: str
    password_hash: str
    roles: List[str]
    is_active: bool


class UserStore(Protocol):
    def get_user_by_email(self, email: str) -> Optional[UserRecord]: ...
    def get_user(self, tenant_id: str, user_id: str) -> Optional[UserRecord]: ...
    def get_company(self, tenant_id: str) -> Optional[CompanyRecord]: ...
    def list_users(self, tenant_id: str) -> List[UserRecord]: ...


class MemoryUserStore:
    """Adapter over the Phase 1 in-memory store."""

    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

    def _map_company(self, c: StoredCompany) -> CompanyRecord:
        return CompanyRecord(
            id=c.id,
            name=c.name,
            slug=c.slug,
            industry=c.industry or "",
            base_currency=c.base_currency,
        )

    def _map_user(self, u: StoredUser) -> UserRecord:
        return UserRecord(
            id=u.id,
            company_id=u.company_id,
            email=u.email,
            full_name=u.full_name,
            title=u.title or "",
            password_hash=u.password_hash,
            roles=list(u.roles),
            is_active=u.is_active,
        )

    def get_user_by_email(self, email: str) -> Optional[UserRecord]:
        user = self._store.get_user_by_email(email)
        return self._map_user(user) if user else None

    def get_user(self, tenant_id: str, user_id: str) -> Optional[UserRecord]:
        user = self._store.get_user(tenant_id, user_id)
        return self._map_user(user) if user else None

    def get_company(self, tenant_id: str) -> Optional[CompanyRecord]:
        company = self._store.get_company(tenant_id)
        return self._map_company(company) if company else None

    def list_users(self, tenant_id: str) -> List[UserRecord]:
        return [self._map_user(u) for u in self._store.list_users(tenant_id)]


class DatabaseUserStore:
    """Adapter over ``aurora_db`` tenant-scoped repositories."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._companies = CompanyRepository(session)

    def get_user_by_email(self, email: str) -> Optional[UserRecord]:
        # Global lookup — no tenant filter (login only).
        users = UserRepository(self._session, tenant_id="")
        user = users.get_by_email(email)
        if user is None:
            return None
        return self._map_user(user)

    def get_user(self, tenant_id: str, user_id: str) -> Optional[UserRecord]:
        users = UserRepository(self._session, tenant_id)
        user = users.get(user_id)
        return self._map_user(user) if user else None

    def get_company(self, tenant_id: str) -> Optional[CompanyRecord]:
        company = self._companies.get(tenant_id)
        if company is None:
            return None
        return CompanyRecord(
            id=company.id,
            name=company.name,
            slug=company.slug,
            industry=company.industry or "",
            base_currency=company.base_currency,
        )

    def list_users(self, tenant_id: str) -> List[UserRecord]:
        users = UserRepository(self._session, tenant_id)
        return [self._map_user(u) for u in users.list(limit=500)]

    def _map_user(self, user) -> UserRecord:
        roles = role_names_for_user(self._session, user.id)
        return UserRecord(
            id=user.id,
            company_id=user.company_id,
            email=user.email,
            full_name=user.full_name,
            title=user.title or "",
            password_hash=user.password_hash or "",
            roles=roles,
            is_active=user.is_active,
        )
