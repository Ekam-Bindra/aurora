# AURORA — Project Master Guide

> **Living document.** Updated after each development session. This is the single operational
> handbook for building, running, testing, and shipping AURORA from your machine and GitHub.
>
> **Companion:** [`AI-HANDOFF.md`](AI-HANDOFF.md) — prompt log and AI continuity brief.

---

## 1. What AURORA is

AURORA is an **Enterprise Decision Intelligence OS**: a multi-tenant platform that unifies
financial, operational, and relationship data into live KPIs, forecasts, risk scores, graph
impact analysis, Monte Carlo simulations, and an explainable executive AI agent.

**Demo tenant:** Nimbus Retail Systems (`cfo@nimbus.test` / `aurora-demo-2026`).

**Source of truth for design:** everything under `docs/` — especially
[`implementation-roadmap.md`](roadmap/implementation-roadmap.md) and
[`mvp-scope.md`](roadmap/mvp-scope.md).

---

## 2. Repository map

| Path | Purpose |
|------|---------|
| `apps/api` | FastAPI backend — auth, RBAC, modules, OpenAPI |
| `apps/web` | Next.js 14 App Router executive UI |
| `packages/database` | SQLAlchemy models, Alembic, Nimbus seeder (`aurora_db`) |
| `packages/ml` | Financial marts, calculators, metric registry (`aurora_ml`) |
| `packages/graph` | Knowledge graph sync + queries (`aurora_graph`) — **Phase 4** |
| `packages/config` | Shared ESLint/TS/Tailwind presets |
| `infra/docker` | Docker Compose (Postgres, Neo4j, Redis, MinIO, nginx) |
| `scripts/local-run.sh` | SQLite dev API without Docker |
| `.github/workflows/ci.yml` | CI: api, database, ml, web |
| `docs/` | Architecture, data model, API spec, roadmap |

**GitHub:** https://github.com/Ekam-Bindra/aurora (private)

**Branches:** `main` = integrated phases; feature work on `feat/phase-N-*`.

---

## 3. Build phases & current status

| Phase | Theme | Status on `main` |
|-------|-------|------------------|
| **P1** | Foundation — monorepo, auth/RBAC, web shell, Docker, CI | ✅ Done |
| **P2** | Data model, Alembic, Nimbus seeder, tenant repos | ✅ Done |
| **P3** | Financial intelligence — marts, `/metrics/*`, Financials UI | ✅ Done (`0868194`) |
| **P4** | Knowledge graph — sync, `/graph/*`, Graph explorer | 🔄 PR open (impact UI done; React Flow next) |
| **P5** | Forecasting + Risk Genome | ⏳ Pending |
| **P6** | Simulation + AI Agent + full dashboard → **MVP** | ⏳ Pending |
| **P7** | Ingestion + live connectors | Post-MVP |
| **P8** | Board reports + Admin console | Post-MVP |
| **P9** | AWS production, ClickHouse, security hardening | Post-MVP |

