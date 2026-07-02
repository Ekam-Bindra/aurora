# Deploy-Prep Session — Design Document

> **Session:** 2026-07-01 · **Branch:** `ekam-testing`
> Companion docs: [`requirements.md`](requirements.md) · [`tasks.md`](tasks.md)

---

## 1. Verified current state (evidence-based)

All claims verified against code on 2026-07-01, not taken from docs alone.

| Fact | Evidence |
|------|----------|
| P1–P9 + PRs #15–#17 merged; working tree clean on `main` @ `d93d291` | `git log`, `git status` |
| 116 pytest tests exist (api 78 + packages 38); 4 Playwright E2E tests | test-function counts in `apps/api/tests/`, `packages/*/tests/`, `apps/web/e2e/` |
| **2 failing tests today**: `test_seed_scaled_passes_core_checks`, `test_seed_full_scale_passes_all_checks` | `packages/database/tests/test_seed.py` — "Anomaly B (revenue dip): expected present, got missing" |
| Board reports / simulations / ingestion jobs are per-process in-memory dicts | `apps/api/aurora/services/board_reports.py:28`, `simulation.py:19-20`, `ingestion.py:26` |
| `BoardReport` table exists but is not wired to the service | `packages/database/aurora_db/models/intelligence.py:150-166` |
| Only the mock AI provider is implemented | `apps/api/aurora/providers/` contains `base.py` + `mock.py` only; `config.py:72` |
| ECS `desired_count = 2` for both api and web services | `infra/terraform/variables.tf:40,46` |
| No Redis/ElastiCache/Neo4j resources in Terraform | grep over `infra/terraform/*.tf` |
| Web deps: next `^14.2.5`, tailwindcss `^3.4.6`, typescript `^5.5.3` | `apps/web/package.json` |
| Zero TODO/FIXME/HACK markers in first-party code | repo-wide grep |
| Machine lacks `aws`, `docker`, `gh`, `k6`; terraform only via `.tools/terraform` | shell probes 2026-07-01 |

## 2. Work item A — seed anomaly date-rollover fix (FR-4)

### Mechanism of the bug

`seed_nimbus` anchors a 36-month window to `date.today()` (`nimbus.py:127`), then multiplies each
month by a calendar-seasonal factor (`SEASONAL`, Nov=1.45 / Dec=1.55 / Jan=0.82) and injects
anomalies at **fixed indices**:

- Anomaly B: `revenue[16] *= 0.78` (`nimbus.py:416`)
- Anomaly A: `marketing[13] *= 2.8` (`nimbus.py:568`)

The verifier detects anomalies **relative to neighboring months** (`nimbus.py:806-820`,
`795-804`). Which calendar month falls at index 16 depends on the run date, so the same code
passes in June (index 16 = Nov, neighbors Oct/Dec) and fails in July (index 16 = **Dec**, the
seasonal peak — a −22% dip on Dec is still above the Nov/Jan neighbor mean). Anomaly A fails by
the same math whenever the run month is November (index 13 lands on January).

### Chosen fix

Pin the injected anomalies to their **realized neighbor months** instead of flat multipliers:

- `revenue[16] = 0.70 × mean(revenue[15], revenue[17])` — always 30% below the neighbor mean;
  detector threshold is 0.85, so it passes with margin in every calendar alignment.
- `marketing[13] = 2.8 × 0.06 × mean(revenue[11,12,14,15])` — detector threshold is 2.0× the
  neighbor mean, passes with margin in every alignment.
- Update `ANOMALY_MANIFEST` magnitudes to describe the neighbor-relative semantics.

### Alternatives rejected

| Alternative | Why rejected |
|-------------|--------------|
| Anchor seed window to a fixed date | Makes the demo data go permanently stale; changes observable product behavior, not just tests (re-architecture without approval) |
| Seasonally-adjust the verifier | Leaves the *injected data* undetectable by the product's own risk logic in peak-month alignments — the check would pass while the demo narrative ("spot the dip") breaks |
| Deepen flat multipliers (e.g. −45%) | Still alignment-dependent, just with a different failure month; not a fix |

