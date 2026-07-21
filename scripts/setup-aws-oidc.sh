#!/usr/bin/env bash
# One-time bootstrap: GitHub-Actions OIDC provider + deploy role for this repo.
# Requires working AWS credentials (aws sts get-caller-identity must succeed).
# Idempotent — safe to re-run. Prints the role ARN for the AWS_ROLE_ARN secret.
#
# Usage: ./scripts/setup-aws-oidc.sh [role-name]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if ! command -v aws >/dev/null 2>&1 && [[ -x "$ROOT/.tools/aws" ]]; then
  export PATH="$ROOT/.tools:$PATH"
fi

ROLE_NAME="${1:-aurora-github-deploy}"
OIDC_HOST="token.actions.githubusercontent.com"

# Repo slug (owner/name) from the git remote.
REMOTE_URL="$(git -C "$ROOT" remote get-url origin)"
REPO_SLUG="$(echo "$REMOTE_URL" | sed -E 's#(git@github.com:|https://github.com/)##; s#\.git$##')"
if [[ ! "$REPO_SLUG" =~ ^[^/]+/[^/]+$ ]]; then
  echo "ERROR: could not derive owner/repo from origin remote: $REMOTE_URL" >&2
  exit 1
fi

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
echo "==> Account: $ACCOUNT_ID · Repo: $REPO_SLUG · Role: $ROLE_NAME"

# ── 1. OIDC identity provider ───────────────────────────
PROVIDER_ARN="arn:aws:iam::${ACCOUNT_ID}:oidc-provider/${OIDC_HOST}"
if aws iam get-open-id-connect-provider --open-id-connect-provider-arn "$PROVIDER_ARN" >/dev/null 2>&1; then
  echo "  OK   OIDC provider exists"
else
  aws iam create-open-id-connect-provider \
    --url "https://${OIDC_HOST}" \
    --client-id-list "sts.amazonaws.com" \
    --thumbprint-list "6938fd4d98bab03faadb97b34396831e3780aea1" "1c58a3a8518e8759bf075b76b750d4f2df264fcd" \
    >/dev/null
  echo "  OK   OIDC provider created"
fi

# ── 2. Deploy role with repo-scoped trust ───────────────
TRUST_DOC="$(cat <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Federated": "${PROVIDER_ARN}" },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": { "${OIDC_HOST}:aud": "sts.amazonaws.com" },
        "StringLike": { "${OIDC_HOST}:sub": "repo:${REPO_SLUG}:*" }
      }
    }
  ]
}
JSON
)"

if aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  aws iam update-assume-role-policy --role-name "$ROLE_NAME" --policy-document "$TRUST_DOC"
  echo "  OK   role exists (trust policy refreshed)"
else
  aws iam create-role \
    --role-name "$ROLE_NAME" \
    --assume-role-policy-document "$TRUST_DOC" \
    --description "GitHub Actions deploy role for ${REPO_SLUG} (ECR push + ECS redeploy)" \
    >/dev/null
  echo "  OK   role created"
fi

# ── 3. Least-privilege deploy permissions ───────────────
PERM_DOC="$(cat <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "EcrAuth",
      "Effect": "Allow",
      "Action": "ecr:GetAuthorizationToken",
      "Resource": "*"
    },
    {
      "Sid": "EcrPush",
      "Effect": "Allow",
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "ecr:PutImage"
      ],
      "Resource": "arn:aws:ecr:*:${ACCOUNT_ID}:repository/aurora-*"
    },
    {
      "Sid": "PassTaskRoles",
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "arn:aws:iam::${ACCOUNT_ID}:role/aurora-*",
      "Condition": {
        "StringEquals": { "iam:PassedToService": "ecs-tasks.amazonaws.com" }
      }
    },
    {
      "Sid": "AlbHealthGate",
      "Effect": "Allow",
      "Action": "elasticloadbalancing:DescribeLoadBalancers",
      "Resource": "*"
    },
    {
      "Sid": "EcsRedeploy",
      "Effect": "Allow",
      "Action": [
        "ecs:DescribeServices",
        "ecs:UpdateService",
        "ecs:ListServices",
        "ecs:DescribeClusters",
        "ecs:RunTask",
        "ecs:DescribeTasks"
      ],
      "Resource": "*",
      "Condition": {
        "ArnLike": { "ecs:cluster": "arn:aws:ecs:*:${ACCOUNT_ID}:cluster/aurora-*" }
      }
    }
  ]
}
JSON
)"

aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "aurora-deploy" \
  --policy-document "$PERM_DOC"
echo "  OK   deploy policy attached"

ROLE_ARN="$(aws iam get-role --role-name "$ROLE_NAME" --query Role.Arn --output text)"
echo ""
echo "==> OIDC role ready"
echo "    Add these GitHub repository secrets (Settings → Secrets and variables → Actions):"
echo "      AWS_ROLE_ARN = ${ROLE_ARN}"
echo "      AWS_REGION   = ${AWS_REGION:-us-east-1}"
