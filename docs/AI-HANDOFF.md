# AURORA — AI Handoff & Session Log

> **Living document.** Another AI (or human) should read this **first** before continuing work.
> For a short "start here tomorrow" brief, see [`SESSION-END-HANDOFF.md`](SESSION-END-HANDOFF.md).

---

## Quick state (session end — 2026-07-01)

| Item | Value |
|------|-------|
| **Repo (local)** | `/Users/ekambindra/Projects/aurora` |
| **GitHub** | https://github.com/Ekam-Bindra/aurora |
| **`main` commit** | `d93d291` (untouched across both 2026-07-01 sessions) |
| **Branch** | `ekam-testing` — deploy-prep + persistence development; awaiting user review/merge |
| **Session docs** | `docs/deploy-prep/` — requirements, design, task list + outcomes (both sessions) |
| **Web stack** | next 16.2 · react 19.2 · typescript 6.0 · tailwind 4.3 · eslint 9 flat config — all build+E2E-gated |
| **Stores** | Board reports / ingestion jobs / simulation runs persist to DB (migration `0002`); safe for `desired_count = 2` |
| **Tests** | **120 pytest** + 4 Playwright E2E green |
| **Next work** | User: review/merge `ekam-testing`; then AWS credentials + Docker (or GitHub-Actions deploy path) → `docs/DEPLOY-CHECKLIST.md` |
| **Demo login** | `cfo@nimbus.test` / `aurora-demo-2026` |
| **Local API** | `./scripts/local-run.sh` → http://localhost:8000 |
| **Local web** | `./scripts/dev-web.sh` → http://localhost:3000 |
| **Deploy docs** | `docs/DEPLOY-CHECKLIST.md`, `docs/DEPLOYMENT.md` |
| **Tests** | **116 pytest** (all packages + API) · **4 Playwright E2E** |

### Copy-paste: continue tomorrow

```bash
cd ~/Projects/aurora
git pull origin main
./scripts/local-run.sh          # terminal 1 — API :8000
./scripts/dev-web.sh            # terminal 2 — web :3000
# Login: cfo@nimbus.test / aurora-demo-2026
cd apps/web && pnpm test:e2e    # E2E suite (4 tests)
./scripts/load-test.sh          # k6/curl smoke
./scripts/deploy-check.sh       # AWS preflight (no creds needed)
# First deploy: docs/DEPLOY-CHECKLIST.md
```

---

## Completed work (comprehensive)

### Design foundation (pre-code)

- 12 design documents under `docs/` — architecture, data model, API spec, roadmap, MVP scope, UI/UX plan, deployment guide, demo dataset spec.

### Build phases P1–P9 (all merged to `main`)

| Phase | Theme | Key deliverables | PR / commit |
|-------|-------|------------------|-------------|
| **P1** | Foundation | Monorepo (pnpm + Python), FastAPI skeleton, Next.js shell, Docker Compose, auth/RBAC/JWT, CI workflow | `9ad7c61` (early main) |
| **P2** | Persistence | SQLAlchemy models (21 entities), Alembic, tenant repos, Nimbus seeder, SQLite local path | `2ed2843` |
| **P3** | Financial intelligence | DuckDB marts, metric registry, `/metrics/*` + `/financials/*`, explainability, KPI dashboard | `0868194` |
| **P4** | Knowledge graph | Neo4j sync, `/graph/*`, impact analysis, React Flow explorer | **PR #4** |
| **P5** | Forecasting + Risk Genome | Prophet forecasts, risk scoring, `/forecasts/*` + `/risk/*`, UI pages | **PR #5** |
| **P6** | Simulation + AI Agent = **MVP** | Monte Carlo engine, mock AI agent, explain overlay, full executive dashboard | **PR #6** |
| **P7** | Ingestion + connectors | CSV upload, source registry, job status, Data Sources UI | **PR #7** |
| **P8** | Board reports + Admin | Board pack generation, audit trail, admin console (API + web) | **PR #8** |
| **P9** | AWS + hardening | Terraform (VPC/ECS/RDS/ALB/ECR), OIDC SSO, security middleware, ClickHouse analytics path, load tests, `docs/DEPLOYMENT.md` | **PR #9** |

