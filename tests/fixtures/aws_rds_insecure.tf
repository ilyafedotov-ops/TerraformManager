# Insecure RDS instance missing critical protections

resource "aws_db_instance" "primary" {
  identifier          = "tfm-rds-insecure"
  engine              = "postgres"
  engine_version      = "14.10"
  instance_class      = "db.t3.medium"
  allocated_storage   = 20
  backup_retention_period = 1
  storage_encrypted   = false
  publicly_accessible = true
  deletion_protection = false
  # monitoring_interval missing
  # performance_insights_enabled missing
  # secure logs exports missing
}
