import json
from pathlib import Path

from jinja2 import Template


GOLDEN_DIR = Path("tests/golden")


def _read(path: Path) -> str:
    return path.read_text()


def test_aws_rds_multi_region_golden() -> None:
    template = Template(_read(Path("backend/generators/aws_rds_multi_region.tf.j2")))
    rendered = template.render(
        primary_region="us-east-1",
        secondary_region="us-west-2",
        environment="prod",
        primary_db_identifier="prod-app-db",
        replica_db_identifier="prod-app-db-usw2",
        primary_resource_name="prod_app_db",
        replica_resource_name="prod_app_db_usw2",
        db_name="appdb",
        engine="postgres",
        engine_version="14.10",
        instance_class="db.m6i.large",
        replica_instance_class="db.m6i.large",
        allocated_storage=100,
        max_allocated_storage=200,
        multi_az=True,
        primary_subnet_group_name="prod-app-db-primary-subnets",
        replica_subnet_group_name="prod-app-db-usw2-subnets",
        primary_subnet_group_resource_name="prod_app_db_primary_subnets",
        replica_subnet_group_resource_name="prod_app_db_usw2_subnets",
        primary_subnet_ids_literal='["subnet-1","subnet-2"]',
        replica_subnet_ids_literal='["subnet-a","subnet-b"]',
        primary_security_group_ids_literal='["sg-primary"]',
        replica_security_group_ids_literal='["sg-replica"]',
        logs_exports_literal='["postgresql"]',
        backup_retention=7,
        preferred_backup_window="03:00-05:00",
        preferred_maintenance_window="sun:05:00-sun:06:00",
        primary_kms_key_id="arn:aws:kms:us-east-1:123456789012:key/primary",
        replica_kms_key_id="arn:aws:kms:us-west-2:123456789012:key/replica",
        owner_tag="platform",
        cost_center_tag="ENG",
        backup_vault_name="prod-app-backup",
        replica_backup_vault_name="prod-app-backup-usw2",
        backup_vault_resource_name="prod_app_backup",
        replica_backup_vault_resource_name="prod_app_backup_usw2",
        backup_plan_name="prod-app-backup-plan",
        backup_plan_resource_name="prod_app_backup_plan",
        backup_rule_name="daily-backup",
        backup_selection_name="rds-primary-selection",
        backup_selection_resource_name="rds_primary_selection",
        backup_cron="cron(0 7 * * ? *)",
        cold_storage_after=30,
        delete_after=120,
        backup_kms_key_arn="arn:aws:kms:us-east-1:123:key/backup",
        replica_backup_kms_key_arn="arn:aws:kms:us-west-2:123:key/backup",
        backup_iam_role_arn="arn:aws:iam::123456789012:role/service-role/AWSBackupDefaultServiceRole",
        backend=None,
    )
    golden = _read(GOLDEN_DIR / "aws_rds_multi_region_expected.tf")
    assert rendered.strip() == golden.strip()


def test_aws_s3_golden() -> None:
    template = Template(_read(Path("backend/generators/aws_s3_bucket.tf.j2")))
    rendered = template.render(
        name="bucket",
        bucket_name="example-bucket",
        region="us-east-1",
        environment="prod",
        versioning=True,
        force_destroy=False,
        kms_key_id="",
        owner_tag="platform",
        cost_center_tag="ENG",
        enforce_secure_transport=True,
        backend=None,
    )
    golden = _read(GOLDEN_DIR / "aws_s3_expected.tf")
    assert rendered.strip() == golden.strip()


def test_aws_observability_golden() -> None:
    template = Template(_read(Path("backend/generators/aws_observability_baseline.tf.j2")))
    rendered = template.render(
        region="us-east-1",
        environment="prod",
        trail_name="org-trail",
        trail_bucket_name="org_trail",
        cloudtrail_bucket="org-trail-logs",
        kms_key_id="",
        owner_tag="platform",
        cost_center_tag="ENG",
        config_recorder_name="default",
        config_role_name="aws-config-role",
        backend=None,
    )
    golden = _read(GOLDEN_DIR / "aws_observability_expected.tf")
    assert rendered.strip() == golden.strip()


