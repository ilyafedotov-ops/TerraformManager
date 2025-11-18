# Development Guide

Guide for contributing to TerraformManager and setting up a development environment.

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 18+ and pnpm
- Git
- Optional: Terraform CLI, Infracost, terraform-docs

### Clone Repository

```bash
git clone https://github.com/ilyafedotov-ops/TerraformManager.git
cd TerraformManager
```

### Backend Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install runtime dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt
```

### Frontend Setup

```bash
cd frontend
pnpm install
cd ..
```

### Run Development Servers

**Option 1: Service Manager**
```bash
python scripts/service_manager.py start all
```

**Option 2: Manual**
```bash
# Terminal 1 - Backend
source .venv/bin/activate
python -m api

# Terminal 2 - Frontend
cd frontend
pnpm dev -- --open
```

---

## Project Structure

```
TerraformManager/
├── api/                    # FastAPI application
│   ├── main.py            # API entry point
│   └── routes/            # Route handlers
├── backend/               # Core Python modules
│   ├── cli.py            # CLI commands
│   ├── scanner.py        # Policy scanner
│   ├── policies/         # Security policies
│   ├── generators/       # Terraform templates
│   ├── db/               # Database models
│   ├── auth/             # Authentication
│   └── utils/            # Utilities
├── frontend/             # SvelteKit dashboard
│   ├── src/
│   │   ├── routes/       # Pages
│   │   ├── lib/          # Components and utilities
│   │   └── app.html      # HTML template
│   └── tests/            # Frontend tests
├── tests/                # Python tests
├── knowledge/            # Knowledge base docs
├── docs/                 # Technical documentation
├── data/                 # Runtime data
│   ├── app.db           # SQLite database
│   └── projects/        # Project workspaces
├── logs/                # Application logs
└── scripts/             # Development scripts
```

---

## Testing

### Backend Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_scanner.py

# Run with coverage
pytest --cov=backend --cov-report=html

# Run tests requiring terraform
TFM_RUN_TERRAFORM_VALIDATE=1 pytest tests/test_terraform_validate_smoke.py

# Run specific test
pytest tests/test_policies_rules.py::test_aws_s3_encryption
```

### Frontend Tests

```bash
cd frontend

# Run tests
pnpm test

# Run tests in watch mode
pnpm test:watch

# Run with coverage
pnpm test:coverage
```

### Test Structure

```
tests/
├── test_cli_workspace.py           # CLI tests
├── test_generators_golden.py       # Generator golden tests
├── test_generators_render.py       # Template rendering tests
├── test_policies_rules.py          # Policy engine tests
├── test_terraform_validate_smoke.py # Terraform validation tests
├── fixtures/                       # Test fixtures
└── golden/                         # Expected outputs
```

---

## Linting & Formatting

### Unified Linting

```bash
# Run all linters
python scripts/lint.py

# Auto-fix Python issues
python scripts/lint.py --fix
```

### Python Only

```bash
# Check with Ruff
python -m ruff check api backend scripts tests

# Auto-fix
python -m ruff check api backend scripts tests --fix

# Format with Ruff
python -m ruff format api backend scripts tests
```

### Frontend Only

```bash
cd frontend

# Lint
pnpm lint

# Type check
pnpm check

# Format
pnpm format
```

### Pre-commit Hooks

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

---

## Code Style

### Python

**Conventions**:
- PEP 8 compliance
- Type hints for all functions
- Docstrings for public APIs
- Max line length: 100 characters

**Example**:
```python
from typing import List, Optional

def scan_terraform_files(
    path: str,
    config_name: Optional[str] = None,
    enable_cost: bool = False
) -> dict:
    """
    Scan Terraform files for policy violations.

    Args:
        path: Directory containing Terraform files
        config_name: Optional review configuration name
        enable_cost: Enable cost analysis

    Returns:
        Report dictionary with findings and summary

    Raises:
        FileNotFoundError: If path doesn't exist
    """
    # Implementation
    pass
```

