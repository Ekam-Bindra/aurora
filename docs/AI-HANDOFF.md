# AURORA — AI Handoff & Session Log

> **Living document.** Another AI (or human) should read this **first** before continuing work.
> Updated after every user prompt that changes code or project direction.

---

## Quick state (as of 2026-06-29)

| Item | Value |
|------|-------|
| **Repo** | `/Users/ekambindra/Projects/aurora` |
| **GitHub** | https://github.com/Ekam-Bindra/aurora |
| **`main` commit** | `27bc579` — Phases 1–8 merged (PR #8) |
| **Active branch** | `feat/phase-9-aws-hardening` |
| **Next work** | Merge PR #9; optional E2E demos |
| **Demo login** | `cfo@nimbus.test` / `aurora-demo-2026` |
| **Local API** | `./scripts/local-run.sh` or uvicorn on port 8000 |
| **Deploy docs** | `docs/DEPLOYMENT.md` |

### What's done

- ✅ Full design docs (12 documents)
- ✅ P1–P8 merged to `main` (through PR #8)
- ✅ **P9 (branch):** Terraform AWS (VPC, ECS, ALB, RDS, ECR, Secrets Manager, S3)
- ✅ **P9:** `docker-compose.prod.yml`, ClickHouse profile, `packages/analytics`
- ✅ **P9:** OIDC SSO (`/auth/oidc/*`), security headers, auth rate limiting
- ✅ **P9:** Load tests (`scripts/load-test.sh`, `tests/load/smoke.js`)
- ✅ **P9:** Deploy workflow stub (`.github/workflows/deploy.yml`)
- ✅ API **78 pytest** / ruff green (was 67)

### What's not done

- ⏳ E2E demos (upload CSV, generate board pack)
- ⏳ P9 merge to `main` (PR #9)

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
| P7 ingestion job store in-memory | Same pattern as simulation/forecast; worker queue in P9 |
| P8 board report store in-memory | Same pattern; `BoardReport` table exists for P9 persistence |
| P8 audit log | Uses `audit_log` table when DB enabled; in-memory + demo seed otherwise |
| P9 `ANALYTICS_BACKEND=postgres` default | DuckDB mart from relational DB; ClickHouse opt-in via env |
| P9 OIDC optional | Email/password login remains when `OIDC_ENABLED=false` |
| P9 Terraform | No credentials in repo; Secrets Manager for DATABASE_URL + JWT |

---

## Key files for next session

| Area | Files |
|------|-------|
| Deploy | `docs/DEPLOYMENT.md`, `infra/terraform/`, `.github/workflows/deploy.yml` |
| **Local CI** | `docs/CI.md` — mirror `.github/workflows/ci.yml` locally |
| Analytics | `packages/analytics/aurora_analytics/` |
| SSO | `apps/api/aurora/modules/auth/oidc_router.py`, `core/oidc.py` |
| Security | `apps/api/aurora/core/security_middleware.py`, `core/config.py` |
| Load tests | `scripts/load-test.sh`, `tests/load/smoke.js` |

---

## Changelog

| Date | Update |
|------|--------|
| 2026-06-29 | P9: AWS Terraform, OIDC, security hardening, ClickHouse analytics path, 78 pytest |
| 2026-06-29 | P8 backend: board reports + admin APIs, audit logging, 67 pytest |
| 2026-06-28 | Initial handoff; P3 merged; P4 started; estimates added |
