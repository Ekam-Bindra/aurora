# AURORA — Master Engineering Prompt

> **Purpose.** Hand this document to any senior engineer or AI agent and they can operate on
> AURORA at full context: what it is, what exists (verified, not aspirational), how it is run,
> the standards every change must meet, and the complete forward backlog ranked the way a
> FAANG product-infra team would rank it. Written 2026-07-02, after the first production-grade
> staging deploy. Companion state docs: [`AI-HANDOFF.md`](AI-HANDOFF.md) (session log, updated
> every prompt) and [`deploy-prep/`](deploy-prep/) (requirements/design/task records).

---

## 1. Mission

AURORA is an **Enterprise Decision Intelligence OS**: a multi-tenant SaaS platform that unifies
a company's financial, operational, and relationship data into live KPIs, probabilistic
forecasts, an eight-dimension risk genome, knowledge-graph impact analysis, Monte Carlo
decision simulations, board-report generation, and an explainable executive AI agent.
Non-negotiable product principle: **if AURORA can't show its work, it doesn't show the
number** — every computed output carries formula, inputs, and evidence references.

Demo tenant: **Nimbus Retail Systems** (`cfo@nimbus.test` / `aurora-demo-2026`) — a seeded
36-month retail dataset with seven engineered anomalies (marketing spike, revenue dip,
liquidity squeeze, concentration creep, vendor slip, margin erosion, attrition cluster) the
platform must detect and explain.

## 2. System as built (all verified live or in CI — nothing aspirational)

### 2.1 Architecture

- **Monorepo** (pnpm + Python): `apps/api` (FastAPI modular monolith), `apps/web` (Next.js
  App Router executive UI), `packages/{database,ml,graph,simulations,analytics,config}`.
  Strict dependency direction: packages never import apps; ml/graph/simulations stay free of
  HTTP concerns.
- **Web stack**: next 16.2 · react 19.2 · typescript 6.0 · tailwind 4.3 (CSS-first + `@config`
  bridge to the shared token preset) · eslint 9 flat config with eslint-config-next 16 rules
  at error level. Playwright E2E (4 CFO flows).
- **API**: FastAPI + SQLAlchemy 2, JWT auth (15-min access tokens), RBAC permission guards on
  every sensitive route, tenant scoping (`company_id`) on every business query, typed error
  envelope (`error.code/message`, incl. 502 `upstream_error`), security-header + auth
  rate-limit middleware, optional OIDC SSO.
