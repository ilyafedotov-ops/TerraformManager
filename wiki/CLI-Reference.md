# CLI Reference

The TerraformManager CLI provides command-line access to all core features including scanning, generation, authentication, and knowledge management.

## Installation

The CLI is included with the backend installation:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Global Usage

```bash
python -m backend.cli <command> [options]
```

## Commands

### scan

Run policy scanner with optional integrations.

**Usage:**
```bash
python -m backend.cli scan --path <directory> [options]
```

**Options:**

| Flag | Type | Description |
|------|------|-------------|
| `--path` | string | Path to Terraform directory (required) |
| `--out` | string | Output JSON report path |
| `--html-out` | string | Output HTML report path |
| `--patch-out` | string | Output auto-fix patch file path |
| `--config` | string | Path to tfreview.yaml config file |
| `--terraform-fmt` | flag | Run terraform fmt checks |
| `--terraform-validate` | flag | Run terraform validate checks |
| `--cost` | flag | Enable Infracost analysis |
| `--cost-usage-file` | string | Infracost usage file path |
| `--plan-json` | string | Terraform plan JSON for drift detection |
| `--llm` | flag | Enable LLM integrations |
| `--llm-model` | string | Override LLM model |
| `--llm-explanations` | flag | Generate explanations for findings |
| `--llm-patches` | flag | Generate auto-fix patches via LLM |
| `--project-id` | string | Scope scan to project workspace |
| `--project-slug` | string | Scope scan to project workspace by slug |

**Examples:**

Basic scan:
```bash
python -m backend.cli scan --path ./terraform --out report.json
```

Full scan with all features:
```bash
python -m backend.cli scan \
  --path ./terraform \
  --out report.json \
  --html-out report.html \
  --patch-out fixes.patch \
  --terraform-fmt \
  --terraform-validate \
  --cost \
  --cost-usage-file usage.yml \
  --plan-json plan.json
```

Scan with LLM assistance:
```bash
python -m backend.cli scan \
  --path ./terraform \
  --out report.json \
  --llm \
  --llm-explanations \
  --llm-patches
```

Project-scoped scan:
```bash
python -m backend.cli scan \
  --path . \
  --project-id <uuid> \
  --out report.json
```

---

### baseline

Generate waiver configuration from current findings.

**Usage:**
```bash
python -m backend.cli baseline --path <directory> [options]
```

**Options:**

| Flag | Type | Description |
|------|------|-------------|
| `--path` | string | Path to Terraform directory (required) |
| `--out` | string | Output file path (default: tfreview.yaml) |
| `--format` | string | Output format: yaml or json (default: yaml) |
| `--project-id` | string | Scope paths to project workspace |
| `--project-slug` | string | Scope paths to project workspace by slug |

**Examples:**

Generate YAML baseline:
```bash
python -m backend.cli baseline --path ./terraform
```

Generate JSON baseline:
```bash
python -m backend.cli baseline \
  --path ./terraform \
  --out baseline.json \
  --format json
```

Project-scoped baseline:
```bash
python -m backend.cli baseline \
  --path . \
  --project-slug my-project \
  --out tfreview.yaml
```

---

### precommit

Generate `.pre-commit-config.yaml` for Terraform workflows.

**Usage:**
```bash
python -m backend.cli precommit [options]
```

**Options:**

| Flag | Type | Description |
|------|------|-------------|
| `--out` | string | Output file path (default: .pre-commit-config.yaml) |

**Example:**

```bash
python -m backend.cli precommit --out .pre-commit-config.yaml
```

**Generated Hooks:**
- terraform fmt
- terraform validate
- tflint
- checkov
- infracost
- terraform-docs

---

### docs

Generate and mirror Terraform documentation.

**Usage:**
```bash
python -m backend.cli docs [options]
```

**Options:**

| Flag | Type | Description |
|------|------|-------------|
| `--project-id` | string | Generate docs for project workspace |
| `--project-slug` | string | Generate docs for project workspace by slug |
| `--skip-reindex` | flag | Skip knowledge base reindexing |

**Examples:**

Generate all docs and reindex:
```bash
python -m backend.cli docs
```

Generate docs for specific project:
```bash
python -m backend.cli docs --project-id <uuid>
```

Generate without reindexing:
```bash
python -m backend.cli docs --skip-reindex
```

**Requires:**
- `terraform-docs` binary on PATH

---

### auth login

Authenticate CLI against API and store tokens.

**Usage:**
```bash
python -m backend.cli auth login [options]
```

**Options:**

| Flag | Type | Description |
|------|------|-------------|
| `--email` | string | User email address (required) |
| `--password` | string | User password (prompted if not provided) |
| `--base-url` | string | API base URL (default: http://localhost:8890) |
| `--out` | string | Token file path (default: tm_auth.json) |

**Examples:**

Interactive login:
```bash
python -m backend.cli auth login \
  --email admin@example.com \
  --base-url http://localhost:8890
```

Non-interactive login:
```bash
python -m backend.cli auth login \
  --email admin@example.com \
  --password mysecret \
  --base-url https://tfm.example.com
```

**Token Storage:**

Tokens are saved to `tm_auth.json`:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_at": 1234567890
}
```

Set `TM_AUTH_FILE` environment variable to use a different location.

---

### reindex

Rebuild TF-IDF knowledge base index.

**Usage:**
```bash
python -m backend.cli reindex
```

**When to Use:**
- After manually adding Markdown files to `knowledge/`
- After updating knowledge content
- To refresh search results

**Example:**

```bash
python -m backend.cli reindex
```

---

### project generator

Invoke a registered generator via API and save to project workspace.

**Usage:**
```bash
python -m backend.cli project generator [options]
```

**Options:**

| Flag | Type | Description |
|------|------|-------------|
| `--project-id` | string | Target project UUID (required) |
| `--project-slug` | string | Target project slug (alternative to --project-id) |
| `--slug` | string | Generator slug (e.g., aws/s3-secure-bucket) (required) |
| `--payload` | string | JSON payload file path (required) |
| `--asset-name` | string | Name for saved asset |
| `--tags` | string | Comma-separated tags |
| `--force-save` | flag | Override validation failures |

**Examples:**

Generate S3 bucket:
```bash
python -m backend.cli project generator \
  --project-id <uuid> \
  --slug aws/s3-secure-bucket \
  --payload payloads/s3.json \
  --asset-name "Logging Bucket" \
  --tags "terraform,baseline"
