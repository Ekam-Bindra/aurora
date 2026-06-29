# AURORA — Deployment Guide

> **Document status:** Foundational. Describes how AURORA runs **locally (Docker Compose)** and
> **on AWS**, plus CI/CD, environment configuration, and secrets handling. The manifests shown
> here are the *designed* topology; the actual files live in
> [`infra/`](../architecture/folder-structure.md#5-infra--infrastructure) and are implemented in
> [Roadmap Phase 1 & 9](../roadmap/implementation-roadmap.md).
>
> **Related:** [System Architecture §11](../architecture/system-architecture.md#11-lean-first--full-infrastructure-strategy) ·
> [Folder Structure](../architecture/folder-structure.md) · [API Spec](../api/api-specification.md)

---

## 1. Deployment postures

AURORA follows a **lean-first, scale-ready** strategy: the *same* application images run in two
postures, switched by configuration only.

| | **Lean (local / single VM)** | **Full (AWS)** |
|---|------------------------------|----------------|
| Orchestration | Docker Compose | ECS/Fargate |
| Relational | Postgres container | RDS PostgreSQL |
| Graph | Neo4j container | Neo4j Aura / EC2 |
| Cache/queue | Redis container | ElastiCache (Redis) |
| Analytics | DuckDB (in-process) | ClickHouse |
| Object storage | MinIO | S3 |
| Secrets | `.env` file | AWS Secrets Manager / SSM |
| Logs/metrics | container stdout | CloudWatch |
| TLS / routing | local nginx | ALB + ACM |
| AI | mock / single key | Bedrock / OpenAI |

---

## 2. Local development (Docker Compose)

### 2.1 Topology

```mermaid
graph TB
    subgraph Host["Developer machine — docker compose"]
        NGINX["nginx :80 (reverse proxy)"]
        WEB["web (Next.js) :3000"]
        API["api (FastAPI) :8000"]
        WORKER["worker (RQ/Celery)"]
        PG[("postgres :5432")]
        NEO[("neo4j :7474/:7687")]
        REDIS[("redis :6379")]
        MINIO[("minio :9000/:9001")]
    end
    NGINX --> WEB
    NGINX --> API
    WEB --> API
    API --> PG
    API --> NEO
    API --> REDIS
    API --> MINIO
    WORKER --> PG
    WORKER --> NEO
    WORKER --> REDIS
    WORKER --> MINIO
    API <-->|pub/sub| REDIS
```

### 2.2 Proposed `infra/docker/docker-compose.yml`

```yaml
# Designed topology — implemented in infra/docker (Roadmap Phase 1).
services:
  nginx:
    image: nginx:1.27-alpine
    ports: ["80:80"]
    volumes: ["./nginx/nginx.conf:/etc/nginx/nginx.conf:ro"]
    depends_on: [web, api]

  web:
    build: { context: ../.., dockerfile: infra/docker/web.Dockerfile }
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost/api/v1
    depends_on: [api]
    # ports exposed via nginx; 3000 internal

  api:
    build: { context: ../.., dockerfile: infra/docker/api.Dockerfile }
    env_file: [../../.env]
    environment:
      - DATABASE_URL=postgresql+psycopg://aurora:${POSTGRES_PASSWORD}@postgres:5432/aurora
      - NEO4J_URI=bolt://neo4j:7687
      - REDIS_URL=redis://redis:6379/0
      - S3_ENDPOINT=http://minio:9000
      - AI_PROVIDER=${AI_PROVIDER:-mock}
    depends_on:
      postgres: { condition: service_healthy }
      neo4j:    { condition: service_healthy }
      redis:    { condition: service_started }
      minio:    { condition: service_started }

  worker:
    build: { context: ../.., dockerfile: infra/docker/api.Dockerfile }
    command: ["python", "-m", "aurora.workers"]
    env_file: [../../.env]
    environment:
      - DATABASE_URL=postgresql+psycopg://aurora:${POSTGRES_PASSWORD}@postgres:5432/aurora
      - REDIS_URL=redis://redis:6379/0
    depends_on: [postgres, redis]

  postgres:
    image: postgres:16-alpine
    environment:
      - POSTGRES_USER=aurora
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=aurora
    volumes: ["pgdata:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U aurora"]
      interval: 5s, timeout: 5s, retries: 10
    ports: ["5432:5432"]

  neo4j:
    image: neo4j:5-community
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}
    volumes: ["neo4jdata:/data"]
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- localhost:7474 || exit 1"]
      interval: 10s, timeout: 5s, retries: 10
    ports: ["7474:7474", "7687:7687"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      - MINIO_ROOT_USER=${S3_ACCESS_KEY}
      - MINIO_ROOT_PASSWORD=${S3_SECRET_KEY}
    volumes: ["miniodata:/data"]
    ports: ["9000:9000", "9001:9001"]

volumes:
  pgdata: {}
  neo4jdata: {}
  miniodata: {}
```

> *YAML above is illustrative of the intended services/wiring; the maintained file lives in
> `infra/docker/`. (Compose `healthcheck` sub-keys are shown compactly for readability.)*

### 2.3 First run

```bash
cp .env.example .env          # fill secrets or accept dev defaults; AI_PROVIDER defaults to mock
docker compose -f infra/docker/docker-compose.yml up -d
docker compose exec api alembic upgrade head        # run migrations
docker compose exec api python -m aurora.seed --demo nimbus   # seed demo + print logins
open http://localhost                                # web via nginx
```

| Service | Local URL |
|---------|-----------|
| Web app | http://localhost |
| API + OpenAPI docs | http://localhost/api/v1 · http://localhost/api/v1/docs |
| Neo4j browser | http://localhost:7474 |
| MinIO console | http://localhost:9001 |

---

## 3. Environment-based configuration

All config comes from environment variables (12-factor); the backend validates them with a typed
`Settings` model and **fails fast** if required vars are missing. Every variable is documented in
**`.env.example`** (the single source of truth), and the frontend's public schema lives in
[`packages/config`](../architecture/folder-structure.md#42-packagesconfig--shared-configuration).

### 3.1 `.env.example` (proposed)

```ini
# ── Core ───────────────────────────────────────────────
APP_ENV=local                       # local | staging | production
LOG_LEVEL=info
SECRET_KEY=change-me                 # JWT signing (use a long random value)
ACCESS_TOKEN_TTL_SECONDS=900
REFRESH_TOKEN_TTL_SECONDS=1209600

# ── Datastores ─────────────────────────────────────────
DATABASE_URL=postgresql+psycopg://aurora:aurora@localhost:5432/aurora
POSTGRES_PASSWORD=aurora
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=aurora
REDIS_URL=redis://localhost:6379/0

# ── Object storage (S3 / MinIO) ────────────────────────
S3_ENDPOINT=http://localhost:9000    # empty on AWS to use real S3
S3_BUCKET=aurora
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_REGION=us-east-1

# ── Analytics ──────────────────────────────────────────
ANALYTICS_ENGINE=duckdb              # duckdb | clickhouse
CLICKHOUSE_URL=                      # set when ANALYTICS_ENGINE=clickhouse

# ── AI provider abstraction ────────────────────────────
AI_PROVIDER=mock                     # mock | openai | bedrock
OPENAI_API_KEY=                      # required only if AI_PROVIDER=openai
OPENAI_MODEL=gpt-4o-mini
AWS_BEDROCK_REGION=                  # required only if AI_PROVIDER=bedrock
BEDROCK_MODEL_ID=

# ── Frontend (public) ──────────────────────────────────
NEXT_PUBLIC_API_URL=http://localhost/api/v1
```

### 3.2 Configuration rules
- **Defaults are dev-only.** `APP_ENV=production` rejects placeholder secrets (`change-me`,
  `minioadmin`, etc.) at startup.
- **`AI_PROVIDER=mock` requires no keys** — the default, so the stack always boots
  ([Architecture §8](../architecture/system-architecture.md#8-ai-provider-abstraction)).
- **No secrets in the repo.** `.env` is git-ignored; only `.env.example` (no real values) is
  committed.
- **Provider/engine swaps are config-only:** `ANALYTICS_ENGINE` and `AI_PROVIDER` switch
  implementations behind their interfaces with no code change.

---

## 4. AWS target architecture

```mermaid
graph TB
    USERS["Users"] --> ALB["ALB (HTTPS, ACM cert)"]
    subgraph VPC
        subgraph Public["Public subnets"]
            ALB
        end
        subgraph Private["Private subnets"]
            ECSWEB["ECS svc: web"]
            ECSAPI["ECS svc: api"]
            ECSWRK["ECS svc: worker"]
        end
        subgraph DataT["Data tier (private)"]
            RDS[("RDS PostgreSQL (Multi-AZ)")]
            EC["ElastiCache (Redis)"]
            NEOA["Neo4j Aura / EC2"]
            CH["ClickHouse"]
        end
    end
    S3[("S3 buckets")]
    SM["Secrets Manager / SSM"]
    CW["CloudWatch (logs+metrics)"]
    ECR["ECR (images)"]
    AI["Bedrock / OpenAI"]

    ALB --> ECSWEB --> ECSAPI
    ALB --> ECSAPI
    ECSAPI --> RDS
    ECSAPI --> EC
    ECSAPI --> NEOA
    ECSAPI --> CH
    ECSAPI --> S3
    ECSWRK --> RDS
    ECSWRK --> EC
    ECSWRK --> S3
    ECSAPI --> AI
    ECSAPI -. read .-> SM
    ECSWRK -. read .-> SM
    ECSWEB --> CW
    ECSAPI --> CW
    ECSWRK --> CW
    ECR -. pull .-> ECSAPI
```

| AWS service | Role |
|-------------|------|
| **ALB + ACM** | TLS termination, routing web/api, health checks |
| **ECS/Fargate** | Run `web`, `api`, `worker` services (autoscaled) |
| **ECR** | Container image registry |
| **RDS PostgreSQL (Multi-AZ)** | Managed relational store + automated backups |
| **ElastiCache (Redis)** | Cache, job queue, pub/sub |
| **Neo4j Aura (or EC2)** | Managed knowledge graph |
| **ClickHouse** | Analytics at scale (replaces DuckDB) |
| **S3** | Uploads, exports (board PDFs), model artifacts |
| **Secrets Manager / SSM** | Secrets + parameters injected into tasks |
| **CloudWatch** | Centralized logs, metrics, alarms |
| **VPC (public/private subnets)** | Network isolation; data tier private only |

**Notes**
- `worker` autoscales on Redis queue depth (simulations/forecasts are bursty).
- Migrations run as a one-off ECS task in the deploy pipeline before the new API goes live.
- The data tier sits in private subnets; only ECS tasks can reach it (security groups).
- Optional **Terraform** in [`infra/terraform`](../architecture/folder-structure.md#52-infraterraform-optional)
  provisions all of the above reproducibly.

---

## 5. CI/CD (GitHub Actions)

### 5.1 Pipeline overview

```mermaid
graph LR
    PR["Pull request"] --> CI["CI: lint · typecheck · unit · contract · build"]
    CI --> E2E["E2E (compose + mock AI)"]
    E2E --> MERGE["Merge to main"]
    MERGE --> IMG["Build & push images → ECR"]
    IMG --> MIG["Run DB migrations (ECS task)"]
    MIG --> DEPLOYS["Deploy → ECS staging"]
    DEPLOYS --> SMOKE["Smoke tests"]
    SMOKE --> APPROVE["Manual approval"]
    APPROVE --> DEPLOYP["Deploy → ECS production"]
```

### 5.2 CI workflow (proposed `.github/workflows/ci.yml`)

```yaml
name: ci
on: { pull_request: {}, push: { branches: [main] } }
jobs:
  backend:
    runs-on: ubuntu-latest
    services:
      postgres: { image: postgres:16, env: { POSTGRES_PASSWORD: aurora }, ports: ["5432:5432"] }
      redis:    { image: redis:7, ports: ["6379:6379"] }
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --project apps/api
      - run: uv run ruff check apps/api
      - run: uv run pytest apps/api --cov         # unit + contract (OpenAPI) tests
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20, cache: pnpm }
      - run: pnpm install --frozen-lockfile
      - run: pnpm turbo lint typecheck build
  e2e:
    runs-on: ubuntu-latest
    needs: [backend, frontend]
    steps:
      - uses: actions/checkout@v4
      - run: docker compose -f infra/docker/docker-compose.yml up -d
      - run: docker compose exec -T api alembic upgrade head
      - run: docker compose exec -T api python -m aurora.seed --demo nimbus
      - run: pnpm --filter web e2e   # Playwright happy-path, AI_PROVIDER=mock
```

### 5.3 Deploy workflow (proposed `.github/workflows/deploy.yml`, on `main`)
1. Configure AWS creds via **OIDC** (no long-lived keys in GitHub).
2. Build `web`/`api` images, tag with the commit SHA, push to **ECR**.
3. Run **migrations** as a one-off ECS task.
4. Update ECS services (rolling) in **staging**; run **smoke tests**.
5. **Manual approval** gate → deploy to **production**; CloudWatch alarms guard rollback.

### 5.4 CI/CD principles
- **No deploy without green CI** incl. the mock-AI E2E happy-path
  ([MVP acceptance](../roadmap/mvp-scope.md#5-mvp-acceptance-criteria)).
- **Immutable images** tagged by SHA; environments differ only by config/secrets.
- **OIDC, least-privilege** IAM for the pipeline; secrets never printed in logs.
- Migrations always precede the new app version going live.

---

## 6. Secrets handling

| Environment | Where secrets live | How they reach the app |
|-------------|--------------------|------------------------|
| Local | git-ignored `.env` (dev defaults) | `env_file` in Compose |
| CI | GitHub **Actions Secrets** / OIDC | injected as env at job runtime |
| AWS | **Secrets Manager / SSM Parameter Store** | referenced by ECS task definitions; injected at task start |

**Rules**
- **Never commit secrets.** Only `.env.example` (placeholders) is tracked; CI can scan for leaked
  secrets.
- **Rotate** DB/Redis/AI credentials via Secrets Manager rotation; the app reads at task start.
- **Least privilege:** scoped IAM roles per ECS service (e.g., the web task gets no DB access).
- **In transit & at rest:** TLS everywhere (ALB/ACM); RDS/S3 encryption enabled; signed,
  expiring URLs for S3 objects.
- **Sensitive fields** (e.g., salaries) are permission-gated and audited
  ([Architecture §7.4](../architecture/system-architecture.md#74-data-protection)).

---

## 7. Operations

| Concern | Local | AWS |
|---------|-------|-----|
| **Migrations** | `alembic upgrade head` | one-off ECS task in deploy pipeline |
| **Seeding demo** | `aurora.seed --demo nimbus` | optional, for demo tenants |
| **Backups** | Postgres volume + `pg_dump` | RDS automated snapshots + PITR; S3 versioning |
| **Logs** | `docker compose logs -f` | CloudWatch Logs |
| **Health** | `/api/v1/health` | ALB health checks + CloudWatch alarms |
| **Scaling** | n/a | ECS service autoscaling (CPU + queue depth) |
| **Disaster recovery** | re-`up` + restore dump | Multi-AZ RDS, snapshots, IaC re-provision |

**Health & readiness:** the API exposes `/health` (liveness) and `/ready` (checks Postgres,
Redis, Neo4j connectivity) for ALB/Compose probes.

---

## 8. Environments

| Env | Purpose | Posture | AI provider |
|-----|---------|---------|-------------|
| `local` | developer machines | Compose | mock (default) |
| `ci` | automated tests | Compose (ephemeral) | mock |
| `staging` | pre-prod verification | AWS | Bedrock/OpenAI (test keys) |
| `production` | live tenants | AWS (Multi-AZ, autoscaled) | Bedrock/OpenAI |

---

## 9. Where to go next
- The infra strategy behind this → [System Architecture §11](../architecture/system-architecture.md#11-lean-first--full-infrastructure-strategy)
- Where manifests/Terraform live → [Folder Structure §infra](../architecture/folder-structure.md#5-infra--infrastructure)
- When each piece is built → [Implementation Roadmap](../roadmap/implementation-roadmap.md) (P1 local, P9 cloud)
- What the deployed app must do → [MVP Scope](../roadmap/mvp-scope.md)
