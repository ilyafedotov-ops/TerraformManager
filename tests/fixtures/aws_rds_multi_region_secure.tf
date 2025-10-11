# Multi-region RDS deployment with cross-region replica and backup copy

provider "aws" {
  region = "us-east-1"
}

provider "aws" {
  alias  = "secondary"
  region = "us-west-2"
}

resource "aws_db_subnet_group" "primary" {
  name       = "primary-subnets"
  subnet_ids = ["subnet-aaa", "subnet-bbb"]
}

resource "aws_db_subnet_group" "replica" {
  provider  = aws.secondary
  name      = "replica-subnets"
  subnet_ids = ["subnet-ccc", "subnet-ddd"]
}

resource "aws_db_instance" "primary" {
  identifier                 = "tfm-rds-primary"
  engine                     = "postgres"
  engine_version             = "14.10"
  instance_class             = "db.m6i.large"
  allocated_storage          = 100
  max_allocated_storage      = 200
  multi_az                   = true
  db_subnet_group_name       = aws_db_subnet_group.primary.name
  publicly_accessible        = false
  storage_encrypted          = true
  kms_key_id                 = "arn:aws:kms:us-east-1:111111111111:key/primary"
  backup_retention_period    = 7
  preferred_backup_window    = "03:00-04:00"
  maintenance_window         = "sun:05:00-sun:06:00"
  deletion_protection        = true
  copy_tags_to_snapshot      = true
  auto_minor_version_upgrade = true
  monitoring_interval        = 60
  performance_insights_enabled = true
  performance_insights_kms_key_id = "arn:aws:kms:us-east-1:111111111111:key/pi"
  enabled_cloudwatch_logs_exports = ["postgresql"]
  username = "masteruser"
  password = "super-secret-password"
}

resource "aws_db_instance" "replica" {
  provider            = aws.secondary
  identifier          = "tfm-rds-replica"
  replicate_source_db = aws_db_instance.primary.id
  instance_class      = "db.m6i.large"
  publicly_accessible = false
  monitoring_interval = 60
  performance_insights_enabled = true
  kms_key_id          = "arn:aws:kms:us-west-2:111111111111:key/replica"
  db_subnet_group_name = aws_db_subnet_group.replica.name
  storage_encrypted   = true
  backup_retention_period = 7
  deletion_protection = true
  depends_on = [aws_db_instance.primary]
}

resource "aws_backup_vault" "primary" {
  name        = "tfm-rds-backup"
  kms_key_arn = "arn:aws:kms:us-east-1:111111111111:key/backup"
}

resource "aws_backup_vault" "replica" {
  provider    = aws.secondary
  name        = "tfm-rds-backup-replica"
  kms_key_arn = "arn:aws:kms:us-west-2:111111111111:key/backup"
}

resource "aws_backup_plan" "rds" {
  name = "tfm-rds-plan"

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
}

resource "aws_backup_selection" "primary" {
  name         = "tfm-rds-selection"
  plan_id      = aws_backup_plan.rds.id
  iam_role_arn = "arn:aws:iam::111111111111:role/service-role/AWSBackupDefaultServiceRole"

  resources = [aws_db_instance.primary.arn]
}
