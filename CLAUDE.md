# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TerraformManager is a RAG/LLM-friendly GUI + CLI tool for:
1. **Generate Terraform** via wizard (AWS, Azure, On-Prem/Kubernetes)
2. **Review** `.tf` files for best practices/security and produce fix reports
3. **Validate syntax** (HCL parse) and optional `terraform fmt`/`terraform validate`
4. **CI pipeline** integration for automated review

## Core Architecture

- **Backend (Python)**: FastAPI service with scanner, generator, and auth modules
- **Frontend (SvelteKit)**: Modern dashboard UI for generator, reviewer, and knowledge workflows
- **CLI**: Command-line interface for scanning, baseline generation, and CI integration
- **Database**: SQLAlchemy with SQLite for config/report storage
- **RAG**: Local TF-IDF retrieval over `knowledge/` directory for AI assistance

## Common Development Commands

### Backend API Development
```bash
# Set up Python environment
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run API server
python -m api  # or uvicorn api.main:app --reload --port 8890

# Run CLI commands
python -m backend.cli scan --path . --out report.json
python -m backend.cli baseline --path .
python -m backend.cli precommit --out .pre-commit-config.yaml
```

### Frontend Development
```bash
cd frontend
pnpm install
pnpm dev -- --open    # Runs on http://localhost:5173
pnpm build             # Production build
pnpm check             # Type checking + linting
pnpm test              # Run tests
```

### Testing
```bash
# Python tests
pytest                               # Run all tests
pytest tests/test_terraform_validate_smoke.py  # Specific test
TFM_RUN_TERRAFORM_VALIDATE=1 pytest  # Tests that require terraform binary

# Frontend tests
cd frontend && pnpm test
```

### Linting
```bash
# Unified linting (Python + Frontend)
python scripts/lint.py              # Run all linters
python scripts/lint.py --fix        # Auto-fix Python issues

# Python only
python -m ruff check api backend scripts tests
python -m ruff check api backend scripts tests --fix

# Frontend only
cd frontend && pnpm lint
```

### Service Manager
```bash
# Start both API and frontend with supervisor
python scripts/service_manager.py start all
python scripts/service_manager.py status
python scripts/service_manager.py logs api --follow
python scripts/service_manager.py restart frontend
python scripts/service_manager.py stop all
```

### Docker Development
```bash
docker build -t terraform-manager:local .
docker run --rm -p 8890:8890 \
  -e TFM_PORT=8890 \
  -e TFM_API_TOKEN=changeme \
  -v "$(pwd)/knowledge:/app/knowledge" \
  -v "$(pwd)/data:/app/data" \
  terraform-manager:local

# Or with docker-compose
docker compose up --build
```

## Key Modules and Components

### Backend Core
- `backend/scanner.py`: Main scanning engine that processes `.tf` files
- `backend/cli.py`: Command-line interface with scan/baseline/precommit commands
- `backend/policies/`: Rule definitions and configuration management
- `backend/generators/`: Jinja2 templates for Terraform code generation
- `backend/auth/`: Authentication system with JWT tokens
- `backend/db/`: SQLAlchemy models and database utilities
- `backend/storage.py`: High-level persistence layer for configs, reports, projects, and assets
- `backend/rag.py`: TF-IDF knowledge retrieval system
- `backend/llm_service.py`: OpenAI/Azure integration for explanations and patches
- `backend/validators.py`: Terraform fmt/validate integration
- `backend/costs/`: Infracost integration
- `backend/drift/`: Terraform plan JSON parsing

### API Structure (`api/main.py`)
- `/scan`: Main scanning endpoint with optional cost/drift analysis
- `/reports/{id}`: Report retrieval (JSON/HTML/CSV)
- `/configs`: Configuration storage and management
- `/generators/*`: Terraform code generation endpoints
- `/knowledge/*`: Knowledge base search and sync
- `/projects`: Project workspace management (CRUD, runs, artifacts)
- `/auth/*`: Authentication endpoints (login, refresh, register, sessions)
- `/settings/llm`: LLM configuration and testing

### Frontend Architecture
- Routes under `(app)/`: Authenticated dashboard pages
- Routes under `(auth)/`: Guest/login flows
- `src/lib/api/`: API client utilities
- `src/lib/stores/`: Svelte state management
- Component-based architecture with TypeScript

## Important Development Patterns

### Project Workspace Management
- All project files live under `data/projects/<slug>/` managed by `backend/storage.py`
- API endpoints enforce path validation to prevent directory traversal
- CLI can scan arbitrary paths but should point to workspace paths for API parity
- Override root with `TERRAFORM_MANAGER_PROJECTS_ROOT` environment variable

### Configuration Management
- Review configs are YAML files (typically `tfreview.yaml`) that define waivers and thresholds
- Database stores configs via `/configs` endpoints
- CLI discovers configs automatically, API requires explicit config names

