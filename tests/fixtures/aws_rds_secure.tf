# Secure RDS primary instance with monitoring, backups, and encryption

resource "aws_db_subnet_group" "db" {
  name       = "db-subnets"
  subnet_ids = ["subnet-123", "subnet-456"]
}

resource "aws_db_instance" "primary" {
  identifier                 = "tfm-rds-primary"
  engine                     = "postgres"
  engine_version             = "14.10"
  instance_class             = "db.m6i.large"
  allocated_storage          = 100
  max_allocated_storage      = 200
  multi_az                   = true
  db_subnet_group_name       = aws_db_subnet_group.db.name
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
