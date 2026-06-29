#!/usr/bin/env bash
# Start API for Playwright E2E (SQLite + demo seed, no pytest gate).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_DIR="$ROOT/apps/api"
VENV="$API_DIR/.venv"
DB_PATH="$ROOT/data/aurora_e2e.db"
API_PORT="${API_PORT:-8000}"

mkdir -p "$ROOT/data"

export DATABASE_URL="sqlite:///${DB_PATH}"
export DEMO_SEED_SCALE="${DEMO_SEED_SCALE:-0.1}"
export SEED_DEMO_ON_STARTUP="${SEED_DEMO_ON_STARTUP:-true}"

if [ ! -d "$VENV" ]; then
  python3 -m venv "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install -q --upgrade pip
pip install -q -e "$ROOT/packages/database" -e "$ROOT/packages/ml" -e "$ROOT/packages/graph"
pip install -q -e "$ROOT/packages/simulations" -e "$ROOT/packages/analytics" -e "$API_DIR[dev]"

echo "==> E2E API on http://127.0.0.1:${API_PORT}/api/v1 (SQLite: ${DB_PATH})"
cd "$API_DIR"
exec uvicorn aurora.main:app --host 0.0.0.0 --port "$API_PORT"
