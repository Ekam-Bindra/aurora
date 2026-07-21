# Deploy-Prep Session — Task List

> **Session:** 2026-07-01 · **Branch:** `ekam-testing`
> Companion docs: [`requirements.md`](requirements.md) · [`design.md`](design.md)
> Status values: ☐ pending · ◐ in progress · ✅ done · ⏭️ skipped (high priority) · 🚫 blocked (user decision/input needed)

## Time estimate (stated before execution, per standing instruction #4)

**Roughly 1.5–2.5 hours of agent working time**, dominated by test-suite runs and the three
major-version dependency bumps. Breakdown: docs authoring ~15 min · seed fix + database suite
(scaled + full reseed) ~20–30 min · full Python baseline ~10 min · web build + E2E ~15 min ·
preflight/terraform ~10 min · dependency bumps ~30–60 min (highest variance; tailwind 4 may be
skipped-and-flagged if it exceeds its box) · docs sync, handoff updates, commits, final report
~20 min. The actual AWS deploy is **not** included — it is blocked by missing tooling/credentials
(requirements.md C-1/C-2).

## Tasks

| # | Task | Requirement | Status | Outcome notes |
|---|------|-------------|--------|---------------|
| T1 | Create `ekam-testing` from `main`; confirm never on `main` | NFR-1 | ✅ | Branched from `d93d291` |
| T2 | Read/understand all files; verify handoff claims against code | FR-1 | ✅ | 2 explorer audits + direct reads; discrepancies recorded in design.md §1 |
| T3 | Author requirements / design / task docs | FR-2 | ✅ | This folder |
| T4 | State time estimate before execution | FR-3 | ✅ | Above |
| T5 | Fix seed anomaly date-rollover bug (A + B), update manifest | FR-4 | ✅ | `nimbus.py`: anomalies pinned vs realized neighbor months; spec doc synced. Root cause: `date.today()`-anchored window × seasonal table × fixed-index flat multipliers — B red since 2026-07 rollover, A would fail every November |
| T6 | Database suite green (scaled + full-scale seed tests) | FR-4 | ✅ | 17/17 pass incl. both seed tests |
| T7 | Full Python baseline green with pipefail (116 tests, 6 packages) | FR-4/FR-6 | ✅ | api 78 · db 17 · ml 10 · graph 2 · sim 6 · analytics 3; ruff clean |
| T8 | Web production build green | FR-6 | ✅ | 13 routes, static prerender |
| T9 | Playwright E2E suite green (4 tests) | FR-6 | ✅ | Required one-time `pnpm test:e2e:install` (chromium binary was missing on this machine) |
| T10 | `deploy-check.sh` + terraform fmt/validate; document machine-gap FAILs | FR-6 | ✅ | fmt + validate OK via `.tools/terraform`; only FAILs = `aws` + `docker` CLIs absent (Q-2); 8 warnings are apply-time items (tfvars, env vars, `.env.production`) |
| T11 | Load-test smoke via curl fallback against local API | FR-6 | ✅ | health / login / metrics-overview / board-reports all OK (k6 not installed → curl path) |
| T12 | Bump `typescript` → 6.0.3; build gate | FR-5 | ✅ | New TS2882 check needed a `*.css` module declaration (`apps/web/css.d.ts`); typecheck + build green |
| T13 | Bump `next` → 16.2.9; build + E2E gates | FR-5 | ✅ | Resolves to 16.2.10; green on React 18.3.1; `next-env.d.ts` regenerated |
| T14 | Bump `tailwindcss` → 4.3.1; build + E2E gates | FR-5 | ✅ | Migration: `@tailwindcss/postcss` plugin, `@import "tailwindcss"` + `@config` bridge to shared preset, autoprefixer dropped; tokens verified in compiled CSS |
| T15 | Sync stale `README.md` status/quickstart | FR-7 | ✅ | Also `apps/web/README.md` (was Phase-1-era) |
| T16 | Update `AI-HANDOFF.md` + `PROJECT-MASTER-GUIDE.md` | FR-7 | ✅ | Quick state, remaining work, standing instructions #8–#9, changelogs |
| T17 | Delete local `feat/*` branches verified merged; list remote for approval | FR-8 | ✅ | 12 local branches deleted (all `--merged main` verified); remote deletion pending Q-5 |
| T18 | Commit (conventional, per logical change) + push `ekam-testing` | NFR-1/NFR-3 | ✅ | 7 commits; `main` untouched |
| T19 | Final report: outcomes, skipped/high-priority, questions, gaps | FR-9 | ✅ | Delivered in session-end message |

