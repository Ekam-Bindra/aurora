"""Admin console service — users, roles, audit within tenant scope."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from aurora_db.models import AppUser, Role, UserRole
from aurora_db.repositories import RoleRepository, UserRepository, role_names_for_user
from aurora_db.types import new_uuid
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..core.rbac import ROLE_PERMISSIONS
from ..core.security import hash_password
from ..repositories.memory import StoredUser, get_store
from .audit import list_audit_logs, record_audit


def list_roles(session: Optional[Session], company_id: str) -> List[Dict[str, Any]]:
    if session is not None:
        repo = RoleRepository(session, company_id)
        return [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "permissions": list(r.permissions or []),
                "is_system": r.is_system,
            }
            for r in repo.list(limit=100)
        ]

    return [
        {
            "id": name,
            "name": name,
            "description": f"System role: {name}",
            "permissions": sorted(ROLE_PERMISSIONS.get(name, frozenset())),
            "is_system": True,
        }
        for name in sorted(ROLE_PERMISSIONS.keys())
    ]


def create_user(
    session: Optional[Session],
    company_id: str,
    *,
    email: str,
    full_name: str,
    title: str,
    roles: List[str],
    password: str,
    actor_id: Optional[str],
) -> Dict[str, Any]:
    normalized = email.strip().lower()
    if not roles:
        raise ValueError("At least one role is required")

    if session is not None:
        global_users = UserRepository(session, tenant_id="")
        if global_users.get_by_email(normalized):
            raise ValueError("Email already registered")

        user = AppUser(
            id=new_uuid(),
            company_id=company_id,
            email=normalized,
            full_name=full_name,
            title=title,
            password_hash=hash_password(password),
            is_active=True,
        )
        session.add(user)
        session.flush()
        assigned = _assign_roles_db(session, company_id, user.id, roles)
        record_audit(
            session,
            company_id,
            user_id=actor_id,
            action="user.create",
            resource_type="user",
            resource_id=user.id,
            after={"email": normalized, "roles": assigned},
        )
        return _user_payload(user, assigned)

    store = get_store()
    if store.get_user_by_email(normalized):
        raise ValueError("Email already registered")
    user = store.add_user(
        StoredUser(
            company_id=company_id,
            email=normalized,
            full_name=full_name,
            title=title,
            password_hash=hash_password(password),
            roles=list(roles),
        )
    )
    record_audit(
        None,
        company_id,
        user_id=actor_id,
        action="user.create",
        resource_type="user",
        resource_id=user.id,
        after={"email": normalized, "roles": roles},
    )
    return _memory_user_payload(user)


def update_user(
    session: Optional[Session],
    company_id: str,
    user_id: str,
    *,
    full_name: Optional[str] = None,
    title: Optional[str] = None,
    is_active: Optional[bool] = None,
    roles: Optional[List[str]] = None,
    actor_id: Optional[str],
) -> Dict[str, Any]:
    if session is not None:
        users = UserRepository(session, company_id)
        user = users.get(user_id)
        if user is None:
            raise KeyError("User not found")
        before = {"full_name": user.full_name, "is_active": user.is_active, "title": user.title}
        if full_name is not None:
            user.full_name = full_name
        if title is not None:
            user.title = title
        if is_active is not None:
            user.is_active = is_active
        assigned = role_names_for_user(session, user.id)
        if roles is not None:
            assigned = _replace_roles_db(session, company_id, user.id, roles)
        session.flush()
        record_audit(
            session,
            company_id,
            user_id=actor_id,
            action="user.update",
            resource_type="user",
            resource_id=user.id,
            before=before,
            after={"full_name": user.full_name, "is_active": user.is_active, "roles": assigned},
        )
        return _user_payload(user, assigned)

    store = get_store()
    user = store.get_user(company_id, user_id)
    if user is None:
        raise KeyError("User not found")
    before = {"full_name": user.full_name, "is_active": user.is_active, "roles": list(user.roles)}
    if full_name is not None:
        user.full_name = full_name
    if title is not None:
        user.title = title
    if is_active is not None:
        user.is_active = is_active
    if roles is not None:
        if not roles:
            raise ValueError("At least one role is required")
        user.roles = list(roles)
    record_audit(
        None,
        company_id,
        user_id=actor_id,
        action="user.update",
        resource_type="user",
        resource_id=user.id,
        before=before,
        after={"full_name": user.full_name, "is_active": user.is_active, "roles": user.roles},
    )
    return _memory_user_payload(user)


def assign_role(
    session: Optional[Session],
    company_id: str,
    user_id: str,
    role_name: str,
    *,
    actor_id: Optional[str],
) -> Dict[str, Any]:
    if session is not None:
        users = UserRepository(session, company_id)
        user = users.get(user_id)
        if user is None:
            raise KeyError("User not found")
        roles_repo = RoleRepository(session, company_id)
        role = roles_repo.get_by_name(role_name)
        if role is None:
            raise ValueError(f"Unknown role: {role_name}")
        existing = session.scalars(
            select(UserRole).where(
                UserRole.company_id == company_id,
                UserRole.user_id == user_id,
                UserRole.role_id == role.id,
            )
        ).first()
        if existing is None:
            session.add(
                UserRole(
                    company_id=company_id,
                    user_id=user_id,
                    role_id=role.id,
                    scope_type="tenant",
                )
            )
            session.flush()
        assigned = role_names_for_user(session, user.id)
        record_audit(
            session,
            company_id,
            user_id=actor_id,
            action="user.role.assign",
            resource_type="user",
            resource_id=user.id,
            after={"role": role_name},
        )
        return _user_payload(user, assigned)

    store = get_store()
    user = store.get_user(company_id, user_id)
    if user is None:
        raise KeyError("User not found")
    if role_name not in ROLE_PERMISSIONS:
        raise ValueError(f"Unknown role: {role_name}")
    if role_name not in user.roles:
        user.roles.append(role_name)
    record_audit(
        None,
        company_id,
        user_id=actor_id,
        action="user.role.assign",
        resource_type="user",
        resource_id=user.id,
        after={"role": role_name},
    )
    return _memory_user_payload(user)


def remove_role(
    session: Optional[Session],
    company_id: str,
    user_id: str,
    role_id: str,
    *,
    actor_id: Optional[str],
) -> Dict[str, Any]:
    if session is not None:
        users = UserRepository(session, company_id)
        user = users.get(user_id)
        if user is None:
            raise KeyError("User not found")
        assignment = session.scalars(
            select(UserRole).where(
                UserRole.company_id == company_id,
                UserRole.user_id == user_id,
                UserRole.role_id == role_id,
            )
        ).first()
        if assignment is None:
            raise KeyError("Role assignment not found")
        role_name = session.get(Role, role_id).name if session.get(Role, role_id) else role_id
        session.delete(assignment)
        session.flush()
        assigned = role_names_for_user(session, user.id)
        if not assigned:
            raise ValueError("User must retain at least one role")
        record_audit(
            session,
            company_id,
            user_id=actor_id,
            action="user.role.remove",
            resource_type="user",
            resource_id=user.id,
            after={"removed_role": role_name},
        )
        return _user_payload(user, assigned)

    store = get_store()
    user = store.get_user(company_id, user_id)
    if user is None:
        raise KeyError("User not found")
    if role_id not in user.roles:
        raise KeyError("Role assignment not found")
    user.roles = [r for r in user.roles if r != role_id]
    if not user.roles:
        raise ValueError("User must retain at least one role")
    record_audit(
        None,
        company_id,
        user_id=actor_id,
        action="user.role.remove",
        resource_type="user",
        resource_id=user.id,
        after={"removed_role": role_id},
    )
    return _memory_user_payload(user)


def get_audit_entries(
    session: Optional[Session],
    company_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
    action: Optional[str] = None,
) -> List[Dict[str, Any]]:
    return list_audit_logs(session, company_id, limit=limit, offset=offset, action=action)


def _assign_roles_db(
    session: Session, company_id: str, user_id: str, roles: List[str]
) -> List[str]:
    roles_repo = RoleRepository(session, company_id)
    assigned: List[str] = []
    for name in roles:
        role = roles_repo.get_by_name(name)
        if role is None:
            raise ValueError(f"Unknown role: {name}")
        session.add(
            UserRole(
                company_id=company_id,
                user_id=user_id,
                role_id=role.id,
                scope_type="tenant",
            )
        )
        assigned.append(name)
    session.flush()
    return assigned


def _replace_roles_db(
    session: Session, company_id: str, user_id: str, roles: List[str]
) -> List[str]:
    session.execute(
        delete(UserRole).where(
            UserRole.company_id == company_id,
            UserRole.user_id == user_id,
        )
    )
    return _assign_roles_db(session, company_id, user_id, roles)


def _user_payload(user: AppUser, roles: List[str]) -> Dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "title": user.title or "",
        "roles": roles,
        "is_active": user.is_active,
    }


def _memory_user_payload(user: StoredUser) -> Dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "title": user.title,
        "roles": list(user.roles),
        "is_active": user.is_active,
    }

