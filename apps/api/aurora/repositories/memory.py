"""In-memory, tenant-scoped store (Phase 1).

Every read is scoped by ``tenant_id`` exactly as the SQLAlchemy repositories will be in Phase 2,
so multi-tenant isolation is enforced and testable from day one. ``get_user_by_email`` is the
only intentionally global lookup (used at login, before a tenant is known).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


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


@dataclass
class StoredAuditEntry:
    id: int
    company_id: str
    user_id: Optional[str]
    action: str
    resource_type: str
    resource_id: Optional[str]
    request_id: Optional[str]
    before: Optional[Dict[str, Any]]
    after: Optional[Dict[str, Any]]
    created_at: str


class InMemoryStore:
    def __init__(self) -> None:
        self._companies: Dict[str, StoredCompany] = {}
        self._users: Dict[str, StoredUser] = {}
        self._audit_logs: List[StoredAuditEntry] = []
        self._audit_seq: int = 0

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

    def append_audit_log(
        self,
        *,
        company_id: str,
        user_id: Optional[str],
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        request_id: Optional[str] = None,
        before: Optional[Dict[str, Any]] = None,
        after: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self._audit_seq += 1
        entry = StoredAuditEntry(
            id=self._audit_seq,
            company_id=company_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=request_id,
            before=before,
            after=after,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._audit_logs.append(entry)
        return {
            "id": str(entry.id),
            "user_id": entry.user_id,
            "action": entry.action,
            "resource_type": entry.resource_type,
            "resource_id": entry.resource_id,
            "request_id": entry.request_id,
            "before": entry.before,
            "after": entry.after,
            "created_at": entry.created_at,
        }

    def list_audit_logs(
        self,
        tenant_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
        action: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        rows = [e for e in self._audit_logs if e.company_id == tenant_id]
        if action:
            rows = [e for e in rows if e.action == action]
        rows.sort(key=lambda e: e.created_at, reverse=True)
        window = rows[offset : offset + limit]
        return [
            {
                "id": str(e.id),
                "user_id": e.user_id,
                "action": e.action,
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
                "request_id": e.request_id,
                "before": e.before,
                "after": e.after,
                "created_at": e.created_at,
            }
            for e in window
        ]

    def count_audit_logs(self, tenant_id: str, *, action: Optional[str] = None) -> int:
        rows = [e for e in self._audit_logs if e.company_id == tenant_id]
        if action:
            rows = [e for e in rows if e.action == action]
        return len(rows)

    def reset(self) -> None:
        self._companies.clear()
        self._users.clear()
        self._audit_logs.clear()
        self._audit_seq = 0


# Process-wide singleton (Phase 1). Swapped for a DB session/repo in Phase 2.
_store = InMemoryStore()


def get_store() -> InMemoryStore:
    return _store
