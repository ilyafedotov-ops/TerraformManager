---
title: AWS EKS Best Practices
provider: aws
service: eks
category: [security, kubernetes, container-orchestration]
tags: [irsa, node-groups, pod-security, network-policies, encryption]
last_updated: 2025-01-18
difficulty: intermediate
---

# AWS EKS Best Practices

Amazon Elastic Kubernetes Service (EKS) is a managed Kubernetes service that simplifies running Kubernetes on AWS. This guide covers security, reliability, and operational best practices for EKS clusters.

## Cluster Security

### Control Plane Access

**Endpoint Configuration:**
- Use **private endpoint** for production clusters to restrict API server access to VPC only
- If public endpoint is required, enable **authorized networks** to restrict source IPs
- Never expose API server to `0.0.0.0/0` in production environments

```terraform
resource "aws_eks_cluster" "main" {
  name     = "production-cluster"
  role_arn = aws_iam_role.cluster.arn

  vpc_config {
    endpoint_private_access = true
    endpoint_public_access  = false  # Private only for production
    subnet_ids              = var.private_subnet_ids

    # If public access is required:
    # endpoint_public_access = true
    # public_access_cidrs    = ["203.0.113.0/24"]  # Your office/VPN CIDRs
  }
}
```

### Enable Secrets Encryption

**Always encrypt Kubernetes secrets at rest using AWS KMS:**
- Create a dedicated KMS key for EKS secrets
- Enable envelope encryption for secrets stored in etcd
- Rotate KMS keys regularly (recommended: annually)

```terraform
resource "aws_kms_key" "eks" {
  description             = "EKS Secrets Encryption Key"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_eks_cluster" "main" {
  # ... other configuration ...

  encryption_config {
    provider {
      key_arn = aws_kms_key.eks.arn
    }
    resources = ["secrets"]
  }
}
```

### Enable Control Plane Logging

**Enable all five log types for comprehensive audit trail:**
- `api` - API server logs
- `audit` - Kubernetes audit logs
- `authenticator` - IAM authenticator logs
- `controllerManager` - Controller manager logs
- `scheduler` - Scheduler logs

```terraform
resource "aws_eks_cluster" "main" {
  enabled_cluster_log_types = ["api", "audit", "authenticator", "controllerManager", "scheduler"]

  # ... other configuration ...
}

resource "aws_cloudwatch_log_group" "eks" {
  name              = "/aws/eks/${var.cluster_name}/cluster"
  retention_in_days = 90  # Adjust based on compliance requirements
  kms_key_id        = aws_kms_key.logs.arn
}
```

## Node Group Security

### Use Managed Node Groups

**Prefer EKS Managed Node Groups over self-managed:**
- Automatic AMI updates and patching
- Built-in support for launch templates
- Simplified node lifecycle management
- Better integration with EKS control plane

```terraform
resource "aws_eks_node_group" "main" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "production-ng"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.private_subnet_ids

  scaling_config {
    desired_size = 3
    min_size     = 3
    max_size     = 10
  }

  update_config {
    max_unavailable_percentage = 33  # Rolling updates
  }

  launch_template {
    id      = aws_launch_template.node.id
    version = "$Latest"
  }

  # Security best practices
  tags = {
    "kubernetes.io/cluster/${var.cluster_name}" = "owned"
  }
}
```

### Node Security Best Practices

**Launch Template Configuration:**

```terraform
resource "aws_launch_template" "node" {
  name_prefix   = "eks-node-"
  instance_type = "t3.medium"

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"     # Require IMDSv2
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "enabled"
  }

  block_device_mappings {
    device_name = "/dev/xvda"

    ebs {
      volume_size           = 100
      volume_type           = "gp3"
      encrypted             = true               # Always encrypt node storage
      delete_on_termination = true
    }
  }

  monitoring {
    enabled = true  # Enable detailed CloudWatch monitoring
  }

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "eks-node-${var.cluster_name}"
    }
  }
}
```

**Security Group Rules:**
- Restrict node-to-node communication to required ports only
- Allow only necessary ingress from load balancers
- Never allow SSH from `0.0.0.0/0` - use Systems Manager Session Manager instead