**Ruff Configuration** (`pyproject.toml`):
```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM"]
```

### TypeScript/Svelte

**Conventions**:
- ESLint + TypeScript strict mode
- Components in PascalCase
- Utilities in camelCase
- Props interface for components

**Example**:
```typescript
<script lang="ts">
interface Props {
  projectId: string;
  onComplete?: () => void;
}

let { projectId, onComplete }: Props = $props();

async function handleSubmit() {
  // Implementation
}
</script>

<div class="project-card">
  <!-- Template -->
</div>

<style>
.project-card {
  /* Styles */
}
</style>
```

---

## Adding Features

### New Policy Rule

1. **Define Rule** (`backend/policies/aws.py`):

```python
from backend.policies.metadata import register_policy

@register_policy(
    policy_id="AWS-NEW-001",
    severity="high",
    provider="aws",
    resource_type="aws_example",
    description="Check example resource configuration",
    remediation="Configure resource properly"
)
def check_example_resource(resource: dict) -> Optional[str]:
    """Check example resource."""
    if not resource.get("secure_setting"):
        return "Example resource missing secure_setting"
    return None
```

2. **Add Test** (`tests/test_policies_rules.py`):

```python
def test_aws_example_secure():
    resource = {"secure_setting": True}
    result = check_example_resource(resource)
    assert result is None

def test_aws_example_insecure():
    resource = {}
    result = check_example_resource(resource)
    assert "missing secure_setting" in result
```

3. **Add Fixture** (`tests/fixtures/aws_example.tf`):

```hcl
resource "aws_example" "test" {
  secure_setting = true
}
```

### New Generator

1. **Create Template** (`backend/generators/aws_example.tf.j2`):

```jinja2
resource "aws_example" "{{ resource_name }}" {
  name = var.resource_name

  {% if enable_feature %}
  feature {
    enabled = true
  }
  {% endif %}

  tags = var.common_tags
}

variable "resource_name" {
  type        = string
  description = "Name of the resource"
}

variable "common_tags" {
  type        = map(string)
  description = "Common resource tags"
  default     = {}
}
```

2. **Define Model** (`backend/generators/models.py`):

```python
from pydantic import BaseModel

class AWSExampleRequest(BaseModel):
    resource_name: str
    enable_feature: bool = False
    common_tags: dict[str, str] = {}
```

3. **Register** (`backend/generators/registry.py`):

```python
GENERATOR_REGISTRY = {
    # ... existing generators ...
    "aws/example": {
        "name": "AWS Example Resource",
        "provider": "aws",
        "category": "compute",
        "template": "aws_example.tf.j2",
        "model": AWSExampleRequest,
        "description": "Example AWS resource"
    }
}
```

4. **Add Test** (`tests/test_generators_render.py`):

```python
def test_aws_example_basic():
    result = render_generator(
        "aws/example",
        {"resource_name": "test"}
    )
    assert "resource \"aws_example\" \"test\"" in result

def test_aws_example_with_feature():
    result = render_generator(
        "aws/example",
        {"resource_name": "test", "enable_feature": True}
    )
    assert "feature {" in result
```

### New API Endpoint

1. **Create Route Handler** (`api/routes/example.py`):

```python
from fastapi import APIRouter, Depends
from backend.auth.dependencies import get_current_user

router = APIRouter()

@router.get("/example")
async def get_examples(
    current_user = Depends(get_current_user)
):
    """Get examples."""
    return {"examples": []}

@router.post("/example")
async def create_example(
    data: dict,
    current_user = Depends(get_current_user)
):
    """Create example."""
    return {"id": "uuid", "data": data}
```

2. **Register Router** (`api/main.py`):

```python
from api.routes import example

app.include_router(
    example.router,
    prefix="/example",
    tags=["example"]
)
```

3. **Add Frontend Client** (`frontend/src/lib/api/example.ts`):

