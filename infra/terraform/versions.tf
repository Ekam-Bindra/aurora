terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Remote state (bucket is versioned, private, SSE; created 2026-07-02).
  # State holds live-infra records incl. generated DB credentials — never in git.
  backend "s3" {
    bucket = "aurora-terraform-state-216812304180"
    key    = "aurora/staging/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "aurora"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
