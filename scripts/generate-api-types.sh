#!/usr/bin/env bash
# Regenerate the web app's typed API artifacts from the FastAPI OpenAPI spec.
# No server needed: imports the app in-process (requires apps/api/.venv).
# Outputs (both versioned): apps/web/openapi.json + apps/web/lib/api-types.ts
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEB_DIR="$ROOT/apps/web"
SPEC="$WEB_DIR/openapi.json"
TYPES="$WEB_DIR/lib/api-types.ts"

echo "==> AURORA API type generation"

source "$ROOT/apps/api/.venv/bin/activate"
python -c "import json; from aurora.main import create_app; print(json.dumps(create_app().openapi(), indent=2))" > "$SPEC"

cd "$WEB_DIR"
pnpm exec openapi-typescript "$SPEC" -o "$TYPES"

echo "    spec:  $SPEC"
echo "    types: $TYPES"
