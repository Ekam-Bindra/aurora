"""Database engine/session lifecycle (when ``DATABASE_URL`` is set).

Phase 2 persistence lives in ``aurora_db``; this module binds it to the FastAPI app lifecycle.
When no URL is configured the API falls back to the in-memory store (Phase 1 / tests).
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from aurora_db.base import Base
from aurora_db.session import make_engine, make_session_factory
from sqlalchemy.orm import Session, sessionmaker

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _normalize_database_url(url: str) -> str:
    """Resolve relative SQLite paths from the monorepo root and ensure parent dirs exist."""
    if not url.startswith("sqlite"):
        return url
    if ":memory:" in url:
        return url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return url
    raw = url[len(prefix):]
    if raw.startswith("./"):
        path = (_REPO_ROOT / raw[2:]).resolve()
    elif raw.startswith("/"):
        path = Path(raw)
    else:
        path = Path(raw).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"

_engine = None
_session_factory: Optional[sessionmaker] = None
_database_url: Optional[str] = None


def _upgrade_sqlite_schema(url: str) -> None:
    """Bring a file-backed SQLite dev database to the current Alembic head.

    ``create_all`` only adds missing *tables*, so column-adding revisions
    (e.g. 0002's ``board_report.content``) never reach long-lived local files
    like ``data/aurora_e2e.db`` without running real migrations.
    """
    from alembic import command
    from aurora_db.migrate import build_config

    command.upgrade(build_config(url), "head")


def init_database(url: str, *, create_tables: bool = False) -> None:
    """Initialize the global engine + session factory. Safe to call once at startup."""
    global _engine, _session_factory, _database_url
    url = _normalize_database_url(url)
    _engine = make_engine(url)
    if create_tables and url.startswith("sqlite"):
        if ":memory:" in url:
            Base.metadata.create_all(_engine)
        else:
            _upgrade_sqlite_schema(url)
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
