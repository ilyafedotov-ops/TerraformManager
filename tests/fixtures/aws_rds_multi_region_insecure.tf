# Multi-region RDS deployment missing replica monitoring and backup copy

provider "aws" {
  region = "us-east-1"
}

provider "aws" {
  alias  = "secondary"
  region = "us-west-2"
}

resource "aws_db_instance" "primary" {
  identifier              = "tfm-rds-primary"
  engine                  = "postgres"
  engine_version          = "14.10"
  instance_class          = "db.m6i.large"
  storage_encrypted       = true
  backup_retention_period = 7
  deletion_protection     = true
  monitoring_interval     = 60
  performance_insights_enabled = true
  publicly_accessible     = false
}

resource "aws_db_instance" "replica" {
  provider            = aws.secondary
  identifier          = "tfm-rds-replica"
  replicate_source_db = aws_db_instance.primary.id
  instance_class      = "db.m6i.large"
  publicly_accessible = false
  # Missing monitoring_interval and performance_insights_enabled
  # Missing backup_retention_period/deletion_protection
}

resource "aws_backup_plan" "rds" {
  name = "tfm-rds-plan"

  rule {
    rule_name = "daily"
    schedule  = "cron(0 7 * * ? *)"
    target_vault_name = "missing"
    # Missing copy_action to secondary vault
  }
}