def test_aws_ecs_fargate_golden() -> None:
    template = Template(_read(Path("backend/generators/aws_ecs_fargate_service.tf.j2")))
    container_def = [
        {
            "name": "web",
            "image": "public.ecr.aws/nginx/nginx:stable",
            "essential": True,
            "portMappings": [
                {
                    "containerPort": 8080,
                    "hostPort": 8080,
                    "protocol": "tcp",
                }
            ],
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": "/aws/ecs/app-ecs-cluster/app-web-service",
                    "awslogs-region": "us-east-1",
                    "awslogs-stream-prefix": "web",
                },
            },
            "environment": [
                {"name": "ENVIRONMENT", "value": "prod"},
            ],
            "readonlyRootFilesystem": True,
        }
    ]
    rendered = template.render(
        region="us-east-1",
        environment="prod",
        cluster_resource_name="app_ecs_cluster",
        cluster_actual_name="app-ecs-cluster",
        service_resource_name="app_ecs_service",
        service_actual_name="app-web-service",
        execution_role_resource_name="app_ecs_exec_role",
        execution_role_actual_name="app-web-service-exec-role",
        task_role_resource_name="app_ecs_task_role",
        task_role_actual_name="app-web-service-task-role",
        task_definition_resource_name="app_ecs_taskdef",
        task_family="app-web-service-task",
        cpu="512",
        memory="1024",
        desired_count=2,
        platform_version="1.4.0",
        enable_execute_command=True,
        circuit_breaker_enabled=True,
        health_check_grace_period=60,
        subnet_ids_literal='["subnet-1","subnet-2"]',
        security_group_ids_literal='["sg-aaa","sg-bbb"]',
        log_group_resource_name="app_ecs_logs",
        log_retention_days=30,
        log_kms_key_id="",
        ssm_parameter_arns_literal='["arn:aws:ssm:us-east-1:123456789012:parameter/app/*"]',
        has_ssm_parameters=True,
        container_definitions_json=json.dumps(container_def, indent=2),
        owner_tag="platform",
        cost_center_tag="ENG",
        backend=None,
    )
    golden = _read(GOLDEN_DIR / "aws_ecs_fargate_expected.tf")
    assert rendered.strip() == golden.strip()


def test_aws_eks_irsa_golden() -> None:
    template = Template(_read(Path("backend/generators/aws_eks_irsa_service.tf.j2")))
    policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "ApplicationAccess",
                "Effect": "Allow",
                "Action": ["s3:GetObject"],
                "Resource": ["arn:aws:s3:::example-bucket/*"],
            }
        ],
    }
    rendered = template.render(
        region="us-east-1",
        environment="prod",
        cluster_name="app-eks",
        cluster_data_resource_name="app_eks_cluster_data",
        namespace="app",
        namespace_resource_name="app",
        service_account_name="app-sa",
        service_account_resource_name="app_sa",
        oidc_provider_arn="arn:aws:iam::123456789012:oidc-provider/oidc.eks.us-east-1.amazonaws.com/id/EXAMPLE",
        oidc_provider_host="oidc.eks.us-east-1.amazonaws.com/id/EXAMPLE",
        create_namespace=True,
        iam_role_resource_name="app_sa_irsa_role",
        iam_role_actual_name="app-sa-irsa-role",
        iam_role_policy_resource_name="app_sa_irsa_policy",
        iam_policy_name="app-sa-access",
        policy_document_json=json.dumps(policy_document, indent=2),
        psa_enforce_level="restricted",
        psa_warn_level="baseline",
        psa_audit_level="restricted",
        owner_tag="platform",
        cost_center_tag="ENG",
        backend=None,
    )
    golden = _read(GOLDEN_DIR / "aws_eks_irsa_expected.tf")
    assert rendered.strip() == golden.strip()


def test_aws_rds_baseline_golden() -> None:
    template = Template(_read(Path("backend/generators/aws_rds_baseline.tf.j2")))
    rendered = template.render(
        region="us-east-1",
        environment="prod",
        db_identifier="prod-app-db",
        db_name="appdb",
        engine="postgres",
        engine_version="14.10",
        instance_class="db.m6i.large",
        allocated_storage=100,
        max_allocated_storage=200,
        multi_az=True,
        subnet_group_name="prod-app-db-subnets",
        subnet_ids_literal='["subnet-111","subnet-222"]',
        security_group_ids_literal='["sg-abc123"]',
        logs_exports_literal='["postgresql"]',
        backup_retention=7,
        preferred_backup_window="03:00-04:00",
        preferred_maintenance_window="sun:05:00-sun:06:00",
        kms_key_id="arn:aws:kms:us-east-1:123456789012:key/example",
        owner_tag="platform",
        cost_center_tag="ENG",
        backend=None,
    )
    golden = _read(GOLDEN_DIR / "aws_rds_baseline_expected.tf")
    assert rendered.strip() == golden.strip()


