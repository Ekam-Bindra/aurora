"""Database engine/session lifecycle (when ``DATABASE_URL`` is set).

Phase 2 persistence lives in ``aurora_db``; this module binds it to the FastAPI app lifecycle.
When no URL is configured the API falls back to the in-memory store (Phase 1 / tests).
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Optional

from aurora_db.base import Base
from aurora_db.session import make_engine, make_session_factory
from sqlalchemy.orm import Session, sessionmaker

_engine = None
_session_factory: Optional[sessionmaker] = None
_database_url: Optional[str] = None


def init_database(url: str, *, create_tables: bool = False) -> None:
    """Initialize the global engine + session factory. Safe to call once at startup."""
    global _engine, _session_factory, _database_url
    _engine = make_engine(url)
    if create_tables and url.startswith("sqlite"):
        Base.metadata.create_all(_engine)
    _session_factory = make_session_factory(_engine)
    _database_url = url


def is_database_enabled() -> bool:
    return _session_factory is not None


def get_database_url() -> Optional[str]:
    return _database_url


def get_session_factory() -> Optional[sessionmaker]:
    return _session_factory


def dispose_database() -> None:
    global _engine, _session_factory, _database_url
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
    _database_url = None


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Transactional scope for startup seeding / one-off jobs."""
    if _session_factory is None:
        raise RuntimeError("Database is not initialized.")
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
