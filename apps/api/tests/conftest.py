"""Shared test fixtures. Each test gets a freshly-seeded demo tenant for isolation."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aurora.core.rbac import Role
from aurora.core.security import hash_password
from aurora.main import create_app
from aurora.repositories.memory import StoredCompany, StoredUser, get_store
from aurora.seed.demo import seed_demo

DEMO_PASSWORD = "test-password-123"


@pytest.fixture()
def store():
    s = get_store()
    seed_demo(s, DEMO_PASSWORD, force=True)
    return s


@pytest.fixture()
def client(store) -> TestClient:
    return TestClient(create_app())


def login(client: TestClient, email: str, password: str = DEMO_PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def auth_header(client: TestClient, email: str, password: str = DEMO_PASSWORD) -> dict:
    token = login(client, email, password).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def second_tenant(store):
    """Add a separate tenant to assert cross-tenant isolation."""
    other = store.add_company(
        StoredCompany(name="OtherCo", slug="otherco", industry="Other")
    )
    user = store.add_user(
        StoredUser(
            company_id=other.id,
            email="admin@otherco.test",
            full_name="Other Admin",
            title="System Administrator",
            password_hash=hash_password(DEMO_PASSWORD),
            roles=[Role.ADMIN],
        )
    )
    return other, user
