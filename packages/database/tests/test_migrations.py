"""The Alembic baseline must build the full schema and cleanly tear it back down.

Runs against a throwaway SQLite file regardless of ``AURORA_TEST_DB_URL`` (passed via alembic's
``-x url=`` which takes top priority in env.py), so it stays fast and self-contained. CI also runs
``alembic upgrade head`` against the real Postgres service as a separate step.
"""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from aurora_db import Base

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def _alembic_config(url: str) -> Config:
    cfg = Config(str(PACKAGE_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PACKAGE_ROOT / "aurora_db" / "migrations"))
    # -x url=... is highest priority in env.py, so this ignores any ambient DATABASE_URL.
    cfg.cmd_opts = Namespace(x=[f"url={url}"])
    return cfg


def _table_names(url: str) -> set:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_upgrade_head_then_downgrade_base(tmp_path):
    url = f"sqlite:///{tmp_path / 'migrate.db'}"
    cfg = _alembic_config(url)

    command.upgrade(cfg, "head")
    after_upgrade = _table_names(url)
    expected = set(Base.metadata.tables.keys())
    assert expected.issubset(after_upgrade), expected - after_upgrade
    assert "alembic_version" in after_upgrade

    command.downgrade(cfg, "base")
    after_downgrade = _table_names(url) - {"alembic_version"}
    assert after_downgrade == set()


def test_migrate_module_reaches_head_without_checkout(tmp_path):
    """`python -m aurora_db.migrate` must work from just the installed package
    (no alembic.ini) — it is the container/one-off-ECS-task migration path."""
    from aurora_db.migrate import main

    url = f"sqlite:///{tmp_path / 'module.db'}"
    assert main(["--url", url]) == 0
    tables = _table_names(url)
    assert "ingestion_job" in tables  # 0002 artifact
    assert "alembic_version" in tables