def test_azure_diagnostics_golden() -> None:
    template = Template(_read(Path("backend/generators/azure_diagnostics_baseline.tf.j2")))


def test_azure_diagnostics_golden() -> None:
    template = Template(_read(Path("backend/generators/azure_diagnostics_baseline.tf.j2")))
    rendered = template.render(
        rg_name="rg",
        rg_actual_name="rg-diag",
        location="eastus",
        environment="prod",
        law_name="law",
        law_actual_name="law-diag",
        log_retention_days=30,
        diagnostic_prefix="diag",
        targets=[{
            "name": "diag_storage",
            "id": "azurerm_storage_account.logstorage.id",
            "id_is_literal": True,
            "index": 1,
            "log_categories": ["StorageRead", "StorageWrite", "StorageDelete"],
            "metric_categories": ["AllMetrics"],
        }],
        create_storage_account=True,
        storage_name="logstorage",
        storage_actual_name="logstorageacct",
        health_alert={
            "resource_name": "law_health",
            "name": "law-ingestion-alert",
            "description": "Alert when ingestion availability drops below 99%",
            "severity": 2,
            "frequency": "PT5M",
            "window_size": "PT5M",
            "metric_name": "SearchServiceAvailability",
            "aggregation": "Average",
            "threshold": 99,
            "action_group_ids": ["/subscriptions/.../actionGroups/notify"],
        },
        owner_tag="platform",
        cost_center_tag="ENG",
        backend=None,
    )
    golden = _read(GOLDEN_DIR / "azure_diagnostics_expected.tf")
    assert rendered.strip() == golden.strip()


def test_azure_storage_golden() -> None:
    template = Template(_read(Path("backend/generators/azure_storage_account.tf.j2")))
    rendered = template.render(
        rg_name="rg",
        rg_actual_name="rg-app",
        sa_name="sa",
        sa_actual_name="stapp1234567890",
        location="eastus",
        environment="prod",
        replication="LRS",
        versioning=True,
        owner_tag="platform",
        cost_center_tag="ENG",
        restrict_network=True,
        ip_rules_literal='["10.0.0.0/24","10.0.1.0/24"]',
        private_endpoint={
            "resource_name": "stapp1234567890_pe",
            "name": "stapp1234567890-pe",
            "connection_name": "stapp1234567890-blob",
            "subnet_id": "/subscriptions/.../subnets/storage-private-endpoint",
            "private_dns_zone_id": "/subscriptions/.../privateDnsZones/privatelink.blob.core.windows.net",
            "dns_zone_group_name": "stapp1234567890_blob_zone",
        },
        backend=None,
    )
    golden = _read(GOLDEN_DIR / "azure_storage_expected.tf")
    assert rendered.strip() == golden.strip()


def test_k8s_argo_cd_golden() -> None:
    template = Template(_read(Path("backend/generators/k8s_argo_cd_baseline.tf.j2")))
    rendered = template.render(
        environment="prod",
        team_label="platform",
        namespace_actual="argocd",
        namespace_resource_name="argocd_ns",
        release_name="argocd",
        release_resource_name="argocd_release",
        helm_repository="https://argoproj.github.io/argo-helm",
        chart_version="5.46.6",
        controller_replicas=2,
        enable_appset=True,
        enable_dex=False,
        disable_admin=True,
        enable_ingress=True,
        ingress_host="argocd.example.com",
        ingress_class="nginx",
        tls_secret_name="argocd-server-tls",
        external_url="https://argocd.example.com",
        allowed_cidrs=["10.0.0.0/24"],
        set_resource_quota=True,
        quota_limits_cpu="20",
        quota_limits_memory="64Gi",
        quota_requests_cpu="10",
        quota_requests_memory="32Gi",
        quota_pods="200",
        backend=None,
    )
    golden = _read(GOLDEN_DIR / "k8s_argo_cd_expected.tf")
    assert rendered.strip() == golden.strip()


