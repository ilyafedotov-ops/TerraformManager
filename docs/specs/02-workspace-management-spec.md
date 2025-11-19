# Workspace Management Implementation Specification

## Overview
Enable TerraformManager to discover, manage, and operate across Terraform workspaces. Workspaces allow managing multiple environments (dev, staging, prod) with the same Terraform configuration.

## Goals
- Discover and list workspaces in a directory
- Create, select, and delete workspaces
- Scan across multiple workspaces
- Environment-specific configuration management
- Workspace comparison and consistency checks
- Multi-workspace deployment tracking

---

## Database Schema

### New Tables

#### `terraform_workspaces`
Track discovered workspaces per project.

```sql
CREATE TABLE terraform_workspaces (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    name TEXT NOT NULL,
    working_directory TEXT NOT NULL, -- Relative to project root
    is_default BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT FALSE, -- Currently selected workspace
    created_at TIMESTAMP,
    selected_at TIMESTAMP,
    last_scanned_at TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    UNIQUE(project_id, working_directory, name)
);
CREATE INDEX idx_workspaces_project ON terraform_workspaces(project_id);
CREATE INDEX idx_workspaces_active ON terraform_workspaces(project_id, is_active);
```

#### `workspace_variables`
Environment-specific variables per workspace.

```sql
CREATE TABLE workspace_variables (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT, -- Encrypted if sensitive
    sensitive BOOLEAN DEFAULT FALSE,
    source TEXT, -- 'tfvars', 'env', 'manual'
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (workspace_id) REFERENCES terraform_workspaces(id) ON DELETE CASCADE,
    UNIQUE(workspace_id, key)
);
CREATE INDEX idx_workspace_vars_workspace ON workspace_variables(workspace_id);
```

#### `workspace_comparisons`
Workspace comparison results for consistency checks.

```sql
CREATE TABLE workspace_comparisons (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    workspace_a_id TEXT NOT NULL,
    workspace_b_id TEXT NOT NULL,
    comparison_type TEXT NOT NULL, -- 'config', 'state', 'variables'
    differences_count INTEGER DEFAULT 0,
    differences TEXT, -- JSON: detailed differences
    compared_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (workspace_a_id) REFERENCES terraform_workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (workspace_b_id) REFERENCES terraform_workspaces(id) ON DELETE CASCADE
);
CREATE INDEX idx_workspace_comparisons_project ON workspace_comparisons(project_id);
```

### Schema Updates

#### Update `project_runs` table
Add workspace field to track which workspace was used for the run.

```sql
ALTER TABLE project_runs ADD COLUMN workspace TEXT DEFAULT 'default';
CREATE INDEX idx_project_runs_workspace ON project_runs(workspace);
```

#### Update `terraform_states` table
Already has workspace field, ensure index exists.

```sql
CREATE INDEX IF NOT EXISTS idx_terraform_states_workspace ON terraform_states(project_id, workspace);
```

---

## Backend Architecture

### Module Structure

```
backend/
├── workspaces/
│   ├── __init__.py
│   ├── manager.py        # Workspace operations (list, create, select, delete)
│   ├── scanner.py        # Multi-workspace scanning
│   ├── comparator.py     # Compare workspaces for consistency
│   ├── variables.py      # Workspace-specific variable management
│   └── models.py         # Pydantic models
```

### Core Components

#### `backend/workspaces/manager.py`

