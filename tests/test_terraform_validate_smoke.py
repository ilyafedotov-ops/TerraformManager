import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Iterable

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
            "preferred_backup_window": "03:00-04:00",
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
            "ip_rules_literal": '["10.0.0.0/24","10.0.1.0/24"]',
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
