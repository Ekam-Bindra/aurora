# Local CI

Run the same checks as [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) before pushing.

## Prerequisites

- Python 3.11 (3.9+ works locally; CI uses 3.11)
- Node 20 + pnpm 9
- Optional: Postgres 16 for database job (SQLite/in-memory tests run without it)

From repo root, install Python packages once:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e packages/database -e packages/ml -e packages/graph \
  -e packages/simulations -e packages/analytics -e "apps/api[dev]"
pip install -e "packages/database[dev,postgres]"  # database job
```

## Per job

### API (`apps/api`)

```bash
cd apps/api
ruff check .
pytest -q
```

### Database (`packages/database`)

Requires Postgres (matches CI service):

```bash
export AURORA_PG_URL=postgresql+psycopg://aurora:aurora@localhost:5432/aurora
export AURORA_TEST_DB_URL="$AURORA_PG_URL"

cd packages/database
ruff check .
alembic -x url="$AURORA_PG_URL" upgrade head
python -m aurora_db.seed --demo nimbus --verify --url "$AURORA_PG_URL" --scale 1.0
pytest -q
```

Skip Postgres locally: `pytest -q` still runs in-memory tests.

### ML, Graph, Simulations, Analytics

```bash
cd packages/ml && ruff check . && pytest -q
cd packages/graph && ruff check . && pytest -q
cd packages/simulations && ruff check . && pytest -q
cd packages/analytics && ruff check . && pytest -q
```

Analytics imports `aurora_ml`; install `packages/database` and `packages/ml` first.

### Web (`apps/web`)

```bash
export NEXT_PUBLIC_API_URL=http://localhost/api/v1
pnpm install --frozen-lockfile
pnpm --filter @aurora/web build
pnpm --filter @aurora/web lint   # optional; not in CI yet
```

## All Python checks (quick)

```bash
for d in apps/api packages/database packages/ml packages/graph packages/simulations packages/analytics; do
  echo "=== $d ==="
  (cd "$d" && ruff check . && pytest -q) || exit 1
done
```
