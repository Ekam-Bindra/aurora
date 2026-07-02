#!/usr/bin/env bash
# Local dev: SQLite persistence + API (no Docker required).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_DIR="$ROOT/apps/api"
VENV="$API_DIR/.venv"
DB_PATH="$ROOT/data/aurora_local.db"
API_PORT="${API_PORT:-8000}"
API_ROOT="http://127.0.0.1:${API_PORT}"
API_BASE="${API_ROOT}/api/v1"

_api_health_ok() {
  curl -sf "${API_BASE}/health" >/dev/null 2>&1
}

_api_root_redirects() {
  local code
  code="$(curl -s -o /dev/null -w "%{http_code}" "${API_ROOT}/")"
  [[ "$code" == "307" || "$code" == "302" ]]
}

_stop_api_on_port() {
  if command -v lsof >/dev/null 2>&1; then
    local pids
    pids="$(lsof -t -iTCP:"$API_PORT" -sTCP:LISTEN 2>/dev/null || true)"
    if [ -n "$pids" ]; then
      echo "==> Stopping process(es) on port $API_PORT: $pids"
      kill $pids 2>/dev/null || true
      sleep 1
    fi
  fi
}

mkdir -p "$ROOT/data"

export DATABASE_URL="sqlite:///${DB_PATH}"
export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-${API_BASE}}"

echo "==> AURORA local run"
echo "    Database: $DATABASE_URL"
echo "    API:      $API_BASE"
echo "    Docs:     ${API_BASE}/docs  (or http://localhost:${API_PORT} → redirects)"
echo "    Web UI:   http://localhost:3000  →  ./scripts/dev-web.sh"
echo ""

if _api_health_ok && _api_root_redirects; then
  echo "==> API already running (healthy + up to date) at ${API_BASE}"
  echo "    Demo login: cfo@nimbus.test / aurora-demo-2026"
  exit 0
fi

if _api_health_ok && ! _api_root_redirects; then
  echo "==> Stale API detected (health OK but missing root → docs redirect). Restarting..."
  _stop_api_on_port
elif command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"$API_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "ERROR: Port $API_PORT is in use but health check failed."
  echo "       Run: lsof -i :$API_PORT  then kill the PID, or set API_PORT=8001"
  exit 1
fi

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
pip install -q -e "$ROOT/packages/simulations"
pip install -q -e "$ROOT/packages/analytics"
pip install -q -e "$API_DIR[dev]"

echo "==> Running API tests (in-memory mode)"
cd "$API_DIR"
unset DATABASE_URL
pytest -q

echo ""
echo "==> Starting API (SQLite + auto-seed at scale 0.1)"
export DATABASE_URL="sqlite:///${DB_PATH}"
echo "    Demo login: cfo@nimbus.test / aurora-demo-2026"
echo ""

exec uvicorn aurora.main:app --reload --host 0.0.0.0 --port "$API_PORT"