```terraform
resource "aws_security_group" "node" {
  name_prefix = "eks-node-"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "eks-node-${var.cluster_name}"
  }
}

# Allow nodes to communicate with control plane
resource "aws_security_group_rule" "node_to_cluster" {
  type                     = "ingress"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  source_security_group_id = aws_eks_cluster.main.vpc_config[0].cluster_security_group_id
  security_group_id        = aws_security_group.node.id
}
```

## IRSA (IAM Roles for Service Accounts)

**Always use IRSA instead of node IAM roles for pod-level permissions:**

### Enable OIDC Provider

```terraform
data "tls_certificate" "cluster" {
  url = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "cluster" {
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.cluster.certificates[0].sha1_fingerprint]
  url             = aws_eks_cluster.main.identity[0].oidc[0].issuer
}
```

### Create Service Account IAM Role

```terraform
data "aws_iam_policy_document" "service_account_assume" {
  statement {
    effect = "Allow"

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.cluster.arn]
    }

    actions = ["sts:AssumeRoleWithWebIdentity"]

    condition {
      test     = "StringEquals"
      variable = "${replace(aws_iam_openid_connect_provider.cluster.url, "https://", "")}:sub"
      values   = ["system:serviceaccount:${var.namespace}:${var.service_account_name}"]
    }

    condition {
      test     = "StringEquals"
      variable = "${replace(aws_iam_openid_connect_provider.cluster.url, "https://", "")}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "service_account" {
  name               = "eks-${var.cluster_name}-${var.service_account_name}"
  assume_role_policy = data.aws_iam_policy_document.service_account_assume.json
}

# Attach minimal permissions - principle of least privilege
resource "aws_iam_role_policy_attachment" "service_account" {
  role       = aws_iam_role.service_account.name
  policy_arn = aws_iam_policy.service_account.arn
}
```

## Network Security

### Network Policies

**Always implement Kubernetes Network Policies:**
- Install a CNI that supports network policies (Calico, Cilium)
- Deny all traffic by default, allow explicitly
- Isolate namespaces from each other

```yaml
# Default deny all ingress/egress
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: production
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
```

### VPC Configuration

**Subnet Design:**
- Deploy control plane ENIs in **private subnets only**
- Use separate subnet groups for pods (via CNI custom networking)
- Enable VPC Flow Logs for network audit trail

```terraform
resource "aws_eks_cluster" "main" {
  vpc_config {
    subnet_ids = concat(
      var.private_subnet_ids,   # Control plane
      var.pod_subnet_ids        # Pods (if using custom networking)
    )

    security_group_ids = [aws_security_group.cluster_additional.id]
  }
}

resource "aws_flow_log" "vpc" {
  vpc_id          = var.vpc_id
  traffic_type    = "ALL"
  iam_role_arn    = aws_iam_role.flow_logs.arn
  log_destination = aws_cloudwatch_log_group.flow_logs.arn
}
```

## Pod Security

### Pod Security Standards

**Implement Pod Security Standards (PSS) at cluster level:**
- Enforce `restricted` profile for production workloads
- Use `baseline` for trusted system components only
- Never use `privileged` in production

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

### Runtime Security

**Best practices for pod configurations:**

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: secure-app
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 10000
    fsGroup: 10000
    seccompProfile:
      type: RuntimeDefault

  containers:
  - name: app
    image: myapp:1.0.0
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop:
          - ALL

    resources:
      requests:
        memory: "256Mi"
        cpu: "100m"
      limits:
        memory: "512Mi"
        cpu: "500m"

    volumeMounts:
    - name: tmp
      mountPath: /tmp

  volumes:
  - name: tmp
    emptyDir: {}
```

## Observability

### Metrics and Logging

**Enable comprehensive monitoring:**

```terraform
# CloudWatch Container Insights
resource "aws_eks_addon" "cloudwatch_observability" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "amazon-cloudwatch-observability"
}

# Or use ADOT (AWS Distro for OpenTelemetry)
resource "aws_eks_addon" "adot" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "adot"
}
```

**Install metrics-server for HPA:**

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

## Add-ons Management

**Use EKS Add-ons for managed components:**

```terraform
# VPC CNI
resource "aws_eks_addon" "vpc_cni" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "vpc-cni"
  addon_version = "v1.16.0-eksbuild.1"  # Use latest compatible version

  configuration_values = jsonencode({
    enableNetworkPolicy = "true"
    env = {
      AWS_VPC_K8S_CNI_CUSTOM_NETWORK_CFG = "true"
      ENI_CONFIG_LABEL_DEF              = "topology.kubernetes.io/zone"
    }
  })
}

