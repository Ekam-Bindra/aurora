"""AURORA Unified Company Data Model (Module 2).

SQLAlchemy 2.0 models, Alembic migrations, tenant-scoped repositories, and the deterministic
"Nimbus Retail Systems" demo seeder. ``apps/api`` consumes this package behind its repository
interface (docs/architecture/folder-structure.md §4.4).
"""

from .base import Base
from .session import make_engine, make_session_factory, session_scope
from .types import GUID, JSONB, new_uuid

__all__ = [
    "Base",
    "make_engine",
    "make_session_factory",
    "session_scope",
    "GUID",
    "JSONB",
    "new_uuid",
]

__version__ = "0.1.0"
