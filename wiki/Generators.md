# Generators Guide

TerraformManager includes opinionated Terraform generators for AWS, Azure, and Kubernetes that follow security best practices and compliance standards.

## Overview

Generators create production-ready Terraform code from high-level configuration. All templates:
- Follow cloud provider best practices
- Include security hardening by default
- Support customization via parameters
- Include comprehensive documentation
- Validate with `terraform fmt` and `terraform validate`

## Available Generators

### AWS

#### S3 Secure Bucket (`aws/s3-secure-bucket`)
Production-hardened S3 bucket with encryption, versioning, and access controls.

**Features**:
- Server-side encryption (SSE-S3 or KMS)
- Versioning enabled by default
- Block public access
- Access logging
- Lifecycle policies
- Bucket policy with least-privilege access

**Parameters**:
```json
{
  "bucket_name": "my-app-data",
  "enable_versioning": true,
  "enable_encryption": true,
  "kms_key_id": "optional-kms-key-arn",
  "enable_logging": true,
  "log_bucket": "log-bucket-name",
  "lifecycle_rules": [...]
}
```

#### VPC Networking (`aws/vpc-networking`)
Complete VPC setup with public/private subnets, NAT gateways, and flow logs.

**Features**:
- Multi-AZ architecture
- Public and private subnets
- NAT gateways for private subnet internet access
- VPC Flow Logs to CloudWatch or S3
- Network ACLs
- Route tables

#### EKS Cluster (`aws/eks-cluster`)
Managed Kubernetes cluster with security hardening.

**Features**:
- Control plane logging (all categories)
- IMDSv2 enforcement on nodes
- Private endpoint access option
- Encryption of secrets at rest
- IRSA (IAM Roles for Service Accounts) support
- Managed node groups

#### RDS Baseline (`aws/rds-baseline`)
Production-ready RDS instance with backups and monitoring.

**Features**:
- Automated backups
- Multi-AZ deployment
- Encryption at rest
- Enhanced monitoring
- Performance Insights
- Parameter groups with security settings

### Azure

#### Storage Account (`azure/storage-account`)
Secure Azure Storage with encryption and access controls.

**Features**:
- Infrastructure encryption
- HTTPS-only access
- Minimum TLS 1.2
- Network rules
- Blob soft delete
- Private endpoints support

#### AKS Cluster (`azure/aks-cluster`)
Azure Kubernetes Service with security baseline.

**Features**:
- Azure Policy add-on enabled
- RBAC enabled
- Azure AD integration
- Control plane diagnostics
- Network policy (Azure or Calico)
- System node pool

#### Key Vault (`azure/key-vault`)
Azure Key Vault with access policies and diagnostics.

**Features**:
- Soft delete enabled
- Purge protection
- RBAC authorization
- Network ACLs
- Diagnostics settings
- Private endpoint support

#### Diagnostics Baseline (`azure/diagnostics-baseline`)
Auto-generate diagnostics settings for Azure resources.

**Features**:
- Log Analytics workspace integration
- Storage account for long-term retention
- Resource-specific log categories
- Metrics collection
- Auto-discovery of resources

### Kubernetes

#### Deployment (`k8s/deployment`)
Production-ready Kubernetes Deployment manifest.

**Features**:
- Resource requests/limits
- Liveness/readiness probes
- Security contexts (read-only root, non-root user)
- Pod disruption budgets
- HPA (Horizontal Pod Autoscaler) support
- ConfigMap/Secret mounting

#### Pod Security Baseline (`k8s/pod-security-baseline`)
PSP/PSA policies for cluster security.

**Features**:
- Restricted security profile
- Prevent privilege escalation
- Drop all capabilities
- Seccomp profiles
- AppArmor/SELinux support
- Read-only root filesystem

#### Argo CD Baseline (`k8s/argo-cd-baseline`)
GitOps platform with security hardening.

**Features**:
- Restricted namespace
- Network policies
- Resource quotas
- Helm chart installation
- Admin user disabled
- Ingress configuration

---

## Using Generators

### Via Web UI

1. Navigate to "Generators" in the dashboard
2. Select provider (AWS, Azure, Kubernetes)
3. Choose a template
4. Fill in the configuration form
5. Preview generated code
6. Download or save to project

### Via API

```bash
curl -X POST http://localhost:8890/generators/aws/s3 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "bucket_name": "my-secure-bucket",
    "enable_versioning": true,
    "enable_encryption": true
  }'
```

### Via CLI

```bash
python -m backend.cli project generator \
  --project-id <uuid> \
  --slug aws/s3-secure-bucket \
  --payload payload.json \
  --asset-name "Production Data Bucket"
```

---

## Blueprint Bundles

Combine multiple generators into environment-specific bundles.

### Example Request

