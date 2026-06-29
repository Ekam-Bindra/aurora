#!/usr/bin/env bash
# Start the Next.js web app (expects API on port 8000).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEB_DIR="$ROOT/apps/web"

export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-/api/v1}"

echo "==> AURORA web dev"
echo "    API target: $NEXT_PUBLIC_API_URL"
echo "    App:        http://localhost:3000"
echo "    Login:      cfo@nimbus.test / aurora-demo-2026"
echo ""

cd "$WEB_DIR"
exec pnpm dev