```python
from pathlib import Path
import subprocess
from typing import List, Dict, Any, Optional
import json

class WorkspaceManager:
    """Manage Terraform workspaces."""

    @staticmethod
    def list_workspaces(working_dir: Path) -> List[str]:
        """List all workspaces in directory."""
        result = subprocess.run(
            ['terraform', 'workspace', 'list'],
            cwd=working_dir,
            capture_output=True,
            text=True,
            check=True
        )

        workspaces = []
        for line in result.stdout.splitlines():
            # Output format: "  default" or "* production"
            workspace = line.strip().lstrip('*').strip()
            if workspace:
                workspaces.append(workspace)

        return workspaces

    @staticmethod
    def get_current_workspace(working_dir: Path) -> str:
        """Get currently active workspace."""
        result = subprocess.run(
            ['terraform', 'workspace', 'show'],
            cwd=working_dir,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()

    @staticmethod
    def create_workspace(working_dir: Path, name: str) -> bool:
        """Create new workspace."""
        try:
            subprocess.run(
                ['terraform', 'workspace', 'new', name],
                cwd=working_dir,
                capture_output=True,
                text=True,
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False

    @staticmethod
    def select_workspace(working_dir: Path, name: str) -> bool:
        """Select/switch to workspace."""
        try:
            subprocess.run(
                ['terraform', 'workspace', 'select', name],
                cwd=working_dir,
                capture_output=True,
                text=True,
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False

    @staticmethod
    def delete_workspace(working_dir: Path, name: str) -> bool:
        """Delete workspace."""
        if name == 'default':
            raise ValueError("Cannot delete default workspace")

        # Must select different workspace first
        current = WorkspaceManager.get_current_workspace(working_dir)
        if current == name:
            WorkspaceManager.select_workspace(working_dir, 'default')

        try:
            subprocess.run(
                ['terraform', 'workspace', 'delete', name],
                cwd=working_dir,
                capture_output=True,
                text=True,
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False

    @staticmethod
    def discover_workspaces(project_root: Path) -> Dict[str, List[str]]:
        """Discover workspaces in all terraform directories."""
        discovered = {}

        for tf_dir in project_root.rglob('*.tf'):
            working_dir = tf_dir.parent
            if working_dir in discovered:
                continue

            try:
                workspaces = WorkspaceManager.list_workspaces(working_dir)
                relative_path = working_dir.relative_to(project_root)
                discovered[str(relative_path)] = workspaces
            except Exception:
                continue

        return discovered
```

#### `backend/workspaces/scanner.py`

```python
from pathlib import Path
from typing import List, Dict, Any
from backend.scanner import scan_paths
from backend.workspaces.manager import WorkspaceManager

class MultiWorkspaceScanner:
    """Scan across multiple workspaces."""

    @staticmethod
    def scan_all_workspaces(
        working_dir: Path,
        workspaces: List[str],
        config_name: str | None = None,
        run_validate: bool = False,
    ) -> Dict[str, Any]:
        """Scan all workspaces and aggregate results."""
        results = {}
        aggregate_stats = {
            'total_files': 0,
            'total_findings': 0,
            'critical_findings': 0,
            'high_findings': 0,
        }

        original_workspace = WorkspaceManager.get_current_workspace(working_dir)

        try:
            for workspace in workspaces:
                # Switch to workspace
                WorkspaceManager.select_workspace(working_dir, workspace)

                # Scan
                scan_result = scan_paths(
                    paths=[working_dir],
                    config_name=config_name,
                    run_validate=run_validate,
                )

                results[workspace] = scan_result

                # Aggregate stats
                aggregate_stats['total_files'] += scan_result.get('file_count', 0)
                aggregate_stats['total_findings'] += len(scan_result.get('findings', []))

                for finding in scan_result.get('findings', []):
                    if finding['severity'] == 'critical':
                        aggregate_stats['critical_findings'] += 1
                    elif finding['severity'] == 'high':
                        aggregate_stats['high_findings'] += 1

        finally:
            # Restore original workspace
            WorkspaceManager.select_workspace(working_dir, original_workspace)

        return {
            'workspaces': results,
            'aggregate': aggregate_stats,
        }
```

#### `backend/workspaces/comparator.py`

