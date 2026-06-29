# AURORA — AI Handoff & Session Log

> **Living document.** Another AI (or human) should read this **first** before continuing work.
> Updated after every user prompt that changes code or project direction.

---

## Quick state (as of 2026-06-29)

| Item | Value |
|------|-------|
| **Repo** | `/Users/ekambindra/Projects/aurora` |
| **GitHub** | https://github.com/Ekam-Bindra/aurora |
| **`main` commit** | `9bede57` — Phases 1–5 integrated |
| **Active branch** | `feat/phase-7-ingestion` (P7 data sources UI + backend ingestion) |
| **Next work** | Backend ingestion endpoints on same branch; E2E upload demo; P8 admin/reports |
| **Demo login** | `cfo@nimbus.test` / `aurora-demo-2026` |
| **Local API** | `./scripts/local-run.sh` or uvicorn on port 8000 |

### What's done

- ✅ Full design docs (12 documents)
- ✅ P1: monorepo, FastAPI auth/RBAC, Next shell, Docker compose skeleton, CI
- ✅ P2: 25 tables, Alembic, Nimbus seeder + verification, SQLite/Postgres
- ✅ P3: `packages/ml`, metrics/financials APIs, Overview + Financials live KPIs
- ✅ PR #1, #2, #3 merged to `main`
- ✅ **P4 complete:** React Flow explorer (impact/neighborhood), Vanguard golden tests, `/graph/*` APIs
- ✅ **P5 complete:** ForecastEngine, RiskGenomeEngine, `/forecasts/*`, `/risk/*`, `/explain/*`; web fan chart + Risk page
- ✅ **P6 backend (merged):** `packages/simulations` Monte Carlo engine; `/scenarios/*`, `/simulations/*`, `/explain/simulation/{id}`; mock AI provider + `/agent/*`; golden + integration tests; API 45 pytest / simulations 6 pytest
- ✅ **P7 frontend (this branch):** `/data` Data Sources page — source registry cards, health status, file upload + schema mapping, job history, lineage drill-down, rejected rows; `lib/api.ts` wired to `/data-sources/*` and `/ingestion/*`; nav `Data Sources` ready

### What's not done

- ⏳ P7 backend: ingestion module (`/data-sources`, `/ingestion/uploads`, job store, ETL worker)
- ⏳ E2E demo: login → upload CSV → metrics refresh
- ⏳ P8–P9 post-MVP (admin, board reports, production AWS)

---

## User standing instructions (carry forward)

1. **Enterprise quality** — tenant isolation, RBAC, tests, explainability, CI green
2. **Keep local + GitHub in sync** — commit and push after each session
3. **Update this file + `PROJECT-MASTER-GUIDE.md`** after each prompt
4. **Time estimate before work** — see § Estimates below; state estimate at start of each prompt
5. **Cursor auto-run** — user wants agent mode without validating each shell command
6. **Docs-first** — follow `docs/`; don't re-architect without user approval
7. **No commits unless asked** — user later asked to manage commits/merges explicitly; continue that pattern when merging phases

---

## Time estimates

### Remaining work (agent-time, ~1–2 prompts per phase at current pace)

| Target | Phases | Est. agent hours | Est. user prompts | Calendar (1–2 prompts/day) |
|--------|--------|------------------|-------------------|----------------------------|
| **MVP demo** (login → dashboard → simulate → AI) | P4 merge + P5 + P6 | 10–16 h | 6–10 | ~1 week |
| **Pilot-ready** (+ ingestion, admin, exports) | P7 + P8 | 8–14 h | 4–8 | 1–2 weeks |
| **Production SaaS** | P9 | 10–16 h | 4–6 | 1–2 weeks |

### Estimate for **next prompt**

| Task | Estimate |
|------|----------|
| Merge PR #4, open PR #5 | 15 min |
| P5 Prophet + risk UI + backtest | 2–4 h |
| **Total** | **~2.5–4.5 h** |

---

## Prompt log

### Prompt 6 — This session (2026-06-29)