**MVP line** = end of P6. **Production-ready** = end of P9 + first AWS deploy.

### Post-MVP hardening (merged after P9)

| Work | Key deliverables | PR |
|------|------------------|-----|
| **CI regression** | Analytics CI job, ruff fixes across packages, `docs/CI.md`, 116 pytest green | **PR #15** |
| **Deploy readiness** | `scripts/deploy-check.sh`, `docs/DEPLOY-CHECKLIST.md`, Terraform lock file + fmt fixes, deploy workflow ECS wait | **PR #16** |
| **E2E Playwright** | 4 CFO-flow tests (`login`, `data-ingestion`, `board-reports`, `admin-audit`), `docs/E2E.md`, `scripts/e2e-api.sh` | **PR #17** |

### Dependabot (merged)

| PR | Package bump |
|----|--------------|
| **#10** | `@types/node` 20 → 26 |
| **#11** | `eslint-config-next` 14 → 16 |

### All merged PRs on `main`

#4, #5, #6, #7, #8, #9, #10, #11, #15, #16, #17

Phases 1–3 landed on `main` before numbered PR workflow (commits `9ad7c61`, `2ed2843`, `0868194`).

### Feature branches (all pushed to origin)

`feat/phase-1-foundation` through `feat/phase-9-aws-hardening`, plus `feat/ci-regression`, `feat/deploy-readiness`, `feat/e2e-tests`. Safe to delete locally/remotely after confirming `main` is current.

---

## Remaining work

| Priority | Item | Notes |
|----------|------|-------|
| **P0** | **Merge `ekam-testing` → `main`** | User review; branch holds the seed fix (CI on `main` stays red without it), persistence feature, dep bumps, docs. 14 commits |
| **P0** | **First AWS production deploy** | User-only inputs left: AWS credentials (`aws configure` — CLI now at `.tools/aws`), Docker (admin install; **optional** if deploying via GitHub Actions), GitHub secrets `AWS_ROLE_ARN`/`AWS_REGION`. Then `docs/DEPLOY-CHECKLIST.md` |
| Done 2026-07-01 | ~~In-memory stores × `desired_count = 2`~~ | Resolved by persistence: `board_report.content`, `ingestion_job` table, `run_id`-grouped `simulation_result` (migration `0002`); SQLite dev DBs self-heal via Alembic-at-startup |
| Done 2026-07-01 | ~~Dependabot PRs #12–#14 + new eslint-10/react-19 PRs~~ | All five closed: ts 6 / next 16 / tailwind 4 / react 19 applied+tested on `ekam-testing`; **eslint 10 rejected** (eslint-plugin-react caps at 9 — retry when eslint-config-next updates) |
| Done 2026-07-01 | ~~Branch cleanup~~ | 12 merged `feat/*` + 5 dependabot branches deleted locally and on origin |
| Follow-up | k6 against staging | Local k6 run has machine-specific connection failures (API exonerated — see `docs/deploy-prep/tasks.md` S2-12); run `BASE_URL=<alb> ./scripts/load-test.sh` post-deploy |
| Follow-up | 8 `set-state-in-effect` lint warnings | Pre-existing fetch-on-mount patterns flagged by eslint-config-next 16's new rule; refactor to event-driven loading when convenient |
| Future | Real AI provider | Swap `AI_PROVIDER=mock` for OpenAI/Anthropic when keys available (user to supply key + provider choice) |
| Future | Redis job queues | Async workers for long simulations/report renders; DB-backed state (above) already covers multi-task correctness |

---

## How to continue

### Local dev (two terminals)

```bash
cd ~/Projects/aurora
git pull origin main

# Terminal 1 — API (SQLite, auto-seeds Nimbus)
./scripts/local-run.sh
# → http://localhost:8000/api/v1/docs

# Terminal 2 — Web (proxies /api/v1 → :8000)
./scripts/dev-web.sh
# → http://localhost:3000
# Login: cfo@nimbus.test / aurora-demo-2026
```

