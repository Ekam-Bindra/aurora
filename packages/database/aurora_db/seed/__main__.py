"""CLI: seed and/or verify the Nimbus demo tenant.

Examples
--------
    python -m aurora_db.seed --demo nimbus --url "postgresql+psycopg://aurora:aurora@localhost/aurora"
    python -m aurora_db.seed --demo nimbus --verify    # seed then self-check (sqlite fallback)
    python -m aurora_db.seed --verify                  # check an already-seeded tenant
"""  # noqa: E501  (the connection-string example is intentionally shown on one line)

import argparse
import os
import sys

from sqlalchemy import select

from ..base import Base
from ..models import Company
from ..session import make_engine, make_session_factory, session_scope
from .nimbus import DEMO_SLUG, all_passed, seed_nimbus, verify


def _resolve_url(cli_url: str) -> str:
    return (
        cli_url
        or os.environ.get("DATABASE_URL")
        or os.environ.get("AURORA_DATABASE_URL")
        or "sqlite:///./aurora_local.db"
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="aurora-db", description="AURORA database seeder")
    parser.add_argument("--demo", metavar="TENANT", help="seed the demo tenant (only 'nimbus')")
    parser.add_argument("--verify", action="store_true", help="run the §7.3 self-checks")
    parser.add_argument("--url", default="", help="DB URL (else $DATABASE_URL / sqlite fallback)")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed (default 42)")
    parser.add_argument("--scale", type=float, default=1.0, help="volume scale (1.0 = full spec)")
    parser.add_argument("--password", default="aurora-demo-2026", help="demo login password")
    parser.add_argument(
        "--create-all",
        action="store_true",
        help="create tables from metadata first (use when not applying Alembic migrations)",
    )
    args = parser.parse_args()

    url = _resolve_url(args.url)
    engine = make_engine(url)
    if args.create_all:
        Base.metadata.create_all(engine)
    session_factory = make_session_factory(engine)

    exit_code = 0
    with session_scope(session_factory) as session:
        company_id = None
        if args.demo:
            if args.demo != "nimbus":
                parser.error("only --demo nimbus is supported")
            result = seed_nimbus(
                session, seed=args.seed, scale=args.scale, password=args.password
            )
            company_id = result["company_id"]
            print(f"Seeded '{DEMO_SLUG}' (scale={args.scale}). Demo password: {args.password}")
            print("Persona logins:")
            for email, role in result["logins"]:
                print(f"  {email:<24} {role}")
            if result.get("counts"):
                print("Row counts:", result["counts"])

        if args.verify:
            if company_id is None:
                company = session.scalars(
                    select(Company).where(Company.slug == DEMO_SLUG)
                ).first()
                if company is None:
                    parser.error("nimbus tenant not found — seed it first")
                company_id = company.id
            checks = verify(session, company_id, full=args.scale >= 1.0)
            print("\nVerification (docs/data-model/demo-dataset-spec.md §7.3):")
            for check in checks:
                mark = "PASS" if check.passed else "FAIL"
                print(
                    f"  [{mark}] {check.name:<34} expected {check.expected:<14} got {check.actual}"
                )
            if not all_passed(checks):
                exit_code = 1
                print("\nVERIFICATION FAILED")
            else:
                print("\nAll checks passed.")

    engine.dispose()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
