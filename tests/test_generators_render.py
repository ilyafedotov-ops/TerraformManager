import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from jinja2 import Template


class GeneratorRenderTests(unittest.TestCase):
    def test_aws_s3_secure_transport_toggle(self) -> None:
        tpl = Template((Path("backend/generators/aws_s3_bucket.tf.j2")).read_text())
        rendered = tpl.render(
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
        self.assertIn("aws:SecureTransport", rendered)

    def test_azure_aks_private_cluster(self) -> None:
        tpl = Template((Path("backend/generators/azure_aks_cluster.tf.j2")).read_text())
        rendered = tpl.render(
            rg_name="rg",
            rg_actual_name="rg-aks",
            location="eastus2",
            environment="prod",
            cluster_name="aks-secure",
            kubernetes_version="1.29.2",
            dns_prefix="akssecure",
            node_pool_name="nodepool1",
            node_vm_size="Standard_D4s_v5",
            node_subnet_id="/subscriptions/000/resourceGroups/rg-aks/providers/Microsoft.Network/virtualNetworks/vnet/subnets/aks",
            private_cluster=True,
            enable_azure_policy=True,
            authorized_ip_ranges_literal="[]",
            node_min_count=3,
            node_desired_count=3,
            node_max_count=6,
            max_pods=110,
            service_cidr="10.2.0.0/16",
            dns_service_ip="10.2.0.10",
            docker_bridge_cidr="172.17.0.1/16",
            log_analytics_retention_days=30,
            owner_tag="platform",
            cost_center_tag="ENG",
            backend=None,
        )
        self.assertRegex(rendered, r"private_cluster_enabled\s*=\s*true")
        self.assertRegex(rendered, r"public_network_access_enabled\s*=\s*false")
        self.assertRegex(rendered, r"azure_policy\s*{\s*enabled\s*=\s*true")
        self.assertIn('category = "kube-controller-manager"', rendered)
        self.assertIn('category = "cluster-autoscaler"', rendered)

    def test_azure_storage_network_rules_toggle(self) -> None:
        tpl = Template((Path("backend/generators/azure_storage_account.tf.j2")).read_text())
        rendered = tpl.render(
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
            ip_rules_literal='["52.160.0.0/24","52.161.0.0/24"]',
            private_endpoint=None,
            backend=None,
        )
        self.assertIn("network_rules", rendered)
        self.assertIn("default_action             = \"Deny\"", rendered)

    def test_azure_storage_private_endpoint_enabled(self) -> None:
        tpl = Template((Path("backend/generators/azure_storage_account.tf.j2")).read_text())
        rendered = tpl.render(
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
            restrict_network=False,
            ip_rules_literal="[]",
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
        self.assertIn('resource "azurerm_private_endpoint"', rendered)
        self.assertIn('private_connection_resource_id = azurerm_storage_account.sa.id', rendered)
        self.assertIn('private_dns_zone_group', rendered)
        self.assertIn('output "storage_private_endpoint_id"', rendered)

    def test_aws_observability_template(self) -> None:
        tpl = Template(Path("backend/generators/aws_observability_baseline.tf.j2").read_text())
        rendered = tpl.render(
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
        self.assertIn('resource "aws_cloudtrail"', rendered)
        self.assertIn('resource "aws_config_configuration_recorder"', rendered)

    def test_aws_ecs_fargate_template(self) -> None:
        tpl = Template(Path("backend/generators/aws_ecs_fargate_service.tf.j2").read_text())
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
        rendered = tpl.render(
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
        self.assertIn('assign_public_ip = "DISABLED"', rendered)
        self.assertIn('"awslogs-group": "/aws/ecs/app-ecs-cluster/app-web-service"', rendered)
        self.assertIn("AmazonECSTaskExecutionRolePolicy", rendered)

    def test_aws_eks_irsa_template(self) -> None:
        tpl = Template(Path("backend/generators/aws_eks_irsa_service.tf.j2").read_text())
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
        rendered = tpl.render(
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
        self.assertIn('resource "kubernetes_namespace"', rendered)
        self.assertIn('"eks.amazonaws.com/role-arn"', rendered)
        self.assertIn("oidc.eks.us-east-1.amazonaws.com/id/EXAMPLE:sub", rendered)

    def test_k8s_argocd_template(self) -> None:
        tpl = Template(Path("backend/generators/k8s_argo_cd_baseline.tf.j2").read_text())
        rendered = tpl.render(
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
        self.assertIn('resource "helm_release" "argocd_release"', rendered)
        self.assertIn('chart      = "argo-cd"', rendered)
        self.assertIn('"accounts.admin.enabled"', rendered)
        self.assertIn('ingress = {', rendered)

    def test_aws_alb_template(self) -> None:
        tpl = Template(Path("backend/generators/aws_alb_waf.tf.j2").read_text())
        rendered = tpl.render(
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
        self.assertIn('resource "aws_lb_listener"', rendered)
        self.assertIn('resource "aws_wafv2_web_acl"', rendered)
        self.assertIn('access_logs {', rendered)
        self.assertIn('aws_s3_bucket.app_alb_logs', rendered)

    def test_aws_alb_template_existing_log_bucket(self) -> None:
        tpl = Template(Path("backend/generators/aws_alb_waf.tf.j2").read_text())
        rendered = tpl.render(
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
            create_log_bucket=False,
            log_bucket_name="org-shared-alb-logs",
            log_bucket_prefix="app-alb",
            log_bucket_resource_name="",
            backend=None,
        )
        self.assertRegex(rendered, r'access_logs\s*{\s*enabled = true')
        self.assertIn('bucket  = "org-shared-alb-logs"', rendered)
        self.assertNotIn('aws_s3_bucket "."', rendered)

    def test_aws_eks_template_imdsv2_disabled(self) -> None:
        tpl = Template(Path("backend/generators/aws_eks_cluster.tf.j2").read_text())
        rendered = tpl.render(
            region="us-east-1",
            environment="prod",
            cluster_name="app-eks",
            kubernetes_version="1.29",
            vpc_id="vpc-abc123",
            private_subnet_ids_literal='["subnet-1","subnet-2"]',
            allow_public_api=False,
            public_access_cidrs_literal="[]",
            kms_key_arn="",
            node_ami_type="AL2_x86_64",
            node_disk_size=50,
            capacity_type="ON_DEMAND",
            node_desired_size=3,
            node_min_size=3,
            node_max_size=6,
            instance_types_literal='["m6i.large"]',
            owner_tag="platform",
            cost_center_tag="ENG",
            enforce_imdsv2=False,
            backend=None,
        )
        self.assertNotIn("aws_launch_template", rendered)
        self.assertIn("disk_size", rendered)

    def test_aws_eks_template_imdsv2_enabled(self) -> None:
        tpl = Template(Path("backend/generators/aws_eks_cluster.tf.j2").read_text())
        rendered = tpl.render(
            region="us-east-1",
            environment="prod",
            cluster_name="app-eks",
            kubernetes_version="1.29",
            vpc_id="vpc-abc123",
            private_subnet_ids_literal='["subnet-1","subnet-2"]',
            allow_public_api=True,
            public_access_cidrs_literal='["203.0.113.0/32"]',
            kms_key_arn="arn:aws:kms:region:acct:key/example",
            node_ami_type="AL2_x86_64",
            node_disk_size=50,
            capacity_type="ON_DEMAND",
            node_desired_size=3,
            node_min_size=3,
            node_max_size=6,
            instance_types_literal='["m6i.large"]',
            owner_tag="platform",
            cost_center_tag="ENG",
            enforce_imdsv2=True,
            backend={
                "bucket": "tfstate",
                "key": "eks/app.tfstate",
                "region": "us-east-1",
                "dynamodb_table": "locks",
            },
        )
        self.assertIn('resource "aws_launch_template"', rendered)
        self.assertIn("http_tokens   = \"required\"", rendered)
        self.assertNotIn("disk_size =", rendered)
        self.assertIn("launch_template {", rendered)

    def test_azure_key_vault_template(self) -> None:
        tpl = Template(Path("backend/generators/azure_key_vault.tf.j2").read_text())
        rendered = tpl.render(
            rg_name="rg",
            rg_actual_name="rg-kv",
            location="eastus2",
            environment="prod",
            kv_name="kv",
            kv_actual_name="kv-secure",
            tenant_id="00000000-0000-0000-0000-000000000000",
            soft_delete_retention_days=90,
            ip_rules_literal='["52.160.0.0/24"]',
            vnet_id="/subscriptions/.../virtualNetworks/vnet-secure",
            subnet_id="/subscriptions/.../subnets/kv-endpoint",
            owner_tag="platform",
            cost_center_tag="ENG",
            backend=None,
        )
        self.assertRegex(rendered, r"purge_protection_enabled\s*=\s*true")
        self.assertIn("azurerm_private_endpoint", rendered)

    def test_azure_diagnostics_template(self) -> None:
        tpl = Template(Path("backend/generators/azure_diagnostics_baseline.tf.j2").read_text())
        rendered = tpl.render(
            rg_name="rg",
            rg_actual_name="rg-diag",
            location="eastus",
            environment="prod",
            law_name="law",
            law_actual_name="law-diag",
            log_retention_days=30,
            diagnostic_prefix="diag",
            targets=[{
                "name": "diag_kv",
                "id": "/subscriptions/000/resourceGroups/rg/providers/Microsoft.KeyVault/vaults/kv-secure",
                "id_is_literal": False,
                "index": 1,
                "log_categories": ["AuditEvent"],
                "metric_categories": ["AllMetrics"],
            }],
            create_storage_account=False,
            storage_name="",
            storage_actual_name="",
            health_alert=None,
            owner_tag="platform",
            cost_center_tag="ENG",
            backend=None,
        )
        self.assertIn("azurerm_monitor_diagnostic_setting", rendered)
        self.assertIn("log_analytics_workspace_id", rendered)
        self.assertIn('category = "AllMetrics"', rendered)
        self.assertIn('output "log_analytics_workspace_id"', rendered)
        self.assertIn('output "diagnostic_setting_ids"', rendered)
        self.assertIn('"diag_kv"', rendered)

    def test_azure_diagnostics_multiple_log_categories(self) -> None:
        tpl = Template(Path("backend/generators/azure_diagnostics_baseline.tf.j2").read_text())
        rendered = tpl.render(
            rg_name="rg",
            rg_actual_name="rg-diag",
            location="eastus",
            environment="prod",
            law_name="law",
            law_actual_name="law-diag",
            log_retention_days=30,
            diagnostic_prefix="diag",
            targets=[{
                "name": "diag_nsg",
                "id": "/subscriptions/000/resourceGroups/rg/providers/Microsoft.Network/networkSecurityGroups/app-nsg",
                "id_is_literal": False,
                "index": 1,
                "log_categories": ["NetworkSecurityGroupEvent", "NetworkSecurityGroupRuleCounter"],
                "metric_categories": ["AllMetrics"],
            }],
            create_storage_account=True,
            storage_name="logstorage",
            storage_actual_name="logstorageacct",
            health_alert=None,
            owner_tag="platform",
            cost_center_tag="ENG",
            backend=None,
        )
        self.assertRegex(rendered, r'category\s*=\s*"NetworkSecurityGroupEvent"')
        self.assertRegex(rendered, r'category\s*=\s*"NetworkSecurityGroupRuleCounter"')
        self.assertRegex(rendered, r"storage_account_id\s*=\s*azurerm_storage_account\.logstorage\.id")
        self.assertIn('output "diagnostics_storage_account_id"', rendered)
        self.assertIn('diagnostic_target_resource_ids', rendered)

    def test_azure_diagnostics_literal_id_target(self) -> None:
        tpl = Template(Path("backend/generators/azure_diagnostics_baseline.tf.j2").read_text())
        rendered = tpl.render(
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
            health_alert=None,
            owner_tag="platform",
            cost_center_tag="ENG",
            backend=None,
        )
        self.assertIn("target_resource_id         = azurerm_storage_account.logstorage.id", rendered)
        self.assertNotIn('"azurerm_storage_account.logstorage.id"', rendered)

    def test_azure_diagnostics_health_alert(self) -> None:
        tpl = Template(Path("backend/generators/azure_diagnostics_baseline.tf.j2").read_text())
        rendered = tpl.render(
            rg_name="rg",
            rg_actual_name="rg-diag",
            location="eastus",
            environment="prod",
            law_name="law",
            law_actual_name="law-diag",
            log_retention_days=30,
            diagnostic_prefix="diag",
            targets=[],
            create_storage_account=False,
            storage_name="",
            storage_actual_name="",
            health_alert={
                "resource_name": "law_health",
                "name": "law-ingestion-alert",
                "description": "Alert when ingestion availability drops below 99%",
                "severity": 2,
                "threshold": 99,
                "frequency": "PT5M",
                "window_size": "PT5M",
                "aggregation": "Average",
                "metric_name": "SearchServiceAvailability",
                "action_group_ids": ["/subscriptions/.../actionGroups/notify"],
            },
            owner_tag="platform",
            cost_center_tag="ENG",
            backend=None,
        )
        self.assertIn('resource "azurerm_monitor_metric_alert" "law_health"', rendered)
        self.assertIn('scopes              = [azurerm_log_analytics_workspace.law.id]', rendered)
        self.assertIn('action_group_id = "/subscriptions/.../actionGroups/notify"', rendered)
        self.assertIn('output "diagnostics_health_alert_id"', rendered)

    def test_k8s_deployment_seccomp_and_apparmor(self) -> None:
        tpl = Template(Path("backend/generators/k8s_deployment.tf.j2").read_text())
        rendered = tpl.render(
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
        self.assertIn('seccomp_profile', rendered)
        self.assertIn('type = "RuntimeDefault"', rendered)
        self.assertIn('"container.apparmor.security.beta.kubernetes.io/web" = "runtime/default"', rendered)
        self.assertRegex(rendered, r'capabilities\s*{\s*drop\s*=\s*\["ALL"\]')

    def test_k8s_psa_namespace_set(self) -> None:
        tpl = Template(Path("backend/generators/k8s_psa_namespaces.tf.j2").read_text())
        rendered = tpl.render(
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
        self.assertIn('resource "kubernetes_namespace" "apps"', rendered)
        self.assertIn('pod-security.kubernetes.io/enforce"         = "restricted"', rendered)
        self.assertIn('pod-security.kubernetes.io/warn"            = "baseline"', rendered)
        self.assertIn('pod-security.kubernetes.io/audit"           = "baseline"', rendered)
        self.assertIn('environment  = "prod"', rendered)
        self.assertIn('team         = "platform"', rendered)
        self.assertIn('team         = "payments"', rendered)

    def test_aws_rds_template(self) -> None:
        tpl = Template(Path("backend/generators/aws_rds_baseline.tf.j2").read_text())
        rendered = tpl.render(
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
            backup_window="03:00-04:00",
            preferred_maintenance_window="sun:05:00-sun:06:00",
            kms_key_id="arn:aws:kms:us-east-1:123456789012:key/example",
            owner_tag="platform",
            cost_center_tag="ENG",
            backend=None,
        )
        self.assertIn("storage_encrypted          = true", rendered)
        self.assertIn("performance_insights_enabled = true", rendered)

    def test_aws_rds_multi_region_template(self) -> None:
        tpl = Template(Path("backend/generators/aws_rds_multi_region.tf.j2").read_text())
        rendered = tpl.render(
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
            backup_window="03:00-05:00",
            replica_backup_window="03:00-05:00",
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
        self.assertIn('provider "aws" {\n  alias  = "secondary"', rendered)
        self.assertIn("replicate_source_db    = aws_db_instance.prod_app_db.id", rendered)
        self.assertIn("aws_backup_plan", rendered)
        self.assertIn("aws_backup_selection", rendered)

    def test_k8s_pod_security_template(self) -> None:
        tpl = Template(Path("backend/generators/k8s_pod_security_baseline.tf.j2").read_text())
        rendered = tpl.render(
            policy_name="psp",
            policy_actual_name="restricted",
            service_account_namespace="default",
            service_account_name="default",
            namespace_name="psp_ns",
            namespace_actual="apps",
            backend=None,
        )
        self.assertIn("kubernetes_pod_security_policy", rendered)
        self.assertIn("pod-security.kubernetes.io/enforce", rendered)

    def test_k8s_hpa_template_renders(self) -> None:
        tpl = Template((Path("backend/generators/k8s_hpa_pdb.tf.j2")).read_text())
        rendered = tpl.render(
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
        self.assertIn("kubernetes_horizontal_pod_autoscaler_v2", rendered)
        self.assertIn("kubernetes_pod_disruption_budget", rendered)

    def test_templates_optional_validate(self) -> None:
        if os.getenv("TFM_RUN_TERRAFORM_VALIDATE") != "1":
            self.skipTest("terraform validation not requested")
        if not shutil.which("terraform"):
            self.skipTest("terraform binary not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            templates = [
                ("aws_s3.tf", Template(Path("backend/generators/aws_s3_bucket.tf.j2").read_text()).render(
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
                )),
                ("azure_storage.tf", Template(Path("backend/generators/azure_storage_account.tf.j2").read_text()).render(
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
                    restrict_network=False,
                    ip_rules_literal="[]",
                    private_endpoint=None,
                    backend=None,
                )),
                ("azure_key_vault.tf", Template(Path("backend/generators/azure_key_vault.tf.j2").read_text()).render(
                    rg_name="rg",
                    rg_actual_name="rg-kv",
                    location="eastus2",
                    environment="prod",
                    kv_name="kv",
                    kv_actual_name="kv-secure",
                    tenant_id="00000000-0000-0000-0000-000000000000",
                    soft_delete_retention_days=90,
                    ip_rules_literal='["52.160.0.0/24"]',
                    vnet_id="/subscriptions/.../virtualNetworks/vnet-secure",
                    subnet_id="/subscriptions/.../subnets/kv-endpoint",
                    owner_tag="platform",
                    cost_center_tag="ENG",
                    backend=None,
                )),
                ("azure_diagnostics.tf", Template(Path("backend/generators/azure_diagnostics_baseline.tf.j2").read_text()).render(
                    rg_name="rg",
                    rg_actual_name="rg-diag",
                    location="eastus",
                    environment="prod",
                    law_name="law",
                    law_actual_name="law-diag",
                    log_retention_days=30,
                    diagnostic_prefix="diag",
                    targets=[{"name": "diag_kv", "id": "/subscriptions/000/resourceGroups/rg/providers/Microsoft.KeyVault/vaults/kv-secure", "index": 1, "default_log_category": "AuditEvent"}],
                    create_storage_account=False,
                    storage_name="",
                    storage_actual_name="",
                    health_alert=None,
                    owner_tag="platform",
                    cost_center_tag="ENG",
                    backend=None,
                )),
                ("azure_vnet.tf", Template(Path("backend/generators/azure_vnet_baseline.tf.j2").read_text()).render(
                    rg_name="rg",
                    rg_actual_name="rg-network",
                    location="eastus",
                    environment="prod",
                    name_prefix="appnet",
                    address_space="10.50.0.0/16",
                    workload_subnet_cidr="10.50.1.0/24",
                    bastion_subnet_cidr="10.50.10.0/27",
                    allowed_management_cidr="10.0.0.0/24",
                    log_analytics_retention_days=30,
                    flow_log_retention_days=90,
                    owner_tag="platform",
                    cost_center_tag="ENG",
                    backend=None,
                )),
                ("aws_vpc.tf", Template(Path("backend/generators/aws_vpc_networking.tf.j2").read_text()).render(
                    region="us-east-1",
                    environment="prod",
                    name_prefix="app",
                    vpc_cidr="10.60.0.0/16",
                    vpc_name="vpc",
                    private_subnet_name="subnet",
                    public_subnet_cidr="10.60.0.0/24",
                    private_subnet_cidr="10.60.1.0/24",
                    public_subnet_az="us-east-1a",
                    private_subnet_az="us-east-1b",
                    owner_tag="platform",
                    cost_center_tag="ENG",
                    flow_logs_retention_days=60,
                    backend=None,
                )),
                ("k8s_namespace.tf", Template(Path("backend/generators/k8s_namespace_baseline.tf.j2").read_text()).render(
                    namespace_name="ns",
                    namespace_actual="apps",
                    environment="prod",
                    team_label="platform",
                    quota_pods="50",
                    quota_limits_cpu="40",
                    quota_limits_memory="160Gi",
                    quota_requests_cpu="20",
                    quota_requests_memory="80Gi",
                    limit_max_cpu="4",
                    limit_max_memory="8Gi",
                    limit_min_cpu="100m",
                    limit_min_memory="128Mi",
                    limit_default_cpu="500m",
                    limit_default_memory="512Mi",
                    limit_default_request_cpu="250m",
                    limit_default_request_memory="256Mi",
                    backend=None,
                )),
                ("aws_observability.tf", Template(Path("backend/generators/aws_observability_baseline.tf.j2").read_text()).render(
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
                )),
                ("aws_alb.tf", Template(Path("backend/generators/aws_alb_waf.tf.j2").read_text()).render(
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
                    backend=None,
                )),
                ("aws_rds.tf", Template(Path("backend/generators/aws_rds_baseline.tf.j2").read_text()).render(
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
                    backup_window="03:00-04:00",
                    preferred_maintenance_window="sun:05:00-sun:06:00",
                    kms_key_id="arn:aws:kms:us-east-1:123456789012:key/example",
                    owner_tag="platform",
                    cost_center_tag="ENG",
                    backend=None,
                )),
                ("k8s_pod_security.tf", Template(Path("backend/generators/k8s_pod_security_baseline.tf.j2").read_text()).render(
                    policy_name="psp",
                    policy_actual_name="restricted",
                    service_account_namespace="default",
                    service_account_name="default",
                    namespace_name="psp_ns",
                    namespace_actual="apps",
                    backend=None,
                )),
                ("aws_eks.tf", Template(Path("backend/generators/aws_eks_cluster.tf.j2").read_text()).render(
                    region="us-east-1",
                    environment="prod",
                    cluster_name="eks-secure",
                    kubernetes_version="1.29",
                    vpc_id="vpc-123456",
                    private_subnet_ids_literal='["subnet-111","subnet-222"]',
                    allow_public_api=False,
                    public_access_cidrs_literal="[]",
                    kms_key_arn="",
                    node_ami_type="AL2_x86_64",
                    node_disk_size=50,
                    capacity_type="ON_DEMAND",
                    node_desired_size=3,
                    node_min_size=3,
                    node_max_size=6,
                    instance_types_literal='["m6i.large"]',
                    owner_tag="platform",
                    cost_center_tag="ENG",
                    backend=None,
                )),
                ("azure_aks.tf", Template(Path("backend/generators/azure_aks_cluster.tf.j2").read_text()).render(
                    rg_name="rg",
                    rg_actual_name="rg-aks",
                    location="eastus2",
                    environment="prod",
                    cluster_name="aks-secure",
                    kubernetes_version="1.29.2",
                    dns_prefix="akssecure",
                    node_pool_name="nodepool1",
                    node_vm_size="Standard_D4s_v5",
                    node_subnet_id="/subscriptions/000/resourceGroups/rg-aks/providers/Microsoft.Network/virtualNetworks/vnet/subnets/aks",
                    private_cluster=True,
                    enable_azure_policy=True,
                    authorized_ip_ranges_literal="[]",
                    node_min_count=3,
                    node_desired_count=3,
                    node_max_count=6,
                    max_pods=110,
                    service_cidr="10.2.0.0/16",
                    dns_service_ip="10.2.0.10",
                    docker_bridge_cidr="172.17.0.1/16",
                    log_analytics_retention_days=30,
                    owner_tag="platform",
                    cost_center_tag="ENG",
                    backend=None,
                )),
            ]
            for filename, contents in templates:
                (tmp / filename).write_text(contents)
            subprocess.run(["terraform", "init", "-backend=false", "-input=false", "-no-color"], cwd=tmp, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            proc = subprocess.run(["terraform", "validate", "-no-color"], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            self.assertEqual(proc.returncode, 0, proc.stdout)


if __name__ == "__main__":
    unittest.main()