```python
from typing import Dict, Any, List
from dataclasses import dataclass

@dataclass
class WorkspaceDifference:
    """Represents a difference between workspaces."""
    category: str  # 'config', 'state', 'variables'
    item: str
    workspace_a_value: Any
    workspace_b_value: Any
    severity: str  # 'critical', 'warning', 'info'

class WorkspaceComparator:
    """Compare workspaces for consistency."""

    @staticmethod
    def compare_configurations(
        workspace_a_config: Dict[str, Any],
        workspace_b_config: Dict[str, Any],
    ) -> List[WorkspaceDifference]:
        """Compare Terraform configurations between workspaces."""
        differences = []

        # Compare provider versions
        providers_a = workspace_a_config.get('required_providers', {})
        providers_b = workspace_b_config.get('required_providers', {})

        for provider, version_a in providers_a.items():
            version_b = providers_b.get(provider)
            if version_a != version_b:
                differences.append(WorkspaceDifference(
                    category='config',
                    item=f'provider.{provider}.version',
                    workspace_a_value=version_a,
                    workspace_b_value=version_b,
                    severity='critical'
                ))

        return differences

    @staticmethod
    def compare_variables(
        workspace_a_vars: Dict[str, Any],
        workspace_b_vars: Dict[str, Any],
    ) -> List[WorkspaceDifference]:
        """Compare variable values between workspaces."""
        differences = []
        all_keys = set(workspace_a_vars.keys()) | set(workspace_b_vars.keys())

        for key in all_keys:
            val_a = workspace_a_vars.get(key)
            val_b = workspace_b_vars.get(key)

            if val_a != val_b:
                # Determine severity
                severity = 'warning'
                if key in ['region', 'environment', 'account_id']:
                    severity = 'info'  # Expected to differ
                elif 'password' in key.lower() or 'secret' in key.lower():
                    severity = 'critical'

                differences.append(WorkspaceDifference(
                    category='variables',
                    item=key,
                    workspace_a_value=val_a,
                    workspace_b_value=val_b,
                    severity=severity
                ))

        return differences

    @staticmethod
    def compare_states(
        state_a: Dict[str, Any],
        state_b: Dict[str, Any],
    ) -> List[WorkspaceDifference]:
        """Compare state files between workspaces."""
        differences = []

        # Compare resource counts
        resources_a = {r['address'] for r in state_a.get('resources', [])}
        resources_b = {r['address'] for r in state_b.get('resources', [])}

        # Resources only in A
        for addr in resources_a - resources_b:
            differences.append(WorkspaceDifference(
                category='state',
                item=f'resource.{addr}',
                workspace_a_value='present',
                workspace_b_value='absent',
                severity='warning'
            ))

        # Resources only in B
        for addr in resources_b - resources_a:
            differences.append(WorkspaceDifference(
                category='state',
                item=f'resource.{addr}',
                workspace_a_value='absent',
                workspace_b_value='present',
                severity='warning'
            ))

        return differences
```

#### `backend/workspaces/variables.py`

```python
from pathlib import Path
from typing import Dict, Any, List
import hcl2
import json

class WorkspaceVariables:
    """Manage workspace-specific variables."""

    @staticmethod
    def load_tfvars(tfvars_path: Path) -> Dict[str, Any]:
        """Load variables from .tfvars file."""
        if not tfvars_path.exists():
            return {}

        content = tfvars_path.read_text()

        # Try HCL2 parsing
        try:
            with open(tfvars_path, 'r') as f:
                parsed = hcl2.load(f)
            return parsed
        except Exception:
            pass

        # Try JSON parsing (for .tfvars.json)
        try:
            return json.loads(content)
        except Exception:
            pass

        return {}

    @staticmethod
    def find_tfvars_files(working_dir: Path, workspace: str) -> List[Path]:
        """Find tfvars files for workspace."""
        candidates = [
            working_dir / f'{workspace}.tfvars',
            working_dir / f'{workspace}.tfvars.json',
            working_dir / 'terraform.tfvars',
            working_dir / 'terraform.tfvars.json',
        ]
        return [p for p in candidates if p.exists()]

    @staticmethod
    def merge_variables(*var_dicts: Dict[str, Any]) -> Dict[str, Any]:
        """Merge multiple variable dictionaries (later overrides earlier)."""
        merged = {}
        for d in var_dicts:
            merged.update(d)
        return merged

    @staticmethod
    def detect_sensitive_vars(variables: Dict[str, Any]) -> List[str]:
        """Detect potentially sensitive variable keys."""
        sensitive_keywords = [
            'password', 'secret', 'token', 'key', 'credential',
            'api_key', 'access_key', 'private_key'
        ]
        sensitive = []

        for key in variables.keys():
            if any(kw in key.lower() for kw in sensitive_keywords):
                sensitive.append(key)

        return sensitive
```

