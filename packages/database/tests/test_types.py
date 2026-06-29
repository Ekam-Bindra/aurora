"""Portable column types: GUID primary keys and JSON(B) round-trips behave identically
across SQLite and Postgres."""

from __future__ import annotations

import uuid

from aurora_db import new_uuid
from aurora_db.models import Company


def test_new_uuid_is_a_canonical_uuid_string():
    value = new_uuid()
    assert isinstance(value, str)
    # Parses as a UUID and normalises back to the same 36-char hyphenated form.
    assert str(uuid.UUID(value)) == value
    assert len(value) == 36


def test_guid_primary_key_is_str_after_flush(session):
    company = Company(name="Acme", slug="acme")
    session.add(company)
    session.flush()
    assert isinstance(company.id, str)
    assert str(uuid.UUID(company.id)) == company.id


def test_jsonb_dict_roundtrips(session):
    payload = {"seed": 42, "scale": 1.0, "nested": {"flags": [1, 2, 3]}, "on": True}
    company = Company(name="JsonCo", slug="jsonco", settings=payload)
    session.add(company)
    session.flush()
    session.expire(company)  # force a fresh load from the database

    loaded = session.get(Company, company.id)
    assert loaded is not None
    assert loaded.settings == payload
    assert loaded.settings["nested"]["flags"] == [1, 2, 3]
