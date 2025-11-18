---
title: AWS RDS Best Practices
provider: aws
service: rds
category: [security, database, high-availability]
tags: [encryption, backups, multi-az, aurora, read-replicas]
last_updated: 2025-01-18
difficulty: intermediate
---

# AWS RDS Best Practices

Amazon RDS simplifies database administration for MySQL, PostgreSQL, Oracle, SQL Server, and MariaDB. Aurora provides MySQL/PostgreSQL-compatible engines with enhanced performance and availability.

## Encryption

### Enable Encryption at Rest

**Always encrypt databases in production:**

```terraform
resource "aws_db_instance" "main" {
  identifier = "prod-db"
  engine     = "postgres"
  engine_version = "15.4"

  storage_encrypted = true
  kms_key_id        = aws_kms_key.rds.arn  # Customer-managed key recommended

  # Other configuration...
}

resource "aws_kms_key" "rds" {
  description             = "RDS encryption key"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name = "rds-encryption-key"
  }
}
```

**Note:** Encryption cannot be enabled on existing unencrypted instances. Must create encrypted snapshot and restore.

### Encrypt Connections (TLS/SSL)

**Enforce TLS connections:**

```terraform
resource "aws_db_parameter_group" "postgres" {
  name   = "postgres-ssl-required"
  family = "postgres15"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }
}

resource "aws_db_instance" "main" {
  parameter_group_name = aws_db_parameter_group.postgres.name
}
```

## High Availability

### Multi-AZ Deployment

**Enable Multi-AZ for production:**

```terraform
resource "aws_db_instance" "main" {
  multi_az = true  # Automatic failover to standby

  backup_retention_period = 7
  backup_window           = "03:00-04:00"  # Daily automated backups
  maintenance_window      = "sun:04:00-sun:05:00"
}
```

**Benefits:**
- Automatic failover (1-2 minutes)
- Synchronous replication to standby
- Backups from standby (no performance impact)
- Zero data loss during failover

### Aurora Multi-AZ Clusters

**Use Aurora for mission-critical workloads:**

```terraform
resource "aws_rds_cluster" "aurora" {
  cluster_identifier      = "prod-aurora-cluster"
  engine                  = "aurora-postgresql"
  engine_version          = "15.4"
  database_name           = "mydb"
  master_username         = "admin"
  master_password         = random_password.db_password.result

  storage_encrypted = true
  kms_key_id        = aws_kms_key.rds.arn

  backup_retention_period = 35  # Up to 35 days
  preferred_backup_window = "03:00-04:00"

  enabled_cloudwatch_logs_exports = ["postgresql"]

  # Deploy across multiple AZs
  availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"]

  db_subnet_group_name = aws_db_subnet_group.aurora.name
  vpc_security_group_ids = [aws_security_group.aurora.id]

  tags = {
    Environment = "production"
  }
}

# Writer instance
resource "aws_rds_cluster_instance" "aurora_writer" {
  identifier         = "prod-aurora-writer"
  cluster_identifier = aws_rds_cluster.aurora.id
  instance_class     = "db.r6g.xlarge"
  engine             = aws_rds_cluster.aurora.engine

  publicly_accessible = false
  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_monitoring.arn

  performance_insights_enabled    = true
  performance_insights_kms_key_id = aws_kms_key.rds.arn
}

# Reader instances for scaling
resource "aws_rds_cluster_instance" "aurora_readers" {
  count              = 2
  identifier         = "prod-aurora-reader-${count.index + 1}"
  cluster_identifier = aws_rds_cluster.aurora.id
  instance_class     = "db.r6g.xlarge"
  engine             = aws_rds_cluster.aurora.engine

  publicly_accessible = false
  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_monitoring.arn

  performance_insights_enabled = true
  performance_insights_kms_key_id = aws_kms_key.rds.arn
}
```

## Network Security

### Private Subnet Deployment

**Never deploy RDS in public subnets:**

```terraform
resource "aws_db_subnet_group" "main" {
  name       = "rds-subnet-group"
  subnet_ids = var.private_subnet_ids  # Private subnets only

  tags = {
    Name = "RDS subnet group"
  }
}

resource "aws_db_instance" "main" {
  db_subnet_group_name = aws_db_subnet_group.main.name
  publicly_accessible  = false  # Never set to true
}
```

