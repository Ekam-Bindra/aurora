#!/usr/bin/env bash
# Local dev: SQLite persistence + API (no Docker required).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_DIR="$ROOT/apps/api"
VENV="$API_DIR/.venv"
DB_PATH="$ROOT/data/aurora_local.db"

mkdir -p "$ROOT/data"

export DATABASE_URL="sqlite:///${DB_PATH}"
export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-http://localhost:8000/api/v1}"

echo "==> AURORA local run"
echo "    Database: $DATABASE_URL"
echo "    API:      http://localhost:8000/api/v1"
echo "    Docs:     http://localhost:8000/api/v1/docs"
echo ""

if [ ! -d "$VENV" ]; then
  echo "==> Creating Python venv at apps/api/.venv"
  python3 -m venv "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install -q --upgrade pip
pip install -q -e "$ROOT/packages/database"
pip install -q -e "$ROOT/packages/ml"
pip install -q -e "$ROOT/packages/graph"
pip install -q -e "$API_DIR[dev]"

echo "==> Running API tests (in-memory mode)"
cd "$API_DIR"
# Tests intentionally omit DATABASE_URL so they stay fast and isolated.
unset DATABASE_URL
pytest -q

echo ""
echo "==> Starting API (SQLite + auto-seed at scale 0.1)"
export DATABASE_URL="sqlite:///${DB_PATH}"
echo "    Demo login: cfo@nimbus.test / aurora-demo-2026"
echo ""

exec uvicorn aurora.main:app --reload --host 0.0.0.0 --port 8000