---

## API Endpoints

### Workspace Discovery & Management

#### `GET /projects/{project_id}/workspaces`
List all workspaces in project.

**Query Params:**
- `working_dir` (optional) - Filter by working directory

**Response:**
```json
{
  "workspaces": [
    {
      "id": "ws_abc123",
      "name": "production",
      "working_directory": "terraform/aws",
      "is_default": false,
      "is_active": true,
      "last_scanned_at": "2025-01-19T10:00:00Z"
    },
    {
      "id": "ws_def456",
      "name": "staging",
      "working_directory": "terraform/aws",
      "is_default": false,
      "is_active": false,
      "last_scanned_at": "2025-01-18T15:30:00Z"
    }
  ]
}
```

#### `POST /projects/{project_id}/workspaces/discover`
Discover workspaces in project directories.

**Response:**
```json
{
  "discovered": {
    "terraform/aws": ["default", "production", "staging"],
    "terraform/azure": ["default", "dev"]
  },
  "total_workspaces": 5
}
```

#### `POST /projects/{project_id}/workspaces`
Create new workspace.

**Request:**
```json
{
  "name": "qa",
  "working_directory": "terraform/aws"
}
```

**Response:**
```json
{
  "id": "ws_ghi789",
  "name": "qa",
  "working_directory": "terraform/aws",
  "created_at": "2025-01-19T12:00:00Z"
}
```

#### `POST /projects/{project_id}/workspaces/{workspace_id}/select`
Switch to workspace.

**Response:**
```json
{
  "success": true,
  "workspace": "qa",
  "message": "Switched to workspace 'qa'"
}
```

#### `DELETE /projects/{project_id}/workspaces/{workspace_id}`
Delete workspace.

**Response:**
```json
{
  "success": true,
  "message": "Workspace 'qa' deleted"
}
```

### Multi-Workspace Operations

#### `POST /projects/{project_id}/workspaces/scan-all`
Scan all workspaces.

**Request:**
```json
{
  "working_directory": "terraform/aws",
  "workspaces": ["production", "staging", "qa"],
  "config_name": "strict",
  "run_validate": true
}
```

**Response:**
```json
{
  "workspaces": {
    "production": {
      "file_count": 15,
      "findings": [...],
      "summary": {"critical": 0, "high": 2}
    },
    "staging": {
      "file_count": 15,
      "findings": [...],
      "summary": {"critical": 1, "high": 3}
    }
  },
  "aggregate": {
    "total_files": 30,
    "total_findings": 12,
    "critical_findings": 1,
    "high_findings": 5
  }
}
```

#### `POST /projects/{project_id}/workspaces/compare`
Compare two workspaces.

**Request:**
```json
{
  "workspace_a": "production",
  "workspace_b": "staging",
  "comparison_types": ["config", "variables", "state"]
}
```

**Response:**
```json
{
  "comparison_id": "cmp_jkl012",
  "workspace_a": "production",
  "workspace_b": "staging",
  "differences_count": 5,
  "differences": [
    {
      "category": "variables",
      "item": "instance_count",
      "workspace_a_value": 10,
      "workspace_b_value": 3,
      "severity": "warning"
    },
    {
      "category": "config",
      "item": "provider.aws.version",
      "workspace_a_value": "5.31.0",
      "workspace_b_value": "5.30.0",
      "severity": "critical"
    }
  ],
  "compared_at": "2025-01-19T13:00:00Z"
}
```

