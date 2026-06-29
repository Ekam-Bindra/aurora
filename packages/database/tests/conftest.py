"""Shared fixtures for the persistence test-suite.

Portable by design: tests run against a temporary SQLite file by default, or any database
pointed to by ``AURORA_TEST_DB_URL`` (CI sets this to the Postgres service). The schema is
created once per session; each test gets its own session and is rolled back afterwards, so
tests stay isolated without paying for a schema rebuild per test.
"""

from __future__ import annotations

import os

import pytest

from aurora_db import Base, make_engine, make_session_factory


@pytest.fixture(scope="session")
def db_url(tmp_path_factory) -> str:
    url = os.environ.get("AURORA_TEST_DB_URL")
    if url:
        return url
    path = tmp_path_factory.mktemp("aurora-db") / "test.db"
    return f"sqlite:///{path}"


@pytest.fixture(scope="session")
def engine(db_url):
    eng = make_engine(db_url)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture()
def session(engine):
    """A fresh session per test. Work is rolled back on teardown for isolation."""
    factory = make_session_factory(engine)
    db = factory()
    try:
        yield db
    finally:
        db.rollback()
        db.close()
