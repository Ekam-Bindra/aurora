"""The repository layer is the enforcement point for multi-tenant isolation: every read is
scoped to one ``company_id``, with a single documented exception (login-by-email)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from aurora_db.models import AppUser, Company, Customer, Role, UserRole
from aurora_db.repositories import (
    CompanyRepository,
    CustomerRepository,
    RoleRepository,
    UserRepository,
    role_names_for_user,
)


@dataclass
class Tenant:
    company: Company
    user: AppUser
    role: Role
    customer: Customer


def _provision(session, slug: str, email: str, role_name: str) -> Tenant:
    company = Company(name=slug.title(), slug=slug)
    session.add(company)
    session.flush()

    role = Role(company_id=company.id, name=role_name, permissions=["read:financials"])
    session.add(role)
    session.flush()

    user = AppUser(
        company_id=company.id, email=email, full_name=f"{slug} user", password_hash="x"
    )
    session.add(user)
    session.flush()

    session.add(UserRole(company_id=company.id, user_id=user.id, role_id=role.id))
    customer = Customer(company_id=company.id, name=f"{slug} customer")
    session.add(customer)
    session.flush()
    return Tenant(company, user, role, customer)


@pytest.fixture()
def two_tenants(session):
    a = _provision(session, "acme", "admin@acme.test", "CEO")
    b = _provision(session, "globex", "admin@globex.test", "CFO")
    return a, b


def test_list_and_count_are_tenant_scoped(session, two_tenants):
    a, b = two_tenants
    repo = CustomerRepository(session, a.company.id)
    listed = repo.list()
    assert [c.id for c in listed] == [a.customer.id]
    assert repo.count() == 1


def test_get_across_tenant_returns_none(session, two_tenants):
    a, b = two_tenants
    repo = CustomerRepository(session, a.company.id)
    # b's customer exists, but is invisible through a's repository.
    assert repo.get(b.customer.id) is None
    assert repo.get(a.customer.id) is not None


def test_get_user_by_email_is_global_for_login(session, two_tenants):
    a, b = two_tenants
    # Login happens before a tenant is known, so this lookup intentionally crosses tenants.
    found = UserRepository(session, a.company.id).get_by_email("ADMIN@GLOBEX.TEST")
    assert found is not None
    assert found.id == b.user.id


def test_role_lookup_and_names_for_user(session, two_tenants):
    a, _ = two_tenants
    assert RoleRepository(session, a.company.id).get_by_name("CEO").id == a.role.id
    assert role_names_for_user(session, a.user.id) == ["CEO"]


def test_company_repository_by_slug(session, two_tenants):
    a, b = two_tenants
    repo = CompanyRepository(session)
    assert repo.get_by_slug("globex").id == b.company.id
    assert repo.get(a.company.id).slug == "acme"
