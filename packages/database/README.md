# @aurora/database (`aurora_db`)

The **Unified Company Data Model (Module 2)** for AURORA: SQLAlchemy 2.0 models, Alembic
migrations, tenant-scoped repositories, and the deterministic **"Nimbus Retail Systems"** demo
seeder. `apps/api` consumes this package behind its repository interface.

> Design source of truth: [`docs/data-model/data-model.md`](../../docs/data-model/data-model.md)
> and [`docs/data-model/demo-dataset-spec.md`](../../docs/data-model/demo-dataset-spec.md).

## What's here

```
aurora_db/
├── base.py          # DeclarativeBase + stable naming convention
├── types.py         # portable GUID (PG uuid / CHAR36) + JSONB variant
├── mixins.py        # UUID PK, timestamps, TenantScopedMixin (company_id)
├── session.py       # engine/session factories + transactional scope
├── models/          # all 25 tables across the 5 entity groups
├── repositories.py  # TenantScopedRepository + concrete repositories
├── seed/            # personas + Nimbus generator + verification + CLI
└── migrations/      # Alembic env + initial baseline migration
```

## Portability

The canonical target is **PostgreSQL** (native `uuid` + `jsonb`). Tests and laptop development
run on **SQLite** via portable column types, so the same models and migrations work on both.

## Common commands

```bash
pip install -e ".[dev,postgres]"

# Apply migrations (defaults to a local sqlite file; override with -x url=... or $DATABASE_URL)
alembic upgrade head
alembic -x url="postgresql+psycopg://aurora:aurora@localhost:5432/aurora" upgrade head

# Seed / re-seed the Nimbus demo tenant (idempotent; only touches the 'nimbus' tenant)
python -m aurora_db.seed --demo nimbus --url "postgresql+psycopg://aurora:aurora@localhost:5432/aurora"
python -m aurora_db.seed --verify --url "..."     # run the §7.3 self-checks

# Tests (SQLite, in-memory)
pytest
```

## Multi-tenancy

Every business table carries an indexed, FK-backed `company_id` (`TenantScopedMixin`). The
repository layer filters on it for **every** read; optional PostgreSQL RLS is the defense-in-depth
backstop (Data Model §4.1). The only intentionally global lookup is `get_user_by_email` (used at
login, before a tenant is known).
