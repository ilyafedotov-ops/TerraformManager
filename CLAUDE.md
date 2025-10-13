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
- `backend/rag.py`: TF-IDF knowledge retrieval system

### API Structure (`api/main.py`)
- `/scan`: Main scanning endpoint with optional cost/drift analysis
- `/reports/{id}`: Report retrieval (JSON/HTML/CSV)
- `/configs`: Configuration storage and management
- `/generators/*`: Terraform code generation endpoints
- `/knowledge/*`: Knowledge base search and sync

### Frontend Architecture
- Routes under `(app)/`: Authenticated dashboard pages
- Routes under `(auth)/`: Guest/login flows
- `src/lib/api/`: API client utilities
- `src/lib/stores/`: Svelte state management
- Component-based architecture with TypeScript

## Important Development Patterns

### Configuration Management
- Review configs are YAML files (typically `tfreview.yaml`) that define waivers and thresholds
- Database stores configs via `/configs` endpoints
- CLI discovers configs automatically, API requires explicit config names

### Authentication Flow
- Supports both legacy API tokens and modern JWT + refresh token flow
- Environment variables control token lifetimes and cookie settings
- Frontend stores tokens in cookies/local storage with CSRF protection

### LLM Integration
- Configurable AI explanations and patch suggestions (OpenAI/Azure)
- Settings stored in database via `/settings/llm` endpoint
- LLM requests are rate-limited and error-handled gracefully

### Terraform Integration
- Optional `terraform validate` and `terraform fmt` integration
- Infracost integration for cost analysis
- Plan JSON parsing for drift detection

## File Structure Conventions

- `backend/generators/*.tf.j2`: Jinja2 templates for Terraform generation
- `knowledge/`: Markdown files for RAG knowledge base
- `sample/`: Example Terraform files for testing
- `tests/`: Python test suite (pytest + unittest)
- `frontend/src/lib/`: Shared utilities and API clients
- `docs/`: Generated documentation and schemas

## Environment Configuration

Key environment variables:
- `TFM_API_TOKEN`: Legacy authentication token
- `TFM_JWT_SECRET`: JWT signing secret
- `TFM_PORT`: API server port (default: 8890)
- `TFM_RUN_TERRAFORM_VALIDATE=1`: Enable terraform validation in tests
- `VITE_API_BASE`: Frontend API base URL (default: http://localhost:8890)

## Database Schema

- `reports`: Scan results with metadata
- `configs`: Review configuration storage
- `settings`: LLM and other user preferences
- `users`: Authentication users and scopes