```typescript
export async function getExamples() {
  const response = await apiClient.get('/example');
  return response.data;
}

export async function createExample(data: any) {
  const response = await apiClient.post('/example', data);
  return response.data;
}
```

---

## Database Migrations

TerraformManager uses SQLAlchemy for database management.

### Creating Models

```python
# backend/db/models.py
from sqlalchemy import Column, String, DateTime
from backend.db.base import Base

class Example(Base):
    __tablename__ = "examples"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)
```

### Applying Changes

Currently using SQLAlchemy Core without migrations. On schema changes:

1. Update model definitions
2. Delete `data/app.db` (development only!)
3. Restart API (recreates tables)

**Future**: Alembic migrations for production.

---

## Debugging

### Backend Debugging

```bash
# Enable debug logging
export TFM_LOG_LEVEL=DEBUG

# Enable SQL logging
export TFM_SQL_ECHO=1

# Run with debugger
python -m pdb -m api
```

### Frontend Debugging

```bash
cd frontend

# Run with source maps
pnpm dev

# Type checking
pnpm check --watch

# Browser DevTools
# Open http://localhost:5173
# F12 → Console/Network/Sources
```

### VS Code Launch Configurations

`.vscode/launch.json`:
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: API",
      "type": "python",
      "request": "launch",
      "module": "api",
      "console": "integratedTerminal",
      "justMyCode": false
    },
    {
      "name": "Python: CLI",
      "type": "python",
      "request": "launch",
      "module": "backend.cli",
      "args": ["scan", "--path", "sample"],
      "console": "integratedTerminal"
    }
  ]
}
```

---

## Contributing

### Workflow

1. **Fork Repository**
2. **Create Feature Branch**
   ```bash
   git checkout -b feature/my-feature
   ```

3. **Make Changes**
   - Write code
   - Add tests
   - Update documentation

4. **Test Changes**
   ```bash
   pytest
   cd frontend && pnpm test
   python scripts/lint.py
   ```

5. **Commit**
   ```bash
   git add .
   git commit -m "feat: add my feature"
   ```

6. **Push**
   ```bash
   git push origin feature/my-feature
   ```

7. **Create Pull Request**

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting
- `refactor`: Code restructuring
- `test`: Adding tests
- `chore`: Maintenance

**Examples**:
```
feat(generators): add AWS Lambda generator

Adds new generator for AWS Lambda functions with:
- VPC configuration
- Environment variables
- IAM role creation

Closes #123
```

```
fix(scanner): handle missing resource attributes

Prevents crashes when resources don't have expected keys.
```

### Pull Request Guidelines

1. **Title**: Clear, descriptive summary
2. **Description**:
   - What changed
   - Why it changed
   - How to test
3. **Tests**: Include test coverage
4. **Documentation**: Update relevant docs
5. **Linting**: All checks passing

---

## Release Process

1. **Update Version** (`pyproject.toml`, `package.json`)
2. **Update CHANGELOG.md**
3. **Run Full Test Suite**
4. **Create Git Tag**
   ```bash
   git tag -a v1.2.0 -m "Release v1.2.0"
   git push origin v1.2.0
   ```
5. **Create GitHub Release**
6. **Build Docker Image**

---

## Resources

- [Architecture Overview](Architecture) - System design
- [API Reference](API-Reference) - Endpoint documentation
- [Testing Guide](https://docs.pytest.org/) - pytest documentation
- [FastAPI Docs](https://fastapi.tiangolo.com/) - Backend framework
- [SvelteKit Docs](https://kit.svelte.dev/) - Frontend framework

---

## Getting Help

- [GitHub Issues](https://github.com/ilyafedotov-ops/TerraformManager/issues) - Bug reports
- [GitHub Discussions](https://github.com/ilyafedotov-ops/TerraformManager/discussions) - Questions
- [Wiki](Home) - Documentation
