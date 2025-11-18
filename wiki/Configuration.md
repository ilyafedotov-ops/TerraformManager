# Configuration Reference

TerraformManager is configured through environment variables and YAML configuration files.

## Environment Variables

### Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `TFM_PORT` / `PORT` | `8890` | API server port |
| `VITE_API_BASE` | `http://localhost:8890` | Frontend API base URL |
| `TERRAFORM_MANAGER_PROJECTS_ROOT` | `data/projects` | Project workspace root directory |

### Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `TFM_API_TOKEN` / `API_TOKEN` | `local-dev` | Legacy single-user token |
| `TFM_JWT_SECRET` | `dev-secret-change-me` | JWT signing secret (CHANGE IN PRODUCTION) |
| `TFM_REFRESH_SECRET` | _falls back to JWT_SECRET_ | Optional distinct secret for refresh tokens |
| `TFM_ACCESS_TOKEN_MINUTES` | `30` | Access token lifetime (minutes) |
| `TFM_REFRESH_TOKEN_MINUTES` | `10080` (7 days) | Refresh token lifetime (minutes) |
| `TFM_SERVICE_USER_EMAIL` | `service@local` | Service user email for API token auth |

### Cookie Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `TFM_COOKIE_SECURE` | `false` | Set `true`/`1` in production for HTTPS-only cookies |
| `TFM_COOKIE_DOMAIN` | _unset_ | Optional domain attribute for cookie scope |
| `TFM_COOKIE_SAMESITE` | `lax` | SameSite mode (`lax`, `strict`, `none`) |
| `TFM_AUTH_REFRESH_COOKIE` | `tm_refresh_token` | Cookie name for refresh token |

### Logging & Observability

| Variable | Default | Description |
|----------|---------|-------------|
| `TFM_LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, WARN, ERROR) |
| `TFM_LOG_DIR` | `logs` | Directory for log files |
| `TFM_LOG_FILE` | `<LOG_DIR>/terraform-manager.log` | Log file path (or `stdout`/`stderr`/`none`) |
| `TFM_LOG_FILE_MAX_BYTES` | `5242880` (5 MB) | Log file rotation threshold |
| `TFM_LOG_FILE_BACKUP_COUNT` | `5` | Number of rotated log files to retain |

### CORS & Security

| Variable | Default | Description |
|----------|---------|-------------|
| `TFM_ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated allowed CORS origins |
| `TFM_TRUSTED_HOSTS` | _unset_ | Optional comma-separated hostname allowlist |
| `PUBLIC_API_BASE` | _auto-detected_ | Force frontend to use specific API origin |
| `PUBLIC_API_PORT` | _derived from TFM_PORT_ | Override API port for frontend |

### Database

| Variable | Default | Description |
|----------|---------|-------------|
| `TFM_SQL_ECHO` / `SQLALCHEMY_ECHO` | `false` | Log SQL queries (for debugging) |

### Optional Features

| Variable | Default | Description |
|----------|---------|-------------|
| `TFM_RUN_TERRAFORM_VALIDATE` | `false` | Enable terraform validation in tests |
| `LLM_CACHE_DIR` | `.llm_cache` | LLM response cache directory |
| `TM_AUTH_FILE` | `tm_auth.json` | CLI authentication token file |

---

## Configuration File: tfreview.yaml

Review configuration files define waivers, severity thresholds, and custom rules.

### Location

- Project-specific: `<project_root>/tfreview.yaml`
- Global: `./tfreview.yaml`
- Custom: Specify with `--config` flag

### Schema

```yaml
# Severity thresholds
thresholds:
  high: 0      # Fail if any high-severity findings
  medium: 5    # Fail if more than 5 medium-severity findings
  low: 10      # Fail if more than 10 low-severity findings

# Waived findings
waivers:
  - policy_id: AWS-S3-001
    resource: aws_s3_bucket.logs
    reason: "Legacy bucket, migration planned for Q2"
    expires: 2024-06-30

  - policy_id: AZURE-AKS-002
    file: terraform/aks.tf
    reason: "Approved by security team"
    approved_by: security@example.com

# Custom rules (advanced)
custom_rules:
  - id: CUSTOM-001
    name: "Enforce specific tags"
    severity: medium
    resource_types:
      - aws_instance
      - aws_s3_bucket
    check: |
      required_tags = ["Environment", "Owner", "CostCenter"]
      actual_tags = resource.get("tags", {}).keys()
      missing = set(required_tags) - set(actual_tags)
      if missing:
        return f"Missing required tags: {', '.join(missing)}"
```