def test_aws_alb_golden() -> None:
    template = Template(_read(Path("backend/generators/aws_alb_waf.tf.j2")))
    rendered = template.render(
        region="us-east-1",
        environment="prod",
        alb_name="alb",
        alb_actual_name="app-alb",
        waf_name="waf",
        waf_actual_name="app-alb-waf",
        security_group_ids_literal='["sg-abc123"]',
        subnet_ids_literal='["subnet-111","subnet-222"]',
        ssl_policy="ELBSecurityPolicy-TLS13-1-2-2021-06",
        internal=False,
        owner_tag="platform",
        cost_center_tag="ENG",
        enable_access_logs=True,
        create_log_bucket=True,
        log_bucket_name="app-alb-logs",
        log_bucket_prefix="app-alb/alb",
        log_bucket_resource_name="app_alb_logs",
        backend=None,
    )
    golden = _read(GOLDEN_DIR / "aws_alb_expected.tf")
    assert rendered.strip() == golden.strip()


def test_azure_key_vault_golden() -> None:
    template = Template(_read(Path("backend/generators/azure_key_vault.tf.j2")))
    rendered = template.render(
        rg_name="rg",
        rg_actual_name="rg-kv",
        location="eastus2",
        environment="prod",
        kv_name="kv",
        kv_actual_name="kv-secure",
        tenant_id="00000000-0000-0000-0000-000000000000",
        soft_delete_retention_days=90,
        ip_rules_literal='["10.0.0.0/24"]',
        vnet_id="/subscriptions/.../virtualNetworks/vnet-secure",
        subnet_id="/subscriptions/.../subnets/kv-endpoint",
        owner_tag="platform",
        cost_center_tag="ENG",
        backend=None,
    )
    golden = _read(GOLDEN_DIR / "azure_key_vault_expected.tf")
    assert rendered.strip() == golden.strip()


def test_k8s_deployment_golden() -> None:
    template = Template(_read(Path("backend/generators/k8s_deployment.tf.j2")))
    rendered = template.render(
        namespace_name="ns",
        namespace_actual="apps",
        app_name="deploy",
        app_actual="web",
        image="nginx:1.25.3",
        container_port=80,
        replicas=2,
        non_root=True,
        set_limits=True,
        cpu_limit="500m",
        mem_limit="256Mi",
        cpu_request="250m",
        mem_request="128Mi",
        environment="prod",
        team_label="platform",
        tier_label="backend",
        enforce_seccomp=True,
        enforce_apparmor=True,
        backend=None,
    )
    golden = _read(GOLDEN_DIR / "k8s_deployment_expected.tf")
    assert rendered.strip() == golden.strip()


def test_k8s_pod_security_golden() -> None:
    template = Template(_read(Path("backend/generators/k8s_pod_security_baseline.tf.j2")))
    rendered = template.render(
        policy_name="policy",
        policy_actual_name="restricted",
        service_account_namespace="default",
        service_account_name="default",
        namespace_name="ns",
        namespace_actual="restricted",
        backend=None,
    )
    golden = _read(GOLDEN_DIR / "k8s_pod_security_expected.tf")
    assert rendered.strip() == golden.strip()


def test_k8s_psa_golden() -> None:
    template = Template(_read(Path("backend/generators/k8s_psa_namespaces.tf.j2")))
    rendered = template.render(
        namespaces=[
            {"resource_name": "apps", "actual_name": "apps", "team_label": "platform"},
            {"resource_name": "payments", "actual_name": "payments", "team_label": "payments"},
        ],
        environment="prod",
        enforce_level="restricted",
        warn_level="baseline",
        audit_level="baseline",
        psa_version="latest",
        backend=None,
    )
    golden = _read(GOLDEN_DIR / "k8s_psa_expected.tf")
    assert rendered.strip() == golden.strip()


def test_k8s_hpa_pdb_golden() -> None:
    template = Template(_read(Path("backend/generators/k8s_hpa_pdb.tf.j2")))
    rendered = template.render(
        resource_name="my_app",
        namespace_actual="apps",
        environment="prod",
        deployment_name="my-app",
        app_label="my-app",
        min_replicas=2,
        max_replicas=6,
        target_cpu_utilization=60,
        target_memory_utilization=None,
        pdb_min_available="1",
        pdb_max_unavailable="",
        backend=None,
    )
    golden = _read(GOLDEN_DIR / "k8s_hpa_pdb_expected.tf")
    assert rendered.strip() == golden.strip()
