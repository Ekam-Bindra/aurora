#!/usr/bin/env bash
# Local dev: SQLite persistence + API (no Docker required).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_DIR="$ROOT/apps/api"
VENV="$API_DIR/.venv"
DB_PATH="$ROOT/data/aurora_local.db"
DEBUG_LOG="$ROOT/.cursor/debug-dbff07.log"
API_PORT="${API_PORT:-8000}"
API_BASE="http://localhost:${API_PORT}/api/v1"

# #region agent log
_agent_log() {
  local hypothesis_id="$1" message="$2" data_json="${3:-{}}"
  python3 -c "
import json, time
entry = {
    'sessionId': 'dbff07',
    'hypothesisId': '$hypothesis_id',
    'location': 'scripts/local-run.sh',
    'message': '$message',
    'data': $data_json,
    'timestamp': int(time.time() * 1000),
}
with open('$DEBUG_LOG', 'a') as f:
    f.write(json.dumps(entry) + '\n')
" 2>/dev/null || true
}
# #endregion

mkdir -p "$ROOT/data"
mkdir -p "$ROOT/.cursor"

export DATABASE_URL="sqlite:///${DB_PATH}"
export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-${API_BASE}}"

echo "==> AURORA local run"
echo "    Database: $DATABASE_URL"
echo "    API:      $API_BASE"
echo "    Docs:     ${API_BASE}/docs"
echo "    Web UI:   http://localhost:3000 (run: cd apps/web && pnpm dev)"
echo ""
echo "    NOTE: http://localhost (port 80) only works with Docker/nginx."
echo "          Use port ${API_PORT} for the API and port 3000 for the web app."
echo ""

# #region agent log
_agent_log "H3" "local-run_start" "{\"api_port\":$API_PORT,\"cwd\":\"$(pwd)\"}"
# #endregion

if curl -sf "${API_BASE}/health" >/dev/null 2>&1; then
  echo "==> API already running at ${API_BASE}"
  echo "    Open docs: ${API_BASE}/docs"
  echo "    Demo login: cfo@nimbus.test / aurora-demo-2026"
  # #region agent log
  _agent_log "H3" "api_already_healthy" "{\"url\":\"${API_BASE}/health\"}"
  # #endregion
  exit 0
fi

if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"$API_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "ERROR: Port $API_PORT is in use but the API health check failed."
  echo "       Kill the stale process or set API_PORT=8001 and retry."
  # #region agent log
  _agent_log "H4" "port_in_use_not_healthy" "{\"port\":$API_PORT}"
  # #endregion
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

# #region agent log
_agent_log "H3" "starting_uvicorn" "{\"port\":$API_PORT}"
# #endregion

exec uvicorn aurora.main:app --reload --host 0.0.0.0 --port "$API_PORT"
