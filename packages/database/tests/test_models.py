"""Schema-level guarantees: FK cascade (the seeder's idempotent wipe) and tenant-unique email."""

from __future__ import annotations

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from aurora_db.models import AppUser, Company, Role


def _make_company(session, slug: str) -> Company:
    company = Company(name=slug.title(), slug=slug)
    session.add(company)
    session.flush()
    return company


def test_delete_company_cascades_to_tenant_rows(session):
    """A bulk ``DELETE FROM company`` must remove all tenant-scoped rows.

    This is exactly the path the seeder uses to re-seed idempotently, and it depends on DB-level
    ``ON DELETE CASCADE`` (native on Postgres, enabled via PRAGMA on SQLite by ``make_engine``).
    """
    company = _make_company(session, "cascade-co")
    session.add(Role(company_id=company.id, name="CEO", permissions=["read:financials"]))
    session.add(
        AppUser(
            company_id=company.id,
            email="user@cascade.test",
            full_name="Cascade User",
            password_hash="x",
        )
    )
    session.flush()

    session.execute(delete(Company).where(Company.id == company.id))
    session.flush()

    assert session.scalar(select(func.count()).select_from(Company)) == 0
    assert session.scalar(select(func.count()).select_from(AppUser)) == 0
    assert session.scalar(select(func.count()).select_from(Role)) == 0


def test_email_is_unique_within_a_tenant(session):
    company = _make_company(session, "unique-co")
    session.add(
        AppUser(company_id=company.id, email="dup@x.test", full_name="First", password_hash="x")
    )
    session.flush()
    session.add(
        AppUser(company_id=company.id, email="dup@x.test", full_name="Second", password_hash="y")
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_same_email_allowed_in_different_tenants(session):
    a = _make_company(session, "tenant-a")
    b = _make_company(session, "tenant-b")
    session.add(
        AppUser(company_id=a.id, email="shared@x.test", full_name="A User", password_hash="x")
    )
    session.add(
        AppUser(company_id=b.id, email="shared@x.test", full_name="B User", password_hash="y")
    )
    session.flush()  # no IntegrityError: uniqueness is (company_id, email)
    assert session.scalar(select(func.count()).select_from(AppUser)) == 2