# CoreDNS
resource "aws_eks_addon" "coredns" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "coredns"
}

# kube-proxy
resource "aws_eks_addon" "kube_proxy" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "kube-proxy"
}

# EBS CSI Driver for persistent volumes
resource "aws_eks_addon" "ebs_csi" {
  cluster_name             = aws_eks_cluster.main.name
  addon_name               = "aws-ebs-csi-driver"
  service_account_role_arn = aws_iam_role.ebs_csi.arn
}
```

## High Availability

### Multi-AZ Deployment

**Always deploy across multiple Availability Zones:**

```terraform
resource "aws_eks_node_group" "main" {
  subnet_ids = var.private_subnet_ids  # Subnets in different AZs

  scaling_config {
    min_size     = 3  # At least one node per AZ
    desired_size = 6  # Two nodes per AZ (3 AZs)
    max_size     = 12
  }
}
```

### Pod Disruption Budgets

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: app-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: critical-service
```

## Upgrade Strategy

**Best practices for version upgrades:**

1. **Control plane first, then nodes** - upgrade cluster, then node groups
2. **One minor version at a time** - never skip versions (1.25 → 1.26 → 1.27)
3. **Test in non-prod** - validate workloads on new version before production
4. **Review deprecations** - check Kubernetes changelog for breaking changes
5. **Blue/green node groups** - create new node group, migrate workloads, delete old

```terraform
resource "aws_eks_cluster" "main" {
  version = "1.28"  # Keep current
}

# Create new node group with updated version
resource "aws_eks_node_group" "new" {
  version = "1.28"  # Match cluster version

  # After migration, delete old node group
}
```

## Cost Optimization

### Right-sizing

**Use appropriate instance types:**
- **Compute-optimized (C6i/C7i)** for CPU-intensive workloads
- **Memory-optimized (R6i/R7i)** for caching, databases
- **General purpose (T3/T4g)** for burstable workloads
- **ARM (Graviton2/3)** for cost savings on compatible workloads

### Autoscaling

```terraform
# Cluster Autoscaler
resource "aws_iam_role" "cluster_autoscaler" {
  name = "eks-cluster-autoscaler"
  assume_role_policy = data.aws_iam_policy_document.cluster_autoscaler_assume.json
}

# Or use Karpenter for more advanced autoscaling
```

**Vertical Pod Autoscaler (VPA)** - automatically adjust pod resource requests/limits

## Compliance

### Security Scanning

**Image scanning:**
- Enable ECR image scanning on push
- Use admission controllers (OPA/Kyverno) to enforce image policies
- Block images with critical vulnerabilities

### Audit Logging

**Enable audit logs and send to CloudWatch:**

```terraform
resource "aws_eks_cluster" "main" {
  enabled_cluster_log_types = ["audit"]
}

# Analyze audit logs for compliance
resource "aws_cloudwatch_log_metric_filter" "unauthorized_calls" {
  name           = "eks-unauthorized-calls"
  log_group_name = "/aws/eks/${var.cluster_name}/cluster"
  pattern        = "{ $.responseStatus.code = 403 }"

  metric_transformation {
    name      = "UnauthorizedAPICalls"
    namespace = "EKS/Security"
    value     = "1"
  }
}
```

## Summary Checklist

- [ ] Private API endpoint enabled
- [ ] Secrets encryption with KMS enabled
- [ ] All control plane logs enabled
- [ ] Managed node groups with encrypted EBS volumes
- [ ] IMDSv2 required on nodes
- [ ] IRSA enabled and used for pod permissions
- [ ] Network policies implemented
- [ ] Pod Security Standards enforced
- [ ] Multi-AZ deployment
- [ ] Cluster Autoscaler or Karpenter configured
- [ ] CloudWatch Container Insights or ADOT enabled
- [ ] EKS add-ons managed via Terraform
- [ ] Image scanning enabled
- [ ] Audit logs analyzed for security events

## References

- [AWS EKS Best Practices Guide](https://aws.github.io/aws-eks-best-practices/)
- [EKS Security Best Practices](https://docs.aws.amazon.com/eks/latest/userguide/security-best-practices.html)
- [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [IRSA Documentation](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html)