```

Force save despite validation errors:
```bash
python -m backend.cli project generator \
  --project-slug my-project \
  --slug azure/storage-account \
  --payload payloads/storage.json \
  --force-save
```

---

### project upload

Upload local artifact to project run.

**Usage:**
```bash
python -m backend.cli project upload [options]
```

**Options:**

| Flag | Type | Description |
|------|------|-------------|
| `--project-id` | string | Target project UUID (required) |
| `--project-slug` | string | Target project slug (alternative to --project-id) |
| `--run-id` | string | Target run UUID (required) |
| `--file` | string | Local file path (required) |
| `--dest` | string | Destination path in workspace (required) |
| `--tags` | string | Comma-separated tags |
| `--metadata` | string | JSON metadata string |

**Examples:**

Upload scan report:
```bash
python -m backend.cli project upload \
  --project-id <uuid> \
  --run-id <run-id> \
  --file report.json \
  --dest reports/scan_$(date +%Y%m%d).json \
  --tags "report,automated" \
  --metadata '{"source": "ci", "branch": "main"}'
```

Upload Terraform plan:
```bash
python -m backend.cli project upload \
  --project-slug production \
  --run-id <run-id> \
  --file plan.json \
  --dest plans/plan.json
```

---

## Environment Variables

The CLI respects these environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `TFM_API_TOKEN` | - | Legacy API token for authentication |
| `TM_AUTH_FILE` | `tm_auth.json` | Path to JWT token file |
| `TERRAFORM_MANAGER_PROJECTS_ROOT` | `data/projects` | Project workspace root |
| `LLM_CACHE_DIR` | `.llm_cache` | LLM response cache directory |
| `TFM_LOG_LEVEL` | `INFO` | CLI log level |

## Authentication Flow

1. Run `auth login` to obtain tokens
2. Tokens stored in `tm_auth.json` (or `TM_AUTH_FILE`)
3. Subsequent commands automatically use stored tokens
4. Tokens auto-refresh when expired
5. Logout by deleting token file

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Validation failure |
| 3 | Authentication error |
| 4 | File not found |
| 5 | Configuration error |

## Integration Examples

### CI/CD Pipeline

```bash
#!/bin/bash
set -e

# Authenticate
python -m backend.cli auth login \
  --email $CI_EMAIL \
  --password $CI_PASSWORD \
  --base-url $API_URL

# Run scan
python -m backend.cli scan \
  --path ./terraform \
  --out report.json \
  --html-out report.html \
  --terraform-fmt \
  --terraform-validate \
  --cost

# Upload results
python -m backend.cli project upload \
  --project-slug $PROJECT_SLUG \
  --run-id $RUN_ID \
  --file report.json \
  --dest reports/report_$CI_COMMIT_SHA.json \
  --tags "ci,automated"

# Check exit code
if [ $? -ne 0 ]; then
  echo "Scan failed"
  exit 1
fi
```

### Pre-commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

python -m backend.cli scan \
  --path . \
  --terraform-fmt \
  --terraform-validate

if [ $? -ne 0 ]; then
  echo "TerraformManager scan failed. Fix issues or use --no-verify to skip."
  exit 1
fi
```

### Scheduled Baseline Updates

```bash
#!/bin/bash
# cron: 0 2 * * 1  # Weekly on Monday 2am

cd /path/to/terraform
python -m backend.cli baseline --path . --out tfreview.yaml

if git diff --quiet tfreview.yaml; then
  echo "No changes to baseline"
else
  git add tfreview.yaml
  git commit -m "chore: update security baseline"
  git push
fi
```

## Troubleshooting

### Authentication Errors

**Problem**: `401 Unauthorized` errors

**Solutions**:
1. Run `auth login` to refresh tokens
2. Verify API URL: `--base-url`
3. Check token file exists: `cat tm_auth.json`
4. Verify API is running: `curl http://localhost:8890/health`

### File Not Found

**Problem**: `FileNotFoundError` when scanning

**Solutions**:
1. Verify path exists: `ls -la <path>`
2. Use absolute paths
3. Check file permissions
4. For project-scoped scans, verify project exists

### Terraform Binary Not Found

**Problem**: `terraform: command not found`

**Solutions**:
1. Install Terraform CLI
2. Add to PATH: `export PATH=$PATH:/path/to/terraform`
3. Skip validation: remove `--terraform-validate` flag

### LLM Errors

**Problem**: LLM requests failing

**Solutions**:
1. Configure LLM settings via API: `POST /settings/llm`
2. Verify API keys are set
3. Check network connectivity
4. Review cache: `ls -la .llm_cache/`

## Next Steps

- [API Reference](API-Reference) - Learn the REST API
- [Configuration](Configuration) - Environment variable reference
- [Generators Guide](Generators) - Master Terraform generation
- [Development Guide](Development) - Extend the CLI
