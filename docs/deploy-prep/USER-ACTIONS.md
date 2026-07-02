# AURORA — Your Action List (step by step)

> **Written:** 2026-07-01 · Everything the AI cannot do on your behalf, in the order to do it.
> Each step says how to verify it worked. Steps 1–2 unblock everything else.

---

## Step 1 — Review and merge `ekam-testing` into `main`  (~10 min)

`main`'s CI is currently **red** (the July seed-date bug) until this merges. The branch holds
14 reviewed commits: the seed fix, database persistence for reports/jobs/simulations, the
next 16 / react 19 / typescript 6 / tailwind 4 / eslint 9 stack, tooling, and docs.

1. Open: **https://github.com/Ekam-Bindra/aurora/compare/main...ekam-testing**
2. Click **Create pull request**, title it e.g. `Deploy prep + persistence hardening`.
3. Wait for CI to go green on the PR (all 7 jobs).
4. Click **Merge pull request** (regular merge, per project convention — never force-push).

**Verify:** the Actions tab shows a green run on `main` after the merge.

---

## Step 2 — AWS credentials on this machine  (~15 min)

You need an AWS account where you're allowed to create: VPC, ECS, RDS, ECR, ALB,
Secrets Manager, SSM, S3, IAM.

1. In the AWS Console: **IAM → Users → Create user** (e.g. `aurora-deployer`)
   → **Attach policies directly** → `AdministratorAccess` for the first deploy
   (you can tighten later) → create an **access key** (type: CLI).
2. In a terminal (blocks are paste-safe — no inline comments, because plain macOS zsh
   treats pasted `#` text as arguments, not comments):

   ```bash
   cd ~/Projects/aurora
   export PATH="$PWD/.tools:$PATH"
   aws configure
   ```

   `export PATH...` makes the repo-local `aws`/`terraform`/`k6` binaries available in this
   terminal (re-run it in every new terminal). At the `aws configure` prompts enter: your
   access key id, your secret key, region `us-east-1`, output `json`.

3. **Verify:**

   ```bash
   aws sts get-caller-identity
   ./scripts/deploy-check.sh --aws-hints
   ```

   The first prints your account id; the preflight should show everything OK except `docker`.

---

## Step 3 — Docker (OPTIONAL — skip if deploying via GitHub Actions)  (~15 min)

The deploy workflow builds images **in GitHub Actions**, so local Docker is only needed if
you want to build/verify images on your machine.

1. Download **Docker Desktop for Mac (Apple silicon)** from https://www.docker.com/products/docker-desktop/
2. Install (needs your admin password), launch it once, accept the license.
3. **Verify:** `docker version` then `./scripts/deploy-check.sh` → zero FAILs.

---

## Step 4 — GitHub Actions deploy secrets  (~10 min with the script, after Step 2)

The deploy workflow assumes an IAM role via GitHub OIDC. A bootstrap script creates the
OIDC provider + role for you:

```bash
cd ~/Projects/aurora
export PATH="$PWD/.tools:$PATH"
./scripts/setup-aws-oidc.sh
```

Then in GitHub: **repo → Settings → Secrets and variables → Actions → New repository secret**

| Secret | Value |
|--------|-------|
| `AWS_ROLE_ARN` | the ARN the script printed |
| `AWS_REGION` | `us-east-1` (or your region) |

Optionally create **environments** named `staging` and `production` (Settings → Environments)
with protection rules.

**Verify:** the script ends with `OIDC role ready`; the two secrets show in repo settings.

---

## Step 5 — First deploy  (~45–60 min, mostly waiting on AWS)

Follow [`DEPLOY-CHECKLIST.md`](../DEPLOY-CHECKLIST.md) top to bottom. Condensed, one block
per sub-step (run all of them in the same terminal so the PATH export sticks):

**5a — Terraform.** Creates billable resources (RDS, ALB, NAT, Fargate).

```bash
cd ~/Projects/aurora
export PATH="$PWD/.tools:$PATH"
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` (set `environment = "staging"`, your region, `cors_origins`), then:

```bash
terraform init
terraform plan
terraform apply
```

Review the plan before typing `yes` on apply.

**5b — Images.** Easiest path (no Docker): GitHub → **Actions → Deploy → Run workflow** →
environment `staging`, image_tag `latest`. Local alternative (needs Docker):
`DEPLOY-CHECKLIST.md` step 3.

**5c — Database migrations** (same terminal, after apply):

```bash
cd ~/Projects/aurora
SECRET_ARN=$(cd infra/terraform && terraform output -raw database_secret_arn)
DATABASE_URL=$(aws secretsmanager get-secret-value --secret-id "$SECRET_ARN" --query SecretString --output text)
source apps/api/.venv/bin/activate
cd packages/database
alembic -x url="$DATABASE_URL" upgrade head
```

**5d — Optional staging demo tenant:**

```bash
python -m aurora_db.seed --demo nimbus --verify --url "$DATABASE_URL" --scale 0.1
```

**5e — Smoke test** (k6 runs properly against staging):

```bash
cd ~/Projects/aurora
ALB=$(cd infra/terraform && terraform output -raw alb_dns_name)
curl -sf "http://${ALB}/api/v1/health"
BASE_URL="http://${ALB}/api/v1" ./scripts/load-test.sh
```

**Verify:** health returns `{"status":"ok"...}`; ECS services healthy in the console;
log in at the ALB URL with `cfo@nimbus.test` / `aurora-demo-2026` (if seeded).

---

## Step 6 — AI provider key (whenever you want, independent of deploy)

Get **one** of:
- an **Anthropic API key** → https://console.anthropic.com → put `ANTHROPIC_API_KEY=...` and
  `AI_PROVIDER=anthropic` in `.env`
- an **OpenAI API key** → https://platform.openai.com → `OPENAI_API_KEY=...` and `AI_PROVIDER=openai`

Restart the API; the agent switches from canned mock answers to the live model.
(Provider adapters are implemented and unit-tested on `ekam-testing`; the key is the only
missing piece. In production, add the key to the ECS task env / Secrets Manager.)

---

## Cost note

`terraform apply` creates billable resources (RDS, ALB, NAT gateway, ECS Fargate — roughly
$2–5/day for a minimal staging). `terraform destroy` tears it all down when done testing.
