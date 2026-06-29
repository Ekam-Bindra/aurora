"""In-memory, tenant-scoped store (Phase 1).

Every read is scoped by ``tenant_id`` exactly as the SQLAlchemy repositories will be in Phase 2,
so multi-tenant isolation is enforced and testable from day one. ``get_user_by_email`` is the
only intentionally global lookup (used at login, before a tenant is known).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class StoredCompany:
    name: str
    slug: str
    industry: str
    base_currency: str = "USD"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class StoredUser:
    company_id: str
    email: str
    full_name: str
    title: str
    password_hash: str
    roles: List[str] = field(default_factory=list)
    is_active: bool = True
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


class InMemoryStore:
    def __init__(self) -> None:
        self._companies: Dict[str, StoredCompany] = {}
        self._users: Dict[str, StoredUser] = {}

    # ── companies ────────────────────────────────────────
    def add_company(self, company: StoredCompany) -> StoredCompany:
        self._companies[company.id] = company
        return company

    def get_company(self, tenant_id: str) -> Optional[StoredCompany]:
        return self._companies.get(tenant_id)

    # ── users (tenant-scoped, except login lookup) ───────
    def add_user(self, user: StoredUser) -> StoredUser:
        self._users[user.id] = user
        return user

    def get_user_by_email(self, email: str) -> Optional[StoredUser]:
        """Global lookup — used only at login, before a tenant is established."""
        email = email.lower()
        for user in self._users.values():
            if user.email.lower() == email:
                return user
        return None

    def get_user(self, tenant_id: str, user_id: str) -> Optional[StoredUser]:
        user = self._users.get(user_id)
        if user is None or user.company_id != tenant_id:
            return None
        return user

    def list_users(self, tenant_id: str) -> List[StoredUser]:
        return [u for u in self._users.values() if u.company_id == tenant_id]

    def reset(self) -> None:
        self._companies.clear()
        self._users.clear()


# Process-wide singleton (Phase 1). Swapped for a DB session/repo in Phase 2.
_store = InMemoryStore()


def get_store() -> InMemoryStore:
    return _store
