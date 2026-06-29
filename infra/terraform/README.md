# AURORA AWS Terraform

Production-ready AWS topology for AURORA: VPC, ECS Fargate (API + web), ALB, RDS PostgreSQL, ECR, Secrets Manager, and optional S3.

## Prerequisites

- Terraform >= 1.5
- AWS CLI configured (`aws configure` or SSO)
- Docker images built and pushed to ECR before first deploy

## Quick start

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars (environment, cors_origins, certificate_arn)

terraform init
terraform plan
terraform apply
```

## Build and push images

```bash
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=us-east-1

aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com

docker build -f infra/docker/api.Dockerfile -t aurora-api .
docker tag aurora-api:latest $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/aurora-api:latest
docker push $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/aurora-api:latest

docker build -f infra/docker/web.Dockerfile -t aurora-web .
docker tag aurora-web:latest $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/aurora-web:latest
docker push $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/aurora-web:latest
```

## Post-apply steps

1. Run Alembic migrations against RDS (see `docs/DEPLOYMENT.md`).
2. Optionally seed demo tenant: `python -m aurora_db.seed --demo nimbus --url "$DATABASE_URL"`.
3. Point DNS at `alb_dns_name` output (or use ALB DNS directly for staging).
4. Configure OIDC env vars on the API task definition if using SSO.

## State

Remote state via S3 backend is commented in `versions.tf`. Enable it before team use.

## Cost note

NAT gateways and Multi-AZ RDS are the main fixed costs. Use `environment=staging` with smaller instance classes for dev/staging.