### First-time setup (if venv missing)

```bash
python3 -m venv apps/api/.venv && source apps/api/.venv/bin/activate
pip install -e packages/database -e packages/ml -e packages/graph \
  -e packages/simulations -e packages/analytics -e "apps/api[dev]"
pnpm install
cp .env.example .env   # if not exists
```

### Tests

```bash
# All Python (116 tests) — mirror CI
source apps/api/.venv/bin/activate
for d in apps/api packages/database packages/ml packages/graph packages/simulations packages/analytics; do
  echo "=== $d ===" && (cd "$d" && ruff check . && pytest -q) || exit 1
done

# Web build
pnpm --filter @aurora/web build

# E2E (needs API + web running, or uses playwright webServer)
cd apps/web && pnpm test:e2e    # 4 tests

# Load smoke
./scripts/load-test.sh

# AWS preflight (no credentials required)
./scripts/deploy-check.sh
```

See `docs/CI.md` for Postgres-backed database job (optional locally).

### Deploy

1. `./scripts/deploy-check.sh` — fix any FAIL
2. `docs/DEPLOY-CHECKLIST.md` — step-by-step first deploy
3. `docs/DEPLOYMENT.md` — runbook reference
4. `.github/workflows/deploy.yml` — manual GitHub Actions deploy after infra exists

### Git workflow

```bash
git checkout main && git pull origin main
git checkout -b feat/my-feature
# ... implement + test ...
git add -A && git commit -m "feat: description"
git push -u origin feat/my-feature
# Open PR → merge when CI green → update this file
```

**Rules:** never force-push `main`; conventional commits (`feat:`, `fix:`, `docs:`); update this file + `PROJECT-MASTER-GUIDE.md` after each session.

---

## Subagent workflow (used throughout build)

Each phase used **parallel subagents**: one for backend (`apps/api` + packages), one for frontend (`apps/web`), coordinated by the parent agent. Pattern:

1. Parent reads `docs/AI-HANDOFF.md` + roadmap phase acceptance criteria
2. Spawn backend + frontend subagents with shared phase spec
3. Parent integrates, runs tests, opens PR, merges to `main`
4. Update handoff docs

Continue this pattern for post-deploy work (e.g. SSO wiring, ops hardening).

---

## Key file map

| Area | Paths |
|------|-------|
| **API** | `apps/api/aurora/` — modules, routers, middleware |
| **Web** | `apps/web/` — Next.js App Router, `e2e/` |
| **Database** | `packages/database/aurora_db/` — models, seeder, repos |
| **ML / Forecast / Risk** | `packages/ml/aurora_ml/` |
| **Graph** | `packages/graph/aurora_graph/` |
| **Simulations** | `packages/simulations/aurora_sim/` |
| **Analytics** | `packages/analytics/aurora_analytics/` |
| **Infra** | `infra/docker/`, `infra/terraform/` |
| **Scripts** | `scripts/local-run.sh`, `dev-web.sh`, `deploy-check.sh`, `load-test.sh`, `e2e-api.sh` |
| **CI/CD** | `.github/workflows/ci.yml`, `deploy.yml` |
| **Docs** | `docs/` — see `PROJECT-MASTER-GUIDE.md` §2 for full map |

---

## Test counts

| Suite | Count | Location |
|-------|-------|----------|
| **pytest (total)** | **116** | `apps/api/tests/` (78) + `packages/*` (38) |
| **Playwright E2E** | **4** | `apps/web/e2e/*.spec.ts` |

Breakdown by package: api 78 · database 17 · ml 10 · graph 2 · simulations 6 · analytics 3.

---

## Architecture decisions (don't reverse without user)

