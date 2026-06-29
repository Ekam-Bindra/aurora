"""Workspace endpoints.

Demonstrates the full stack working together: authentication, tenant scoping, and RBAC. The
``/users`` listing is permission-guarded (``manage:users``) and tenant-scoped, proving both the
authorization and isolation guarantees end to end.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ...core.errors import NotFound
from ...core.pagination import PaginationParams, paginate
from ...core.rbac import AuthContext, Permission
from ...deps import get_auth_context, get_user_store, require_permission
from ...domain.models import CompanyPublic, UserPublic
from ...repositories.facade import UserStore

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("/current", response_model=CompanyPublic)
def current_workspace(
    context: AuthContext = Depends(get_auth_context),
    store: UserStore = Depends(get_user_store),
) -> CompanyPublic:
    company = store.get_company(context.tenant_id)
    if company is None:
        raise NotFound("Workspace not found.")
    return CompanyPublic(
        id=company.id,
        name=company.name,
        slug=company.slug,
        industry=company.industry,
        base_currency=company.base_currency,
    )


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