### Waiver Fields

| Field | Required | Description |
|-------|----------|-------------|
| `policy_id` | Yes | Policy ID to waive |
| `resource` | No | Specific resource name (if omitted, applies to all) |
| `file` | No | Specific file path |
| `reason` | Yes | Justification for waiver |
| `expires` | No | Expiration date (YYYY-MM-DD) |
| `approved_by` | No | Approver email/name |

### Threshold Options

| Key | Description |
|-----|-------------|
| `high` | Max high-severity findings allowed |
| `medium` | Max medium-severity findings allowed |
| `low` | Max low-severity findings allowed |

Set to `0` to fail on any findings of that severity.
Omit to disable threshold enforcement for that severity.

---

## Example Configurations

### Production Environment

`.env`:
```bash
# Server
TFM_PORT=8890
PUBLIC_API_BASE=https://tfm.example.com

# Security
TFM_JWT_SECRET=your-secure-random-secret-here
TFM_REFRESH_SECRET=different-secure-secret-here
TFM_COOKIE_SECURE=true
TFM_COOKIE_DOMAIN=example.com
TFM_COOKIE_SAMESITE=strict

# CORS
TFM_ALLOWED_ORIGINS=https://tfm.example.com,https://dashboard.example.com
TFM_TRUSTED_HOSTS=tfm.example.com,api.tfm.example.com

# Logging
TFM_LOG_LEVEL=INFO
TFM_LOG_DIR=/var/log/tfm
TFM_LOG_FILE=/var/log/tfm/terraform-manager.log

# Authentication
TFM_ACCESS_TOKEN_MINUTES=15
TFM_REFRESH_TOKEN_MINUTES=43200  # 30 days
```

`tfreview.yaml`:
```yaml
thresholds:
  high: 0
  medium: 0
  low: 5

waivers:
  - policy_id: AWS-S3-001
    resource: aws_s3_bucket.legacy_logs
    reason: "Legacy system, migration planned Q2 2024"
    expires: 2024-06-30
    approved_by: security@example.com
```

### Development Environment

`.env`:
```bash
# Server
TFM_PORT=8890
VITE_API_BASE=http://localhost:8890

# Security (dev defaults)
TFM_JWT_SECRET=dev-secret-change-me
TFM_COOKIE_SECURE=false

# Logging
TFM_LOG_LEVEL=DEBUG
TFM_SQL_ECHO=true

# CORS (local development)
TFM_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

`tfreview.yaml`:
```yaml
# Relaxed thresholds for development
thresholds:
  high: 5
  medium: 20
  low: 50
```

### CI/CD Environment

`.env`:
```bash
# Server
TFM_PORT=8890

# Authentication (use service account)
TFM_API_TOKEN=${CI_TFM_TOKEN}

# Logging
TFM_LOG_LEVEL=INFO
TFM_LOG_FILE=stdout

# Disable interactive features
VITE_API_BASE=${CI_API_URL}
```

`tfreview.yaml`:
```yaml
# Strict enforcement in CI
thresholds:
  high: 0
  medium: 0
  low: 0

