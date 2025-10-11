# AWS Best Practices (selected)

- S3: block public access, enable **SSE** (KMS preferred), and **versioning**.
- S3: enable server access logging to a separate bucket for audit trails.
- S3: configure account-level public access blocks (all four flags set to `true`).
- IAM: avoid `*` in Action/Resource; use least privilege.
- SG: avoid `0.0.0.0/0` on sensitive ports (22, 3389, 5432, etc.).
- RDS: require deletion protection, enable Enhanced Monitoring (`monitoring_interval` > 0), and pair critical workloads with cross-region read replicas plus AWS Backup copy actions.
