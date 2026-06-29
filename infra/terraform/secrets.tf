resource "aws_secretsmanager_secret" "database_url" {
  name                    = "${var.project_name}/${var.environment}/database-url"
  recovery_window_in_days = var.environment == "production" ? 30 : 0
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id = aws_secretsmanager_secret.database_url.id
  secret_string = format(
    "postgresql+psycopg://%s:%s@%s:%s/%s",
    var.db_username,
    random_password.db_password.result,
    aws_db_instance.main.address,
    aws_db_instance.main.port,
    var.db_name,
  )
}

resource "aws_secretsmanager_secret" "jwt_secret" {
  name                    = "${var.project_name}/${var.environment}/jwt-secret"
  recovery_window_in_days = var.environment == "production" ? 30 : 0
}

resource "random_password" "jwt_secret" {
  length  = 64
  special = true
}

resource "aws_secretsmanager_secret_version" "jwt_secret" {
  secret_id     = aws_secretsmanager_secret.jwt_secret.id
  secret_string = random_password.jwt_secret.result
}

resource "aws_ssm_parameter" "app_env" {
  name  = "/${var.project_name}/${var.environment}/APP_ENV"
  type  = "String"
  value = var.environment == "production" ? "production" : "staging"
}

resource "aws_ssm_parameter" "cors_origins" {
  name  = "/${var.project_name}/${var.environment}/CORS_ORIGINS"
  type  = "String"
  value = join(",", var.cors_origins)
}

resource "aws_ssm_parameter" "analytics_backend" {
  name  = "/${var.project_name}/${var.environment}/ANALYTICS_BACKEND"
  type  = "String"
  value = "postgres"
}
