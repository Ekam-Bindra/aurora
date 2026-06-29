"""Portable column types.

The canonical target is PostgreSQL (UUID + JSONB), but tests and laptop development run on
SQLite. These adapters render the native PostgreSQL type when connected to Postgres and a
portable fallback elsewhere, so the *same* models and migrations work on both.
"""

import uuid

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB as _PG_JSONB
from sqlalchemy.dialects.postgresql import UUID as _PG_UUID
from sqlalchemy.types import CHAR, TypeDecorator


class GUID(TypeDecorator):
    """UUID stored as PostgreSQL ``uuid`` natively, or ``CHAR(36)`` elsewhere.

    Values are always surfaced to Python as ``str`` so the application layer (JWT subjects,
    equality checks, JSON serialization) can treat ids uniformly.
    """

    impl = CHAR(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(_PG_UUID(as_uuid=False))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return str(value)


# JSONB on PostgreSQL, generic JSON elsewhere (e.g., SQLite).
JSONB = JSON().with_variant(_PG_JSONB(), "postgresql")


def new_uuid() -> str:
    """Generate a new UUID4 as a string (matches :class:`GUID` surface type)."""
    return str(uuid.uuid4())