### Authentication Flow
- Supports both legacy API tokens and modern JWT + refresh token flow
- Environment variables control token lifetimes and cookie settings
- Frontend stores tokens in cookies/local storage with CSRF protection
- Service user created automatically when `TFM_API_TOKEN` is set

### LLM Integration
- Configurable AI explanations and patch suggestions (OpenAI/Azure)
- Settings stored in database via `/settings/llm` endpoint
- LLM requests are rate-limited and error-handled gracefully
- File-backed cache at `LLM_CACHE_DIR`

### Terraform Integration
- Optional `terraform validate` and `terraform fmt` integration
- Infracost integration for cost analysis
- Plan JSON parsing for drift detection
- Requires terraform binary on PATH for validation tests

## File Structure Conventions

- `backend/generators/*.tf.j2`: Jinja2 templates for Terraform generation
- `knowledge/`: Markdown files for RAG knowledge base
- `sample/`: Example Terraform files for testing
- `tests/`: Python test suite (pytest + unittest)
- `frontend/src/lib/`: Shared utilities and API clients
- `docs/`: Generated documentation and schemas
- `data/projects/`: Managed workspace for project files
- `logs/`: Service manager and application logs (JSON structured)

## Environment Configuration

### Core Settings
- `TFM_PORT` / `PORT`: API server port (default: 8890)
- `TFM_API_TOKEN`: Legacy authentication token
- `TFM_JWT_SECRET`: JWT signing secret
- `TFM_REFRESH_SECRET`: Optional distinct secret for refresh tokens
- `VITE_API_BASE`: Frontend API base URL (default: http://localhost:8890)
- `TERRAFORM_MANAGER_PROJECTS_ROOT`: Override project workspace root

### Authentication
- `TFM_ACCESS_TOKEN_MINUTES`: Access token lifetime (default: 30)
- `TFM_REFRESH_TOKEN_MINUTES`: Refresh token lifetime (default: 10080)
- `TFM_COOKIE_SECURE`: Set `true` in production for Secure cookies
- `TFM_COOKIE_DOMAIN`: Optional cookie domain
- `TFM_COOKIE_SAMESITE`: SameSite mode (default: lax)
- `TFM_SERVICE_USER_EMAIL`: Service user email (default: service@local)

### Logging and Observability
- `TFM_LOG_LEVEL`: Log level (DEBUG/INFO/WARN/ERROR, default: INFO)
- `TFM_LOG_DIR`: Log directory (default: logs)
- `TFM_LOG_FILE`: Override log file path or disable
- `TFM_LOG_FILE_MAX_BYTES`: Rotation threshold (default: 5MB)
- `TFM_LOG_FILE_BACKUP_COUNT`: Retained rotated files (default: 5)

### CORS and Security
- `TFM_ALLOWED_ORIGINS`: Comma-separated dashboard origins for CORS
- `TFM_TRUSTED_HOSTS`: Optional hostname allowlist for TrustedHostMiddleware
- `PUBLIC_API_BASE`: Force frontend to use specific API origin
- `PUBLIC_API_PORT`: Override API port detection

### Optional Features
- `TFM_RUN_TERRAFORM_VALIDATE`: Enable terraform validation in tests
- `TFM_SQL_ECHO` / `SQLALCHEMY_ECHO`: Log SQL queries
- `LLM_CACHE_DIR`: Override LLM response cache location

## Database Schema

- `reports`: Scan results with metadata and timestamps
- `report_comments`: User comments on specific findings
- `configs`: Review configuration storage
- `settings`: LLM and other user preferences
- `users`: Authentication users and scopes
- `projects`: Project metadata and configuration
- `project_runs`: Scan runs within projects
- `project_configs`: Project-specific review configs
- `project_artifacts`: Files generated or uploaded during runs
- `generated_assets`: Reusable Terraform assets promoted from runs
- `generated_asset_versions`: Versioned snapshots of assets

## CLI Commands Reference

- `scan`: Run policy scanner with optional fmt/validate/cost/drift
- `baseline`: Generate waiver YAML from current findings
- `precommit`: Scaffold `.pre-commit-config.yaml` for Terraform workflows
- `docs`: Render terraform-docs output and mirror to knowledge base
- `auth login`: Authenticate CLI against API and store tokens
- `reindex`: Rebuild TF-IDF knowledge index

## Generator Templates

Available in `backend/generators/`:
- **AWS**: S3, VPC, EKS, ECS, RDS, ALB/WAF, Observability, IRSA
- **Azure**: Storage, AKS, Key Vault, Service Bus, Functions, API Management, Diagnostics, VNet
- **Kubernetes**: Deployments, Namespaces, Pod Security, Argo CD, HPA/PDB, PSA

Blueprint bundler combines multiple templates with environment placeholders and remote state backends.
