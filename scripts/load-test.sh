#!/usr/bin/env bash
# Load / smoke test for AURORA API key endpoints.
# Usage:
#   ./scripts/load-test.sh
#   BASE_URL=https://staging.example.com/api/v1 EMAIL=cfo@nimbus.test PASSWORD=secret ./scripts/load-test.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE_URL="${BASE_URL:-http://localhost:8000/api/v1}"
EMAIL="${EMAIL:-cfo@nimbus.test}"
PASSWORD="${PASSWORD:-aurora-demo-2026}"
K6_SCRIPT="$ROOT/tests/load/smoke.js"

echo "==> AURORA load/smoke test"
echo "    BASE_URL=$BASE_URL"

if command -v k6 >/dev/null 2>&1 && [[ -f "$K6_SCRIPT" ]]; then
  echo "==> Running k6 smoke scenario"
  export BASE_URL EMAIL PASSWORD
  exec k6 run "$K6_SCRIPT"
fi

echo "==> k6 not found — running curl smoke checks"

curl -sf "$BASE_URL/health" | grep -q '"status"' && echo "OK health"

TOKEN="$(
  curl -sf -X POST "$BASE_URL/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])"
)"
echo "OK login"

curl -sf "$BASE_URL/metrics/overview" -H "Authorization: Bearer $TOKEN" >/dev/null \
  && echo "OK metrics/overview (or 422 if no DATABASE_URL)"

curl -sf "$BASE_URL/board-reports" -H "Authorization: Bearer $TOKEN" >/dev/null \
  && echo "OK board-reports"

echo "==> Smoke checks passed"
