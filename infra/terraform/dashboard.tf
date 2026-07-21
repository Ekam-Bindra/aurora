# Single-pane operations dashboard + saved Logs Insights queries.
# Console: CloudWatch → Dashboards → aurora-<environment>.

locals {
  lb  = aws_lb.main.arn_suffix
  api = aws_lb_target_group.api.arn_suffix
  web = aws_lb_target_group.web.arn_suffix
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.project_name}-${var.environment}"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric", x = 0, y = 0, width = 12, height = 6,
        properties = {
          title  = "ALB — requests & errors"
          region = var.aws_region
          stat   = "Sum"
          period = 300
          metrics = [
            ["AWS/ApplicationELB", "RequestCount", "LoadBalancer", local.lb],
            [".", "HTTPCode_Target_5XX_Count", ".", ".", { color = "#d62728" }],
            [".", "HTTPCode_ELB_5XX_Count", ".", ".", { color = "#ff9896" }],
            [".", "HTTPCode_Target_4XX_Count", ".", ".", { color = "#ff7f0e" }],
          ]
        }
      },
      {
        type = "metric", x = 12, y = 0, width = 12, height = 6,
        properties = {
          title  = "ALB — target response time"
          region = var.aws_region
          period = 300
          metrics = [
            ["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", local.lb, { stat = "p50" }],
            ["...", { stat = "p95" }],
            ["...", { stat = "p99", color = "#d62728" }],
          ]
        }
      },
      {
        type = "metric", x = 0, y = 6, width = 12, height = 6,
        properties = {
          title  = "Target health (api / web)"
          region = var.aws_region
          stat   = "Minimum"
          period = 60
          metrics = [
            ["AWS/ApplicationELB", "HealthyHostCount", "TargetGroup", local.api, "LoadBalancer", local.lb, { label = "api healthy" }],
            [".", "UnHealthyHostCount", ".", ".", ".", ".", { label = "api unhealthy", color = "#d62728" }],
            [".", "HealthyHostCount", "TargetGroup", local.web, "LoadBalancer", local.lb, { label = "web healthy" }],
            [".", "UnHealthyHostCount", ".", ".", ".", ".", { label = "web unhealthy", color = "#ff9896" }],
          ]
        }
      },
      {
        type = "metric", x = 12, y = 6, width = 12, height = 6,
        properties = {
          title  = "ECS — CPU / memory"
          region = var.aws_region
          stat   = "Average"
          period = 300
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ClusterName", aws_ecs_cluster.main.name, "ServiceName", aws_ecs_service.api.name, { label = "api cpu" }],
            [".", "MemoryUtilization", ".", ".", ".", ".", { label = "api mem" }],
            [".", "CPUUtilization", "ClusterName", aws_ecs_cluster.main.name, "ServiceName", aws_ecs_service.web.name, { label = "web cpu" }],
            [".", "MemoryUtilization", ".", ".", ".", ".", { label = "web mem" }],
          ]
        }
      },
      {
        type = "metric", x = 0, y = 12, width = 12, height = 6,
        properties = {
          title  = "RDS vitals"
          region = var.aws_region
          period = 300
          metrics = [
            ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", aws_db_instance.main.identifier, { stat = "Average" }],
            [".", "DatabaseConnections", ".", ".", { stat = "Maximum", yAxis = "right" }],
            [".", "FreeableMemory", ".", ".", { stat = "Minimum", visible = false }],
          ]
        }
      },
      {
        type = "metric", x = 12, y = 12, width = 12, height = 6,
        properties = {
          title  = "RDS free storage (GiB)"
          region = var.aws_region
          stat   = "Minimum"
          period = 300
          metrics = [
            ["AWS/RDS", "FreeStorageSpace", "DBInstanceIdentifier", aws_db_instance.main.identifier],
          ]
        }
      },
      {
        type = "alarm", x = 0, y = 18, width = 24, height = 3,
        properties = {
          title = "Alarms"
          alarms = concat(
            [
              aws_cloudwatch_metric_alarm.alb_5xx.arn,
              aws_cloudwatch_metric_alarm.alb_latency_p95.arn,
              aws_cloudwatch_metric_alarm.rds_cpu_high.arn,
              aws_cloudwatch_metric_alarm.rds_storage_low.arn,
              aws_cloudwatch_metric_alarm.rds_connections_high.arn,
            ],
            [for a in aws_cloudwatch_metric_alarm.target_unhealthy : a.arn],
            [for a in aws_cloudwatch_metric_alarm.ecs_cpu_high : a.arn],
          )
        }
      },
    ]
  })
}

# ── Saved Logs Insights queries (Console → Logs Insights → Saved queries) ──

resource "aws_cloudwatch_query_definition" "api_errors" {
  name            = "${var.project_name}-${var.environment}/api-errors-last-hour"
  log_group_names = [aws_cloudwatch_log_group.api.name]
  query_string    = <<-EOT
    fields @timestamp, request_id, logger, message
    | filter level = "error" or level = "warning"
    | sort @timestamp desc
    | limit 100
  EOT
}

resource "aws_cloudwatch_query_definition" "trace_request_id" {
  name            = "${var.project_name}-${var.environment}/trace-a-request-id"
  log_group_names = [aws_cloudwatch_log_group.api.name]
  query_string    = <<-EOT
    fields @timestamp, level, logger, message
    | filter request_id = "req_PASTE_ID_HERE"
    | sort @timestamp asc
  EOT
}

resource "aws_cloudwatch_query_definition" "http_5xx" {
  name            = "${var.project_name}-${var.environment}/http-5xx-access-lines"
  log_group_names = [aws_cloudwatch_log_group.api.name]
  query_string    = <<-EOT
    fields @timestamp, @message
    | filter @message like / 5[0-9][0-9] /
    | sort @timestamp desc
    | limit 100
  EOT
}