### Security Groups

**Restrict access to known sources:**

```terraform
resource "aws_security_group" "rds" {
  name        = "rds-sg"
  description = "Security group for RDS instance"
  vpc_id      = var.vpc_id

  tags = {
    Name = "rds-sg"
  }
}

# Allow from application tier only
resource "aws_security_group_rule" "allow_app" {
  type                     = "ingress"
  from_port                = 5432  # PostgreSQL
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.app.id
  security_group_id        = aws_security_group.rds.id
}

# No outbound rules needed (RDS doesn't initiate connections)
```

## Backup and Recovery

### Automated Backups

**Configure retention and windows:**

```terraform
resource "aws_db_instance" "main" {
  backup_retention_period = 30  # 1-35 days, 7 recommended minimum
  backup_window           = "03:00-04:00"  # UTC, avoid peak hours

  # Enable automated backups (required for point-in-time recovery)
  skip_final_snapshot       = false
  final_snapshot_identifier = "prod-db-final-snapshot-${timestamp()}"

  delete_automated_backups = false  # Retain after deletion
}
```

### Manual Snapshots

**Create snapshots before major changes:**

```terraform
resource "aws_db_snapshot" "before_upgrade" {
  db_instance_identifier = aws_db_instance.main.id
  db_snapshot_identifier = "pre-upgrade-snapshot-${timestamp()}"

  tags = {
    Purpose = "Pre-upgrade backup"
  }
}
```

### Cross-Region Backups

**For disaster recovery:**

```terraform
resource "aws_db_instance" "main" {
  # Enable automated backups first
  backup_retention_period = 7

  # Copy snapshots to another region
  depends_on = [aws_db_instance_automated_backups_replication.replica]
}

resource "aws_db_instance_automated_backups_replication" "replica" {
  source_db_instance_arn = aws_db_instance.main.arn
  kms_key_id             = aws_kms_key.replica_region.arn  # Key in target region

  provider = aws.replica_region
}
```

## Performance

### Instance Sizing

**Choose appropriate instance class:**

| Workload | Instance Class | Notes |
|----------|---------------|-------|
| **Dev/Test** | db.t3.micro - db.t3.medium | Burstable, cost-effective |
| **Production (general)** | db.m6i.large - db.m6i.2xlarge | Balanced compute/memory |
| **Memory-intensive** | db.r6i.xlarge - db.r6i.4xlarge | 2:1 memory to vCPU ratio |
| **Aurora** | db.r6g.large+ | Graviton2, better price/performance |

### Storage Configuration

```terraform
resource "aws_db_instance" "main" {
  # Use gp3 for best price/performance
  storage_type = "gp3"
  allocated_storage = 100  # GB
  max_allocated_storage = 1000  # Enable storage autoscaling

  # gp3 allows independent IOPS and throughput tuning
  iops = 3000  # 3000-16000 IOPS
  storage_throughput = 125  # 125-1000 MB/s
}
```

### Read Replicas

**Scale read-heavy workloads:**

```terraform
resource "aws_db_instance" "read_replica" {
  identifier             = "prod-db-replica"
  replicate_source_db    = aws_db_instance.main.identifier
  instance_class         = "db.r6i.large"

  # Can be in different AZ or region
  availability_zone = "us-east-1b"

  auto_minor_version_upgrade = true
  publicly_accessible        = false

  # Independent storage from source
  storage_type = "gp3"
  iops         = 3000
}
```

## Monitoring

### Enhanced Monitoring

```terraform
resource "aws_db_instance" "main" {
  monitoring_interval = 60  # Seconds (0, 1, 5, 10, 15, 30, 60)
  monitoring_role_arn = aws_iam_role.rds_monitoring.arn

  enabled_cloudwatch_logs_exports = [
    "postgresql",  # Or "error", "general", "slowquery" for MySQL
  ]
}

resource "aws_iam_role" "rds_monitoring" {
  name = "rds-monitoring-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "monitoring.rds.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}
```

### Performance Insights

```terraform
resource "aws_db_instance" "main" {
  performance_insights_enabled    = true
  performance_insights_retention_period = 7  # 7 (free) or 731 days
  performance_insights_kms_key_id = aws_kms_key.rds.arn
}
```

