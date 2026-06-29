"""Engine and session helpers.

Phase 2 uses synchronous SQLAlchemy 2.0 (FastAPI runs sync route handlers in a threadpool),
which keeps the existing endpoints unchanged. ``make_engine`` applies the small SQLite tweaks
needed for tests/laptop use; production points at PostgreSQL via ``postgresql+psycopg``.
"""

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def make_engine(url: str, *, echo: bool = False) -> Engine:
    connect_args = {}
    if url.startswith("sqlite"):
        # Allow cross-thread use (FastAPI threadpool / TestClient) on SQLite.
        connect_args["check_same_thread"] = False
    engine = create_engine(
        url,
        echo=echo,
        future=True,
        pool_pre_ping=not url.startswith("sqlite"),
        connect_args=connect_args,
    )
    if url.startswith("sqlite"):
        # SQLite ignores FKs unless explicitly enabled; turn them on so ON DELETE CASCADE
        # (used by tenant teardown/re-seed) behaves like PostgreSQL.
        @event.listens_for(engine, "connect")
        def _fk_pragma(dbapi_connection, _record):  # pragma: no cover - trivial
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def make_session_factory(engine: Engine) -> "sessionmaker[Session]":
    return sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
        future=True,
        class_=Session,
    )


@contextmanager
def session_scope(session_factory: "sessionmaker[Session]") -> Iterator[Session]:
    """Transactional scope: commit on success, roll back on error, always close."""
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
