"""Run Alembic migrations without a checkout of alembic.ini.

``python -m aurora_db.migrate [--url URL] [--revision REV]``

Used by the one-off ECS migration task (the API image installs ``aurora_db``
but not the repo's alembic.ini) and handy anywhere the package is installed.
Falls back to ``DATABASE_URL`` / ``AURORA_DATABASE_URL`` when --url is omitted,
matching migrations/env.py.
"""

from __future__ import annotations

import argparse
import os
import sys
from argparse import Namespace
from pathlib import Path

from alembic import command
from alembic.config import Config


def build_config(url: str) -> Config:
    cfg = Config(cmd_opts=Namespace(x=[f"url={url}"]))
    cfg.set_main_option(
        "script_location", str(Path(__file__).resolve().parent / "migrations")
    )
    return cfg


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m aurora_db.migrate")
    parser.add_argument("--url", help="Database URL (default: $DATABASE_URL)")
    parser.add_argument("--revision", default="head", help="Target revision (default: head)")
    args = parser.parse_args(argv)

    url = args.url or os.environ.get("DATABASE_URL") or os.environ.get("AURORA_DATABASE_URL")
    if not url:
        print("ERROR: no database URL (pass --url or set DATABASE_URL)", file=sys.stderr)
        return 2

    command.upgrade(build_config(url), args.revision)
    print(f"Migrated to {args.revision}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