| Decision | Rationale |
|----------|-----------|
| `DATABASE_URL` unset → in-memory store | Fast pytest; financial/graph endpoints return 422 |
| SQLite OK for local dev | No Docker required |
| `demo_seed_scale` | Laptop-friendly Nimbus seed |
| `AI_PROVIDER=mock` through MVP | No external keys |
| Graph is projection of Postgres | Rebuildable; Neo4j optional with in-memory fallback for local |
| Python 3.9 compat | `Optional[]` not `\|` unions in API/database/ml |
| P6 simulation store in-memory | Redis/job queue in later iteration |
| P7 ingestion job store in-memory | Same pattern; worker queue in P9 |
| P8 board report store in-memory | `BoardReport` table exists for P9 persistence |
| P8 audit log | Uses `audit_log` table when DB enabled |
| P9 `ANALYTICS_BACKEND=postgres` default | DuckDB mart from relational DB; ClickHouse opt-in |
| P9 OIDC optional | Email/password login when `OIDC_ENABLED=false` |
| P9 Terraform | No credentials in repo; Secrets Manager for DATABASE_URL + JWT |

---

## User standing instructions (carry forward)

1. **Enterprise quality** — tenant isolation, RBAC, tests, explainability, CI green
2. **Keep local + GitHub in sync** — commit and push after each session
3. **Update this file + `PROJECT-MASTER-GUIDE.md`** after each prompt
4. **Time estimate before work** — state estimate at start of each prompt
5. **Cursor auto-run** — user wants agent mode without validating each shell command
6. **Docs-first** — follow `docs/`; don't re-architect without user approval
7. **No commits unless asked** — unless user explicitly requests save/sync
8. **Work on `ekam-testing`, never `main`** (2026-07-01 prompt: "at all times") — commits land on
   `ekam-testing`; merging to `main` is the user's call
9. **Skip-and-flag protocol** (2026-07-01) — if stuck on an item: skip it, mark it high priority,
   continue, report at the end; report all confusions as questions and surface gaps/overlooked items

---

## Changelog

| Date | Update |
|------|--------|
| 2026-07-01 | **Session 2 (`ekam-testing`):** persisted board reports / ingestion jobs / simulation runs to DB (migration `0002`, 120 pytest green) resolving the `desired_count=2` risk; Alembic-at-startup for file-backed SQLite (stale dev DBs self-heal — found via real E2E failure); react 19.2 bump gated green; ESLint 9 flat-config migration (`next lint` removed in 16; eslint 10 rejected — plugin incompat); aws CLI v1 + k6 installed into `.tools` with script fallbacks; 12 `feat/*` + 5 dependabot branches deleted on origin (PRs #12–#14 + eslint-10 + react-19 closed as superseded); k6-local flagged machine-specific (API exonerated 300/300); Docker + AWS credentials + GitHub secrets remain user-only |
| 2026-07-01 | **Session 1 — deploy-prep (`ekam-testing`):** fixed date-rollover seed bug (anomalies A/B now pinned vs neighbor months — suite was red since the July rollover; CI on `main` red until merged); bumped typescript 6.0.3 / next 16.2.x / tailwindcss 4.3.1 with build+E2E gates (Tailwind 4 PostCSS migration included); Dependabot PRs #12–#14 superseded (stale branches — do not merge); deploy preflight run (only FAILs = missing `aws`/`docker` CLIs); README + web README synced to merged reality; local merged `feat/*` branches deleted; session docs under `docs/deploy-prep/` incl. open questions Q-1…Q-7; 116 pytest + 4 E2E green |
| 2026-06-29 | **Session end:** comprehensive handoff; P1–P9 + PRs #15–#17 complete; deploy checklist ready; 116 pytest + 4 E2E |
| 2026-06-29 | Deploy readiness (PR #16): preflight script, first-deploy checklist, Terraform fixes |
| 2026-06-29 | E2E (PR #17): Playwright suite, `docs/E2E.md` |
| 2026-06-29 | CI regression (PR #15): analytics job, `docs/CI.md`, 116 tests |
| 2026-06-29 | P9 (PR #9): AWS Terraform, OIDC, security, ClickHouse path |
| 2026-06-29 | P8 (PR #8): board reports + admin APIs |
| 2026-06-28 | Initial handoff; P3 merged; estimates added |
