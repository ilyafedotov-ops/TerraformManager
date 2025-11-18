# Getting Started

This guide will help you install and run TerraformManager on your local machine.

## Prerequisites

- **Python 3.11+** - Backend API and CLI
- **Node.js 18+** and **pnpm** - Frontend dashboard
- **Git** - Version control
- **Optional**: Terraform CLI, Infracost, terraform-docs for extended features

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/ilyafedotov-ops/TerraformManager.git
cd TerraformManager
```

### 2. Backend Setup

Create a Python virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Frontend Setup

Install Node.js dependencies:

```bash
cd frontend
pnpm install
cd ..
```

## Running the Application

### Option 1: Service Manager (Recommended)

Use the built-in supervisor to run both services:

```bash
python scripts/service_manager.py start all
```

Check status:
```bash
python scripts/service_manager.py status
```

View logs:
```bash
python scripts/service_manager.py logs api --follow
python scripts/service_manager.py logs frontend --follow
```

Stop services:
```bash
python scripts/service_manager.py stop all
```

### Option 2: Manual Start

**Terminal 1 - Backend:**
```bash
source .venv/bin/activate
python -m api
```

**Terminal 2 - Frontend:**
```bash
cd frontend
pnpm dev -- --open
```

## Accessing the Application

- **Dashboard**: http://localhost:5173
- **API**: http://localhost:8890
- **API Docs**: http://localhost:8890/docs

## Initial Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Authentication
TFM_API_TOKEN=your-secure-token-here
TFM_JWT_SECRET=your-jwt-secret-here

# Server
TFM_PORT=8890

# Logging
TFM_LOG_LEVEL=INFO

# Frontend
VITE_API_BASE=http://localhost:8890
```

See [Configuration](Configuration) for complete environment variable reference.

### Database Initialization

The SQLite database is created automatically on first run at `data/app.db`.

## First Steps

### 1. Create a User Account

Navigate to http://localhost:5173 and register a new account, or use the CLI:

```bash
python -m backend.cli auth login --email admin@example.com --base-url http://localhost:8890
```

### 2. Create Your First Project

In the dashboard:
1. Click "Projects" in the navigation
2. Click "New Project"
3. Fill in project details (name, description, tags)
4. Click "Create"

### 3. Run a Security Scan

Scan an existing Terraform directory:

```bash
python -m backend.cli scan --path /path/to/terraform --out report.json
```

View the report:
- JSON: `cat report.json`
- HTML: `python -m backend.cli scan --path /path/to/terraform --html-out report.html`
- Dashboard: Upload via Projects → Runs → Upload Artifact

### 4. Generate Terraform Code

In the dashboard:
1. Navigate to "Generators"
2. Select a provider (AWS, Azure, or Kubernetes)
3. Choose a template (e.g., "S3 Secure Bucket")
4. Fill in the configuration form
5. Click "Generate"
6. Download or copy the generated Terraform code

## CLI Quick Reference

```bash
# Scan infrastructure
python -m backend.cli scan --path . --out report.json

# Generate baseline waiver
python -m backend.cli baseline --path .

# Create pre-commit hooks
python -m backend.cli precommit --out .pre-commit-config.yaml

# Authenticate CLI
python -m backend.cli auth login --email you@example.com

# Generate docs
python -m backend.cli docs

# Reindex knowledge base
python -m backend.cli reindex
```

See [CLI Reference](CLI-Reference) for complete command documentation.

## Docker Quick Start

Run both API and frontend in a container:

```bash
docker build -t terraform-manager:local .
docker run --rm -p 8890:8890 \
  -e TFM_PORT=8890 \
  -e TFM_API_TOKEN=changeme \
  -v "$(pwd)/knowledge:/app/knowledge" \
  -v "$(pwd)/data:/app/data" \
  terraform-manager:local
```

Or use Docker Compose:

```bash
docker compose up --build
```

Access at http://localhost:8890

## Optional Integrations

### Terraform CLI

Install Terraform to enable:
- `terraform fmt` formatting checks
- `terraform validate` syntax validation

```bash
# macOS
brew install terraform

# Linux
wget https://releases.hashicorp.com/terraform/1.5.0/terraform_1.5.0_linux_amd64.zip
unzip terraform_1.5.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/
```

### Infracost

Install Infracost for cost analysis:

```bash
# macOS
brew install infracost

# Linux
curl -fsSL https://raw.githubusercontent.com/infracost/infracost/master/scripts/install.sh | sh
```

Configure API key:
```bash
infracost configure set api_key YOUR_API_KEY
```

Use in scans:
```bash
python -m backend.cli scan --path . --cost --cost-usage-file usage.yml
```

### terraform-docs

Install terraform-docs for automatic documentation generation:

```bash
# macOS
brew install terraform-docs

# Linux
GO111MODULE="on" go install github.com/terraform-docs/terraform-docs@latest
```

Generate docs:
```bash
python -m backend.cli docs
```

## Troubleshooting

### Port Already in Use

If port 8890 is already taken:
```bash
export TFM_PORT=9000
export PUBLIC_API_PORT=9000
python -m api
```

### Permission Errors

Ensure the `data/` and `logs/` directories are writable:
```bash
chmod -R 755 data/ logs/
```

### Frontend Not Connecting to API

Check the API base URL:
```bash
# In frontend/.env
VITE_API_BASE=http://localhost:8890
```

### Database Issues

Reset the database:
```bash
rm data/app.db
python -m api  # Will recreate on startup
```

## Next Steps

- [Architecture Overview](Architecture) - Understand the system design
- [CLI Reference](CLI-Reference) - Learn all CLI commands
- [API Reference](API-Reference) - Explore the REST API
- [Generators Guide](Generators) - Master Terraform generation
- [Configuration](Configuration) - Configure advanced settings

## Getting Help

- [Troubleshooting](Troubleshooting) - Common issues and solutions
- [GitHub Issues](https://github.com/ilyafedotov-ops/TerraformManager/issues) - Report bugs or request features
- [GitHub Discussions](https://github.com/ilyafedotov-ops/TerraformManager/discussions) - Ask questions
