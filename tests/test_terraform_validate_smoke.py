import os
import shutil
import subprocess
from pathlib import Path
import pytest
from jinja2 import Template


CASES = (
    (
        "aws_s3_bucket",
        "backend/generators/aws_s3_bucket.tf.j2",
        {
            "name": "bucket",
            "bucket_name": "example-bucket",
            "region": "us-east-1",
            "environment": "prod",
            "versioning": True,
            "force_destroy": False,
            "kms_key_id": "",
            "owner_tag": "platform",
            "cost_center_tag": "ENG",
            "enforce_secure_transport": True,
            "backend": None,
        },
    ),
    (
        "aws_rds_baseline",
        "backend/generators/aws_rds_baseline.tf.j2",
        {
            "region": "us-east-1",
            "environment": "prod",
            "db_identifier": "prod-app-db",
            "db_name": "appdb",
            "engine": "postgres",
            "engine_version": "14.10",
            "instance_class": "db.m6i.large",
            "allocated_storage": 100,
            "max_allocated_storage": 200,
            "multi_az": True,
            "subnet_group_name": "prod-app-db-subnets",
            "subnet_ids_literal": '["subnet-111","subnet-222"]',
            "security_group_ids_literal": '["sg-abc123"]',
            "logs_exports_literal": '["postgresql"]',
            "backup_retention": 7,
            "backup_window": "03:00-04:00",
            "preferred_maintenance_window": "sun:05:00-sun:06:00",
            "kms_key_id": "arn:aws:kms:us-east-1:123456789012:key/example",
            "owner_tag": "platform",
            "cost_center_tag": "ENG",
            "backend": None,
        },
    ),
    (
        "azure_storage_account",
        "backend/generators/azure_storage_account.tf.j2",
        {
            "rg_name": "rg",
            "rg_actual_name": "rg-app",
            "sa_name": "sa",
            "sa_actual_name": "stapp1234567890",
            "location": "eastus",
            "environment": "prod",
            "replication": "LRS",
            "versioning": True,
            "owner_tag": "platform",
            "cost_center_tag": "ENG",
            "restrict_network": True,
            "ip_rules_literal": '["52.160.0.0/24","52.161.0.0/24"]',
            "private_endpoint": None,
            "backend": None,
        },
    ),
    (
        "k8s_deployment",
        "backend/generators/k8s_deployment.tf.j2",
        {
            "namespace_name": "ns",
            "namespace_actual": "apps",
            "app_name": "deploy",
            "app_actual": "web",
            "image": "nginx:1.25.3",
            "container_port": 80,
            "replicas": 1,
            "non_root": True,
            "set_limits": True,
            "cpu_limit": "500m",
            "mem_limit": "256Mi",
            "cpu_request": "250m",
            "mem_request": "128Mi",
            "environment": "prod",
            "team_label": "platform",
            "tier_label": "backend",
            "enforce_seccomp": True,
            "enforce_apparmor": True,
            "backend": None,
        },
    ),
    (
        "k8s_namespace_baseline",
        "backend/generators/k8s_namespace_baseline.tf.j2",
        {
            "namespace_name": "apps",
            "namespace_actual": "apps",
            "environment": "prod",
            "team_label": "platform",
            "quota_limits_cpu": "8",
            "quota_limits_memory": "32Gi",
            "quota_requests_cpu": "4",
            "quota_requests_memory": "16Gi",
            "quota_pods": "100",
            "limit_max_cpu": "2",
            "limit_max_memory": "2Gi",
            "limit_min_cpu": "250m",
            "limit_min_memory": "256Mi",
            "limit_default_cpu": "500m",
            "limit_default_memory": "512Mi",
            "limit_default_request_cpu": "250m",
            "limit_default_request_memory": "256Mi",
            "backend": None,
        },
    ),
    (
        "k8s_hpa_pdb",
        "backend/generators/k8s_hpa_pdb.tf.j2",
        {
            "resource_name": "web",
            "namespace_actual": "apps",
            "deployment_name": "web",
            "app_label": "web",
            "environment": "prod",
            "min_replicas": 2,
            "max_replicas": 5,
            "target_cpu_utilization": 65,
            "target_memory_utilization": 70,
            "pdb_min_available": None,
            "pdb_max_unavailable": "25%",
            "backend": None,
        },
    ),
    (
        "k8s_psa_namespaces",
        "backend/generators/k8s_psa_namespaces.tf.j2",
        {
            "namespaces": [
                {"resource_name": "apps", "actual_name": "apps", "team_label": "platform"},
                {"resource_name": "payments", "actual_name": "payments", "team_label": "payments"},
            ],
            "environment": "prod",
            "enforce_level": "restricted",
            "warn_level": "baseline",
            "audit_level": "baseline",
            "psa_version": "latest",
            "backend": None,
        },
    ),
)


@pytest.mark.skipif(
    os.getenv("TFM_RUN_TERRAFORM_VALIDATE") != "1" or shutil.which("terraform") is None,
    reason="Set TFM_RUN_TERRAFORM_VALIDATE=1 and install terraform to run smoke validation.",
)
def test_templates_validate(tmp_path: Path) -> None:
    for name, template_path, context in CASES:
        workdir = tmp_path / name
        workdir.mkdir()
        template = Template(Path(template_path).read_text())
        (workdir / f"{name}.tf").write_text(template.render(**context))

        init = subprocess.run(
            ["terraform", "init", "-backend=false", "-input=false"],
            cwd=workdir,
            check=False,
            capture_output=True,
            text=True,
        )
        assert init.returncode == 0, f"terraform init failed for {name}: {init.stderr}"

        validate = subprocess.run(
            ["terraform", "validate"],
            cwd=workdir,
            check=False,
            capture_output=True,
            text=True,
        )
        assert validate.returncode == 0, f"terraform validate failed for {name}: {validate.stderr}"