```json
{
  "name": "production-infrastructure",
  "environments": ["dev", "staging", "prod"],
  "components": [
    {
      "slug": "aws/vpc-networking",
      "payload": {
        "vpc_cidr": "10.0.0.0/16",
        "availability_zones": ["us-east-1a", "us-east-1b"]
      }
    },
    {
      "slug": "aws/eks-cluster",
      "payload": {
        "cluster_name": "{env}-cluster",
        "kubernetes_version": "1.28"
      }
    }
  ],
  "backend": {
    "type": "s3",
    "config": {
      "bucket": "terraform-state-{env}",
      "key": "infrastructure.tfstate",
      "region": "us-east-1"
    }
  }
}
```

### Environment Placeholders

Use `{env}` in payloads for environment-specific values:
- `{env}-cluster` → `dev-cluster`, `staging-cluster`, `prod-cluster`
- `terraform-state-{env}` → `terraform-state-dev`, etc.

### Backend Options

Supported backends:
- **S3**: AWS remote state
- **Azure**: Azure Storage backend
- **Local**: Local state files (dev only)

---

## Generator Development

### Template Structure

```
backend/generators/
├── aws_s3_bucket.tf.j2          # Jinja2 template
├── models.py                     # Pydantic models
├── registry.py                   # Generator registration
└── docs.py                       # Documentation generation
```

### Creating a New Generator

1. **Create Jinja2 Template** (`aws_new_resource.tf.j2`):

```jinja2
resource "aws_example" "main" {
  name = var.resource_name

  {% if enable_encryption %}
  encryption {
    enabled = true
  }
  {% endif %}

  tags = merge(
    var.common_tags,
    {
      Name = var.resource_name
    }
  )
}
```

2. **Define Pydantic Model** (`models.py`):

```python
class AWSExampleRequest(BaseModel):
    resource_name: str
    enable_encryption: bool = True
    common_tags: dict[str, str] = {}
```

3. **Register Generator** (`registry.py`):

```python
GENERATOR_REGISTRY = {
    "aws/example": {
        "name": "AWS Example Resource",
        "provider": "aws",
        "category": "compute",
        "template": "aws_new_resource.tf.j2",
        "model": AWSExampleRequest,
        "description": "Create example AWS resource"
    }
}
```

4. **Add Tests** (`tests/test_generators_render.py`):

```python
def test_aws_example_basic():
    result = render_generator(
        "aws/example",
        {"resource_name": "test"}
    )
    assert "resource \"aws_example\"" in result
```

### Template Best Practices

1. **Use Variables**: Extract hardcoded values to variables
2. **Provide Defaults**: Set sensible defaults for optional params
3. **Add Documentation**: Include comments and terraform-docs
4. **Validate Inputs**: Use Pydantic validators
5. **Follow Conventions**: Match cloud provider naming patterns
6. **Include Outputs**: Expose useful resource attributes

---

## Validation

Generators support automatic validation:

```bash
python -m backend.cli project generator \
  --project-id <uuid> \
  --slug aws/s3-secure-bucket \
  --payload payload.json \
  --validate
```

**Validation Checks**:
- `terraform fmt -check` - Formatting
- `terraform validate` - Syntax
- Schema validation - Required fields
- Security policy scan - Best practices

**Override Validation**:
```bash
--force-save  # Save despite validation failures
```

---

## Generator Metadata

View all available generators:

```bash
curl http://localhost:8890/generators/metadata
```

Response includes:
- Generator slug
- Provider and category
- Description
- JSON schema for payload
- Required vs optional fields
- Example payloads

---

## Common Patterns

### Conditional Resources

```jinja2
{% if enable_monitoring %}
resource "aws_cloudwatch_alarm" "example" {
  # ...
}
{% endif %}
```

### Dynamic Blocks

```jinja2
dynamic "lifecycle_rule" {
  for_each = var.lifecycle_rules
  content {
    id     = lifecycle_rule.value.id
    status = lifecycle_rule.value.status
  }
}
```

### Module Composition

```jinja2
module "vpc" {
  source = "./modules/vpc"

  {% for key, value in vpc_config.items() %}
  {{ key }} = {{ value | tojson }}
  {% endfor %}
}
```

---

## Troubleshooting

### Template Rendering Errors

**Symptom**: Jinja2 syntax errors

**Solution**:
1. Check template syntax
2. Verify all variables are defined
3. Test with minimal payload
4. Review Jinja2 docs for filters

### Validation Failures

**Symptom**: `terraform validate` fails

**Solution**:
1. Check required provider configuration
2. Verify resource dependencies
3. Review Terraform docs for resource
4. Use `--force-save` if intentional

### Missing Parameters

**Symptom**: Required field errors

**Solution**:
1. Check generator metadata for required fields
2. Provide all required parameters in payload
3. Review example payloads

---

## Next Steps

- [API Reference](API-Reference) - Generator API endpoints
- [CLI Reference](CLI-Reference) - Generator CLI commands
- [Development Guide](Development) - Create custom generators
- [Knowledge Base](Knowledge-Base) - Best practices documentation
