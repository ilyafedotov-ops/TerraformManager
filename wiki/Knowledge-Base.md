# Knowledge Base Guide

The TerraformManager knowledge base provides searchable best practices documentation using TF-IDF retrieval.

## Overview

The knowledge system includes:
- **RAG Search**: TF-IDF-based retrieval over Markdown docs
- **GitHub Sync**: Pull documentation from repositories
- **Auto-indexing**: Automatic reindexing on updates
- **Context-aware**: Project-specific recommendations

## Knowledge Directory

```
knowledge/
├── terraform_language.md            # Terraform basics
├── aws_best_practices.md            # AWS security
├── azure_best_practices.md          # Azure security
├── kubernetes_best_practices.md     # K8s security
├── aws_ecs_eks_service_hardening.md # Container hardening
├── azure_servicebus_best_practices.md # Service Bus
├── onprem_notes.md                  # On-prem/vSphere
└── cli-workspace-workflows.md       # CLI workflows
```

## Using Knowledge Search

### Web Dashboard

1. Navigate to "Knowledge" in dashboard
2. Enter search query (e.g., "S3 encryption")
3. View scored results with snippets
4. Click to view full document

### API

```bash
curl "http://localhost:8890/knowledge/search?q=S3%20encryption&limit=5" \
  -H "Authorization: Bearer $TOKEN"
```

**Response**:
```json
{
  "results": [
    {
      "filename": "aws_best_practices.md",
      "score": 0.87,
      "snippet": "...S3 bucket encryption using SSE-S3 or KMS...",
      "url": "/knowledge/doc?path=aws_best_practices.md"
    }
  ]
}
```

### CLI Integration

Knowledge search is automatically triggered during scans to suggest relevant remediation docs.

## Adding Documentation

### Manual Addition

1. **Create Markdown File**:

```bash
cat > knowledge/my_topic.md <<EOF
# My Topic

## Overview
Description of the topic...

## Best Practices
1. Practice one
2. Practice two

## Example

\`\`\`hcl
resource "example" "demo" {
  # configuration
}
\`\`\`

## References
- [Link](https://example.com)
EOF
```

2. **Reindex**:

```bash
python -m backend.cli reindex
```

### GitHub Sync

Pull documentation from GitHub repositories:

```bash
curl -X POST http://localhost:8890/knowledge/sync \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/user/terraform-docs",
    "branch": "main",
    "target_dir": "terraform"
  }'
```

**Process**:
1. Clones repository
2. Copies Markdown files to `knowledge/`
3. Automatically reindexes

## Document Format

### Best Practices Structure

```markdown
# Topic Name

## Overview
Brief description of the topic.

## Security Concerns
Common security issues related to this topic.

## Best Practices

### 1. Practice Name
Description and rationale.

**Example**:
\`\`\`hcl
# Good
resource "aws_s3_bucket" "example" {
  # secure configuration
}
\`\`\`

**Anti-pattern**:
\`\`\`hcl
# Bad
resource "aws_s3_bucket" "example" {
  # insecure configuration
}
\`\`\`

## Remediation Steps
1. Step one
2. Step two

## Tools & Automation
- Tool name and usage
- Scripts and automation

## References
- [Documentation](https://example.com)
- [Blog Post](https://example.com)

## Related Policies
- POLICY-ID-001: Description
- POLICY-ID-002: Description
```

### Metadata

Include frontmatter for better organization:

```markdown
---
title: AWS S3 Security Best Practices
category: storage
provider: aws
tags: [s3, security, encryption]
updated: 2024-01-15
---

# AWS S3 Security Best Practices
...
```

## Search Algorithm

### TF-IDF Scoring

The system uses scikit-learn's TF-IDF vectorizer:

1. **Indexing**: All Markdown files vectorized
2. **Query**: User query vectorized
3. **Similarity**: Cosine similarity computed
4. **Ranking**: Results sorted by score

### Improving Results

**Use specific keywords**:
- ✅ "S3 bucket encryption KMS"
- ❌ "storage security"

