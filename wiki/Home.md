# TerraformManager Wiki

Welcome to the TerraformManager documentation wiki. TerraformManager is an IaC co-pilot that combines a modern SvelteKit workspace with a FastAPI backend to help teams generate secure Terraform blueprints, review existing infrastructure, and curate reusable assets.

## Quick Navigation

### Getting Started
- [Getting Started](Getting-Started) - Installation, setup, and first steps
- [Architecture Overview](Architecture) - System design and component interactions
- [Deployment Guide](Deployment) - Docker, production deployment, and service management

### Core Features
- [CLI Reference](CLI-Reference) - Command-line interface usage and examples
- [API Reference](API-Reference) - REST API endpoints and authentication
- [Generators Guide](Generators) - Terraform code generation templates and blueprints
- [Configuration](Configuration) - Environment variables and config file reference

### Advanced Topics
- [Authentication](Authentication) - JWT flow, tokens, and session management
- [Development Guide](Development) - Contributing, testing, and development workflow
- [Knowledge Base](Knowledge-Base) - RAG system and best practices documentation
- [Troubleshooting](Troubleshooting) - Common issues and solutions

## Key Capabilities

### 1. Terraform Generation
Generate production-ready Terraform code for:
- **AWS**: S3, VPC, EKS, ECS, RDS, ALB/WAF, Observability, IRSA
- **Azure**: Storage, AKS, Key Vault, Service Bus, Functions, API Management, Diagnostics, VNet
- **Kubernetes**: Deployments, Namespaces, Pod Security, Argo CD, HPA/PDB

All generators follow cloud provider best practices and security standards.

### 2. Infrastructure Review
- Policy-based scanning for AWS, Azure, and Kubernetes resources
- Security and compliance checks aligned with CIS benchmarks
- Drift detection from Terraform plan JSON
- Cost analysis integration with Infracost
- HTML/CSV/JSON report exports

### 3. Project Workspace
- Browser-based project management
- Run tracking and artifact storage
- Version control for generated assets
- Metadata tagging and search

### 4. Knowledge & AI
- TF-IDF knowledge base search over curated Markdown docs
- Optional LLM integration for explanations and autofix suggestions
- Context-aware recommendations based on project metadata

## Quick Start

```bash
# Backend setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m api

# Frontend setup (separate terminal)
cd frontend
pnpm install
pnpm dev -- --open
```

Access the dashboard at http://localhost:5173 and API at http://localhost:8890.

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────┐
│  Clients                                                │
│  ┌──────────────────────┐  ┌─────────────────────────┐ │
│  │ SvelteKit Dashboard  │  │ CLI Commands            │ │
│  │ frontend/            │  │ python -m backend.cli   │ │
│  └──────────┬───────────┘  └──────────┬──────────────┘ │
└─────────────┼──────────────────────────┼────────────────┘
              │                          │
              │ REST API                 │ Direct + REST
              ▼                          ▼
     ┌────────────────────────────────────────────┐
     │  FastAPI Service (api/main.py)             │
     │  ┌──────────┐ ┌────────┐ ┌──────────────┐ │
     │  │ Scanner  │ │ Auth   │ │ Generators   │ │
     │  └──────────┘ └────────┘ └──────────────┘ │
     └────────────────────────────────────────────┘
              │              │              │
              ▼              ▼              ▼
     ┌──────────────┐ ┌──────────┐ ┌─────────────┐
     │ Policies     │ │ Database │ │ Knowledge   │
     │ backend/     │ │ SQLite   │ │ RAG (TF-IDF)│
     │ policies/    │ │          │ │ knowledge/  │
     └──────────────┘ └──────────┘ └─────────────┘
```

## Common Workflows

### Scanning Infrastructure
```bash
python -m backend.cli scan --path . --out report.json \
  --terraform-fmt --terraform-validate --cost
```

### Generating Terraform
Use the web UI generator wizard or CLI:
```bash
python -m backend.cli project generator \
  --project-id <uuid> \
  --slug aws/s3-secure-bucket \
  --payload payloads/s3.json
```

### Creating Baselines
```bash
python -m backend.cli baseline --path .
```

## Project Structure

- `api/` - FastAPI application and route handlers
- `backend/` - Core Python modules (scanner, generators, policies, CLI)
- `frontend/` - SvelteKit dashboard application
- `knowledge/` - Markdown knowledge base for RAG
- `docs/` - Technical documentation and schemas
- `tests/` - Python test suite (pytest)
- `data/` - Workspace for projects, reports, and database

## Resources

- [GitHub Repository](https://github.com/ilyafedotov-ops/TerraformManager)
- [Report an Issue](https://github.com/ilyafedotov-ops/TerraformManager/issues)
- [Latest Release](https://github.com/ilyafedotov-ops/TerraformManager/releases)

## Contributing

See the [Development Guide](Development) for information on:
- Setting up your development environment
- Running tests and linters
- Code style and conventions
- Submitting pull requests
