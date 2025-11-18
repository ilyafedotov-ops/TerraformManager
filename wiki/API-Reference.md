# API Reference

TerraformManager provides a RESTful API built with FastAPI for all core operations.

## Base URL

**Development**: `http://localhost:8890`
**Production**: Configure via `PUBLIC_API_BASE` environment variable

## Interactive Documentation

- **Swagger UI**: `http://localhost:8890/docs`
- **ReDoc**: `http://localhost:8890/redoc`

## Authentication

See [Authentication Guide](Authentication) for detailed information.

### Methods

1. **JWT Bearer Token** (Recommended)
   ```http
   Authorization: Bearer <access_token>
   ```

2. **API Token** (Legacy)
   ```http
   X-API-Token: <api_token>
   ```
   or
   ```http
   Authorization: Bearer <api_token>
   ```

### Obtaining Tokens

**Login**:
```http
POST /auth/token
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=secret
```

**Response**:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800,
  "refresh_token_csrf": "abc123..."
}
```

**Refresh**:
```http
POST /auth/refresh
Cookie: tm_refresh_token=<refresh_token>
X-Refresh-Token-CSRF: <csrf_token>
```

---

## Endpoints

### Health & Info

#### GET /health

Health check endpoint.

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### GET /

API metadata and version information.

**Response**:
```json
{
  "name": "TerraformManager API",
  "version": "1.0.0",
  "docs": "/docs"
}
```

---

### Scanning

#### POST /scan

Run policy scanner on Terraform files.

**Request Body**:
```json
{
  "path": "terraform/",
  "config_name": "default",
  "terraform_fmt": true,
  "terraform_validate": true,
  "enable_cost": true,
  "cost_usage_file": "usage.yml",
  "plan_json_path": "plan.json",
  "project_id": "uuid-optional"
}
```

**Response**:
```json
{
  "report_id": "uuid",
  "summary": {
    "total_files": 10,
    "total_findings": 5,
    "by_severity": {
      "high": 2,
      "medium": 2,
      "low": 1
    }
  },
  "findings": [...],
  "cost_summary": {...},
  "drift_summary": {...}
}
```

#### POST /scan/upload

Upload and scan Terraform files.

**Request**: `multipart/form-data`

**Form Fields**:
- `files`: Terraform files (multiple)
- `plan_json`: Plan JSON file (optional)
- `cost_usage`: Infracost usage file (optional)
- `config_name`: Config name (optional)
- `project_id`: Project UUID (optional)

**Response**: Same as `/scan`

---

### Reports

#### GET /reports

List all scan reports.

**Query Parameters**:
- `skip`: Offset (default: 0)
- `limit`: Page size (default: 100)
- `project_id`: Filter by project

**Response**:
```json
{
  "total": 50,
  "items": [
    {
      "id": "uuid",
      "created_at": "2024-01-15T10:00:00Z",
      "path": "terraform/",
      "total_findings": 5,
      "summary": {...}
    }
  ]
}
```

#### GET /reports/{id}

Get report by ID.

**Response**:
```json
{
  "id": "uuid",
  "created_at": "2024-01-15T10:00:00Z",
  "summary": {...},
  "findings": [...],
  "metadata": {...}
}
```

#### GET /reports/{id}/html

Get report as HTML.

**Response**: HTML document

#### GET /reports/{id}/csv

Get report as CSV.

**Response**: CSV file

#### DELETE /reports/{id}

Delete a report.

**Response**:
```json
{
  "message": "Report deleted successfully"
}
```

---

### Configurations

#### GET /configs

List all review configurations.

**Response**:
```json
{
  "items": [
    {
      "name": "default",
      "content": "...",
      "created_at": "2024-01-15T10:00:00Z"
    }
  ]
}
```

#### POST /configs

Create or update a configuration.

**Request Body**:
```json
{
  "name": "production",
  "content": "waivers:\n  - policy_id: AWS-S3-001\n    reason: Legacy bucket"
}
```

**Response**:
```json
{
  "message": "Configuration saved successfully",
  "name": "production"
}
```

#### GET /configs/{name}

Get configuration by name.

**Response**:
```json
{
  "name": "production",
  "content": "...",
  "created_at": "2024-01-15T10:00:00Z"
}
```

#### DELETE /configs/{name}

Delete a configuration.

**Response**:
```json
{
  "message": "Configuration deleted successfully"
}
```

---

### Generators

#### GET /generators/metadata

List all available generators.

**Response**:
```json
{
  "generators": [
    {
      "slug": "aws/s3-secure-bucket",
      "name": "S3 Secure Bucket",
      "provider": "aws",
      "category": "storage",
      "description": "...",
      "schema": {...}
    }
  ]
}
```

#### POST /generators/aws/s3

Generate AWS S3 bucket configuration.

**Request Body**:
```json
{
  "bucket_name": "my-secure-bucket",
  "enable_versioning": true,
  "enable_encryption": true,
  "enable_logging": true,
  "log_bucket": "logs-bucket"
}
```

**Response**:
```json
{
  "code": "resource \"aws_s3_bucket\" ...",
  "files": {
    "main.tf": "...",
    "variables.tf": "...",
    "outputs.tf": "..."
  }
}
```

#### POST /generators/blueprints

Generate multi-environment blueprint bundle.

**Request Body**:
```json
{
  "name": "production-infrastructure",
  "environments": ["dev", "staging", "prod"],
  "components": [
    {
      "slug": "aws/vpc-networking",
      "payload": {...}
    },
    {
      "slug": "aws/eks-cluster",
      "payload": {...}
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

**Response**:
```json
{
  "files": {...},
  "archive_base64": "UEsDBBQ...",
  "archive_filename": "production-infrastructure.zip"
}
```

---

### Projects

#### GET /projects

List all projects.

**Query Parameters**:
- `skip`: Offset (default: 0)
- `limit`: Page size (default: 100)

**Response**:
```json
{
  "total": 10,
  "items": [
    {
      "id": "uuid",
      "slug": "production-infra",
      "name": "Production Infrastructure",
      "description": "...",
      "tags": ["terraform", "aws"],
      "created_at": "2024-01-15T10:00:00Z"
    }
  ]
}
```

#### POST /projects

Create a new project.

**Request Body**:
```json
{
  "name": "Production Infrastructure",
  "slug": "production-infra",
  "description": "AWS production environment",
  "tags": ["terraform", "aws", "production"]
}
```

**Response**:
```json
{
  "id": "uuid",
  "slug": "production-infra",
  "name": "Production Infrastructure",
  "created_at": "2024-01-15T10:00:00Z"
}
```

#### GET /projects/{id}

Get project by ID or slug.

**Response**:
```json
{
  "id": "uuid",
  "slug": "production-infra",
  "name": "Production Infrastructure",
  "description": "...",
  "tags": [...],
  "metadata": {...},
  "stats": {
    "total_runs": 15,
    "total_artifacts": 50
  }
}
```

#### PATCH /projects/{id}

Update project.

**Request Body**:
```json
{
  "name": "Updated Name",
  "description": "Updated description",
  "tags": ["new", "tags"]
}
```

**Response**: Updated project object

#### DELETE /projects/{id}

Delete a project and all associated data.

**Response**:
```json
{
  "message": "Project deleted successfully"
}
```

#### GET /projects/{id}/runs

List project runs.

**Response**:
```json
{
  "total": 20,
  "items": [
    {
      "id": "uuid",
      "project_id": "uuid",
      "run_number": 15,
      "status": "completed",
      "created_at": "2024-01-15T10:00:00Z",
      "artifact_count": 5
    }
  ]
}
```

#### POST /projects/{id}/runs

Create a new run.

**Request Body**:
```json
{
  "name": "Scan #15",
  "metadata": {
    "branch": "main",
    "commit": "abc123"
  }
}
```

**Response**:
```json
{
  "id": "uuid",
  "project_id": "uuid",
  "run_number": 15,
  "created_at": "2024-01-15T10:00:00Z"
}
```

#### GET /projects/{id}/runs/{run_id}/artifacts

List run artifacts.

**Response**:
```json
{
  "items": [
    {
      "id": "uuid",
      "filename": "report.json",
      "path": "reports/report.json",
      "size": 12345,
      "tags": ["report", "automated"],
      "created_at": "2024-01-15T10:00:00Z"
    }
  ]
}
```

#### POST /projects/{id}/runs/{run_id}/artifacts

Upload artifact to run.

**Request**: `multipart/form-data`

**Form Fields**:
- `file`: File to upload
- `path`: Destination path in workspace
- `tags`: JSON array of tags (optional)
- `metadata`: JSON object (optional)

**Response**:
```json
{
  "id": "uuid",
  "filename": "report.json",
  "path": "reports/report.json",
  "size": 12345
}
```

#### GET /projects/{id}/runs/{run_id}/artifacts/{artifact_id}

Download artifact.

**Response**: File download

#### DELETE /projects/{id}/runs/{run_id}/artifacts/{artifact_id}

Delete artifact.

**Response**:
```json
{
  "message": "Artifact deleted successfully"
}
```

---

### Knowledge

#### POST /knowledge/sync

Sync knowledge base from GitHub.

**Request Body**:
```json
{
  "repo_url": "https://github.com/user/terraform-docs",
  "branch": "main",
  "target_dir": "terraform"
}
```

**Response**:
```json
{
  "message": "Knowledge base synced successfully",
  "files_added": 10,
  "files_updated": 5
}
```

#### GET /knowledge/search

Search knowledge base.

**Query Parameters**:
- `q`: Search query
- `limit`: Max results (default: 10)

**Response**:
```json
{
  "results": [
    {
      "filename": "aws_best_practices.md",
      "score": 0.85,
      "snippet": "...",
      "url": "/knowledge/doc?path=aws_best_practices.md"
    }
  ]
}
```

#### GET /knowledge/doc

Get knowledge document.

**Query Parameters**:
- `path`: Document path

**Response**:
```json
{
  "filename": "aws_best_practices.md",
  "content": "# AWS Best Practices\n...",
  "metadata": {...}
}
```

---

### LLM Settings

#### GET /settings/llm

Get LLM configuration.

**Response**:
```json
{
  "provider": "openai",
  "model": "gpt-4",
  "enable_explanations": true,
  "enable_patches": true,
  "api_key_configured": true
}
```

#### POST /settings/llm

Update LLM configuration.

**Request Body**:
```json
{
  "provider": "azure",
  "model": "gpt-4",
  "enable_explanations": true,
  "enable_patches": false,
  "api_key": "sk-...",
  "azure_endpoint": "https://example.openai.azure.com/"
}
```

**Response**:
```json
{
  "message": "LLM settings saved successfully"
}
```

#### POST /settings/llm/test

Test LLM configuration.

**Request Body**:
```json
{
  "prompt": "Explain S3 bucket encryption best practices"
}
```

**Response**:
```json
{
  "success": true,
  "response": "...",
  "latency_ms": 450
}
```

---

### Authentication

#### POST /auth/token

Login and obtain access token.

**Request Body** (form-encoded):
```
username=user@example.com
password=secret
```

**Response**:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800,
  "refresh_token_csrf": "abc123..."
}
```

**Sets Cookie**: `tm_refresh_token` (HttpOnly)

#### POST /auth/refresh

Refresh access token.

**Headers**:
- `Cookie`: `tm_refresh_token=<token>`
- `X-Refresh-Token-CSRF`: `<csrf_token>`

**Response**:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800,
  "refresh_token_csrf": "new_csrf..."
}
```

#### POST /auth/logout

Logout and revoke session.

**Headers**:
- `Authorization`: `Bearer <access_token>`

**Response**:
```json
{
  "message": "Logged out successfully"
}
```

#### GET /auth/me

Get current user information.

**Response**:
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "scopes": ["read", "write"],
  "created_at": "2024-01-15T10:00:00Z"
}
```

#### GET /auth/sessions

List active sessions.

**Response**:
```json
{
  "sessions": [
    {
      "id": "uuid",
      "created_at": "2024-01-15T10:00:00Z",
      "last_used": "2024-01-15T12:00:00Z",
      "user_agent": "...",
      "ip_address": "192.168.1.1"
    }
  ]
}
```

#### DELETE /auth/sessions/{id}

Revoke a session.

**Response**:
```json
{
  "message": "Session revoked successfully"
}
```

#### POST /auth/register

Register new user.

**Request Body**:
```json
{
  "email": "newuser@example.com",
  "password": "securepassword123",
  "full_name": "John Doe"
}
```

**Response**:
```json
{
  "id": "uuid",
  "email": "newuser@example.com",
  "created_at": "2024-01-15T10:00:00Z"
}
```

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message",
  "error_code": "ERROR_CODE",
  "timestamp": "2024-01-15T10:00:00Z"
}
```

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 204 | No Content |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 409 | Conflict |
| 422 | Validation Error |
| 429 | Rate Limit Exceeded |
| 500 | Internal Server Error |

## Rate Limiting

Authentication endpoints are rate-limited:
- Login: 5 requests per minute
- Refresh: 10 requests per minute
- Register: 3 requests per minute

**Rate Limit Headers**:
```http
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 3
X-RateLimit-Reset: 1705315200
```

## Pagination

List endpoints support pagination:

**Query Parameters**:
- `skip`: Number of items to skip (default: 0)
- `limit`: Max items to return (default: 100, max: 1000)

**Response Headers**:
```http
X-Total-Count: 150
Link: </api/resource?skip=100&limit=100>; rel="next"
```

## CORS

Configure allowed origins via `TFM_ALLOWED_ORIGINS`:

```bash
export TFM_ALLOWED_ORIGINS="https://app.example.com,https://dashboard.example.com"
```

## Webhooks (Future)

Webhook support is planned for:
- Scan completion
- Report generation
- Project updates

## SDKs (Future)

Official SDKs planned for:
- Python
- TypeScript/JavaScript
- Go

## Next Steps

- [Authentication Guide](Authentication) - Detailed auth flow
- [CLI Reference](CLI-Reference) - Command-line alternative
- [Configuration](Configuration) - API server configuration
- [Development Guide](Development) - Building API extensions