- **Data**: PostgreSQL (prod RDS 16) / SQLite (dev, auto-migrates to Alembic head at startup —
  `create_all` alone cannot add columns to existing files). Alembic `0001` metadata baseline +
  `0002` persistent stores (defensively written; see the migration's docstring). DuckDB marts
  for analytics with opt-in ClickHouse backend. In-memory fallback stores keep the no-database
  test mode working.
- **Persistence guarantee**: board reports, ingestion jobs, simulation runs (run_id-grouped
  per-metric rows), and (in progress) agent chat sessions are database-backed — the platform
  is correct behind a load balancer with N API tasks. Failed ingestion rolls back partial data
  writes but persists the failed job record.
- **AI provider abstraction**: `AI_PROVIDER = mock | anthropic | openai` (bedrock rejected at
  boot until implemented). Real adapters are httpx-based, share a grounded system prompt built
  from tool context (metrics/genome/simulation, distributions trimmed), keep evidence-trail
  parity with mock, map failures to 502, and validate keys at startup. Mock needs no keys and
  powers the full demo.
- **AWS (staging, account 216812304180, us-east-1, live since 2026-07-02)**: VPC with public/
  private subnets + NAT · ALB (path `/api/*` → api target group, else web — same-origin, so
  CORS is moot) · ECS Fargate services `aurora-staging-{api,web}` (2 tasks each) · RDS
  Postgres 16 `db.t4g.micro/20GB` (**free-plan account limit** — t4g.medium was rejected with
  FreeTierRestrictionError) · ECR · Secrets Manager (`database-url`, `jwt-secret`) · S3
  uploads bucket · CloudWatch logs. **Terraform state**: S3 remote backend
  `aurora-terraform-state-216812304180` (versioned/private/SSE) — never local, never in git.
- **Deploy path**: GitHub Actions `deploy.yml` (workflow_dispatch: environment + image_tag)
  assumes OIDC role `aurora-github-deploy` (least-privilege: ECR push + ECS redeploy),
  builds both images, pushes, forces new deployment, waits for stability. **Migrations run as
  a one-off ECS task**: `python -m aurora_db.migrate` (checkout-free; reads DATABASE_URL from
  the task's secret injection). Seeding likewise: `python -m aurora_db.seed --demo nimbus
  --verify --scale 0.1`. RDS is private — never expect to reach it from a laptop.
- **CI** (8 jobs on every PR): api / database-on-Postgres (migrate + full-scale seed + tests) /
  ml / graph / simulations / analytics (ruff + pytest each) · web (lint + typecheck + build) ·
  E2E (Playwright with `--with-deps` chromium, boots real API+web). 139+ pytest, 4 E2E.

### 2.2 Hard-won correctness facts (do not relearn these by breaking them)

1. **Calendar-anchored seed windows shift monthly** — engineered anomalies must be injected
   relative to realized neighbor months, never as flat multipliers on seasonal series.
2. **PostgreSQL unique-constraint names are schema-global** (backing indexes) — constraint
   names must be table-scoped (`role_company_name`, not `company_id_name`).
3. **Containers are not checkouts**: `Path(__file__).parents[3]` crashed the image at import;
   the API package installs the `[postgres]` extra explicitly or RDS is unreachable.
4. **pnpm version is pinned once** — in `package.json#packageManager`; never also in
   pnpm/action-setup (newer action releases hard-error on double-spec).
5. **eslint 10 is blocked upstream** (eslint-plugin-react peaks at 9) — retry only when
   eslint-config-next upgrades its plugin set.
6. **This dev machine**: no Docker/brew/sudo; `aws` (CLI v1) + `terraform` + `k6` live in
   gitignored `.tools/` and scripts auto-fallback to them; Python 3.9 locally (keep
   `Optional[]` unions) while CI/containers run 3.11; zsh pastes treat `#` as arguments —
   instruction code blocks stay comment-free.
7. **AWS free plan**: charges draw down credits ($120 remaining at last check, expires
   2027-01-02), no card billing; account restricts when exhausted. Burn ≈ $2–5/day while
   staging runs; `terraform destroy` stops it, rebuild is ~25 min from code.

### 2.3 Engineering standards (every change, no exceptions)

- Tenant isolation + RBAC on every new query/route; explainability shipped with every new
  computed output; typed errors; no secrets in git ever (state, tfvars, .env are ignored).
- Tests move with code: unit (golden values on Nimbus), API integration, cross-instance
  persistence proofs where state is involved, E2E for user-visible flows. CI must be green
  before merge — merges happen through PRs (`ekam-testing` → `main`), never direct pushes.
- Conventional commits; one logical change per commit; docs sync in the same PR
  (`AI-HANDOFF.md` + relevant guides); update `docs/deploy-prep/tasks.md` session records.
- Workflow rituals: state a time estimate before starting; skip-and-flag blockers (mark HIGH
  PRIORITY, keep moving); every session ends with outcomes + open questions; all work on
  `ekam-testing`.

## 3. Forward backlog — ranked as a FAANG platform team would

Epics in priority order; items marked ☐ open, ◐ partial, 🚫 needs-user-input.

### E1 — Production readiness & reliability (highest)
- ✅ **State everywhere** (2026-07): board reports, ingestion jobs, simulation runs, agent
  chat — all database-backed with cross-instance tests.
- ✅ **Observability baseline** (2026-07): 9 CloudWatch alarms → SNS email, operations
  dashboard (`aurora-staging`), 3 saved Logs Insights queries keyed on request_id.
- ✅ **Continuous delivery** (2026-07): merge-to-main auto-deploys staging with immutable
  `sha-` tags + post-deploy ALB health gate; production stays manual dispatch. Open slice:
  workflow-invoked migration task behind an approval gate.
- ◐ **Graceful degradation**: readiness (`/ready`, 503 on DB loss) drives ALB rotation while
  liveness restarts wedged processes; degradation contract tested. Open: rotation/task-cycling
  drills under real infra.
- ✅ **Backups/DR** (2026-07-20): snapshot policy reviewed (1d staging / 7d+protection prod),
  `docs/RUNBOOK-DR.md` with measured 30-min rebuild drill + secret rotation. Open: rehearse
  the timed destroy→rebuild once the owner decides staging uptime.
- ✅ **SLOs** (2026-07-20): targets published in the runbook; `slo.yml` runs k6 twice weekly
  against staging at p95<500ms (measured 42.8ms), no-ops when the stack is down.

### E2 — Security & governance
- 🚫 **Branch protection** on `main`: attempted via API — GitHub Free + private repo returns
  403 ("Upgrade to GitHub Pro or make this repository public"). Owner decision.
- 🚫 **HTTPS**: needs a domain the user buys/owns → ACM cert → `certificate_arn` tfvars →
  re-apply → HTTP→HTTPS redirect listener. Until then the ALB is HTTP-only.
- ◐ **Secret rotation**: manual runbook shipped (`RUNBOOK-DR.md` §4 — JWT key + DB password
  via `-replace`). Open: automated rotation, and scoping the deployer IAM user down from
  AdministratorAccess.
- ◐ **Dependency hygiene cadence**: triage ritual proven twice (apply-on-branch within ranges,
  gate, close superseded PRs — sessions of 2026-07-01 and 2026-07-20). Open: write it up as a
  weekly checklist; secret scanning + CodeQL blocked with branch protection on the plan tier.
- ✅ **Audit trail depth** (2026-07-20): report approval, data-source registration, uploads,
  syncs, scenario creation, and simulation runs all audited (admin was already covered at the
  service layer); coverage pinned by `test_audit_coverage.py`. Agent Q&A excluded by design
  (`ai_interaction` is its own trail). Auth-event auditing: open decision (volume trade-off).

### E3 — Product depth (the moat)
- 🚫 **Live AI provider**: implemented + tested; activates the moment the user supplies
  `ANTHROPIC_API_KEY` (preferred) or `OPENAI_API_KEY` and flips `AI_PROVIDER`. Then: prompt
  eval harness (golden Q&A against Nimbus), token/cost telemetry (fields already recorded),
  streaming responses, provider fallback chain.
- ☐ **Async job architecture**: long simulations and board-pack rendering move to background
  workers (SQS or Redis/RQ per ADR-007) with job-status polling the UI already supports;
  removes request-timeout ceilings and enables >10k-trial runs.
- ◐ **Board pack rendering** (2026-07-20): real multi-page reportlab PDF engine shipped
  (cover + per-section layouts, sparse-safe). Open: scheduled generation, S3 storage +
  signed URLs (bucket + IAM already provisioned).
- ✅ **Forecast ensemble** (2026-07-20): SARIMAX + ensemble + "auto" with rolling-backtest
  selection; `accuracy.backtest` carries {selected, mape_by_method, holdout_points} as the
  explainability evidence (synthetic backtest: sarimax 0.7% vs baseline 20.5% MAPE). Open:
  surface the backtest block in the forecasting UI.
- ☐ **Live connectors** beyond CSV: one real accounting SaaS connector (QuickBooks/Xero
  sandbox) through the existing connector registry + lineage.
- ☐ **Graph durability**: Neo4j in prod or keep in-memory projection rebuilt at boot
  (current, acceptable — it's derived data); decide explicitly and record the ADR.

### E4 — Scale & multi-tenancy (when real tenants arrive)
- ☐ Tenant onboarding flow (signup → company provisioning → invite), billing hooks,
  per-tenant usage metering (AI tokens, storage, simulations).
- ☐ ClickHouse analytics backend activation path + data-volume load tests (seed --scale 1.0
  is the fixture); autoscaling policies for ECS; RDS instance right-sizing off the free plan.
- ☐ Schema-per-tenant isolation option per ADR-004's documented upgrade path.

### E5 — Developer experience
- ◐ OpenAPI-generated typed client (2026-07-20): versioned spec + generated types pipeline
  (`pnpm generate:api-types`); auth/login/health types generated-backed. Open: add
  `response_model` envelopes to API routes so the remaining hand-rolled interfaces (board
  reports, ingestion, metrics…) can flip to generated — also fixes the found drift
  (client-only `template` field).
- ✅ Pre-commit hooks (2026-07-20): `.githooks/pre-commit` lints staged files only
  (ruff/eslint); enable per clone with `git config core.hooksPath .githooks`.
- ☐ Devcontainer/Nix for parity with CI (kills the 3.9-vs-3.11 gap and the no-Docker gap).
- ◐ PR template + CODEOWNERS shipped (2026-07-20); open: issue templates, release tagging +
  changelog automation.

## 4. Owner action list (everything only the product owner can do)

Ordered by urgency. Nothing here blocks the engineering backlog except where noted.

1. **⚠️ URGENT — credits** ($11 as of 2026-07-20, ~2 days of staging runtime): either say
   "destroy staging" (30-min documented rebuild whenever wanted) or upgrade the AWS account
   plan (Console → Billing). Doing nothing = staging dies on credit exhaustion.
2. **Alarm email confirmation** (optional): CloudWatch alarms stay silent until the AWS SNS
   confirmation email is clicked. Deliberately NOT re-sent (owner asked for no more emails);
   click the existing one only if alarm emails are wanted.
3. **GitHub Pro or public repo**: unlocks branch protection (+ secret scanning/CodeQL).
4. **Domain name**: unlocks ACM cert → HTTPS listener (procedure ready in tfvars).
5. **AI provider key**: `ANTHROPIC_API_KEY` (preferred) or `OPENAI_API_KEY` + flip
   `AI_PROVIDER` — the live agent is one env var away.
6. **Apply the least-privilege deployer policy** from the AWS Console when convenient
   (`infra/aws/deployer-least-privilege.json`, procedure: RUNBOOK-DR §7).
7. **First real connector choice**: QuickBooks vs Xero (needs a sandbox account from you).

---

*Maintenance: this document describes intent + verified state. When reality changes, update
§2/§3 in the same PR that changes it, and log the session in `AI-HANDOFF.md`.*