**User asked:** Complete P4 (React Flow, golden tests, CI), merge PR #4, start P5 foundation.

**Completed:**

- ✅ React Flow graph explorer with impact/neighborhood modes (`apps/web/components/graph/GraphExplorer.tsx`)
- ✅ Golden tests: Vanguard → Electronics → Continental chain (`packages/graph/tests/test_sync.py`, `apps/api/tests/test_graph.py`)
- ✅ Local CI green: ruff, pytest (api/ml/graph), web build
- ✅ P4 pushed to `feat/phase-4-knowledge-graph` (`a5ea395`)
- ✅ P5 foundation on `feat/phase-5-forecasting-risk` (`f906a60`):
  - `packages/ml/aurora_ml/forecast.py` — baseline forecaster + CIs
  - `packages/ml/aurora_ml/risk.py` — 8-dimension Risk Genome engine
  - `/forecasts/*`, `/risk/*` API routes + tests
- ⚠️ PR #4 merge to `main` requires manual approval (protected branch / no `gh` CLI)

**Remaining for P5 acceptance:**

1. Prophet (or ensemble) with rolling-origin backtest + MAPE target on Nimbus
2. Full risk scorers (operational/talent graph-coupled)
3. Dashboard forecast fan chart + Risk page UI — **done** (`/forecasting`, `/risk`, Overview widgets)
4. `/explain/forecast/*` and `/explain/risk/*` endpoints

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
| P6 simulation store in-memory | Redis/job queue in later iteration; matches forecast pattern |

---

## Key files for next session

| Area | Files |
|------|-------|
| Roadmap | `docs/roadmap/implementation-roadmap.md` |
| Forecast spec | `docs/architecture/financial-risk-simulation-models.md` §3–4 |
| P5 ML | `packages/ml/aurora_ml/forecast.py`, `risk.py` |
| P5 API | `apps/api/aurora/modules/forecasts/router.py`, `modules/risk/router.py`, `services/risk.py` |
| P5 Web | `apps/web/app/(dashboard)/forecasting/page.tsx`, `risk/page.tsx`, `lib/api.ts` |
| P6 Simulations | `packages/simulations/aurora_sim/engine.py` |
| P6 API | `apps/api/aurora/modules/simulation/router.py`, `modules/agent/router.py`, `providers/mock.py`, `services/simulation.py`, `services/agent.py` |
| P6 Web | `apps/web/app/(dashboard)/simulations/page.tsx`, `agent/page.tsx`, `components/agent/AgentChat.tsx` |
| P7 Web | `apps/web/app/(dashboard)/data/page.tsx`, `lib/api.ts` (data-sources + ingestion) |
| Graph UI | `apps/web/components/graph/GraphExplorer.tsx` |
| RBAC | `apps/api/aurora/core/rbac.py` |

---

## Handoff prompt (copy for new AI)

```
You are continuing AURORA at ~/Projects/aurora.
Read docs/AI-HANDOFF.md and docs/PROJECT-MASTER-GUIDE.md first.
Merge PR #4 if not done. Active: Phase 5 on feat/phase-5-forecasting-risk.
Deliver: Prophet forecast, risk UI, backtest MAPE, explain endpoints, CI green.
Demo: cfo@nimbus.test / aurora-demo-2026. Enterprise quality.
```

---

## Changelog

| Date | Update |
|------|--------|
| 2026-06-28 | Initial handoff; P3 merged; P4 started; estimates added |
| 2026-06-29 | P5 backend complete: forecast ensemble + backtest, 8-dim risk genome, explain endpoints |
| 2026-06-29 | P4 React Flow + golden tests complete; P5 foundation started |
| 2026-06-29 | P5 forecast + risk UI shipped on web (`/forecasting`, `/risk`) |
| 2026-06-29 | P6 backend: Monte Carlo engine, scenarios/simulations/agent APIs, mock AI provider |
| 2026-06-29 | P6 frontend: simulations, AI agent, Explain overlay, dashboard polish |
| 2026-06-29 | P7 frontend: Data Sources page at `/data`, ingestion API client, nav enabled |
