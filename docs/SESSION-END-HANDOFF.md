# AURORA — Start Here Tomorrow

> **Session ended:** 2026-07-02 · **STAGING IS LIVE ON AWS.** PRs #20–#22 merged; CI 8/8 green.

---

## 30-second status

AURORA runs on AWS staging: ECS Fargate (2×api, 2×web) behind an ALB, RDS Postgres
(migrated to Alembic head, Nimbus seeded + verified), images built by the GitHub-Actions
Deploy workflow via an OIDC role. All persistence is database-backed, the web stack is
next 16 / react 19 / ts 6 / tailwind 4 / eslint 9, and real Anthropic/OpenAI agent
providers are implemented (mock active until a key is supplied). **138 pytest + 4 E2E green.**

| | |
|---|---|
| **Staging** | http://aurora-staging-959198614.us-east-1.elb.amazonaws.com · `cfo@nimbus.test` / `aurora-demo-2026` |
| **Deploys** | GitHub → Actions → Deploy (staging · latest) — no local Docker needed |
| **Costs** | RDS micro + ALB + NAT + Fargate ≈ $2–5/day — `terraform destroy` in `infra/terraform` to stop |
| **Next** | AI provider key · custom domain + ACM for HTTPS · production environment |

---

## Start local dev (copy-paste)

```bash
cd ~/Projects/aurora
git pull origin main
./scripts/local-run.sh          # terminal 1 — API :8000
./scripts/dev-web.sh            # terminal 2 — web :3000
```

Open http://localhost:3000 and log in with the demo credentials above.

---

## Run tests

```bash
# E2E (4 Playwright tests — API must be running)
cd apps/web && pnpm test:e2e

# Full Python suite (116 pytest)
source apps/api/.venv/bin/activate
for d in apps/api packages/database packages/ml packages/graph packages/simulations packages/analytics; do
  (cd "$d" && ruff check . && pytest -q) || exit 1
done

# AWS preflight (no credentials needed)
./scripts/deploy-check.sh
```

---

## What's done vs. what's left

**Done:** P1–P9 (foundation → AWS hardening), PRs #4–#11, #15–#17, design docs, CI, E2E, deploy checklist.

**Left:** First `terraform apply` + ECR push + ECS deploy (see checklist). Optional: review open Dependabot PRs #12–#14.

---

## Read next (in order)

1. **[`AI-HANDOFF.md`](AI-HANDOFF.md)** — full session log, architecture decisions, file map, subagent workflow
2. **[`PROJECT-MASTER-GUIDE.md`](PROJECT-MASTER-GUIDE.md)** — operational handbook (setup, env vars, troubleshooting)
3. **[`DEPLOY-CHECKLIST.md`](DEPLOY-CHECKLIST.md)** — step-by-step first AWS deploy
4. **[`roadmap/implementation-roadmap.md`](roadmap/implementation-roadmap.md)** — phase acceptance criteria

---

## Pick-up prompt for next AI agent

> Read `docs/SESSION-END-HANDOFF.md` and `docs/AI-HANDOFF.md`. AURORA Phases 1–9 are merged to `main` with 116 pytest + 4 E2E tests green. Your task is the first AWS production deploy: run `./scripts/deploy-check.sh`, follow `docs/DEPLOY-CHECKLIST.md`, apply Terraform, push images to ECR, run migrations, and trigger `.github/workflows/deploy.yml`. Demo login is `cfo@nimbus.test` / `aurora-demo-2026`. Do not force-push `main`.