# No waivers in CI - all issues must be fixed
waivers: []
```

---

## Configuration Precedence

Settings are resolved in this order (highest to lowest priority):

1. Environment variables
2. `.env` file in project root
3. Command-line flags (CLI only)
4. Configuration file (`tfreview.yaml`)
5. Default values

### Example

If both are set:
```bash
export TFM_PORT=9000
# .env file contains: TFM_PORT=8890
```

The environment variable (`9000`) takes precedence.

---

## Validation

### Required in Production

These **must** be changed from defaults in production:

- `TFM_JWT_SECRET` - Use a strong random secret
- `TFM_REFRESH_SECRET` - Use a different strong random secret
- `TFM_COOKIE_SECURE` - Set to `true` for HTTPS
- `TFM_ALLOWED_ORIGINS` - List your actual domains

### Generating Secrets

```bash
# Generate secure random secrets
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Or using openssl
openssl rand -base64 32
```

---

## Configuration Management

### Docker

Use environment variables in `docker-compose.yml`:

```yaml
version: '3.8'
services:
  tfm:
    image: terraform-manager:latest
    environment:
      - TFM_PORT=8890
      - TFM_JWT_SECRET=${TFM_JWT_SECRET}
      - TFM_COOKIE_SECURE=true
    volumes:
      - ./data:/app/data
      - ./knowledge:/app/knowledge
    ports:
      - "8890:8890"
```

### Kubernetes

Use ConfigMaps and Secrets:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: tfm-config
data:
  TFM_PORT: "8890"
  TFM_LOG_LEVEL: "INFO"
  TFM_COOKIE_SECURE: "true"
---
apiVersion: v1
kind: Secret
metadata:
  name: tfm-secrets
type: Opaque
stringData:
  TFM_JWT_SECRET: "your-secret-here"
  TFM_REFRESH_SECRET: "your-other-secret-here"
```

### Systemd

Use environment file:

```ini
# /etc/tfm/config.env
TFM_PORT=8890
TFM_JWT_SECRET=secret-from-vault
TFM_COOKIE_SECURE=true
TFM_LOG_DIR=/var/log/tfm
```

```ini
# /etc/systemd/system/tfm.service
[Service]
EnvironmentFile=/etc/tfm/config.env
ExecStart=/opt/tfm/venv/bin/python -m api
```

---

## Troubleshooting

### Configuration Not Loading

1. Check environment variable spelling
2. Verify `.env` file location (must be in project root)
3. Check file permissions: `chmod 600 .env`
4. Look for typos in variable names

### CORS Errors

**Symptom**: Browser blocks API requests

**Solution**:
```bash
export TFM_ALLOWED_ORIGINS="http://localhost:5173,https://your-domain.com"
```

Restart the API server after changing.

### Cookie Not Set

**Symptom**: Refresh token cookie not appearing

**Solutions**:
1. Set `TFM_COOKIE_SECURE=false` for local development (HTTP)
2. Use HTTPS in production with `TFM_COOKIE_SECURE=true`
3. Check `TFM_COOKIE_DOMAIN` matches your domain

### Token Expired Too Quickly

**Solution**: Increase token lifetime
```bash
export TFM_ACCESS_TOKEN_MINUTES=60
export TFM_REFRESH_TOKEN_MINUTES=43200  # 30 days
```

---

## Security Best Practices

1. **Never commit secrets** to version control
   - Use `.env` files (add to `.gitignore`)
   - Use secret management tools (Vault, AWS Secrets Manager)

2. **Use strong secrets** in production
   - Generate with cryptographically secure RNG
   - Minimum 32 bytes entropy
   - Different secrets for JWT and refresh tokens

3. **Enable secure cookies** in production
   ```bash
   TFM_COOKIE_SECURE=true
   TFM_COOKIE_SAMESITE=strict
   ```

4. **Restrict CORS origins**
   ```bash
   TFM_ALLOWED_ORIGINS=https://trusted-domain.com
   ```

5. **Use short access token lifetimes**
   ```bash
   TFM_ACCESS_TOKEN_MINUTES=15
   ```

6. **Enable trusted host checking**
   ```bash
   TFM_TRUSTED_HOSTS=api.example.com
   ```

7. **Rotate secrets regularly**
   - Schedule periodic JWT secret rotation
   - Invalidate all sessions on rotation

---

## Next Steps

- [Getting Started](Getting-Started) - Initial setup
- [Authentication Guide](Authentication) - Auth configuration details
- [Deployment Guide](Deployment) - Production deployment
- [Troubleshooting](Troubleshooting) - Common configuration issues
