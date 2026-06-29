"""Admin console API routes (Phase 8)."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.errors import NotFound, ValidationError
from ...core.logging import get_request_id
from ...core.pagination import PaginationParams, paginate
from ...core.rbac import AuthContext, Permission
from ...deps import get_db_session, get_user_store, require_permission
from ...domain.models import UserPublic
from ...repositories.facade import UserStore
from ...services.admin import (
    assign_role,
    create_user,
    get_audit_entries,
    list_roles,
    remove_role,
    update_user,
)

router = APIRouter(tags=["admin"])


class UserCreate(BaseModel):
    email: str
    full_name: str
    title: str = ""
    roles: List[str] = Field(default_factory=list)
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    title: Optional[str] = None
    is_active: Optional[bool] = None
    roles: Optional[List[str]] = None


class RoleAssign(BaseModel):
    role: str
    scope_type: str = "tenant"
    scope_id: Optional[str] = None


@router.get("/users")
def list_users(
    params: PaginationParams = Depends(),
    context: AuthContext = Depends(require_permission(Permission.MANAGE_USERS)),
    store: UserStore = Depends(get_user_store),
) -> dict:
    users = [
        UserPublic(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            title=u.title,
            roles=u.roles,
            is_active=u.is_active,
        ).model_dump()
        for u in store.list_users(context.tenant_id)
    ]
    return paginate(users, params)


@router.post("/users", status_code=status.HTTP_201_CREATED)
def post_user(
    body: UserCreate,
    context: AuthContext = Depends(require_permission(Permission.MANAGE_USERS)),
    session: Optional[Session] = Depends(get_db_session),
) -> dict:
    try:
        data = create_user(
            session,
            context.tenant_id,
            email=body.email,
            full_name=body.full_name,
            title=body.title,
            roles=body.roles,
            password=body.password,
            actor_id=context.user_id,
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    return {"data": data, "meta": {"request_id": get_request_id()}}


@router.patch("/users/{user_id}")
def patch_user(
    user_id: str,
    body: UserUpdate,
    context: AuthContext = Depends(require_permission(Permission.MANAGE_USERS)),
    session: Optional[Session] = Depends(get_db_session),
) -> dict:
    try:
        data = update_user(
            session,
            context.tenant_id,
            user_id,
            full_name=body.full_name,
            title=body.title,
            is_active=body.is_active,
            roles=body.roles,
            actor_id=context.user_id,
        )
    except KeyError as exc:
        raise NotFound("User not found") from exc
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    return {"data": data, "meta": {"request_id": get_request_id()}}


@router.get("/roles")
def get_roles(
    context: AuthContext = Depends(require_permission(Permission.MANAGE_USERS)),
    session: Optional[Session] = Depends(get_db_session),
) -> dict:
    items = list_roles(session, context.tenant_id)
    return {"data": items, "meta": {"request_id": get_request_id()}}


@router.post("/users/{user_id}/roles", status_code=status.HTTP_201_CREATED)
def post_user_role(
    user_id: str,
    body: RoleAssign,
    context: AuthContext = Depends(require_permission(Permission.MANAGE_USERS)),
    session: Optional[Session] = Depends(get_db_session),
) -> dict:
    try:
        data = assign_role(
            session,
            context.tenant_id,
            user_id,
            body.role,
            actor_id=context.user_id,
        )
    except KeyError as exc:
        raise NotFound("User not found") from exc
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    return {"data": data, "meta": {"request_id": get_request_id()}}


@router.delete("/users/{user_id}/roles/{role_id}", status_code=status.HTTP_200_OK)
def delete_user_role(
    user_id: str,
    role_id: str,
    context: AuthContext = Depends(require_permission(Permission.MANAGE_USERS)),
    session: Optional[Session] = Depends(get_db_session),
) -> dict:
    try:
        data = remove_role(
            session,
            context.tenant_id,
            user_id,
            role_id,
            actor_id=context.user_id,
        )
    except KeyError as exc:
        raise NotFound("User or role assignment not found") from exc
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    return {"data": data, "meta": {"request_id": get_request_id()}}


@router.get("/audit-logs")
def get_audit_logs(
    params: PaginationParams = Depends(),
    action: Optional[str] = Query(None),
    context: AuthContext = Depends(require_permission(Permission.VIEW_AUDIT_LOG)),
    session: Optional[Session] = Depends(get_db_session),
) -> dict:
    items = get_audit_entries(
        session,
        context.tenant_id,
        limit=params.page_size,
        offset=params.offset,
        action=action,
    )
    return paginate(items, params)
