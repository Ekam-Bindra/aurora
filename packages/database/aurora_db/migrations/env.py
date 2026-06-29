"""Alembic environment.

Resolves the target database URL at runtime and points autogenerate at the full
``Base.metadata`` so future migrations diff against the ORM models.
"""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

# Make the package importable when alembic is invoked from packages/database.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import aurora_db.models  # noqa: E402,F401  (registers all tables on Base.metadata)
from aurora_db.base import Base  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_url() -> str:
    x_args = context.get_x_argument(as_dictionary=True)
    return (
        x_args.get("url")
        or os.environ.get("DATABASE_URL")
        or os.environ.get("AURORA_DATABASE_URL")
        or "sqlite:///./aurora_local.db"
    )


def run_migrations_offline() -> None:
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=url.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = _get_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    connectable = create_engine(
        url, poolclass=pool.NullPool, future=True, connect_args=connect_args
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=url.startswith("sqlite"),
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