### Workspace Variables

#### `GET /projects/{project_id}/workspaces/{workspace_id}/variables`
List variables for workspace.

**Response:**
```json
{
  "variables": [
    {
      "key": "region",
      "value": "us-east-1",
      "sensitive": false,
      "source": "tfvars"
    },
    {
      "key": "db_password",
      "value": "***REDACTED***",
      "sensitive": true,
      "source": "manual"
    }
  ]
}
```

#### `POST /projects/{project_id}/workspaces/{workspace_id}/variables`
Add/update variable.

**Request:**
```json
{
  "key": "instance_type",
  "value": "t3.medium",
  "sensitive": false,
  "description": "EC2 instance type for app servers"
}
```

#### `DELETE /projects/{project_id}/workspaces/{workspace_id}/variables/{key}`
Remove variable.

---

## CLI Commands

### Workspace Discovery

```bash
# Discover workspaces
python -m backend.cli workspace discover --project my-project

# List workspaces
python -m backend.cli workspace list \
  --project my-project \
  --working-dir terraform/aws
```

### Workspace Management

```bash
# Create workspace
python -m backend.cli workspace create \
  --project my-project \
  --working-dir terraform/aws \
  --name qa

# Switch workspace
python -m backend.cli workspace select \
  --project my-project \
  --working-dir terraform/aws \
  --name production

# Delete workspace
python -m backend.cli workspace delete \
  --project my-project \
  --working-dir terraform/aws \
  --name old-qa
```

### Multi-Workspace Scanning

```bash
# Scan all workspaces
python -m backend.cli workspace scan-all \
  --project my-project \
  --working-dir terraform/aws \
  --config strict \
  --out workspace-scan-results.json

# Scan specific workspaces
python -m backend.cli workspace scan-all \
  --project my-project \
  --working-dir terraform/aws \
  --workspaces production,staging \
  --out prod-staging-scan.json
```

### Workspace Comparison

```bash
# Compare workspaces
python -m backend.cli workspace compare \
  --project my-project \
  --workspace-a production \
  --workspace-b staging \
  --types config,variables,state \
  --out workspace-diff.json

# Show comparison
python -m backend.cli workspace comparison show \
  --project my-project \
  --comparison-id cmp_jkl012
```

### Variable Management

```bash
# List variables
python -m backend.cli workspace vars \
  --project my-project \
  --workspace production

# Set variable
python -m backend.cli workspace var set \
  --project my-project \
  --workspace production \
  --key instance_type \
  --value t3.large

# Import from tfvars
python -m backend.cli workspace vars import \
  --project my-project \
  --workspace production \
  --file production.tfvars
```

---

## Frontend Components

### Workspace Management Dashboard

**Route:** `/projects?project=<slug>&tab=workspaces`

**Components:**

#### `WorkspaceList.svelte`
- Display all workspaces with metadata
- Active workspace indicator
- Last scanned timestamp
- Quick switch button
- Create workspace button

#### `WorkspaceSelector.svelte`
- Dropdown to select workspace
- Show current workspace
- Switch workspace action
- Used in scan form and other operations

#### `WorkspaceCreateForm.svelte`
- Workspace name input
- Working directory selector
- Copy variables from existing workspace option
- Create button

#### `MultiWorkspaceScanPanel.svelte`
- Select workspaces to scan (checkboxes)
- Scan all button
- Results table showing per-workspace stats
- Aggregate summary
- Drill down into workspace-specific findings

#### `WorkspaceComparisonView.svelte`
- Select two workspaces to compare
- Comparison type checkboxes (config, variables, state)
- Run comparison button
- Differences table with severity indicators
- Visual diff for each difference
- Export comparison report

#### `WorkspaceVariablesPanel.svelte`
- Variable list table (key, value, source, sensitive)
- Add variable form
- Import from tfvars button
- Sensitive value masking
- Edit/delete actions

### Workspace Switcher (Global)

