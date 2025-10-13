import textwrap
import unittest
from pathlib import Path

import backend.policies.aws
from backend.policies.aws import (
    check_s3_sse,
    check_vpc_flow_logs,
    check_s3_secure_transport,
    check_s3_access_logging,
    check_s3_account_public_block,
    check_rds_encryption,
    check_rds_backup_retention,
    check_rds_deletion_protection,
    check_rds_enhanced_monitoring,
    check_rds_performance_insights,
    check_backup_plan_copy_action,
    check_alb_https,
    check_waf_association,
    check_alb_access_logging,
    check_eks_imdsv2,
    check_eks_control_plane_logging,
    check_ecs_public_ip,
    check_eks_irsa_trust,
    check_cloudwatch_log_retention,
    check_backend_s3_encryption,
)
from backend.policies.azure import (
    check_storage_https,
    check_storage_private_endpoint,
    check_log_analytics_health_alert,
    check_nsg_flow_logs,
    check_aks_private_cluster,
    check_aks_azure_policy,
    check_aks_diagnostic_categories,
    check_key_vault_purge_protection,
    check_key_vault_network,
    check_diagnostic_settings,
    check_backend_azurerm_state,
)
from backend.policies.k8s import (
    check_image_not_latest,
    check_run_as_non_root,
    check_resources_limits,
    check_seccomp_profile,
    check_apparmor_profile,
    check_namespace_network_policy,
    check_pdb_for_deployments,
    check_privileged_containers,
    check_hostpath_volumes,
)


