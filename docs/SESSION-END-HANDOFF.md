# AURORA — Start Here Tomorrow

> **Session ended:** 2026-07-21 · Repo **PUBLIC** with branch protection · **staging DESTROYED
> on purpose** (credit preservation — rebuild ≈30 min) · everything merged to `main`, working
> tree clean, all branches aligned.

---

## 30-second status

AURORA is feature-complete through the E1–E3 hardening program: database-backed persistence
everywhere (reports, jobs, simulations, agent chat), typed response envelopes + generated web
client types, real multi-page PDF board packs with S3 archival, SARIMAX/ensemble forecasting
with backtest-evidence UI, full audit-trail coverage, CloudWatch observability, continuous
delivery with health gates and one-click migrations, DR runbook with two passed live drills
(task-kill: zero downtime; cold build: 30 min). Real Anthropic/OpenAI agent providers are
implemented — mock is active until a key is supplied (`OPENAI_BASE_URL` supports free tiers
like Groq). **150+ pytest + 4 E2E green.**

| | |
|---|---|
| **Repo** | https://github.com/Ekam-Bindra/aurora — PUBLIC, branch protection (8 required checks), secret scanning on |
| **AWS** | Stack destroyed 2026-07-21 (≈$9 credits preserved; plan expires 2027-01-02). State safe in S3. Deploy workflow no-ops until rebuilt |
| **Rebuild** | `RUNBOOK-DR.md` §3 — terraform apply → Actions deploy (run_migrations ✓) → seed task ≈ 30 min |
| **Demo now** | Runs fully locally, zero cloud: two terminals below · `cfo@nimbus.test` / `aurora-demo-2026` |

---

## Start local dev (copy-paste)

```bash
cd ~/Projects/aurora
git pull origin main
./scripts/local-run.sh
```

```bash
cd ~/Projects/aurora
./scripts/dev-web.sh
```

Open http://localhost:3000 and log in with the demo credentials above.

---

## Run tests

```bash
cd ~/Projects/aurora
source apps/api/.venv/bin/activate
for d in apps/api packages/database packages/ml packages/graph packages/simulations packages/analytics; do (cd "$d" && ruff check . && pytest -q) || break; done
```

```bash
cd ~/Projects/aurora/apps/web
pnpm test:e2e
```

---

## Owner action list (nothing is urgent while the stack is down)

1. AI key when wanted — free path: Groq key + `AI_PROVIDER=openai`,
   `OPENAI_BASE_URL=https://api.groq.com/openai`; best quality: Anthropic key.
2. Domain when wanted (GitHub Student Pack has free `.me`/`.tech`; Porkbun $1–3/yr) — then
   HTTPS is handled for you. Zero-domain alternative: CloudFront in front of the ALB.
3. Apply `infra/aws/deployer-least-privilege.json` from the IAM console (RUNBOOK §7).
4. Rebuild staging whenever a live demo is needed (ask, or RUNBOOK §3).
5. Pick QuickBooks vs Xero (+ sandbox account) to start the first live connector.

## Read next (in order)

1. **[`MASTER-PROMPT.md`](MASTER-PROMPT.md)** — mission, verified system state, hard-won
   correctness facts, standards, ranked epic backlog, owner list
2. **[`AI-HANDOFF.md`](AI-HANDOFF.md)** — session log + standing instructions
3. **[`RUNBOOK-DR.md`](RUNBOOK-DR.md)** — rebuild/restore/rotation procedures + drill log
4. **[`deploy-prep/tasks.md`](deploy-prep/tasks.md)** — per-session records (10 sessions)

---

## Pick-up prompt for next AI agent

> Read `docs/MASTER-PROMPT.md` first, then `docs/AI-HANDOFF.md`. Follow the standards and
> rituals in MASTER-PROMPT §2.3 (estimate first, all work on `ekam-testing`, PR-only merges —
> `main` is branch-protected, 8 CI checks required). The AWS staging stack is deliberately
> destroyed; the deploy workflow no-ops until it is rebuilt per `RUNBOOK-DR.md` §3. The repo
> is PUBLIC — never commit anything sensitive. Continue with the open items in
> MASTER-PROMPT §3 (async job workers are the next big E3 slice) or whatever the owner asks.
