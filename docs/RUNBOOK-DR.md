# AURORA — Backup, Restore & Disaster-Recovery Runbook

> Staging account `216812304180`, us-east-1. All commands assume repo root with
> `export PATH="$PWD/.tools:$PATH"` (paste-safe blocks — no inline comments).
> Timings are measured from the real 2026-07-02 first deploy, not estimates.

## 1. What is backed up, and what is disposable

| Asset | Mechanism | Loss impact |
|-------|-----------|-------------|
| Terraform state | S3 `aurora-terraform-state-216812304180`, versioned + SSE | None while bucket exists (state is recoverable from any machine) |
| RDS (tenant data) | Automated snapshots — retention **1 day staging / 7 days production**; final snapshot skipped on staging destroy, forced + deletion-protected on production | Staging: demo data only — fully regenerable by the seeder |
| Secrets (`database-url`, `jwt-secret`) | Secrets Manager (recreated by Terraform) | Rotating invalidates active JWTs only |
| Images | ECR `latest` + immutable `sha-*` tags | Rebuildable from any commit via the deploy workflow |
| Uploads bucket | S3 (staging demo uploads) | Demo-only on staging |
| Everything else (VPC/ALB/ECS/alarms) | Terraform code | None — `terraform apply` recreates |

**Staging DR stance:** the database is a *cache of the seeder*. The fastest recovery is
always rebuild + reseed, not snapshot surgery. Production must use snapshot restore.

## 2. Restore RDS from a snapshot (production path)

```bash
aws rds describe-db-snapshots --db-instance-identifier aurora-staging --query "DBSnapshots[].[DBSnapshotIdentifier,SnapshotCreateTime]" --output text
```

1. Restore to a NEW instance (never in place):

```bash
aws rds restore-db-instance-from-db-snapshot --db-instance-identifier aurora-staging-restore --db-snapshot-identifier <SNAPSHOT_ID> --db-instance-class db.t4g.micro --no-publicly-accessible
```

2. Wait `available`, then point the app at it by updating the Secrets Manager
   `aurora/<env>/database-url` secret to the new endpoint (keep credentials identical), and
   force an ECS redeploy of the api service.
3. When satisfied, retire the old instance and (optionally) rename the new one back via
   Terraform state surgery — or simpler: update `identifier` handling in a maintenance PR.

## 3. Full destroy ⇄ rebuild drill (staging)

Measured 2026-07-02 totals: **≈ 30 minutes cold-to-healthy.**

### Destroy (~4 min; stops the ~$2–6/day credit burn)

```bash
cd infra/terraform
terraform destroy
```

State stays in S3; nothing else to save (see §1).

### Rebuild (~30 min end-to-end)

| Step | Command | Measured |
|------|---------|----------|
| 1. Infra | `cd infra/terraform && terraform apply` | ~13 min (RDS ≈ 10) |
| 2. Images + services | GitHub → Actions → deploy → run on `main` (or merge anything) — health gate included | ~14 min |
| 3. Migrations | one-off ECS task: see block below | ~1 min |
| 4. Demo seed | same block, seed command | ~2 min |
| 5. Verify | `curl http://<alb>/api/v1/health` + login smoke | <1 min |

One-off task template (fill subnets/SG from `aws ecs describe-services --cluster aurora-staging --services aurora-staging-api --query "services[0].networkConfiguration"`):

```bash
aws ecs run-task --cluster aurora-staging --task-definition aurora-staging-api --launch-type FARGATE --network-configuration "awsvpcConfiguration={subnets=[SUBNET_A,SUBNET_B],securityGroups=[SG_ID],assignPublicIp=DISABLED}" --overrides '{"containerOverrides":[{"name":"api","command":["python","-m","aurora_db.migrate"]}]}'
```

Seed: replace the command with
`["python","-m","aurora_db.seed","--demo","nimbus","--verify","--scale","0.1"]`.

New ALB DNS after rebuild: `cd infra/terraform && terraform output -raw alb_dns_name`.

## 4. Secret rotation

### 4.1 JWT signing key (`SECRET_KEY`) — invalidates active sessions, zero data risk

```bash
aws secretsmanager put-secret-value --secret-id aurora/staging/jwt-secret --secret-string "$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
aws ecs update-service --cluster aurora-staging --service aurora-staging-api --force-new-deployment
```

Users re-login (access tokens are 15-minute anyway).

### 4.2 Database password

Terraform owns it (`random_password`). Rotate by replacing the resource and letting
Terraform update both RDS and the secret, then cycle the api service:

```bash
cd infra/terraform
terraform apply -replace=random_password.db_password
aws ecs update-service --cluster aurora-staging --service aurora-staging-api --force-new-deployment
```

## 5. Free-plan guardrails

- Credits are the blast radius: check with
  `aws freetier get-account-plan-state` before leaving staging running unattended.
  At exhaustion AWS restricts the account (no card billing) — treat <$15 remaining as
  "destroy now or upgrade now".
- Backup storage beyond the DB's allocated size draws credits — staging's 1-day retention
  is deliberate.
- RDS instance classes above t4g.micro are rejected on the free plan.

## 6. Drill log

| Date | Drill | Result |
|------|-------|--------|
| 2026-07-02 | Cold build (first deploy) | ~30 min to healthy incl. two real defects found/fixed (psycopg extra, parents[3]) |
| — | Next: timed destroy→rebuild rehearsal | pending owner's staging-uptime decision |
