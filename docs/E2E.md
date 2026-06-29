# AURORA — End-to-End (E2E) Web Tests

Playwright browser tests for the Next.js app (`apps/web`) against a live API.

**Location:** `apps/web/e2e/`  
**Runner:** `@playwright/test` via `pnpm test:e2e` in `apps/web`

---

## Prerequisites

- **Node.js 20+** and **pnpm 9**
- **Python 3.9+** (API venv is created automatically on first run)
- Chromium (installed once via `pnpm test:e2e:install`)

---

## Quick start

From the repo root:

```bash
# Install web deps + Playwright browser
pnpm install
cd apps/web && pnpm test:e2e:install

# Run the full suite (starts API + web dev server automatically)
cd apps/web && pnpm test:e2e
```

Playwright will:

1. Start the API with `./scripts/e2e-api.sh` (SQLite at `data/aurora_e2e.db`, demo seed scale 0.1)
2. Start `pnpm dev` on port 3000 (proxies `/api/v1` → API)
3. Run tests in Chromium (single worker — shared backend state)

If you already have `./scripts/local-run.sh` and `./scripts/dev-web.sh` running, Playwright reuses those servers (`reuseExistingServer` when not in CI).

---

## Demo credentials

| Email | Password |
|-------|----------|
| `cfo@nimbus.test` | `aurora-demo-2026` |

Tests sign in as the CFO persona (financials, data sources, board reports, audit log).

---

## What is covered

| Spec | Flow |
|------|------|
| `e2e/login.spec.ts` | Login → `/overview` KPI cards load |
| `e2e/data-ingestion.spec.ts` | Register file source → upload `fixtures/customers.csv` → job `completed` |
| `e2e/board-reports.spec.ts` | Generate board pack → status visible → **Download PDF** |
| `e2e/admin-audit.spec.ts` | `/admin` audit log table for CFO |

Sample CSV columns match the ingestion API (`name,segment,region,industry,status`), aligned with `apps/api/tests/test_ingestion.py` and the accounting CSV connector samples.

---

## Useful commands

```bash
cd apps/web

pnpm test:e2e              # headless run
pnpm test:e2e:ui             # interactive UI mode
pnpm exec playwright test login.spec.ts   # single file
pnpm exec playwright test --debug         # step-through debugger
```

### Environment overrides

| Variable | Default | Purpose |
|----------|---------|---------|
| `PLAYWRIGHT_BASE_URL` | `http://localhost:3000` | Web origin |
| `API_PORT` | `8000` | API port for health check / proxy |
| `PORT` | `3000` | Next.js dev port |
| `CI` | unset | When set, always starts fresh servers (no reuse) |

---

## CI notes

Set `CI=true` so Playwright does not reuse local servers. Ensure `pnpm test:e2e:install` runs before `pnpm test:e2e`. Typical job steps:

```yaml
- run: pnpm install
- run: cd apps/web && pnpm test:e2e:install
- run: cd apps/web && pnpm test:e2e
  env:
    CI: true
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Port 8000 in use | Stop other API or set `API_PORT=8001` and `AURORA_API_DEV_URL=http://127.0.0.1:8001` |
| KPI cards show warning banner | Ensure `DATABASE_URL` is set (use `./scripts/e2e-api.sh` or `./scripts/local-run.sh`) |
| Login 401 | Demo seed missing — delete `data/aurora_e2e.db` and re-run |
| Browser not found | Run `pnpm test:e2e:install` |

See also [`docs/DEPLOYMENT.md`](DEPLOYMENT.md) for production deploy and smoke/load tests.
