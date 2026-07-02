#!/usr/bin/env bash
# Pre-flight checks before first AWS deploy or CI deploy workflow.
# Validates tooling, env vars, Terraform syntax, and Docker compose config locally.
# Does NOT call AWS APIs (safe without credentials).
#
# Usage:
#   ./scripts/deploy-check.sh              # local validation only
#   ./scripts/deploy-check.sh --aws-hints  # also print AWS CLI sanity commands
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TF_DIR="$ROOT/infra/terraform"
COMPOSE_FILE="$ROOT/infra/docker/docker-compose.prod.yml"
AWS_HINTS=false
FAILURES=0
WARNINGS=0

usage() {
  sed -n '2,8p' "$0" | sed 's/^# \?//'
  echo ""
  echo "Options:"
  echo "  --aws-hints   Print optional AWS CLI commands (requires credentials)"
  echo "  -h, --help    Show this help"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --aws-hints) AWS_HINTS=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

pass() { echo "  OK   $*"; }
warn() { echo "  WARN $*"; WARNINGS=$((WARNINGS + 1)); }
fail() { echo "  FAIL $*" >&2; FAILURES=$((FAILURES + 1)); }

echo "==> AURORA deploy preflight"
echo "    Repo: $ROOT"
echo ""

# ── Tooling ─────────────────────────────────────────────
echo "==> Required tools"

if command -v terraform >/dev/null 2>&1; then
  pass "terraform $(terraform version | head -1)"
elif [[ -x "$ROOT/.tools/terraform" ]]; then
  pass "terraform ($ROOT/.tools/terraform)"
  export PATH="$ROOT/.tools:$PATH"
else
  fail "terraform not found (install >= 1.5 or place binary in .tools/terraform)"
fi

if command -v aws >/dev/null 2>&1; then
  pass "aws $(aws --version 2>&1 | awk '{print $1}')"
elif [[ -x "$ROOT/.tools/aws" ]]; then
  pass "aws ($ROOT/.tools/aws — $("$ROOT/.tools/aws" --version 2>&1 | awk '{print $1}'))"
  export PATH="$ROOT/.tools:$PATH"
else
  fail "aws CLI not found (install v2, or pip-install awscli into .tools — see infra/terraform/README.md)"
fi

if command -v docker >/dev/null 2>&1; then
  pass "docker $(docker --version | awk '{print $3}' | tr -d ',')"
else
  fail "docker not found (required to build/push API and web images)"
fi

if docker compose version >/dev/null 2>&1; then
  pass "docker compose $(docker compose version --short 2>/dev/null || echo available)"
elif command -v docker-compose >/dev/null 2>&1; then
  pass "docker-compose legacy CLI"
else
  warn "docker compose plugin not found (prod compose validation skipped)"
fi

if command -v python3 >/dev/null 2>&1; then
  pass "python3 $(python3 --version | awk '{print $2}')"
else
  warn "python3 not found (Alembic migrations will fail)"
fi

echo ""

# ── Environment variables (AWS deploy) ──────────────────
echo "==> AWS deploy environment (export before terraform apply / deploy workflow)"

REQUIRED_AWS_VARS=(
  AWS_REGION
)
RECOMMENDED_AWS_VARS=(
  AWS_PROFILE
  TF_VAR_environment
  TF_VAR_cors_origins
  TF_VAR_certificate_arn
)

GITHUB_SECRETS=(
  AWS_ROLE_ARN
  AWS_REGION
)

for var in "${REQUIRED_AWS_VARS[@]}"; do
  if [[ -n "${!var:-}" ]]; then
    pass "$var is set"
  else
    warn "$var unset (default us-east-1 used by Terraform and workflow)"
  fi
done

for var in "${RECOMMENDED_AWS_VARS[@]}"; do
  if [[ -n "${!var:-}" ]]; then
    pass "$var is set"
  else
    warn "$var unset (set in terraform.tfvars or TF_VAR_* for apply)"
  fi
done

echo ""
echo "    GitHub Actions secrets (repository settings):"
for secret in "${GITHUB_SECRETS[@]}"; do
  echo "      - $secret"
done

