"""Auth request/response schemas (docs/api/api-specification.md §2)."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class CompanyClaim(BaseModel):
    id: str
    name: str
    slug: str


class AuthUser(BaseModel):
    id: str
    full_name: str
    email: str
    title: str
    company: CompanyClaim
    roles: List[str]
    permissions: List[str]


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: AuthUser


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
