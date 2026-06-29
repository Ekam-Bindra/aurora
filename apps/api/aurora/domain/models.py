"""API-facing domain models.

These mirror a subset of the Unified Company Data Model (docs/data-model/data-model.md). In
Phase 1 they are populated from the in-memory store; in Phase 2 they will be projected from the
SQLAlchemy entities. Public models never expose secrets (e.g., password hashes).
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel


class CompanyPublic(BaseModel):
    id: str
    name: str
    slug: str
    industry: str
    base_currency: str


class UserPublic(BaseModel):
    id: str
    email: str
    full_name: str
    title: str
    roles: List[str]
    is_active: bool


class RolePublic(BaseModel):
    name: str
    permissions: List[str]
