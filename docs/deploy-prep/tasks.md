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

## Blocked / not-executed items (carried to final report)

| Item | Why | Owner action |
|------|-----|--------------|
| `terraform apply` → ECR push → ECS deploy → RDS migrations (DEPLOY-CHECKLIST steps 2–6) | No `aws`/`docker` CLI, no credentials; billable + irreversible without go-ahead | Q-2: provision tooling + credentials, then re-run checklist |
| Docker image build validation | No `docker` CLI | Q-2 |
| GitHub Actions deploy secrets (`AWS_ROLE_ARN`, `AWS_REGION`) + environments | User's GitHub settings | DEPLOY-CHECKLIST step 5 |
| Merging Dependabot PRs #12–#14 (or `ekam-testing`) into `main` | No `gh` CLI; `main` off-limits this session | Q-3 |
| Real AI provider | No API keys; only `mock` implemented | Q-7 |
| Persistent queues / board-report DB wiring | Marked "Future"; production-correctness decision needed (design.md §5.1) | Q-6 |
| Remote `feat/*` branch deletion | Outward-facing destructive action | Q-5 |