### CloudWatch Alarms

```terraform
resource "aws_cloudwatch_metric_alarm" "cpu" {
  alarm_name          = "rds-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.id
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "storage" {
  alarm_name          = "rds-low-storage"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 10737418240  # 10 GB in bytes

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.id
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
}
```

## Security Best Practices

### IAM Database Authentication

**Eliminate password management:**

```terraform
resource "aws_db_instance" "main" {
  iam_database_authentication_enabled = true
}
```

**Connect using IAM:**

```bash
# Generate auth token
TOKEN=$(aws rds generate-db-auth-token \
  --hostname mydb.abc123.us-east-1.rds.amazonaws.com \
  --port 5432 \
  --username iamuser)

# Connect with token
psql "host=mydb.abc123.us-east-1.rds.amazonaws.com port=5432 dbname=postgres user=iamuser password=$TOKEN sslmode=require"
```

### Secrets Manager Integration

```terraform
resource "aws_db_instance" "main" {
  manage_master_user_password = true
  master_user_secret_kms_key_id = aws_kms_key.secrets.arn
}

# Access password from Secrets Manager
data "aws_secretsmanager_secret_version" "db_password" {
  secret_id = aws_db_instance.main.master_user_secret[0].secret_arn
}
```

### Parameter Group Hardening

```terraform
resource "aws_db_parameter_group" "postgres_secure" {
  name   = "postgres-secure"
  family = "postgres15"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }

  parameter {
    name  = "log_statement"
    value = "ddl"  # Log DDL statements
  }
}
```

## Upgrade Strategy

### Minor Version Upgrades

```terraform
resource "aws_db_instance" "main" {
  auto_minor_version_upgrade = true  # Automatic patches during maintenance window
  allow_major_version_upgrade = false  # Prevent accidental major upgrades
}
```

### Major Version Upgrades

**Test in non-prod first:**

```bash
# 1. Create snapshot
aws rds create-db-snapshot \
  --db-instance-identifier prod-db \
  --db-snapshot-identifier pre-upgrade-snapshot

# 2. Restore to test instance
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier test-db \
  --db-snapshot-identifier pre-upgrade-snapshot

# 3. Upgrade test instance
aws rds modify-db-instance \
  --db-instance-identifier test-db \
  --engine-version 16.1 \
  --allow-major-version-upgrade \
  --apply-immediately

# 4. Test application compatibility

# 5. Upgrade production (during maintenance window)
```

## Cost Optimization

### Reserved Instances

**1-year or 3-year commitments for 40-60% savings:**

```terraform
resource "aws_rds_reserved_instance" "main" {
  offering_id         = data.aws_rds_reserved_instance_offering.postgres.offering_id
  instance_count      = 1
  reservation_id      = "my-reservation"
}
```

### Aurora Serverless v2

**For variable workloads:**

```terraform
resource "aws_rds_cluster" "serverless" {
  engine         = "aurora-postgresql"
  engine_mode    = "provisioned"
  engine_version = "15.4"

  serverlessv2_scaling_configuration {
    min_capacity = 0.5  # ACUs
    max_capacity = 16
  }
}

resource "aws_rds_cluster_instance" "serverless" {
  cluster_identifier = aws_rds_cluster.serverless.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.serverless.engine
}
```

## Summary Checklist

- [ ] Encryption at rest enabled with KMS
- [ ] TLS/SSL enforced for connections
- [ ] Multi-AZ enabled for production
- [ ] Deployed in private subnets
- [ ] Security groups restrict access to app tier
- [ ] Backup retention ≥7 days configured
- [ ] Automated backups enabled
- [ ] Enhanced monitoring enabled (60s)
- [ ] Performance Insights enabled
- [ ] CloudWatch alarms configured
- [ ] IAM database authentication considered
- [ ] Secrets Manager for password management
- [ ] Parameter group hardened
- [ ] Auto minor version upgrades enabled
- [ ] Appropriate instance class selected

## References

- [RDS Best Practices](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_BestPractices.html)
- [Aurora Best Practices](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/Aurora.BestPractices.html)
- [RDS Security](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.html)
- [CIS AWS Database Services Benchmark](https://www.cisecurity.org/benchmark/amazon_web_services)
