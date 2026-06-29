"""The Nimbus seeder: it must be idempotent, produce authenticatable personas, and satisfy the
docs/data-model/demo-dataset-spec.md §7.3 self-checks (including all volume bands at full scale)."""

from __future__ import annotations

import base64
import hashlib
import hmac

from sqlalchemy import func, select

from aurora_db.models import AppUser, Company, Role
from aurora_db.seed import (
    DEMO_SLUG,
    PERSONAS,
    all_passed,
    seed_nimbus,
    verify,
)


def _failed(checks):
    return [f"{c.name}: expected {c.expected}, got {c.actual}" for c in checks if not c.passed]


def _verify_password(password: str, encoded: str) -> bool:
    algo, iterations, salt_b64, dk_b64 = encoded.split("$")
    assert algo == "pbkdf2_sha256"

    def _unb64(value: str) -> bytes:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), _unb64(salt_b64), int(iterations))
    return hmac.compare_digest(dk, _unb64(dk_b64))


def test_seed_scaled_passes_core_checks(session):
    """A small dataset is cheap and still exercises every anomaly and concentration check."""
    result = seed_nimbus(session, scale=0.25)
    checks = verify(session, result["company_id"], full=False)
    assert all_passed(checks), _failed(checks)


def test_seed_full_scale_passes_all_checks(session):
    """Canonical guarantee: the full Nimbus dataset satisfies every §7.3 band by construction."""
    result = seed_nimbus(session, scale=1.0)
    checks = verify(session, result["company_id"], full=True)
    assert all_passed(checks), _failed(checks)
    # Sanity-check that the full run really did exercise the volume bands.
    assert any(c.name == "Invoices" for c in checks)


def test_seed_is_idempotent(session):
    first = seed_nimbus(session, scale=0.2, seed=7)
    second = seed_nimbus(session, scale=0.2, seed=7)

    # Re-seeding wipes and recreates the tenant rather than duplicating it.
    company_count = session.scalar(
        select(func.count()).select_from(Company).where(Company.slug == DEMO_SLUG)
    )
    assert company_count == 1
    assert first["counts"] == second["counts"]


def test_personas_seeded_and_authenticatable(session):
    password = "unit-test-pw"
    result = seed_nimbus(session, scale=0.2, password=password)
    cid = result["company_id"]

    users = session.scalars(select(AppUser).where(AppUser.company_id == cid)).all()
    assert len(users) == len(PERSONAS) == 8

    ceo = session.scalars(
        select(AppUser).where(AppUser.company_id == cid, AppUser.email == "ceo@nimbus.test")
    ).first()
    assert ceo is not None
    assert _verify_password(password, ceo.password_hash)
    assert not _verify_password("wrong-password", ceo.password_hash)


def test_roles_persist_permission_matrix(session):
    result = seed_nimbus(session, scale=0.2)
    ceo_role = session.scalars(
        select(Role).where(Role.company_id == result["company_id"], Role.name == "CEO")
    ).first()
    assert ceo_role is not None
    assert "read:financials" in ceo_role.permissions
    assert ceo_role.is_system is True
