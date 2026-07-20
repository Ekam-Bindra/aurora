variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment (staging | production)."
  type        = string
  default     = "staging"
}

variable "project_name" {
  description = "Short project name used in resource naming."
  type        = string
  default     = "aurora"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "api_image_tag" {
  description = "Docker image tag for the API service."
  type        = string
  default     = "latest"
}

variable "web_image_tag" {
  description = "Docker image tag for the web service."
  type        = string
  default     = "latest"
}

variable "api_desired_count" {
  description = "Number of API tasks to run."
  type        = number
  default     = 2
}

variable "web_desired_count" {
  description = "Number of web tasks to run."
  type        = number
  default     = 2
}

variable "db_instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t4g.medium"
}

variable "db_allocated_storage_gb" {
  description = "RDS allocated storage in GB."
  type        = number
  default     = 50
}

variable "db_username" {
  description = "RDS master username."
  type        = string
  default     = "aurora"
}

variable "db_name" {
  description = "RDS database name."
  type        = string
  default     = "aurora"
}

variable "cors_origins" {
  description = "Allowed CORS origins for the API (comma-separated in env)."
  type        = list(string)
  default     = ["https://app.example.com"]
}

variable "enable_s3_uploads" {
  description = "Create S3 bucket for uploads and exports."
  type        = bool
  default     = true
}

variable "certificate_arn" {
  description = "ACM certificate ARN for HTTPS on the ALB (optional)."
  type        = string
  default     = ""
}

variable "alert_email" {
  description = "Email address for CloudWatch alarm notifications (empty disables the SNS topic)."
  type        = string
  default     = ""
}
