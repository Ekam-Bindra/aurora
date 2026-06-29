# AURORA — Deployment Guide (Phase 9)

Production deployment for AWS ECS/Fargate, local production compose, SSO, analytics backends, and operational runbooks.

**Related:** [`infra/terraform/README.md`](../infra/terraform/README.md) · [`deployment/deployment-guide.md`](deployment/deployment-guide.md)

---

## 1. Deployment options

| Posture | Orchestration | Database | Analytics | Secrets |
|---------|---------------|----------|-----------|---------|
| **Local dev** | `./scripts/local-run.sh` (SQLite) | SQLite / in-memory | Postgres path (DuckDB mart) | `.env` |
| **Docker dev** | `infra/docker/docker-compose.yml` | Postgres container | Postgres path (default) | `.env` |
| **Docker prod** | `infra/docker/docker-compose.prod.yml` | Postgres | Postgres or ClickHouse | `.env.production` |
| **AWS** | Terraform → ECS Fargate | RDS PostgreSQL | Postgres (default) | Secrets Manager + SSM |

---

## 2. Environment variables

Copy `.env.example` to `.env` (local) or `.env.production` (prod compose).

### Core

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `APP_ENV` | No | `local` | `local` \| `staging` \| `production` |
| `SECRET_KEY` | **Yes in prod** | dev placeholder | JWT signing; ≥32 chars in production |
| `ACCESS_TOKEN_TTL_SECONDS` | No | `900` | Must be ≤900 in production |
| `REFRESH_TOKEN_TTL_SECONDS` | No | `1209600` | 14 days |
| `DATABASE_URL` | No | unset | SQLite/Postgres DSN; unset = in-memory (tests) |
| `CORS_ORIGINS` | Prod | localhost | Comma-separated allowed origins |
| `SEED_DEMO_ON_STARTUP` | No | `true` | Set `false` in production |

### Analytics

| Variable | Default | Values |
|----------|---------|--------|
| `ANALYTICS_BACKEND` | `postgres` | `postgres` \| `clickhouse` |
| `CLICKHOUSE_URL` | — | Required when backend is `clickhouse` (e.g. `http://localhost:8123`) |

**Migration path:** Start with `ANALYTICS_BACKEND=postgres` (current behavior: relational DB → in-process DuckDB mart). When ready for scale:

1. Enable ClickHouse: `docker compose --profile clickhouse up -d clickhouse`
2. Set `ANALYTICS_BACKEND=clickhouse` and `CLICKHOUSE_URL=http://clickhouse:8123`
3. Restart API; marts sync on first metrics request per tenant
4. On AWS, run ClickHouse on EC2/ClickHouse Cloud and point `CLICKHOUSE_URL` at the service

### SSO / OIDC

| Variable | Required when SSO on | Example |
|----------|---------------------|---------|
| `OIDC_ENABLED` | — | `true` |
| `OIDC_ISSUER` | Yes | `https://YOUR_TENANT.auth0.com` |
| `OIDC_CLIENT_ID` | Yes | Application client ID |
| `OIDC_CLIENT_SECRET` | Yes | Client secret (Secrets Manager in AWS) |
| `OIDC_REDIRECT_URI` | Yes | `https://app.example.com/api/v1/auth/oidc/callback` |
| `OIDC_SCOPES` | No | `openid profile email` |

When `OIDC_ENABLED=false`, email/password login (`/auth/login`) remains available for demo and break-glass access.

**Auth0 setup:** Create Regular Web Application → set Allowed Callback URLs to your `OIDC_REDIRECT_URI` → copy Domain as issuer base (e.g. `https://tenant.auth0.com`) → enable OIDC endpoints.

### Object storage (optional)

| Variable | AWS | Local (MinIO) |
|----------|-----|---------------|
| `S3_BUCKET` | Terraform output | `aurora` |
| `S3_REGION` | `us-east-1` | `us-east-1` |
| `S3_ENDPOINT` | leave empty | `http://minio:9000` |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | IAM role (ECS) | MinIO credentials |

