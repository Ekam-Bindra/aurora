"""initial baseline schema (Unified Company Data Model)

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-28

This baseline creates the entire schema from ``Base.metadata``. We deliberately use a
metadata-create baseline (rather than 25 hand-written ``op.create_table`` blocks) so that:

* the schema is always in lock-step with the SQLAlchemy models, and
* portable column types render per-dialect (PostgreSQL ``uuid``/``jsonb``; ``CHAR(36)``/``json``
  on SQLite).

Subsequent migrations are generated normally with ``alembic revision --autogenerate``, diffing
against the same ``Base.metadata``.
"""

from alembic import op

import aurora_db.models  # noqa: F401  (registers all tables on Base.metadata)
from aurora_db.base import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(op.get_bind())
