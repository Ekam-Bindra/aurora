# AURORA — First AWS Deploy Checklist

Step-by-step guide for the **first** deploy to AWS (staging recommended). Assumes Phase 9 infra is merged (`infra/terraform/`, `.github/workflows/deploy.yml`).

**Related:** [`DEPLOYMENT.md`](DEPLOYMENT.md) · [`infra/terraform/README.md`](../infra/terraform/README.md) · [`../scripts/deploy-check.sh`](../scripts/deploy-check.sh)

---

## Before you start

- [ ] AWS account with permissions for VPC, ECS, RDS, ECR, ALB, Secrets Manager, SSM, S3
- [ ] Terraform >= 1.5 and AWS CLI v2 installed locally
- [ ] Docker installed (build and push images)
- [ ] Optional: ACM certificate ARN in the same region as the ALB (HTTPS)
- [ ] Run preflight locally (no AWS credentials required):

```bash
./scripts/deploy-check.sh
```

Fix any `FAIL` lines before continuing. Use `./scripts/deploy-check.sh --aws-hints` once credentials are configured.

---

## Step 1 — Configure Terraform

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:

| Variable | Staging example |
|----------|-----------------|
| `environment` | `staging` |
| `aws_region` | `us-east-1` |
| `cors_origins` | `["https://staging.yourdomain.com"]` |
| `certificate_arn` | ACM ARN or `""` for HTTP-only ALB |

Validate locally:

```bash
terraform init          # or terraform init -backend=false for syntax-only
terraform fmt -check -recursive .
terraform validate
terraform plan
```

---

## Step 2 — Apply infrastructure

```bash
terraform apply
```

Record outputs:

| Output | Use |
|--------|-----|
| `alb_dns_name` | Public URL (or point DNS CNAME here) |
| `ecr_api_repository_url` | Push API image |
| `ecr_web_repository_url` | Push web image |
| `database_secret_arn` | Retrieve `DATABASE_URL` for migrations |
| `ecs_cluster_name` | ECS cluster for services |

**Note:** First apply creates RDS and Secrets Manager secrets. ECS tasks will not become healthy until images exist and migrations have run.

---

## Step 3 — Build and push Docker images to ECR

From repo root:

```bash
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=us-east-1   # match terraform.tfvars

aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin \
  "$AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com"

# API
docker build -f infra/docker/api.Dockerfile -t aurora-api:latest .
docker tag aurora-api:latest "$AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/aurora-api:latest"
docker push "$AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/aurora-api:latest"

# Web
docker build -f infra/docker/web.Dockerfile -t aurora-web:latest .
docker tag aurora-web:latest "$AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/aurora-web:latest"
docker push "$AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/aurora-web:latest"
```

Or trigger `.github/workflows/deploy.yml` after configuring GitHub secrets (Step 5).

---

## Step 4 — Database migrate (and optional seed)

Retrieve database URL from Secrets Manager:

```bash
SECRET_ARN=$(terraform output -raw database_secret_arn)
DATABASE_URL=$(aws secretsmanager get-secret-value \
  --secret-id "$SECRET_ARN" \
  --query SecretString --output text)

pip install -e packages/database
alembic -x url="$DATABASE_URL" upgrade head
```

Optional demo tenant (**staging only**):

```bash
python -m aurora_db.seed --demo nimbus --verify --url "$DATABASE_URL" --scale 0.1
```

Demo login: `cfo@nimbus.test` / `aurora-demo-2026`

Force ECS to pick up healthy tasks if they were crash-looping before migrations:

```bash
aws ecs update-service --cluster aurora-staging --service aurora-staging-api --force-new-deployment
aws ecs update-service --cluster aurora-staging --service aurora-staging-web --force-new-deployment
```

---

## Step 5 — Configure GitHub Actions (ongoing deploys)

Repository **Settings → Secrets and variables → Actions**:

| Secret | Value |
|--------|-------|
| `AWS_ROLE_ARN` | IAM role for OIDC (trust GitHub repo) |
| `AWS_REGION` | e.g. `us-east-1` |

Create GitHub **environments** `staging` and `production` with optional protection rules.

Deploy via **Actions → Deploy → Run workflow**:

1. Choose `staging` or `production`
2. Set `image_tag` (e.g. `latest` or git SHA)
3. Workflow builds, pushes to ECR, and forces ECS redeployment

**Important:** The workflow does **not** run Alembic migrations. Run Step 4 manually whenever schema changes.

---

## Step 6 — Smoke test

```bash
ALB=$(terraform output -raw alb_dns_name)

curl -sf "http://${ALB}/api/v1/health"
# Expected: {"status":"ok",...}

BASE_URL="http://${ALB}/api/v1" ./scripts/load-test.sh
```

Expected load-test output (curl fallback when k6 is not installed):

```
==> AURORA load/smoke test
    BASE_URL=http://<alb>/api/v1
==> k6 not found — running curl smoke checks
OK health
OK login
OK metrics/overview (or 422 if no DATABASE_URL)
OK board-reports
==> Smoke checks passed
```

With k6 installed, the same script runs `tests/load/smoke.js` with VUs and thresholds.

Verify in AWS Console:

- [ ] ECS services `aurora-<env>-api` and `aurora-<env>-web` running
- [ ] ALB target groups healthy
- [ ] CloudWatch log groups `/ecs/aurora-<env>/api` and `/web` show startup logs

---

## Step 7 — Post-deploy (optional)

- [ ] Point DNS CNAME at `alb_dns_name`
- [ ] Set `certificate_arn` in `terraform.tfvars` and re-apply for HTTPS listener
- [ ] Configure OIDC env vars on API task definition if using SSO
- [ ] Set `SEED_DEMO_ON_STARTUP=false` (already default in Terraform ECS task env)

---

## Troubleshooting

| Symptom | Action |
|---------|--------|
| ECS tasks unhealthy | Check migrations; verify ECR images exist; inspect CloudWatch logs |
| `terraform validate` fails | `terraform init -backend=false` then re-validate |
| Compose config fails locally | `export POSTGRES_PASSWORD=...` and run from repo root |
| Login 401 on smoke test | Run seed (staging) or create user via admin flow |
| CORS errors | Update `cors_origins` in `terraform.tfvars` and re-apply |

See [`DEPLOYMENT.md`](DEPLOYMENT.md) §7 for more operational notes.