Anomalies C–G reviewed for the same fragility: they are ratio-, count-, or trend-based and are
calendar-robust; left unchanged.

## 3. Work item B — dependency bumps (FR-5)

Three open Dependabot PRs target `main`; this machine has no `gh` CLI and `main` is off-limits,
so the identical bumps are applied on `ekam-testing` and gated:

| Order | Bump | Risk | Gate |
|-------|------|------|------|
| 1 | `typescript` 5.5.3 → 6.0.3 | Major; compiler strictness | `pnpm --filter @aurora/web build` |
| 2 | `next` 14.2.5 → 16.2.9 | **Two majors**; App Router API changes, React 19 peer | build + full E2E |
| 3 | `tailwindcss` 3.4.6 → 4.3.1 | Major; new config model (CSS-first), PostCSS plugin split | build + full E2E + visual sanity |

Policy: one bump per commit, verify, then next. A failing bump that cannot be fixed within its
box is reverted and flagged **high priority** in the final report (skip-and-flag protocol,
NFR-5). Order rationale: typescript first (cheapest signal), then next (tailwind 3 is compatible
with next 16), tailwind last (largest blast radius, independent of the other two).

## 4. Work item C — deploy preparation matrix (FR-6)

| Check | Runs on this machine? | Method |
|-------|----------------------|--------|
| Python suite (116) + ruff, 6 packages | ✅ | venv at `apps/api/.venv`, `set -o pipefail` |
| Web production build | ✅ | `pnpm --filter @aurora/web build` |
| Playwright E2E (4) | ✅ | `pnpm test:e2e` (playwright `webServer` boots API+web) |
| Load smoke | ✅ (curl fallback) | `./scripts/load-test.sh` against local API |
| `deploy-check.sh` preflight | ✅ partially | terraform via `.tools`; `aws`/`docker` lines will FAIL — documented as machine gaps |
| Terraform fmt + validate | ✅ | `.tools/terraform`, `-backend=false` init already present |
| Docker image builds | ❌ C-1 | flagged; first item once Docker exists |
| `terraform apply` / ECR push / ECS deploy / Alembic vs RDS | ❌ C-1, C-2 | flagged; `DEPLOY-CHECKLIST.md` steps 2–6 remain user-gated |
| GitHub Actions deploy secrets (`AWS_ROLE_ARN`, `AWS_REGION`) | ❌ user's GitHub settings | flagged |

## 5. Production risk register (report to user, no unilateral change)

1. **In-memory stores × `desired_count = 2`** — board reports, simulations, and ingestion jobs
   are per-process dicts; with two API tasks behind the ALB, a job created on task 1 is
   invisible to task 2 (404s on status polls, lost reports). Options: (a) set
   `api_desired_count = 1` for the first deploy, (b) wire `BoardReport` persistence + move job
   state to the DB, (c) add ElastiCache/Redis. Decision required (Q-6).
2. **Major-version bumps** — next 16 and tailwind 4 are large; even if green here, staging
   validation is recommended before production.
3. **Seed date-sensitivity class** — fixed for A/B; if future anomalies are added, follow the
   neighbor-relative pattern.
4. **Terraform remote state** — S3 backend is commented out in `versions.tf`; enable before
   team/CI applies (`infra/terraform/README.md:50`).

## 6. Docs-sync set (FR-7)

- `README.md`: Phase 4 row says "In progress"; quickstart says "Not yet runnable" — both false
  since P4–P9 merged. Update status table + quickstart note to reflect `local-run.sh` reality.
- `AI-HANDOFF.md` + `PROJECT-MASTER-GUIDE.md`: session entry, new test truths, this folder linked.
- Not changed without approval: `system-architecture.md` §12 ADR section referenced by the
  roadmap but absent — flagged as a gap instead of inventing ADRs retroactively.

## 7. Branch & commit policy (NFR-1, NFR-3)

- Everything on `ekam-testing` (created from `main` @ `d93d291`); zero commits to `main`.
- Conventional commits, one logical change each: docs scaffold · seed fix · each dep bump ·
  docs sync · handoff update.
- Push `ekam-testing` to origin at session end (standing instruction #2). No PR opened —
  merging to `main` is the user's call.
