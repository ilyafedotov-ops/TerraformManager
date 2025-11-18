# Sample: AWS RDS multi-region baseline

provider "aws" {
  region = "us-east-1"
}

provider "aws" {
  alias  = "secondary"
  region = "us-west-2"
}

locals {
  common_tags = {
    ManagedBy   = "TerraformManager"
    Environment = "prod"
    Owner       = "platform-team"
    CostCenter  = "ENG-SRE"
  }
}

resource "aws_db_subnet_group" "primary" {
  name       = "primary-subnets"
  subnet_ids = ["subnet-111", "subnet-222"]
  tags       = local.common_tags
}

resource "aws_db_subnet_group" "replica" {
  provider  = aws.secondary
  name      = "replica-subnets"
  subnet_ids = ["subnet-aaa", "subnet-bbb"]
  tags      = local.common_tags
}

resource "aws_db_instance" "primary" {
  identifier                 = "prod-app-db"
  engine                     = "postgres"
  engine_version             = "14.10"
  instance_class             = "db.m6i.large"
  allocated_storage          = 100
  max_allocated_storage      = 200
  multi_az                   = true
  db_subnet_group_name       = aws_db_subnet_group.primary.name
  publicly_accessible        = false
  storage_encrypted          = true
  kms_key_id                 = "arn:aws:kms:us-east-1:123456789012:key/primary"
  backup_retention_period    = 7
  backup_window              = "03:00-04:00"
  maintenance_window         = "sun:05:00-sun:06:00"
  deletion_protection        = true
  copy_tags_to_snapshot      = true
  auto_minor_version_upgrade = true
  monitoring_interval        = 60
  performance_insights_enabled = true
  performance_insights_kms_key_id = "arn:aws:kms:us-east-1:123456789012:key/pi"
  enabled_cloudwatch_logs_exports = ["postgresql"]
  username = "masteruser"
  password = "change-me-strong"
  tags     = local.common_tags
}

resource "aws_db_instance" "replica" {
  provider               = aws.secondary
  identifier             = "prod-app-db-usw2"
  replicate_source_db    = aws_db_instance.primary.id
  instance_class         = "db.m6i.large"
  publicly_accessible    = false
  monitoring_interval    = 60
  performance_insights_enabled = true
  backup_window          = "03:00-04:00"
  kms_key_id             = "arn:aws:kms:us-west-2:123456789012:key/replica"
  db_subnet_group_name   = aws_db_subnet_group.replica.name
  storage_encrypted      = true
  backup_retention_period = 7
  deletion_protection    = true
  tags                   = local.common_tags
  depends_on             = [aws_db_instance.primary]
}

resource "aws_backup_vault" "primary" {
  name        = "prod-app-backup"
  kms_key_arn = "arn:aws:kms:us-east-1:123456789012:key/backup"
  tags        = local.common_tags
}

resource "aws_backup_vault" "replica" {
  provider    = aws.secondary
  name        = "prod-app-backup-usw2"
  kms_key_arn = "arn:aws:kms:us-west-2:123456789012:key/backup"
  tags        = local.common_tags
}

resource "aws_backup_plan" "rds" {
  name = "prod-app-backup-plan"

  rule {
    rule_name         = "daily"
    target_vault_name = aws_backup_vault.primary.name
    schedule          = "cron(0 7 * * ? *)"

    lifecycle {
      cold_storage_after = 30
      delete_after       = 120
    }

    copy_action {
      destination_vault_arn = aws_backup_vault.replica.arn
    }
  }

  tags = local.common_tags
}

resource "aws_backup_selection" "primary" {
  name         = "prod-app-backup-selection"
  plan_id      = aws_backup_plan.rds.id
  iam_role_arn = "arn:aws:iam::123456789012:role/service-role/AWSBackupDefaultServiceRole"
  resources    = [aws_db_instance.primary.arn]
}