### Security

| Variable | Default | Notes |
|----------|---------|-------|
| `SECURITY_HEADERS_ENABLED` | `true` | HSTS, X-Frame-Options, etc. |
| `AUTH_RATE_LIMIT_PER_MINUTE` | `20` | Auth route rate limit (10 in prod if unset) |

**Audit logs:** Stored in `audit_log` table when `DATABASE_URL` is set. Retain per your compliance policy (recommend ≥90 days in production; export to S3/Glacier for long-term retention).

**Secrets:** Never commit `.env`, `.env.production`, or Terraform state with credentials. Use AWS Secrets Manager (`infra/terraform/secrets.tf`) or SSM Parameter Store.

---

## 3. AWS deployment

### 3.1 Provision infrastructure

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit environment, cors_origins, certificate_arn

terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

Outputs: `alb_dns_name`, `ecr_api_repository_url`, `ecr_web_repository_url`, `database_secret_arn`.

### 3.2 Build and push images

See [`infra/terraform/README.md`](../infra/terraform/README.md) for ECR login and push commands.

### 3.3 Database migrate and seed

```bash
# Retrieve DATABASE_URL from Secrets Manager, then:
pip install -e packages/database
alembic -x url="$DATABASE_URL" upgrade head

# Optional demo tenant (staging only):
python -m aurora_db.seed --demo nimbus --verify --url "$DATABASE_URL" --scale 0.1
```

### 3.4 Health checks

| Endpoint | Expected |
|----------|----------|
| `GET /api/v1/health` | `200` `{"status":"ok"}` |
| ALB target group | Healthy after migrations complete |
| ECS task health check | Container-level `/api/v1/health` |

### 3.5 GitHub Actions deploy

Manual dispatch via `.github/workflows/deploy.yml`:

1. Configure repository secrets: `AWS_ROLE_ARN`, `AWS_REGION`
2. Actions → **Deploy** → Run workflow → choose `staging` or `production`
3. Workflow builds images, pushes to ECR, forces ECS service redeployment

---

## 4. Local production compose

```bash
cp .env.example .env.production
# Set POSTGRES_PASSWORD, SECRET_KEY (≥32 chars), APP_ENV=production

docker compose -f infra/docker/docker-compose.prod.yml up -d --build

# Migrate
docker compose -f infra/docker/docker-compose.prod.yml exec api \
  alembic -x url="$DATABASE_URL" upgrade head
```

With ClickHouse:

```bash
docker compose -f infra/docker/docker-compose.prod.yml --profile clickhouse up -d
# Set ANALYTICS_BACKEND=clickhouse and CLICKHOUSE_URL in .env.production
```

---

## 5. Load / smoke tests

```bash
# Against local API (default http://localhost:8000)
./scripts/load-test.sh

# Against staging
BASE_URL=https://staging.example.com/api/v1 ./scripts/load-test.sh
```

Uses [k6](https://k6.io/) if installed; falls back to curl smoke checks.

Scenarios: health, login, metrics overview, board report list.

---

## 6. Security scanning

- **Dependabot:** `.github/dependabot.yml` monitors Python and npm dependencies weekly
- **ECR:** Image scan on push enabled in Terraform
- **Pre-deploy:** Run `ruff check` and `pytest` (CI gate on `main`)

---

## 7. Troubleshooting

| Symptom | Check |
|---------|-------|
| API won't start in prod | `SECRET_KEY` length, `ACCESS_TOKEN_TTL_SECONDS` ≤900 |
| Metrics 422 | `DATABASE_URL` set and migrations applied |
| SSO 422 | `OIDC_ENABLED=true` and all OIDC_* vars set |
| ClickHouse errors | `pip install aurora-analytics[clickhouse]` in API image |
| CORS errors | `CORS_ORIGINS` includes your web origin |