class PolicyRuleTests(unittest.TestCase):
    def test_aws_s3_sse_rule_flags_missing_encryption(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_s3_bucket" "critical" {
              bucket = "example"
            }
            """
        )
        path = Path("insecure_aws.tf")
        findings = check_s3_sse(path, text)
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding["rule_id"], "AWS-S3-SSE")
        self.assertEqual(finding["context"]["resource"], "critical")
        self.assertIn("aws_s3_bucket_server_side_encryption_configuration", finding["suggested_fix_snippet"])

    def test_azure_storage_https_enforced(self) -> None:
        text = textwrap.dedent(
            """
            resource "azurerm_storage_account" "bad" {
              name = "stbad"
              enable_https_traffic_only = false
            }
            """
        )
        path = Path("insecure_azure.tf")
        findings = check_storage_https(path, text)
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding["rule_id"], "AZ-STORAGE-HTTPS")
        self.assertEqual(finding["context"]["resource"], "bad")
        self.assertIn("enable_https_traffic_only = true", finding["suggested_fix_snippet"])

    def test_azure_storage_private_endpoint_missing(self) -> None:
        text = textwrap.dedent(
            """
            resource "azurerm_storage_account" "secure" {
              name = "stsecure"
              enable_https_traffic_only = true
            }
            """
        )
        findings = check_storage_private_endpoint(Path("azure.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "AZ-STORAGE-PRIVATE-ENDPOINT")
        self.assertEqual(findings[0]["context"]["resource"], "secure")

    def test_azure_storage_private_endpoint_present(self) -> None:
        text = textwrap.dedent(
            """
            resource "azurerm_storage_account" "secure" {
              name = "stsecure"
            }

            resource "azurerm_private_endpoint" "pe" {
              private_service_connection {
                private_connection_resource_id = azurerm_storage_account.secure.id
              }
            }
            """
        )
        findings = check_storage_private_endpoint(Path("azure.tf"), text)
        self.assertEqual(len(findings), 0)

    def test_backend_s3_missing_encryption(self) -> None:
        text = textwrap.dedent(
            """
            terraform {
              backend "s3" {
                bucket = "example-state"
                key    = "env/terraform.tfstate"
              }
            }
            """
        )
        findings = check_backend_s3_encryption(Path("backend.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "TF-BACKEND-S3-ENCRYPT")
        self.assertIn("encrypt", findings[0]["context"]["missing"])

    def test_backend_s3_with_encryption_and_locking(self) -> None:
        text = textwrap.dedent(
            """
            terraform {
              backend "s3" {
                bucket         = "example-state"
                key            = "env/terraform.tfstate"
                region         = "us-east-1"
                encrypt        = true
                dynamodb_table = "terraform-locks"
              }
            }
            """
        )
        findings = check_backend_s3_encryption(Path("backend.tf"), text)
        self.assertEqual(len(findings), 0)

    def test_backend_azurerm_missing_fields(self) -> None:
        text = textwrap.dedent(
            """
            terraform {
              backend "azurerm" {
                resource_group_name = "rg"
              }
            }
            """
        )
        findings = check_backend_azurerm_state(Path("backend.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "TF-BACKEND-AZURE-STATE")
        self.assertIn("storage_account_name", findings[0]["context"]["missing"])

    def test_backend_azurerm_complete(self) -> None:
        text = textwrap.dedent(
            """
            terraform {
              backend "azurerm" {
                resource_group_name  = "rg-state"
                storage_account_name = "ststate0001"
                container_name       = "tfstate"
                key                  = "env/app.tfstate"
              }
            }
            """
        )
        findings = check_backend_azurerm_state(Path("backend.tf"), text)
        self.assertEqual(len(findings), 0)

    def test_cloudwatch_log_group_retention_missing(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_cloudwatch_log_group" "lg" {
              name = "/aws/lambda/app"
            }
            """
        )
        findings = check_cloudwatch_log_retention(Path("cloudwatch.tf"), text)
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding["rule_id"], "AWS-CW-LOG-RETENTION")
        self.assertEqual(finding["context"]["resource"], "lg")

    def test_cloudwatch_log_group_retention_present(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_cloudwatch_log_group" "lg" {
              name              = "/aws/lambda/app"
              retention_in_days = 30
            }
            """
        )
        findings = check_cloudwatch_log_retention(Path("cloudwatch.tf"), text)
        self.assertEqual(len(findings), 0)

    def test_log_analytics_health_alert_missing(self) -> None:
        text = textwrap.dedent(
            """
            resource "azurerm_log_analytics_workspace" "law" {
              name                = "law"
              resource_group_name = "rg"
              location            = "eastus"
              sku                 = "PerGB2018"
            }
            """
        )
        findings = check_log_analytics_health_alert(Path("azure.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "AZ-LAW-HEALTH-ALERT")
        self.assertEqual(findings[0]["context"]["resource"], "law")

    def test_log_analytics_health_alert_present(self) -> None:
        text = textwrap.dedent(
            """
            resource "azurerm_log_analytics_workspace" "law" {
              name                = "law"
              resource_group_name = "rg"
              location            = "eastus"
              sku                 = "PerGB2018"
            }

            resource "azurerm_monitor_metric_alert" "law_health" {
              name                = "law-health"
              resource_group_name = "rg"
              scopes              = [azurerm_log_analytics_workspace.law.id]
              frequency           = "PT5M"
              window_size         = "PT5M"
              criteria {
                metric_namespace = "microsoft.operationalinsights/workspaces"
                metric_name      = "SearchServiceAvailability"
                aggregation      = "Average"
                operator         = "LessThan"
                threshold        = 99
              }
            }
            """
        )
        findings = check_log_analytics_health_alert(Path("azure.tf"), text)
        self.assertEqual(len(findings), 0)

    def test_azure_aks_policy_disabled(self) -> None:
        text = textwrap.dedent(
            """
            resource "azurerm_kubernetes_cluster" "aks" {
              name = "aks"
              addon_profile {
                azure_policy {
                  enabled = false
                }
              }
            }
            """
        )
        findings = check_aks_azure_policy(Path("azure.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "AZ-AKS-AZURE-POLICY")

    def test_azure_aks_policy_enabled(self) -> None:
        text = textwrap.dedent(
            """
            resource "azurerm_kubernetes_cluster" "aks" {
              name = "aks"
              addon_profile {
                azure_policy {
                  enabled = true
                }
              }
            }
            """
        )
        findings = check_aks_azure_policy(Path("azure.tf"), text)
        self.assertEqual(len(findings), 0)

    def test_azure_aks_diagnostics_missing_categories(self) -> None:
        text = textwrap.dedent(
            """
            resource "azurerm_kubernetes_cluster" "aks" {
              name = "aks"
            }

            resource "azurerm_monitor_diagnostic_setting" "aks_diag" {
              name               = "aks-diag"
              target_resource_id = azurerm_kubernetes_cluster.aks.id
              log_analytics_workspace_id = azurerm_log_analytics_workspace.law.id
              log {
                category = "kube-apiserver"
                enabled  = true
              }
            }
            """
        )
        findings = check_aks_diagnostic_categories(Path("azure.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "AZ-AKS-DIAGNOSTICS")
        self.assertIn("missing_categories", findings[0]["context"])

    def test_azure_aks_diagnostics_complete(self) -> None:
        text = textwrap.dedent(
            """
            resource "azurerm_kubernetes_cluster" "aks" {
              name = "aks"
            }

            resource "azurerm_monitor_diagnostic_setting" "aks_diag" {
              name               = "aks-diag"
              target_resource_id = azurerm_kubernetes_cluster.aks.id
              log_analytics_workspace_id = azurerm_log_analytics_workspace.law.id
              log { category = "kube-apiserver"        enabled = true }
              log { category = "kube-audit"            enabled = true }
              log { category = "kube-audit-admin"      enabled = true }
              log { category = "kube-controller-manager" enabled = true }
              log { category = "kube-scheduler"        enabled = true }
              log { category = "cluster-autoscaler"    enabled = true }
              log { category = "guard"                 enabled = true }
            }
            """
        )
        findings = check_aks_diagnostic_categories(Path("azure.tf"), text)
        self.assertEqual(len(findings), 0)

    def test_k8s_latest_image_detected(self) -> None:
        text = textwrap.dedent(
            """
            resource "kubernetes_deployment" "web" {
              metadata {
                name = "web"
              }
              spec {
                template {
                  spec {
                    container {
                      name  = "web"
                      image = "nginx:latest"
                    }
                  }
                }
              }
            }
            """
        )
        findings = check_image_not_latest(Path("insecure_k8s.tf"), text)
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding["rule_id"], "K8S-IMAGE-NO-LATEST")
        self.assertEqual(finding["context"]["image"], "nginx:latest")
        self.assertIn(":1.0.0", finding["suggested_fix_snippet"])

    def test_k8s_run_as_non_root_missing_daemonset(self) -> None:
        text = textwrap.dedent(
            """
            resource "kubernetes_daemonset" "agent" {
              metadata { name = "agent" }
              spec {
                template {
                  spec {
                    container {
                      name  = "agent"
                      image = "org/agent:1.2.3"
                    }
                  }
                }
              }
            }
            """
        )
        findings = check_run_as_non_root(Path("k8s.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["context"]["resource"], "daemonset.agent")

    def test_k8s_run_as_non_root_present_statefulset(self) -> None:
        text = textwrap.dedent(
            """
            resource "kubernetes_stateful_set" "db" {
              metadata { name = "db" }
              spec {
                selector { match_labels = { app = "db" } }
                service_name = "db"
                template {
                  metadata { labels = { app = "db" } }
                  spec {
                    container {
                      name  = "db"
                      image = "postgres:15"
                      security_context {
                        run_as_non_root           = true
                        read_only_root_filesystem = true
                      }
                    }
                  }
                }
              }
            }
            """
        )
        findings = check_run_as_non_root(Path("k8s.tf"), text)
        self.assertEqual(len(findings), 0)

    def test_k8s_resources_limits_missing(self) -> None:
        text = textwrap.dedent(
            """
            resource "kubernetes_pod" "tool" {
              metadata { name = "tool" }
              spec {
                container {
                  name  = "tool"
                  image = "busybox"
                }
              }
            }
            """
        )
        findings = check_resources_limits(Path("k8s.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["context"]["resource"], "pod.tool")

    def test_k8s_resources_limits_present(self) -> None:
        text = textwrap.dedent(
            """
            resource "kubernetes_deployment" "svc" {
              metadata { name = "svc" }
              spec {
                template {
                  spec {
                    container {
                      name  = "svc"
                      image = "nginx:1.25"
                      resources {
                        limits   = { cpu = "500m", memory = "256Mi" }
                        requests = { cpu = "250m", memory = "128Mi" }
                      }
                    }
                  }
                }
              }
            }
            """
        )
        findings = check_resources_limits(Path("k8s.tf"), text)
        self.assertEqual(len(findings), 0)

    def test_k8s_seccomp_missing(self) -> None:
        text = textwrap.dedent(
            """
            resource "kubernetes_deployment" "svc" {
              metadata { name = "svc" }
              spec {
                template {
                  spec {
                    container {
                      name  = "svc"
                      image = "nginx:1.25"
                      security_context {
                        run_as_non_root = true
                      }
                    }
                  }
                }
              }
            }
            """
        )
        findings = check_seccomp_profile(Path("k8s.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "K8S-POD-SECCOMP")

    def test_k8s_seccomp_present(self) -> None:
        text = textwrap.dedent(
            """
            resource "kubernetes_deployment" "svc" {
              metadata { name = "svc" }
              spec {
                template {
                  spec {
                    container {
                      name  = "svc"
                      image = "nginx:1.25"
                      security_context {
                        seccomp_profile {
                          type = "RuntimeDefault"
                        }
                      }
                    }
                  }
                }
              }
            }
            """
        )
        findings = check_seccomp_profile(Path("k8s.tf"), text)
        self.assertEqual(len(findings), 0)

    def test_k8s_apparmor_missing(self) -> None:
        text = textwrap.dedent(
            """
            resource "kubernetes_deployment" "svc" {
              metadata {
                name = "svc"
              }
              spec {
                template {
                  metadata { labels = { app = "svc" } }
                  spec {
                    container {
                      name  = "svc"
                      image = "nginx:1.25"
                    }
                  }
                }
              }
            }
            """
        )
        findings = check_apparmor_profile(Path("k8s.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "K8S-POD-APPARMOR")

    def test_k8s_apparmor_present(self) -> None:
        text = textwrap.dedent(
            """
            resource "kubernetes_deployment" "svc" {
              metadata {
                name = "svc"
                annotations = {
                  "container.apparmor.security.beta.kubernetes.io/svc" = "runtime/default"
                }
              }
              spec {
                template {
                  metadata { labels = { app = "svc" } }
                  spec {
                    container {
                      name  = "svc"
                      image = "nginx:1.25"
                    }
                  }
                }
              }
            }
            """
        )
        findings = check_apparmor_profile(Path("k8s.tf"), text)
        self.assertEqual(len(findings), 0)

    def test_ecs_public_ip_enabled(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_ecs_service" "web" {
              name         = "web"
              cluster      = aws_ecs_cluster.app.id
              launch_type  = "FARGATE"
              network_configuration {
                subnets         = ["subnet-1"]
                security_groups = ["sg-123"]
                assign_public_ip = "ENABLED"
              }
            }
            """
        )
        findings = check_ecs_public_ip(Path("ecs.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "AWS-ECS-PUBLIC-IP")
        self.assertIn("assign_public_ip", findings[0]["snippet"])

    def test_ecs_public_ip_disabled(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_ecs_service" "web" {
              name         = "web"
              cluster      = aws_ecs_cluster.app.id
              launch_type  = "FARGATE"
              network_configuration {
                subnets         = ["subnet-1"]
                security_groups = ["sg-123"]
                assign_public_ip = "DISABLED"
              }
            }
            """
        )
        findings = check_ecs_public_ip(Path("ecs.tf"), text)
        self.assertEqual(len(findings), 0)

    def test_eks_irsa_trust_missing_conditions(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_iam_role" "irsa" {
              name = "app-irsa-role"
              assume_role_policy = jsonencode({
                Version = "2012-10-17"
                Statement = [{
                  Effect = "Allow"
                  Principal = {
                    Federated = "arn:aws:iam::123456789012:oidc-provider/oidc.eks.us-east-1.amazonaws.com/id/EXAMPLE"
                  }
                  Action = "sts:AssumeRoleWithWebIdentity"
                }]
              })
            }
            """
        )
        findings = check_eks_irsa_trust(Path("irsa.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "AWS-EKS-IRSA-TRUST")
        self.assertIn("missing", findings[0]["context"])

    def test_eks_irsa_trust_with_sub_and_aud(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_iam_role" "irsa" {
              name = "app-irsa-role"
              assume_role_policy = jsonencode({
                Version = "2012-10-17"
                Statement = [{
                  Effect = "Allow"
                  Principal = {
                    Federated = "arn:aws:iam::123456789012:oidc-provider/oidc.eks.us-east-1.amazonaws.com/id/EXAMPLE"
                  }
                  Action = "sts:AssumeRoleWithWebIdentity"
                  Condition = {
                    "StringEquals" = {
                      "oidc.eks.us-east-1.amazonaws.com/id/EXAMPLE:sub" = "system:serviceaccount:app:app-sa"
                    }
                    "StringLike" = {
                      "oidc.eks.us-east-1.amazonaws.com/id/EXAMPLE:aud" = "sts.amazonaws.com"
                    }
                  }
                }]
              })
            }
            """
        )
        findings = check_eks_irsa_trust(Path("irsa.tf"), text)
        self.assertEqual(len(findings), 0)


    def test_stateful_set_missing_controls(self) -> None:
        text = textwrap.dedent(
            """
            resource "kubernetes_stateful_set" "db" {
              metadata { name = "db" }
              spec {
                service_name = "db"
                selector { match_labels = { app = "db" } }
                template {
                  metadata { labels = { app = "db" } }
                  spec {
                    container {
                      name  = "db"
                      image = "postgres:15"
                    }
                  }
                }
              }
            }
            """
        )
        findings = check_run_as_non_root(Path("k8s.tf"), text)
        run_non_root_ids = {f["context"]["resource"] for f in findings}
        self.assertIn("stateful_set.db", run_non_root_ids)

        findings = check_resources_limits(Path("k8s.tf"), text)
        self.assertTrue(any(f["context"]["resource"] == "stateful_set.db" for f in findings))

        findings = check_seccomp_profile(Path("k8s.tf"), text)
        self.assertTrue(any(f["context"]["resource"] == "stateful_set.db" for f in findings))

        findings = check_apparmor_profile(Path("k8s.tf"), text)
        self.assertTrue(any(f["context"]["resource"] == "stateful_set.db" for f in findings))

    def test_daemonset_missing_controls(self) -> None:
        text = textwrap.dedent(
            """
            resource "kubernetes_daemonset" "agent" {
              metadata { name = "agent" }
              spec {
                selector { match_labels = { app = "agent" } }
                template {
                  metadata { labels = { app = "agent" } }
                  spec {
                    container {
                      name  = "agent"
                      image = "busybox:1.36"
                      security_context {
                        run_as_non_root = false
                      }
                    }
                  }
                }
              }
            }
            """
        )
        findings = check_run_as_non_root(Path("k8s.tf"), text)
        self.assertTrue(any(f["context"]["resource"] == "daemonset.agent" for f in findings))

        findings = check_seccomp_profile(Path("k8s.tf"), text)
        self.assertTrue(any(f["context"]["resource"] == "daemonset.agent" for f in findings))

        findings = check_apparmor_profile(Path("k8s.tf"), text)
        self.assertTrue(any(f["context"]["resource"] == "daemonset.agent" for f in findings))

        findings = check_resources_limits(Path("k8s.tf"), text)
        self.assertTrue(any(f["context"]["resource"] == "daemonset.agent" for f in findings))
    def test_aws_vpc_missing_flow_logs(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_vpc" "main" {
              cidr_block = "10.0.0.0/16"
            }
            """
        )
        findings = check_vpc_flow_logs(Path("network.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "AWS-VPC-FLOW-LOGS")

    def test_azure_nsg_missing_flow_logs(self) -> None:
        text = textwrap.dedent(
            """
            resource "azurerm_network_security_group" "nsg" {
              name = "app-nsg"
              location = "eastus"
              resource_group_name = "rg"
            }
            """
        )
        findings = check_nsg_flow_logs(Path("network.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "AZ-NET-FLOW-LOGS")

    def test_k8s_namespace_without_network_policy(self) -> None:
        text = textwrap.dedent(
            """
            resource "kubernetes_namespace" "app" {
              metadata { name = "app" }
            }
            """
        )
        findings = check_namespace_network_policy(Path("k8s.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "K8S-NAMESPACE-NETPOL")

    def test_k8s_privileged_containers_flagged(self) -> None:
        text = textwrap.dedent(
            """
            resource "kubernetes_daemonset" "ds" {
              metadata { name = "ds" }
              spec {
                template {
                  spec {
                    container {
                      name = "agent"
                      security_context {
                        privileged = true
                      }
                    }
                  }
                }
              }
            }
            """
        )
        findings = check_privileged_containers(Path("k8s.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "K8S-POD-PRIVILEGED")

    def test_k8s_hostpath_volume_flagged(self) -> None:
        text = textwrap.dedent(
            """
            resource "kubernetes_pod" "pod" {
              metadata { name = "tooling" }
              spec {
                container {
                  name  = "tool"
                  image = "busybox"
                }
                volume {
                  name = "host"
                  host_path {
                    path = "/var/log"
                  }
                }
              }
            }
            """
        )
        findings = check_hostpath_volumes(Path("k8s.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "K8S-POD-HOSTPATH")

    def test_s3_missing_secure_transport_policy(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_s3_bucket" "secure" {
              bucket = "my-bucket"
            }
            """
        )
        findings = check_s3_secure_transport(Path("s3.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "AWS-S3-SECURE-TRANSPORT")

    def test_s3_access_logging_missing(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_s3_bucket" "app" {
              bucket = "my-app"
            }
            """
        )
        findings = check_s3_access_logging(Path("s3.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "AWS-S3-ACCESS-LOGGING")

    def test_s3_access_logging_inline_present(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_s3_bucket" "app" {
              bucket = "my-app"
              logging {
                target_bucket = "logs"
                target_prefix = "app/"
              }
            }
            """
        )
        findings = check_s3_access_logging(Path("s3.tf"), text)
        self.assertEqual(len(findings), 0)

    def test_s3_account_public_block_missing(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_s3_bucket" "app" {
              bucket = "my-app"
            }
            """
        )
        findings = check_s3_account_public_block(Path("s3.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "AWS-S3-ACCOUNT-BLOCK")

    def test_s3_account_public_block_flags(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_s3_account_public_access_block" "bad" {
              block_public_acls  = true
              ignore_public_acls = false
            }
            """
        )
        findings = check_s3_account_public_block(Path("s3.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertIn("ignore_public_acls", findings[0]["context"]["missing_flags"])

    def test_rds_encryption_required(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_db_instance" "db" {
              identifier = "prod-db"
              engine = "postgres"
              storage_encrypted = false
            }
            """
        )
        findings = check_rds_encryption(Path("rds.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "AWS-RDS-ENCRYPTION")

    def test_rds_backup_retention(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_db_instance" "db" {
              identifier = "prod-db"
              engine = "postgres"
              storage_encrypted = true
              backup_retention_period = 1
            }
            """
        )
        findings = check_rds_backup_retention(Path("rds.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "AWS-RDS-BACKUP")

    def test_rds_deletion_protection_required(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_db_instance" "db" {
              identifier = "prod-db"
              engine     = "postgres"
              storage_encrypted = true
              deletion_protection = false
            }
            """
        )
        findings = check_rds_deletion_protection(Path("rds.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "AWS-RDS-DELETION-PROTECTION")

    def test_rds_deletion_protection_ok(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_db_instance" "db" {
              identifier = "prod-db"
              engine     = "postgres"
              deletion_protection = true
            }
            """
        )
        findings = check_rds_deletion_protection(Path("rds.tf"), text)
        self.assertEqual(len(findings), 0)

    def test_rds_enhanced_monitoring_missing(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_db_instance" "db" {
              identifier = "prod-db"
              engine     = "postgres"
            }
            """
        )
        findings = check_rds_enhanced_monitoring(Path("rds.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "AWS-RDS-ENHANCED-MONITORING")

    def test_rds_enhanced_monitoring_present(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_db_instance" "db" {
              identifier = "prod-db"
              engine     = "postgres"
              monitoring_interval = 60
            }
            """
        )
        findings = check_rds_enhanced_monitoring(Path("rds.tf"), text)
        self.assertEqual(len(findings), 0)

    def test_rds_performance_insights(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_db_instance" "db" {
              identifier = "prod-db"
              storage_encrypted = true
            }
            """
        )
        findings = check_rds_performance_insights(Path("rds.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "AWS-RDS-PERF-INSIGHTS")

    def test_backup_plan_missing_copy_action(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_backup_plan" "plan" {
              name = "plan"
              rule {
                rule_name = "daily"
                schedule  = "cron(0 7 * * ? *)"
                target_vault_name = "primary"
              }
            }
            """
        )
        findings = check_backup_plan_copy_action(Path("backup.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "AWS-BACKUP-CROSS-REGION")
        self.assertEqual(findings[0]["context"]["resource"], "plan")

    def test_backup_plan_with_copy_action(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_backup_plan" "plan" {
              name = "plan"
              rule {
                rule_name = "daily"
                schedule  = "cron(0 7 * * ? *)"
                target_vault_name = "primary"
                copy_action {
                  destination_vault_arn = aws_backup_vault.replica.arn
                }
              }
            }
            """
        )
        findings = check_backup_plan_copy_action(Path("backup.tf"), text)
        self.assertEqual(len(findings), 0)

    def test_alb_https_listener_requirements(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_lb_listener" "http" {
              protocol = "HTTP"
            }
            """
        )
        findings = check_alb_https(Path("alb.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "AWS-ALB-HTTPS")

    def test_alb_access_logging_missing(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_lb" "alb" {
              load_balancer_type = "application"
            }
            """
        )
        findings = check_alb_access_logging(Path("alb.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "AWS-ALB-ACCESS-LOGS")

    def test_alb_access_logging_present(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_lb" "alb" {
              load_balancer_type = "application"
              access_logs {
                enabled = true
                bucket  = "logs"
                prefix  = "alb"
              }
            }
            """
        )
        findings = check_alb_access_logging(Path("alb.tf"), text)
        self.assertEqual(len(findings), 0)

    def test_eks_imdsv2_missing_launch_template(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_eks_node_group" "ng" {
              cluster_name    = "eks"
              node_group_name = "eks-ng"
            }
            """
        )
        findings = check_eks_imdsv2(Path("eks.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "AWS-EKS-IMDSV2")

    def test_eks_imdsv2_enforced(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_launch_template" "eks_ng_lt" {
              name_prefix = "eks-ng-"
              metadata_options {
                http_tokens = "required"
              }
            }

            resource "aws_eks_node_group" "ng" {
              cluster_name    = "eks"
              node_group_name = "eks-ng"
              launch_template {
                name = aws_launch_template.eks_ng_lt.name
              }
            }
            """
        )
        findings = check_eks_imdsv2(Path("eks.tf"), text)
        self.assertEqual(len(findings), 0)

    def test_eks_control_plane_logging_missing(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_eks_cluster" "eks" {
              name = "eks"
            }
            """
        )
        findings = check_eks_control_plane_logging(Path("eks.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "AWS-EKS-CONTROL-LOGS")

    def test_eks_control_plane_logging_partial(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_eks_cluster" "eks" {
              name = "eks"
              enabled_cluster_log_types = ["api", "audit"]
            }
            """
        )
        findings = check_eks_control_plane_logging(Path("eks.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertIn("controllerManager", findings[0]["context"]["missing_logs"])

    def test_eks_control_plane_logging_complete(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_eks_cluster" "eks" {
              name = "eks"
              enabled_cluster_log_types = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
            }
            """
        )
        findings = check_eks_control_plane_logging(Path("eks.tf"), text)
        self.assertEqual(len(findings), 0)

    def test_waf_association_required(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_lb" "alb" {}
            """
        )
        findings = check_waf_association(Path("alb.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "AWS-WAF-ASSOCIATION")

    def test_cloudtrail_not_multi_region(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_cloudtrail" "trail" {
              name = "org-trail"
              is_multi_region_trail = false
              enable_log_file_validation = false
            }
            """
        )
        findings = backend.policies.aws.check_cloudtrail_multi_region(Path("trail.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "AWS-CLOUDTRAIL-MULTI-REGION")

    def test_config_recorder_missing_flags(self) -> None:
        text = textwrap.dedent(
            """
            resource "aws_config_configuration_recorder" "recorder" {
              name = "default"
              role_arn = "arn:aws:iam::123456789012:role/config-role"
              recording_group {
                all_supported = false
                include_global_resource_types = false
              }
            }
            """
        )
        findings = backend.policies.aws.check_config_recorder(Path("config.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "AWS-CONFIG-RECORDER")

    def test_aks_public_api_flagged(self) -> None:
        text = textwrap.dedent(
            """
            resource "azurerm_kubernetes_cluster" "aks" {
              name = "aks"
              private_cluster_enabled = false
              public_network_access_enabled = true
            }
            """
        )
        findings = check_aks_private_cluster(Path("aks.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "AZ-AKS-PRIVATE-API")

    def test_k8s_deployment_requires_pdb(self) -> None:
        text = textwrap.dedent(
            """
            resource "kubernetes_deployment" "web" {
              metadata { labels = { app = "web" } }
              spec { replicas = 3 template { metadata { labels = { app = "web" } } } }
            }
            """
        )
        findings = check_pdb_for_deployments(Path("k8s.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "K8S-PDB-REQUIRED")

    def test_key_vault_purge_protection_missing(self) -> None:
        text = textwrap.dedent(
            """
            resource "azurerm_key_vault" "kv" {
              name = "kv"
              purge_protection_enabled = false
              soft_delete_enabled = false
            }
            """
        )
        findings = check_key_vault_purge_protection(Path("kv.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "AZ-KV-PURGE-PROTECTION")

    def test_key_vault_public_network_access_flagged(self) -> None:
        text = textwrap.dedent(
            """
            resource "azurerm_key_vault" "kv" {
              name = "kv"
              public_network_access_enabled = true
            }
            """
        )
        findings = check_key_vault_network(Path("kv.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "AZ-KV-NETWORK")

    def test_diagnostic_settings_missing(self) -> None:
        text = textwrap.dedent(
            """
            resource "azurerm_key_vault" "kv" {
              name = "kv"
            }
            """
        )
        findings = check_diagnostic_settings(Path("diag.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule_id"], "AZ-DIAGNOSTICS-MISSING")

    def test_diagnostic_settings_present(self) -> None:
        text = textwrap.dedent(
            """
            resource "azurerm_key_vault" "kv" {
              name = "kv"
            }

            resource "azurerm_monitor_diagnostic_setting" "kv_diag" {
              name                       = "kv-diag"
              target_resource_id         = azurerm_key_vault.kv.id
              log_analytics_workspace_id = "/subscriptions/.../resourceGroups/rg/providers/Microsoft.OperationalInsights/workspaces/law"
            }
            """
        )
        findings = check_diagnostic_settings(Path("diag.tf"), text)
        self.assertEqual(len(findings), 0)

    def test_diagnostic_settings_storage_literal_ref(self) -> None:
        text = textwrap.dedent(
            """
            resource "azurerm_storage_account" "log" {
              name                     = "log"
              resource_group_name      = "rg"
              location                 = "eastus"
              account_tier             = "Standard"
              account_replication_type = "LRS"
            }

            resource "azurerm_monitor_diagnostic_setting" "log_diag" {
              name                       = "log-diag"
              target_resource_id         = azurerm_storage_account.log.id
              log_analytics_workspace_id = "/subscriptions/.../resourceGroups/rg/providers/Microsoft.OperationalInsights/workspaces/law"
            }
            """
        )
        findings = check_diagnostic_settings(Path("diag.tf"), text)
        self.assertEqual(len(findings), 0)

    def test_diagnostic_settings_existing_storage_string(self) -> None:
        text = textwrap.dedent(
            """
            resource "azurerm_monitor_diagnostic_setting" "storage_shared" {
              name                       = "diag-storage"
              target_resource_id         = "/subscriptions/000/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/sharedlogs"
              log_analytics_workspace_id = "/subscriptions/000/resourceGroups/rg/providers/Microsoft.OperationalInsights/workspaces/law"
              enabled_log {
                category = "StorageRead"
              }
              enabled_metric {
                category = "AllMetrics"
              }
            }
            """
        )
        findings = check_diagnostic_settings(Path("diag.tf"), text)
        self.assertEqual(len(findings), 0)

    def test_diagnostic_settings_nsg_missing(self) -> None:
        text = textwrap.dedent(
            """
            resource "azurerm_network_security_group" "nsg" {
              name = "nsg"
            }
            """
        )
        findings = check_diagnostic_settings(Path("diag.tf"), text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["context"]["resource"], "network_security_group.nsg")

    def test_diagnostic_settings_nsg_present(self) -> None:
        text = textwrap.dedent(
            """
            resource "azurerm_network_security_group" "nsg" {
              name = "nsg"
            }

            resource "azurerm_monitor_diagnostic_setting" "nsg_diag" {
              name                       = "nsg-diag"
              target_resource_id         = azurerm_network_security_group.nsg.id
              log_analytics_workspace_id = "/subscriptions/.../resourceGroups/rg/providers/Microsoft.OperationalInsights/workspaces/law"
            }
            """
        )
        findings = check_diagnostic_settings(Path("diag.tf"), text)
        self.assertEqual(len(findings), 0)

    def test_diagnostic_settings_vnet_and_subnet_missing(self) -> None:
        text = textwrap.dedent(
            """
            resource "azurerm_virtual_network" "vnet" {
              name                = "vnet"
              resource_group_name = "rg"
              location            = "eastus"
              address_space       = ["10.0.0.0/16"]
            }

            resource "azurerm_subnet" "subnet" {
              name                 = "subnet"
              resource_group_name  = "rg"
              virtual_network_name = azurerm_virtual_network.vnet.name
              address_prefixes     = ["10.0.1.0/24"]
            }
            """
        )
        findings = check_diagnostic_settings(Path("diag.tf"), text)
        contexts = {finding["context"]["resource"] for finding in findings}
        self.assertIn("virtual_network.vnet", contexts)
        self.assertIn("subnet.subnet", contexts)

    def test_diagnostic_settings_vnet_and_subnet_present(self) -> None:
        text = textwrap.dedent(
            """
            resource "azurerm_virtual_network" "vnet" {
              name                = "vnet"
              resource_group_name = "rg"
              location            = "eastus"
              address_space       = ["10.0.0.0/16"]
            }

            resource "azurerm_subnet" "subnet" {
              name                 = "subnet"
              resource_group_name  = "rg"
              virtual_network_name = azurerm_virtual_network.vnet.name
              address_prefixes     = ["10.0.1.0/24"]
            }

            resource "azurerm_monitor_diagnostic_setting" "vnet_diag" {
              name                       = "vnet-diag"
              target_resource_id         = azurerm_virtual_network.vnet.id
              log_analytics_workspace_id = "/subscriptions/.../resourceGroups/rg/providers/Microsoft.OperationalInsights/workspaces/law"
            }

            resource "azurerm_monitor_diagnostic_setting" "subnet_diag" {
              name                       = "subnet-diag"
              target_resource_id         = azurerm_subnet.subnet.id
              log_analytics_workspace_id = "/subscriptions/.../resourceGroups/rg/providers/Microsoft.OperationalInsights/workspaces/law"
            }
            """
        )
        findings = check_diagnostic_settings(Path("diag.tf"), text)
        self.assertEqual(len(findings), 0)


if __name__ == "__main__":
    unittest.main()