## Additional findings recorded during execution

- **Dependabot PRs #12–#14 are unsafe to merge as-is**: their branches predate PRs #10/#11/#17 —
  merging would downgrade `@types/node` (26→20) and `eslint-config-next` (16→14) and delete the
  Playwright E2E scripts + `@playwright/test` dependency. Superseded by T12–T14; recommend closing.
- **Pre-existing peer mismatch** (introduced by merged PR #11): `eslint-config-next@16` wants
  `eslint >= 9`, repo has `eslint 8.57`. Install-time warning only; `next build` is unaffected.
  Bumping eslint to 9 (flat-config migration) was NOT done — out of scope, needs a decision.
- **Playwright chromium binary** is a per-machine prerequisite: `pnpm test:e2e:install` (now in
  `apps/web/README.md`).
- **`scripts/local-run.sh` contains leftover Cursor debug instrumentation** (`_agent_log` writing
  to `.cursor/debug-dbff07.log`). Harmless; left untouched (not in scope). Flagging for cleanup.

## Session 2 (2026-07-01, same day) — "complete the list, continue development"

User authorized acting on their behalf for anything obtainable, and directed completing the
remaining list + continuing development. Outcomes:

| # | Task | Status | Outcome notes |
|---|------|--------|---------------|
| S2-1 | Install `aws` CLI | ✅ | v2 pkg installer fails user-locally (no sudo); **aws-cli v1.44 via pip** into `.tools/aws-venv`, `.tools/aws` symlink; `deploy-check.sh` now finds it (preflight: only Docker still FAILs) |
| S2-2 | Install `k6` | ✅ | v2.1.0 arm64 binary in `.tools/k6`; `load-test.sh` picks it up |
| S2-3 | Install Docker | 🚫 user-only | Needs admin install (Docker Desktop / colima). **Optional for deploys**: `.github/workflows/deploy.yml` builds images in Actions |
| S2-4 | **Persistence development** (the Q-6 decision, resolved as "persist") | ✅ | Board reports → `board_report` (+`content` col), ingestion jobs → new `ingestion_job` table, simulation runs → `run_id`-grouped `simulation_result` rows; migration `0002`; in-memory fallback kept for no-DB test mode; failed ingestion runs roll back partial inserts but persist the failed job; 4 new cross-instance + tenant-isolation tests |
| S2-5 | SQLite schema-evolution fix (found via E2E failure) | ✅ | `create_all` never adds columns to existing tables → stale `data/*.db` 500ed after 0002. Startup now runs **Alembic upgrade head** for file-backed SQLite; stale DBs self-heal (verified against the real stale `aurora_e2e.db`) |
| S2-6 | Web lint under Next 16 | ✅ | `next lint` removed in 16 → ESLint 9 flat config with `eslint-config-next` arrays; new `set-state-in-effect` rule flags 8 pre-existing fetch-on-mount sites (downgraded to warnings pending refactor) |
| S2-7 | eslint 10.6.0 (new Dependabot PR) | ⏭️ rejected | `eslint-plugin-react` (transitive) caps at eslint 9 and crashes on a removed API; documented in `eslint.config.mjs`; PR closed |
| S2-8 | React 19.2.x group bump (new Dependabot PR) | ✅ | react/react-dom/@types 18→19; typecheck + lint + build + 4 E2E green; stale PR branch closed |
| S2-9 | Remote branch cleanup + close Dependabot PRs | ✅ | 12 merged `feat/*` + 5 dependabot branches deleted on origin (closes PRs #12–#14 + the two new ones) |
| S2-10 | `local-run.sh` debug-cruft removal | ✅ | Leftover Cursor `_agent_log` instrumentation stripped |
| S2-11 | ADR §12 gap | ✅ no change needed | Section exists in `system-architecture.md:557` — session 1's doc-sweep claim was wrong |
| S2-12 | k6 load test run | ⏭️ flagged | k6 executes, but ~50–85% connection-level failures **specific to k6 on this machine**; API exonerated: 300/300 concurrent curl requests 200 OK, k6's own p95 latency 81ms on successful requests, zero non-200s in API logs. Rerun k6 against staging post-deploy |

## Session 3 (2026-07-01, same day) — "instructions for me, keep working"

| # | Task | Status | Outcome notes |
|---|------|--------|---------------|
| S3-1 | Step-by-step user action guide | ✅ | [`USER-ACTIONS.md`](USER-ACTIONS.md) — merge, AWS credentials, optional Docker, GitHub secrets, first deploy, AI key; each step with verification |
| S3-2 | GitHub OIDC bootstrap script | ✅ | `scripts/setup-aws-oidc.sh` — idempotent; creates provider + least-privilege deploy role (ECR push, ECS redeploy) and prints `AWS_ROLE_ARN` |
| S3-3 | CI: web lint + typecheck steps, new E2E job | ✅ | Per `docs/E2E.md` CI notes; failure traces uploaded as artifacts |
| S3-4 | Real AI providers (Anthropic + OpenAI) | ✅ | httpx adapters, grounded system prompt from tool context, evidence-trail parity with mock, `AIProviderError` → 502 envelope, startup key validation, 12 MockTransport tests; `AI_PROVIDER=mock` still default; bedrock explicitly rejected at boot |
| S3-5 | `set-state-in-effect` refactor (8 sites) | ✅ | Redundant draft-mirroring effect deleted (render already falls back); dead null-reset branches removed (render guards by id); load-on-param-change effects schedule state updates into promise callbacks. Rule restored to **error**; lint fully clean |

| Item | Why | Owner action |
|------|-----|--------------|
| `terraform apply` → ECR push → ECS deploy → RDS migrations (DEPLOY-CHECKLIST steps 2–6) | No `aws`/`docker` CLI, no credentials; billable + irreversible without go-ahead | Q-2: provision tooling + credentials, then re-run checklist |
| Docker image build validation | No `docker` CLI | Q-2 |
| GitHub Actions deploy secrets (`AWS_ROLE_ARN`, `AWS_REGION`) + environments | User's GitHub settings | DEPLOY-CHECKLIST step 5 |
| Merging Dependabot PRs #12–#14 (or `ekam-testing`) into `main` | No `gh` CLI; `main` off-limits this session | Q-3 |
| Real AI provider | No API keys; only `mock` implemented | Q-7 |
| Persistent queues / board-report DB wiring | Marked "Future"; production-correctness decision needed (design.md §5.1) | Q-6 |
| Remote `feat/*` branch deletion | Outward-facing destructive action | Q-5 |

## Session 5 (2026-07-02) — "continue as a FAANG team would"

| # | Task | Status | Outcome notes |
|---|------|--------|---------------|
| S5-1 | Master engineering prompt | ✅ | [`../MASTER-PROMPT.md`](../MASTER-PROMPT.md): verified state, hard-won correctness facts, standards, ranked epic backlog E1–E5, open product-owner questions |
| S5-2 | Agent chat persistence | ✅ | Last in-memory store gone: interactions → `ai_interaction` (incl. `latency_ms`), sessions = grouped interactions; cross-instance + tenant-isolation tests |
| S5-3 | k6 vs staging | ✅ | First run exposed login-per-iteration tripping the auth rate limiter (feature, not bug) — smoke.js now logs in once in `setup()`; result: **965/965 checks, 0% failures, p95 35.6ms** |
| S5-4 | Continuous delivery | ✅ | Push-to-main auto-deploys staging (production stays manual); immutable `sha-` image tags; concurrency guard; post-deploy ALB health gate (deploy role gained `elbv2:DescribeLoadBalancers`) |
| S5-5 | Branch protection | 🚫 user decision | GitHub Free + private repo → 403 "Upgrade to GitHub Pro or make this repository public". HIGH PRIORITY governance gap |
| S5-6 | CloudWatch alarms | ✅ | 9 alarms (ALB 5xx / p95 latency / unhealthy hosts ×2, ECS CPU ×2, RDS CPU/storage/connections) → SNS email; **user must click the AWS subscription-confirmation email** |

## Session 6 (2026-07-20) — "begin work using the master prompt"

| # | Task | Status | Outcome notes |
|---|------|--------|---------------|
| S6-0 | Recon after 18 idle days | ✅ | Staging healthy, branches aligned, main CI+deploy green. **Credits $11.05 — ~2 days of runway** (was $120 on 07-02); SNS confirm still pending → resent; 5 new Dependabot patch PRs |
| S6-1 | Readiness vs liveness | ✅ | `/ready` now 503s when DB unreachable and the ALB api target group probes it (rotation-correct); ECS container check stays on `/health`; degradation contract test; verified live — targets 2/2 healthy on the new probe |
| S6-2 | Backups/DR runbook | ✅ | [`../RUNBOOK-DR.md`](../RUNBOOK-DR.md): snapshot policy (1d/7d), restore procedure, measured 30-min rebuild drill, JWT/DB-password rotation, free-plan guardrails |
| S6-3 | Operations dashboard | ✅ | CloudWatch dashboard (traffic, latency percentiles, target health, ECS, RDS, alarm strip) + 3 saved Logs Insights queries; applied |
| S6-4 | Scheduled SLO gate | ✅ | `slo.yml` Mon+Thu k6 vs staging at p95<500ms (measured 42.8ms), graceful no-op when stack destroyed; smoke.js gains SLO_P95_MS |
| S6-5 | Audit coverage | ✅ | Report approve, source register, upload, sync, scenario create, simulation run now audited (+ pinning test); admin was already service-layer audited |
| S6-6 | Dependabot batch (#27–#31) | ✅ | All five were within-range lockfile bumps; applied + gated; PRs closed as superseded |
| S6-7 | Governance files | ✅ | PR template with standards checklist, CODEOWNERS |
| S6-8 | IAM deployer scoping | ⏭️ flagged | Deferred — apply-time lockout risk needs a careful, tested policy; runbook documents the manual rotation meanwhile |

## Session 7 (2026-07-20, same day) — "subagents, owner-tasks aside, stop the emails"

| # | Task | Status | Outcome notes |
|---|------|--------|---------------|
| S7-1 | Stop notification spam | ✅ | GitHub repo subscription set to **ignored** for the owner (zero repo emails; revert via Watch menu); SNS confirmation deliberately NOT re-sent |
| S7-2 | Owner action list | ✅ | MASTER-PROMPT §4 rewritten as the single ordered "only-you" list (credits URGENT, SNS optional, GitHub Pro, domain, AI key, IAM apply, connector choice) |
| S7-3 | Subagent A — board-pack PDF engine | ✅ | reportlab multi-page renderer (cover + per-section layouts, sparse-safe, cents→$), export contract unchanged, pypdf-verified tests; full API suite green |
| S7-4 | Subagent B — forecast ensemble | ✅ | SARIMAX + ensemble + auto (rolling backtest selection, accuracy.backtest evidence); synthetic backtest sarimax 0.7% vs baseline 20.5% MAPE; ensemble semantics redefined (was prophet-absent local blend) — defaults untouched |
| S7-5 | Subagent C — typed API client | ✅ | openapi-typescript pipeline (versioned spec+types, no Python needed at build), AuthUser/Login/health generated-backed; untyped {data,meta} envelopes documented as the unlock; drift found (client-only `template` field) |
| S7-6 | IAM least-privilege policy | ✅ artifact | `infra/aws/deployer-least-privilege.json` + RUNBOOK §7 console procedure; NOT auto-applied (lockout risk) — owner item |
| S7-7 | Pre-commit hook | ✅ | `.githooks/pre-commit` staged-file ruff/eslint; validated itself on every session commit |

## Session 8 (2026-07-20, same day) — "next items on your end"

| # | Task | Status | Outcome notes |
|---|------|--------|---------------|
| S8-0 | Recon | ✅ | Credits **$9.28** (~2 days); staging healthy; branches aligned |
| S8-1 | Typed response envelopes | ✅ | Envelope[T] + payload models (extra-allow, serializer-exact) on health/ready, board reports, ingestion; `template` field declared server-side |
| S8-2 | Client flip to generated types | ✅ | BoardReport*/DataSource/IngestionJob* generated-backed with narrowing overrides; OmitIndexSignature helper (additionalProperties pitfall); gates green |
| S8-3 | Backtest evidence UI | ✅ | Forecasting page: method selector (baseline/sarimax/ensemble/auto) + "Why this method" panel rendering accuracy.backtest |
| S8-4 | ADR-009 + issue templates | ✅ | Graph stays boot-rebuilt projection (revisit >30s rebuilds); bug/feature templates |

## Session 9 (2026-07-20, same day) — "next items on your end" (2)

| # | Task | Status | Outcome notes |
|---|------|--------|---------------|
| S9-1 | Task-cycling drill (live) | ✅ | Stopped a live api task: **90/90 probes green over 3 min, zero downtime**, ECS self-healed to 2/2; logged in RUNBOOK §6 |
| S9-2 | S3 board-pack archival | ✅ | Exports write through to the provisioned bucket + 1h presigned link in X-Export-Archive-Url; best-effort (S3 failure never blocks the download); bucket/IAM/env were already wired |
| S9-3 | Workflow migrations | ✅ | deploy.yml dispatch input run_migrations runs the one-off ECS migrate task (exit-code gated) before redeploy; OIDC role gained RunTask/DescribeTasks + scoped PassRole |
| S9-4 | Dependabot ritual | ✅ | PROJECT-MASTER-GUIDE §16 |