**MVP** = end of Phase 6 (runnable demo without external AI keys).
**Production-ready for real users** = end of Phase 9 (+ your org's SSO, onboarding, ops).

---

## 4. Prerequisites

- **Python 3.9+** (3.11 recommended for CI parity)
- **Node 20** + **pnpm 9**
- **Optional:** Docker Desktop for full stack (Postgres, Neo4j, Redis)
- **No Docker required** for API dev: SQLite via `scripts/local-run.sh`

---

## 5. First-time setup

```bash
cd ~/Projects/aurora
cp .env.example .env
# Edit SECRET_KEY for non-local use; DATABASE_URL defaults to SQLite.

# Python packages (from repo root)
python3 -m venv apps/api/.venv
source apps/api/.venv/bin/activate
pip install -e packages/database -e packages/ml -e packages/graph -e 'apps/api[dev]'

# Node
pnpm install
```

---

## 6. Running locally

### Option A — SQLite API only (fastest)

```bash
./scripts/local-run.sh
# API: http://localhost:8000/api/v1
# Docs: http://localhost:8000/api/v1/docs
# Login: cfo@nimbus.test / aurora-demo-2026
```

First startup seeds Nimbus at `demo_seed_scale` (default 0.1 in `.env` via settings).

### Option B — Web + API

```bash
# Terminal 1 — API (as above, or with DATABASE_URL set)
export DATABASE_URL=sqlite:///./data/aurora_local.db
export NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
cd apps/api && uvicorn aurora.main:app --reload --port 8000

# Terminal 2 — Web
cd apps/web && pnpm dev
# http://localhost:3000
```

### Option C — Full Docker stack

```bash
docker compose -f infra/docker/docker-compose.yml up -d
# Web via nginx: http://localhost
# Neo4j browser: http://localhost:7474
```

See [`deployment-guide.md`](deployment/deployment-guide.md) for details.

---

## 7. Testing (run before every push)

```bash
# From repo root with venv active
cd packages/ml && pytest && cd ../database && pytest -k "not postgres"
cd ../../apps/api && pytest
cd ../web && pnpm build
```

**Lint:**

```bash
cd apps/api && ruff check .
cd packages/ml && ruff check .
cd packages/graph && ruff check .
```

CI runs the same on every PR to `main`.

---

## 8. Git & GitHub workflow

### Branch naming

`feat/phase-N-short-description` (e.g. `feat/phase-4-knowledge-graph`).

### Standard loop (each prompt / session)

1. Branch from latest `main`
2. Implement + test locally
3. Commit with conventional message: `feat:`, `fix:`, `docs:`, `chore:`
4. Push branch → open PR to `main`
5. Merge when CI green
6. Update this guide + `AI-HANDOFF.md`
7. Delete or keep feature branch per preference

### Commit message style

```
feat: Phase N — short summary

One or two sentences on why, not just what.
```

### Merging

- Prefer merge commits or GitHub PR merge for phase boundaries
- Never force-push `main`
- Close superseded PRs when content is already on `main`

---

## 9. Environment variables (essential)

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | JWT signing — **required in production** |
| `DATABASE_URL` | Postgres/SQLite — unset = in-memory API (tests only) |
| `NEO4J_URI` | `bolt://localhost:7687` when using Neo4j |
| `NEO4J_USER` / `NEO4J_PASSWORD` | Neo4j auth |
| `DEMO_SEED_SCALE` | `0.05`–`1.0` — smaller = faster seed |
| `AI_PROVIDER` | `mock` (default) — no API keys needed through MVP |
| `NEXT_PUBLIC_API_URL` | Web → API base URL |

Full list: `.env.example`.

---

## 10. API surface (implemented)

| Module | Endpoints | Permission | Requires |
|--------|-----------|------------|----------|
| Auth | `/auth/login`, `/auth/me` | — | — |
| Health | `/health` | — | — |
| Metrics | `/metrics/*`, `/financials/*`, `/explain/metric/*` | `read:financials` | `DATABASE_URL` |
| Graph | `/graph/*` | `read:graph` | `DATABASE_URL` |

OpenAPI: `/api/v1/docs` when API is running.

---

## 11. Enterprise quality standards

Every phase must include:

1. **Tenant isolation** — every query scoped by `company_id` / `tenant_id`
2. **RBAC** — permission guards on every mutating and sensitive read endpoint
3. **Typed errors** — consistent envelope (`error.code`, `error.message`)
4. **Explainability** — formulas + inputs for computed outputs
5. **Tests** — unit (golden values on Nimbus), API integration, CI green
6. **No secrets in repo** — `.env` only locally; GitHub secrets for CI deploy later
7. **Docs sync** — update this file + handoff after each session
8. **Graceful degradation** — clear 422 when optional infra missing (e.g. no DB, no Neo4j)

---

## 12. Cursor / AI agent setup

### Reduce command approval prompts

In **Cursor Settings → Agents** (or **Features → Agent**):

- Enable **auto-run** for terminal commands (sometimes called YOLO / Run everything)
- Or approve workspace-trusted mode for this repo

The agent should run tests, git, and pip without per-command approval when you want
hands-off iteration. You explicitly requested this mode for AURORA development.

### Per-prompt ritual for the agent

1. Read `docs/AI-HANDOFF.md` first
2. State **time estimate** before starting work
3. Complete implementation + tests + push
4. Update `AI-HANDOFF.md` and this guide's status table
5. Report what merged and what's next

---

## 13. Troubleshooting

| Issue | Fix |
|-------|-----|
| Metrics return 422 | Set `DATABASE_URL` and restart API |
| Graph returns 422 | Set `DATABASE_URL`; graph sync runs on startup |
| Slow first boot | Lower `DEMO_SEED_SCALE` to `0.05` |
| Web can't reach API | Match `NEXT_PUBLIC_API_URL` to API port |
| pytest auth fails | Use `with TestClient(create_app())` for lifespan seed |
| Ruff on Python 3.9 | No `X \| None` unions — use `Optional[X]` |

---

## 14. What remains until users can use AURORA

| Milestone | What it means | Phases left |
|-----------|---------------|-------------|
| **Internal demo (MVP)** | CFO login → dashboard → risk → simulate → AI answer | P4–P6 |
| **Pilot customers** | File ingestion, admin, board exports | P7–P8 |
| **Production SaaS** | AWS, SSO, scale, security review | P9 |

See **time estimates** in `AI-HANDOFF.md` § Estimates.

---

## 15. Document changelog

| Date | Change |
|------|--------|
| 2026-06-28 | P3 merged; P4 foundation (graph package, APIs, impact UI) |
