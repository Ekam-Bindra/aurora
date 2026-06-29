# AURORA — AI Handoff & Session Log

> **Living document.** Another AI (or human) should read this **first** before continuing work.
> Updated after every user prompt that changes code or project direction.

---

## Quick state (as of 2026-06-28)

| Item | Value |
|------|-------|
| **Repo** | `/Users/ekambindra/Projects/aurora` |
| **GitHub** | https://github.com/Ekam-Bindra/aurora |
| **`main` commit** | `0868194` — Phases 1–3 integrated |
| **Active branch** | `feat/phase-4-knowledge-graph` |
| **Next work** | React Flow explorer, Neo4j optional sync, merge P4 PR |
| **Demo login** | `cfo@nimbus.test` / `aurora-demo-2026` |
| **Local API** | `./scripts/local-run.sh` or uvicorn on port 8000 |

### What's done

- ✅ Full design docs (12 documents)
- ✅ P1: monorepo, FastAPI auth/RBAC, Next shell, Docker compose skeleton, CI
- ✅ P2: 25 tables, Alembic, Nimbus seeder + verification, SQLite/Postgres
- ✅ P3: `packages/ml`, metrics/financials APIs, Overview + Financials live KPIs
- ✅ PR #1, #2, #3 merged to `main`

### What's not done

- 🔄 P4 Knowledge Graph — core done on branch; React Flow + Neo4j optional remaining
- ⏳ P5 Forecasting + Risk Genome
- ⏳ P6 Simulation + AI Agent + MVP dashboard
- ⏳ P7–P9 post-MVP (connectors, board reports, production AWS)

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

### How to use

Before starting **any** new prompt, the agent should post:

- **This prompt:** expected duration + scope
- **Risk:** what might expand scope

### Remaining work (agent-time, ~1–2 prompts per phase at current pace)

| Target | Phases | Est. agent hours | Est. user prompts | Calendar (1–2 prompts/day) |
|--------|--------|------------------|-------------------|----------------------------|
| **MVP demo** (login → dashboard → simulate → AI) | P4 + P5 + P6 | 12–20 h | 8–12 | 1–2 weeks |
| **Pilot-ready** (+ ingestion, admin, exports) | P7 + P8 | 8–14 h | 4–8 | 1–2 weeks |
| **Production SaaS** | P9 | 10–16 h | 4–6 | 1–2 weeks |
| **From now → MVP** | | **12–20 h** | **~8–12** | **~1–2 weeks** |
| **From now → real users (prod)** | all | **30–50 h** | **~18–26** | **~3–6 weeks** |

### Per-prompt typology (going forward)

| Prompt type | Examples | Typical time |
|-------------|----------|--------------|
| **XS** | Doc tweak, single bugfix, config | 15–30 min |
| **S** | One API route + test | 30–60 min |
| **M** | One module slice (e.g. graph impact API) | 1–2 h |
| **L** | Full phase (e.g. all of P3) | 2–4 h, often 1–2 prompts |
| **XL** | P5 or P6 (forecast + risk, or sim + agent) | 3–6 h, 2–4 prompts |

### Estimate for **this prompt** (2026-06-28)

| Task | Estimate |
|------|----------|
| Merge PR #3, update docs, Cursor notes | 30–45 min |
| P4 foundation (graph package + APIs + basic UI) | 2–3 h |
| **Total** | **~2.5–4 h** (may spill to next prompt for React Flow polish + Neo4j CI) |

---

## Prompt log

### Prompt 1 — Initial design foundation

**User asked:** Create `~/Projects/aurora` with full documentation; no app code unless requested.

**Completed:** 12 design docs (~4,420 lines), README, architecture, data model, API spec, roadmap, deployment.

---

### Prompt 2 — GitHub + Phase 1

**User asked:** Create branch, commit, push, private repo under `Ekam-Bindra`, Phase 1 at same depth as docs.

**Completed:** Monorepo, FastAPI auth/RBAC, Next shell, Docker, CI, Phase 1 on `feat/phase-1-foundation`.

---

### Prompt 3 — Publish + local run

**User asked:** Push phase 2 branch, manage PRs, complete next steps, local run.

**Completed:** API↔DB wiring, `local-run.sh`, SQLite path verified, demo login works.

---

### Prompt 4 — Merge phases + Phase 3

**User asked:** Manage commits/merging, combine P1+P2 into `main`, continue Phase 3.

**Completed:** `main` fast-forwarded; P3 `packages/ml`, metrics APIs, Overview/Financials UI; PR #3 opened.

---

### Prompt 5 — This session (2026-06-28)

**User asked:**

- Mode without validating each command
- Master guide + evolving handoff doc
- Keep code updated locally and on GitHub after each prompt
- Enterprise quality
- Merge PR #3, begin P4
- **Before work:** time estimates for task, total to user-ready, per-prompt estimates going forward

**Completed:**

- ✅ Merged PR #3 to `main` (local + GitHub)
- ✅ Created `docs/PROJECT-MASTER-GUIDE.md`
- ✅ Created `docs/AI-HANDOFF.md` (this file)
- ✅ P4 foundation: `packages/graph`, `/graph/*` APIs, impact analysis UI, tests, CI
- ✅ Cursor `cursor.agent.enableAutoRun` enabled in user settings (verify in Settings → Agents)

**Remaining for P4 acceptance:**

1. React Flow visual explorer + neighborhood mode
2. Optional Neo4j projection for Docker deployments
3. Golden-value test vs demo spec revenue-at-risk target
4. Open + merge PR #4

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

---

## Key files for next session

| Area | Files |
|------|-------|
| Roadmap | `docs/roadmap/implementation-roadmap.md` |
| Graph spec | `docs/data-model/data-model.md` §5, `docs/api/api-specification.md` §6.4 |
| Demo chain | `docs/data-model/demo-dataset-spec.md` §6 — Vanguard → Electronics → Continental |
| Seeder | `packages/database/aurora_db/seed/nimbus.py` |
| RBAC | `apps/api/aurora/core/rbac.py` |
| API modules | `apps/api/aurora/modules/*/router.py` |
| Config | `apps/api/aurora/core/config.py`, `.env.example` |

---

## Handoff prompt (copy for new AI)

```
You are continuing AURORA at ~/Projects/aurora.
Read docs/AI-HANDOFF.md and docs/PROJECT-MASTER-GUIDE.md first.
main is at Phase 3 (0868194). Active work: Phase 4 Knowledge Graph on feat/phase-4-knowledge-graph.
Deliver: packages/graph, /graph/* APIs, graph explorer UI, tests, CI, push + PR.
Demo: cfo@nimbus.test / aurora-demo-2026. Estimate time BEFORE starting. Enterprise quality.
```

---

## Changelog

| Date | Update |
|------|--------|
| 2026-06-28 | Initial handoff; P3 merged; P4 started; estimates added |