echo ""
echo "    Production app secrets (created by Terraform in Secrets Manager):"
echo "      - aurora/<environment>/database-url  (DATABASE_URL)"
echo "      - aurora/<environment>/jwt-secret    (SECRET_KEY)"
echo ""

# ── Terraform ───────────────────────────────────────────
echo "==> Terraform ($TF_DIR)"

if command -v terraform >/dev/null 2>&1 || [[ -x "$ROOT/.tools/terraform" ]]; then
  TF="${TF_BIN:-terraform}"
  [[ -x "$ROOT/.tools/terraform" ]] && TF="$ROOT/.tools/terraform"

  if (cd "$TF_DIR" && $TF fmt -check -recursive . >/dev/null 2>&1); then
    pass "terraform fmt"
  else
    fail "terraform fmt -check (run: cd infra/terraform && terraform fmt -recursive .)"
  fi

  if (cd "$TF_DIR" && $TF init -backend=false -input=false >/dev/null 2>&1); then
    if (cd "$TF_DIR" && $TF validate >/dev/null 2>&1); then
      pass "terraform validate"
    else
      fail "terraform validate (run: cd infra/terraform && terraform init -backend=false && terraform validate)"
    fi
  else
    fail "terraform init (network required to download providers)"
  fi

  if [[ -f "$TF_DIR/terraform.tfvars" ]]; then
    pass "terraform.tfvars present"
  else
    warn "terraform.tfvars missing (copy from terraform.tfvars.example before apply)"
  fi
else
  warn "Skipping Terraform checks (terraform not installed)"
fi

echo ""

# ── Docker compose prod ─────────────────────────────────
echo "==> Docker Compose ($COMPOSE_FILE)"

if [[ -f "$ROOT/.env.production" ]]; then
  pass ".env.production present"
else
  warn ".env.production missing (copy from .env.example; required for prod compose up)"
fi

if docker compose version >/dev/null 2>&1; then
  export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-deploy-check-placeholder}"
  if docker compose -f "$COMPOSE_FILE" config >/dev/null 2>&1; then
    pass "docker compose config"
  else
    fail "docker compose config (set POSTGRES_PASSWORD and fix compose paths)"
  fi
elif python3 -c "import yaml" >/dev/null 2>&1; then
  if python3 -c "import yaml; yaml.safe_load(open('$COMPOSE_FILE'))" >/dev/null 2>&1; then
    pass "compose YAML syntax (docker not available for full config)"
  else
    fail "compose YAML parse error"
  fi
else
  warn "Cannot validate compose (install docker or python3 PyYAML)"
fi

echo ""

# ── Docker build hints (dry-run) ────────────────────────
echo "==> Docker build commands (run manually before first ECS deploy)"
echo "    cd $ROOT"
echo "    docker build -f infra/docker/api.Dockerfile -t aurora-api:check ."
echo "    docker build -f infra/docker/web.Dockerfile -t aurora-web:check ."
echo "    # After ECR repos exist (terraform apply):"
echo "    # aws ecr get-login-password --region \$AWS_REGION | docker login --username AWS --password-stdin \$ACCOUNT.dkr.ecr.\$AWS_REGION.amazonaws.com"
echo "    # docker tag aurora-api:check \$ECR_API_URL:latest && docker push \$ECR_API_URL:latest"
echo ""

# ── Optional AWS hints ──────────────────────────────────
if $AWS_HINTS; then
  echo "==> AWS CLI hints (requires credentials)"
  if aws sts get-caller-identity >/dev/null 2>&1; then
    pass "aws sts get-caller-identity"
    aws sts get-caller-identity
  else
    warn "aws sts get-caller-identity failed (configure profile or OIDC role)"
  fi
  echo ""
fi

# ── Summary ─────────────────────────────────────────────
echo "==> Summary"
if [[ $FAILURES -eq 0 ]]; then
  echo "    Preflight passed ($WARNINGS warning(s))."
  echo "    Next: docs/DEPLOY-CHECKLIST.md"
  exit 0
else
  echo "    Preflight failed: $FAILURES error(s), $WARNINGS warning(s)." >&2
  exit 1
fi