**Component:** `WorkspaceSwitcher.svelte`
- Appears in navbar or project header
- Shows current workspace
- Dropdown to switch
- Quick access from any page

---

## Storage Layer Extensions

### `backend/storage.py`

```python
def create_workspace(
    project_id: str,
    name: str,
    working_directory: str,
    is_default: bool = False,
) -> Dict[str, Any]:
    """Create workspace record."""
    from backend.db.models import TerraformWorkspace

    workspace = TerraformWorkspace(
        project_id=project_id,
        name=name,
        working_directory=working_directory,
        is_default=is_default,
    )

    with get_session() as session:
        session.add(workspace)
        session.commit()
        return workspace.to_dict()

def get_workspace(workspace_id: str) -> Dict[str, Any] | None:
    """Get workspace by ID."""
    with get_session() as session:
        ws = session.query(TerraformWorkspace).filter_by(id=workspace_id).first()
        return ws.to_dict() if ws else None

def list_workspaces(project_id: str, working_directory: str | None = None) -> List[Dict[str, Any]]:
    """List workspaces for project."""
    with get_session() as session:
        query = session.query(TerraformWorkspace).filter_by(project_id=project_id)
        if working_directory:
            query = query.filter_by(working_directory=working_directory)
        return [ws.to_dict() for ws in query.all()]

def set_active_workspace(project_id: str, workspace_id: str) -> None:
    """Mark workspace as active."""
    with get_session() as session:
        # Deactivate all other workspaces
        session.query(TerraformWorkspace).filter_by(
            project_id=project_id
        ).update({'is_active': False})

        # Activate target workspace
        workspace = session.query(TerraformWorkspace).filter_by(id=workspace_id).first()
        if workspace:
            workspace.is_active = True
            workspace.selected_at = datetime.now(timezone.utc)
        session.commit()
```

---

## Security Considerations

### Workspace Isolation
- Ensure workspace selection doesn't leak data between environments
- Validate workspace names (no path traversal)
- Require permissions per workspace

### Variable Security
- Encrypt sensitive variables at rest
- Never log sensitive variable values
- Mask sensitive variables in API responses
- Audit variable access

### Access Control
- Require `workspace:read` scope to list workspaces
- Require `workspace:write` scope to create/delete
- Require `workspace:variables:write` scope to modify variables
- Production workspace protection (require additional approval)

---

## Testing Requirements

### Unit Tests

```python
# tests/test_workspace_manager.py
def test_list_workspaces():
    """Test listing workspaces."""

def test_create_workspace():
    """Test creating new workspace."""

def test_switch_workspace():
    """Test switching between workspaces."""

# tests/test_workspace_comparator.py
def test_compare_variables():
    """Test variable comparison between workspaces."""

def test_detect_config_drift():
    """Test detecting config differences."""
```

### Integration Tests

```python
# tests/integration/test_workspace_scan.py
def test_scan_multiple_workspaces():
    """Test scanning across workspaces."""

def test_workspace_comparison():
    """Test full comparison workflow."""
```

---

## Migration Plan

### Phase 1: Database & Core (Week 1)
- Create workspace tables
- Implement WorkspaceManager
- Write unit tests

### Phase 2: API & CLI (Week 2)
- Workspace CRUD endpoints
- Multi-workspace scan endpoint
- CLI commands

### Phase 3: Comparison & Variables (Week 3)
- Workspace comparator
- Variable management
- Comparison endpoint

### Phase 4: Frontend (Week 4)
- Workspace list and selector
- Multi-workspace scan panel
- Comparison view
- Variable management

### Phase 5: Integration (Week 5)
- Integrate with existing scan workflow
- Update run tracking with workspace
- Link states to workspaces
- E2E tests

---

## Success Metrics

- Discover workspaces in 100% of Terraform directories
- Create/delete workspaces via CLI/API
- Scan multiple workspaces in single command
- Compare workspaces with detailed diff
- Manage workspace variables securely
- Response time < 1s for workspace operations