**Multi-word queries**:
- ✅ "Azure Key Vault access policies"
- Better than single words

**Document titles matter**:
- Titles get higher weight
- Use descriptive titles

## Integration with Policies

Link knowledge docs to policies:

```python
# backend/policies/aws.py
@register_policy(
    policy_id="AWS-S3-001",
    knowledge_refs=["aws_best_practices.md#s3-encryption"]
)
def check_s3_encryption(resource):
    # ...
```

Scan reports include knowledge links:

```json
{
  "findings": [{
    "policy_id": "AWS-S3-001",
    "knowledge_refs": ["aws_best_practices.md#s3-encryption"]
  }]
}
```

## Automation

### CI/CD Integration

Update knowledge base in CI:

```yaml
# .github/workflows/knowledge-sync.yml
name: Sync Knowledge Base

on:
  schedule:
    - cron: '0 2 * * 0'  # Weekly

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Sync docs
        run: |
          curl -X POST $API_URL/knowledge/sync \
            -H "Authorization: Bearer $TOKEN" \
            -d '{"repo_url":"https://github.com/org/docs"}'
```

### Scheduled Reindexing

```bash
# cron: 0 3 * * * - Daily at 3am
python -m backend.cli reindex
```

## Generator Documentation

Auto-generate docs for Terraform templates:

```bash
python -m backend.cli docs
```

**Process**:
1. Runs `terraform-docs` on each generator
2. Generates Markdown reference
3. Mirrors to `knowledge/generators/`
4. Reindexes automatically

**Example Output**:

```markdown
# AWS S3 Secure Bucket Generator

## Usage

\`\`\`hcl
module "s3_bucket" {
  source = "./modules/s3-secure-bucket"

  bucket_name        = "my-bucket"
  enable_versioning  = true
  enable_encryption  = true
}
\`\`\`

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| bucket_name | S3 bucket name | string | - | yes |
| enable_versioning | Enable versioning | bool | true | no |

## Outputs

| Name | Description |
|------|-------------|
| bucket_id | S3 bucket ID |
| bucket_arn | S3 bucket ARN |
```

## Context-Aware Recommendations

The dashboard surfaces relevant knowledge based on:

1. **Project tags**: AWS/Azure/K8s
2. **Recent findings**: Policy violations
3. **Generator usage**: Selected templates

Example:
- Project tagged "aws" + "eks"
- Dashboard suggests: `aws_ecs_eks_service_hardening.md`

## Advanced Search

### Multi-document Search

```bash
# Search across multiple documents
curl "http://localhost:8890/knowledge/search?q=encryption+KMS&limit=10"
```

### Filtered Search (Future)

```bash
# Filter by provider
?q=encryption&provider=aws

# Filter by category
?q=networking&category=security
```

## Knowledge Analytics (Future)

Track knowledge usage:
- Most searched topics
- Most viewed documents
- Search success rate
- Document recommendations

## Troubleshooting

### No Results

1. **Reindex**:
   ```bash
   python -m backend.cli reindex
   ```

2. **Verify files exist**:
   ```bash
   ls -la knowledge/*.md
   ```

3. **Check permissions**:
   ```bash
   chmod -R 755 knowledge/
   ```

### Stale Index

Reindex after adding/updating docs:
```bash
python -m backend.cli reindex
```

### Sync Fails

1. Check repository URL
2. Verify network connectivity
3. Use access token for private repos

## Best Practices

1. **Organize by provider**: Separate AWS/Azure/K8s docs
2. **Use descriptive titles**: Improve search relevance
3. **Include code examples**: Practical remediation
4. **Link to official docs**: External references
5. **Update regularly**: Keep docs current
6. **Tag appropriately**: Enable filtering (future)

## Contributing Knowledge

See [Development Guide](Development) for:
- Writing style guide
- Markdown conventions
- Review process
- Testing documentation

## Next Steps

- [Getting Started](Getting-Started) - Setup knowledge base
- [CLI Reference](CLI-Reference) - Knowledge commands
- [API Reference](API-Reference) - Knowledge endpoints
- [Development Guide](Development) - Contributing docs
