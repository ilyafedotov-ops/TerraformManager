# Plan Management Implementation Specification

## Overview
Enable TerraformManager to generate, store, analyze, and visualize Terraform execution plans. Plans show what Terraform will do before actually doing it, making them critical for safe infrastructure changes.

## Goals
- Generate execution plans (terraform plan)
- Store plan files (binary and JSON)
- Parse and analyze plan output
- Visualize resource changes
- Calculate cost impact per resource
- Detect security-impactful changes
- Support plan approval workflows
- Compare plans over time
- Enable targeted planning

---

## Database Schema

### New Tables

#### `terraform_plans`
Store plan metadata and results.

```sql
CREATE TABLE terraform_plans (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    run_id TEXT, -- Link to project run if applicable
    workspace TEXT NOT NULL DEFAULT 'default',
    working_directory TEXT NOT NULL,
    plan_type TEXT NOT NULL, -- 'standard', 'destroy', 'refresh-only', 'targeted'
    target_resources TEXT, -- JSON: list of -target flags if applicable
    has_changes BOOLEAN DEFAULT FALSE,
    resource_changes TEXT, -- JSON: resource change summary
    output_changes TEXT, -- JSON: output changes
    total_resources INTEGER DEFAULT 0,
    resources_to_add INTEGER DEFAULT 0,
    resources_to_change INTEGER DEFAULT 0,
    resources_to_destroy INTEGER DEFAULT 0,
    resources_to_replace INTEGER DEFAULT 0,
    plan_file_path TEXT, -- Path to binary plan file
    plan_json_path TEXT, -- Path to JSON plan output
    plan_output TEXT, -- Human-readable plan output (truncated)
    cost_estimate TEXT, -- JSON: cost impact per resource
    security_impact TEXT, -- JSON: security-sensitive changes
    approval_status TEXT DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
    approved_by TEXT,
    approved_at TIMESTAMP,
    expires_at TIMESTAMP, -- Plans expire after X hours
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (run_id) REFERENCES project_runs(id) ON DELETE SET NULL
);
CREATE INDEX idx_plans_project ON terraform_plans(project_id);
CREATE INDEX idx_plans_workspace ON terraform_plans(workspace);
CREATE INDEX idx_plans_approval ON terraform_plans(approval_status);
CREATE INDEX idx_plans_created ON terraform_plans(created_at DESC);
```

#### `plan_resource_changes`
Detailed per-resource changes from plan.

```sql
CREATE TABLE plan_resource_changes (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    resource_address TEXT NOT NULL,
    module_address TEXT,
    mode TEXT NOT NULL, -- 'managed' or 'data'
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    provider TEXT NOT NULL,
    action TEXT NOT NULL, -- 'create', 'update', 'delete', 'replace', 'no-op'
    action_reason TEXT, -- 'tainted', 'requested', 'config_changed'
    before_attributes TEXT, -- JSON: resource state before
    after_attributes TEXT, -- JSON: resource state after
    before_sensitive TEXT, -- JSON: sensitive paths in before
    after_sensitive TEXT, -- JSON: sensitive paths in after
    attribute_changes TEXT, -- JSON: detailed attribute diffs
    security_impact_score INTEGER, -- 0-10 scale
    cost_impact REAL, -- Estimated monthly cost change
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (plan_id) REFERENCES terraform_plans(id) ON DELETE CASCADE
);
CREATE INDEX idx_plan_changes_plan ON plan_resource_changes(plan_id);
CREATE INDEX idx_plan_changes_action ON plan_resource_changes(action);
CREATE INDEX idx_plan_changes_type ON plan_resource_changes(type);
```

#### `plan_approvals`
Approval workflow tracking.

```sql
CREATE TABLE plan_approvals (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    approver_id TEXT NOT NULL,
    status TEXT NOT NULL, -- 'pending', 'approved', 'rejected'
    comments TEXT,
    required BOOLEAN DEFAULT TRUE, -- Is this approval required or optional?
    approved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (plan_id) REFERENCES terraform_plans(id) ON DELETE CASCADE,
    FOREIGN KEY (approver_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX idx_plan_approvals_plan ON plan_approvals(plan_id);
CREATE INDEX idx_plan_approvals_status ON plan_approvals(status);
```

---

## Backend Architecture

### Module Structure

```
backend/
├── plans/
│   ├── __init__.py
│   ├── generator.py      # Generate plans (terraform plan)
│   ├── parser.py         # Parse plan JSON output
│   ├── analyzer.py       # Analyze security/cost impact
│   ├── visualizer.py     # Generate visual diffs and graphs
│   ├── approvals.py      # Approval workflow logic
│   └── models.py         # Pydantic models
```

### Core Components

#### `backend/plans/generator.py`

```python
from pathlib import Path
import subprocess
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

class PlanGenerator:
    """Generate Terraform execution plans."""

    @staticmethod
    def generate_plan(
        working_dir: Path,
        workspace: str = 'default',
        target_resources: List[str] | None = None,
        destroy: bool = False,
        refresh_only: bool = False,
        parallelism: int = 10,
        var_files: List[Path] | None = None,
    ) -> Dict[str, Any]:
        """Generate a Terraform plan."""

        # Build plan command
        plan_file = working_dir / f'tfplan_{datetime.now().strftime("%Y%m%d_%H%M%S")}.tfplan'
        json_file = plan_file.with_suffix('.json')

        cmd = [
            'terraform', 'plan',
            f'-out={plan_file}',
            f'-parallelism={parallelism}',
            '-input=false',
            '-no-color',
        ]

        if destroy:
            cmd.append('-destroy')

        if refresh_only:
            cmd.append('-refresh-only')

        if target_resources:
            for target in target_resources:
                cmd.extend(['-target', target])

        if var_files:
            for var_file in var_files:
                cmd.extend(['-var-file', str(var_file)])

        # Switch workspace
        subprocess.run(
            ['terraform', 'workspace', 'select', workspace],
            cwd=working_dir,
            check=True,
            capture_output=True
        )

        # Initialize if needed
        subprocess.run(
            ['terraform', 'init', '-input=false'],
            cwd=working_dir,
            check=True,
            capture_output=True
        )

        # Run plan
        result = subprocess.run(
            cmd,
            cwd=working_dir,
            capture_output=True,
            text=True
        )

        if result.returncode not in [0, 2]:  # 0=no changes, 2=changes
            raise RuntimeError(f"terraform plan failed: {result.stderr}")

        # Convert plan to JSON
        json_cmd = [
            'terraform', 'show',
            '-json',
            str(plan_file)
        ]

        json_result = subprocess.run(
            json_cmd,
            cwd=working_dir,
            capture_output=True,
            text=True,
            check=True
        )

        json_file.write_text(json_result.stdout)

        return {
            'plan_file': str(plan_file),
            'json_file': str(json_file),
            'has_changes': result.returncode == 2,
            'output': result.stdout,
            'exit_code': result.returncode,
        }

    @staticmethod
    def validate_plan_age(plan_created_at: datetime, max_age_hours: int = 24) -> bool:
        """Check if plan is still valid (not too old)."""
        age = datetime.now() - plan_created_at
        return age < timedelta(hours=max_age_hours)
```

#### `backend/plans/parser.py`

```python
import json
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass

@dataclass
class ResourceChange:
    """Represents a single resource change."""
    address: str
    type: str
    action: str  # 'create', 'update', 'delete', 'replace', 'no-op'
    before: Dict[str, Any]
    after: Dict[str, Any]
    changes: Dict[str, Any]
    provider: str

class PlanParser:
    """Parse Terraform plan JSON output."""

    @staticmethod
    def parse_plan_file(plan_json_path: Path) -> Dict[str, Any]:
        """Parse plan JSON file."""
        data = json.loads(plan_json_path.read_text())

        resource_changes = []
        counts = {
            'create': 0,
            'update': 0,
            'delete': 0,
            'replace': 0,
            'no-op': 0
        }

        for change in data.get('resource_changes', []):
            change_block = change.get('change', {})
            actions = change_block.get('actions', [])

            action = PlanParser._determine_action(actions)
            counts[action] += 1

            resource_changes.append({
                'address': change.get('address'),
                'module_address': change.get('module_address'),
                'mode': change.get('mode'),
                'type': change.get('type'),
                'name': change.get('name'),
                'provider': change.get('provider_name'),
                'action': action,
                'action_reason': change_block.get('action_reason'),
                'before': change_block.get('before'),
                'after': change_block.get('after'),
                'before_sensitive': change_block.get('before_sensitive', []),
                'after_sensitive': change_block.get('after_sensitive', []),
            })

        output_changes = []
        for name, output_change in (data.get('output_changes') or {}).items():
            output_changes.append({
                'name': name,
                'actions': output_change.get('actions', []),
                'before': output_change.get('before'),
                'after': output_change.get('after'),
            })

        return {
            'terraform_version': data.get('terraform_version'),
            'format_version': data.get('format_version'),
            'resource_changes': resource_changes,
            'output_changes': output_changes,
            'counts': counts,
            'total_changes': sum([
                counts['create'],
                counts['update'],
                counts['delete'],
                counts['replace']
            ]),
            'has_changes': any([
                counts['create'],
                counts['update'],
                counts['delete'],
                counts['replace']
            ]),
        }

    @staticmethod
    def _determine_action(actions: List[str]) -> str:
        """Determine primary action from action list."""
        if not actions or actions == ['no-op']:
            return 'no-op'
        if 'create' in actions and 'delete' in actions:
            return 'replace'
        if 'create' in actions:
            return 'create'
        if 'delete' in actions:
            return 'delete'
        if 'update' in actions:
            return 'update'
        return 'no-op'

    @staticmethod
    def compute_attribute_diff(before: Any, after: Any) -> Dict[str, Any]:
        """Compute detailed attribute-level diff."""
        if not isinstance(before, dict) or not isinstance(after, dict):
            return {'before': before, 'after': after}

        diff = {}
        all_keys = set(before.keys()) | set(after.keys())

        for key in all_keys:
            before_val = before.get(key)
            after_val = after.get(key)

            if before_val != after_val:
                if isinstance(before_val, dict) and isinstance(after_val, dict):
                    diff[key] = PlanParser.compute_attribute_diff(before_val, after_val)
                else:
                    diff[key] = {'before': before_val, 'after': after_val}

        return diff
```

#### `backend/plans/analyzer.py`

```python
from typing import Dict, Any, List

class PlanAnalyzer:
    """Analyze plan for security and cost impact."""

    SECURITY_SENSITIVE_ATTRIBUTES = [
        'ingress', 'egress', 'security_group', 'network_acl',
        'iam_role', 'iam_policy', 'encryption', 'kms_key',
        'public_access', 'publicly_accessible', 'public_ip',
        'cidr_blocks', 'ipv6_cidr_blocks',
    ]

    @staticmethod
    def assess_security_impact(resource_change: Dict[str, Any]) -> int:
        """Assess security impact on 0-10 scale."""
        score = 0
        action = resource_change['action']
        resource_type = resource_change['type']
        before = resource_change.get('before', {}) or {}
        after = resource_change.get('after', {}) or {}

        # Critical: Deleting security resources
        if action == 'delete':
            if 'security_group' in resource_type or 'network_acl' in resource_type:
                score += 8

        # Critical: Modifying security groups
        if action in ['update', 'replace']:
            for attr in PlanAnalyzer.SECURITY_SENSITIVE_ATTRIBUTES:
                if attr in before or attr in after:
                    before_val = before.get(attr)
                    after_val = after.get(attr)

                    if before_val != after_val:
                        score += PlanAnalyzer._assess_attribute_change(
                            attr, before_val, after_val
                        )

        return min(score, 10)

    @staticmethod
    def _assess_attribute_change(attr: str, before: Any, after: Any) -> int:
        """Score individual attribute change."""
        # Opening to 0.0.0.0/0
        if attr == 'cidr_blocks' and after and '0.0.0.0/0' in str(after):
            return 10

        # Disabling encryption
        if 'encryption' in attr:
            if before and not after:
                return 9

        # Public access enabled
        if 'public' in attr:
            if not before and after:
                return 7

        return 3  # Default for security-sensitive change

    @staticmethod
    def detect_breaking_changes(resource_changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect potentially breaking changes."""
        breaking = []

        for change in resource_changes:
            if change['action'] in ['delete', 'replace']:
                # Deleting databases, load balancers, storage
                if any(keyword in change['type'] for keyword in [
                    'db_instance', 'rds_cluster', 's3_bucket',
                    'load_balancer', 'alb', 'elb'
                ]):
                    breaking.append({
                        'resource': change['address'],
                        'action': change['action'],
                        'reason': 'Deleting or replacing critical resource',
                        'severity': 'critical'
                    })

        return breaking

    @staticmethod
    def estimate_blast_radius(
        resource_changes: List[Dict[str, Any]],
        dependency_graph: Dict[str, List[str]]
    ) -> Dict[str, int]:
        """Estimate impact radius of changes."""
        impact = {}

        for change in resource_changes:
            if change['action'] in ['delete', 'replace']:
                address = change['address']
                dependents = dependency_graph.get(address, [])
                impact[address] = len(dependents)

        return impact
```

#### `backend/plans/visualizer.py`

```python
from typing import Dict, Any, List

class PlanVisualizer:
    """Generate visual representations of plans."""

    @staticmethod
    def generate_mermaid_graph(resource_changes: List[Dict[str, Any]]) -> str:
        """Generate Mermaid diagram of resource changes."""
        lines = ['graph TD']

        for change in resource_changes:
            addr = change['address'].replace('.', '_')
            action = change['action']
            resource_type = change['type']

            # Node styling based on action
            if action == 'create':
                style = ':::created'
                symbol = '[+]'
            elif action == 'delete':
                style = ':::deleted'
                symbol = '[-]'
            elif action == 'replace':
                style = ':::replaced'
                symbol = '[~]'
            elif action == 'update':
                style = ':::updated'
                symbol = '[*]'
            else:
                continue

            lines.append(f'    {addr}["{symbol} {resource_type}"{style}]')

        # Add styling classes
        lines.extend([
            '    classDef created fill:#90EE90',
            '    classDef deleted fill:#FFB6C1',
            '    classDef replaced fill:#FFD700',
            '    classDef updated fill:#87CEEB',
        ])

        return '\n'.join(lines)

    @staticmethod
    def generate_diff_html(before: Dict[str, Any], after: Dict[str, Any]) -> str:
        """Generate HTML diff view."""
        # Simplified diff (use difflib in real implementation)
        html = ['<table class="diff">']

        all_keys = set(before.keys()) | set(after.keys())

        for key in sorted(all_keys):
            before_val = before.get(key, '')
            after_val = after.get(key, '')

            if before_val != after_val:
                html.append(f'<tr>')
                html.append(f'  <td class="key">{key}</td>')
                html.append(f'  <td class="before">{before_val}</td>')
                html.append(f'  <td class="after">{after_val}</td>')
                html.append(f'</tr>')

        html.append('</table>')
        return '\n'.join(html)
```

---

## API Endpoints

### Plan Generation

#### `POST /projects/{project_id}/plans/generate`
Generate execution plan.

**Request:**
```json
{
  "workspace": "production",
  "working_directory": "terraform/aws",
  "target_resources": ["aws_instance.app"],
  "destroy": false,
  "refresh_only": false,
  "var_files": ["production.tfvars"]
}
```

**Response:**
```json
{
  "plan_id": "plan_abc123",
  "has_changes": true,
  "total_changes": 5,
  "resources_to_add": 2,
  "resources_to_change": 3,
  "resources_to_destroy": 0,
  "created_at": "2025-01-19T14:00:00Z",
  "expires_at": "2025-01-20T14:00:00Z"
}
```

#### `GET /projects/{project_id}/plans`
List plans for project.

**Query Params:**
- `workspace` (optional)
- `approval_status` (optional)
- `limit`, `offset` (pagination)

**Response:**
```json
{
  "plans": [
    {
      "id": "plan_abc123",
      "workspace": "production",
      "plan_type": "standard",
      "has_changes": true,
      "total_changes": 5,
      "approval_status": "approved",
      "created_at": "2025-01-19T14:00:00Z"
    }
  ],
  "total": 10
}
```

#### `GET /projects/{project_id}/plans/{plan_id}`
Get plan details.

**Response:**
```json
{
  "id": "plan_abc123",
  "workspace": "production",
  "working_directory": "terraform/aws",
  "plan_type": "standard",
  "has_changes": true,
  "resource_changes": {
    "create": 2,
    "update": 3,
    "delete": 0,
    "replace": 0
  },
  "security_impact": [
    {
      "resource": "aws_security_group.app",
      "score": 8,
      "reason": "Opening ingress to 0.0.0.0/0"
    }
  ],
  "cost_estimate": {
    "monthly_change": 150.00,
    "currency": "USD"
  },
  "approval_status": "pending",
  "created_at": "2025-01-19T14:00:00Z",
  "expires_at": "2025-01-20T14:00:00Z"
}
```

#### `GET /projects/{project_id}/plans/{plan_id}/changes`
Get detailed resource changes.

**Response:**
```json
{
  "changes": [
    {
      "address": "aws_instance.app",
      "type": "aws_instance",
      "action": "create",
      "security_impact_score": 2,
      "cost_impact": 75.00,
      "attributes": {
        "instance_type": "t3.medium",
        "ami": "ami-12345678"
      }
    }
  ]
}
```

#### `GET /projects/{project_id}/plans/{plan_id}/visual`
Get visual representation (Mermaid diagram).

**Response:**
```json
{
  "format": "mermaid",
  "diagram": "graph TD\n  aws_instance_app[\"[+] aws_instance\"::created]\n..."
}
```

#### `DELETE /projects/{project_id}/plans/{plan_id}`
Delete plan.

---

### Plan Approval

#### `POST /projects/{project_id}/plans/{plan_id}/approvals`
Request approval from users.

**Request:**
```json
{
  "approvers": ["user_abc", "user_def"],
  "required": true,
  "message": "Please review this plan for production deployment"
}
```

#### `POST /projects/{project_id}/plans/{plan_id}/approve`
Approve plan.

**Request:**
```json
{
  "comments": "LGTM, security changes look good"
}
```

#### `POST /projects/{project_id}/plans/{plan_id}/reject`
Reject plan.

**Request:**
```json
{
  "comments": "Opening to 0.0.0.0/0 is too broad, please restrict"
}
```

#### `GET /projects/{project_id}/plans/{plan_id}/approvals`
List approval status.

**Response:**
```json
{
  "approvals": [
    {
      "approver": "security-team",
      "status": "pending",
      "required": true
    },
    {
      "approver": "ops-lead",
      "status": "approved",
      "comments": "LGTM",
      "approved_at": "2025-01-19T15:00:00Z"
    }
  ],
  "overall_status": "pending"
}
```

---

## CLI Commands

### Plan Generation

```bash
# Generate plan
python -m backend.cli plan generate \
  --project my-project \
  --workspace production \
  --working-dir terraform/aws \
  --var-file production.tfvars

# Generate destroy plan
python -m backend.cli plan generate \
  --project my-project \
  --workspace production \
  --destroy

# Targeted plan
python -m backend.cli plan generate \
  --project my-project \
  --target aws_instance.app \
  --target aws_security_group.app
```

### Plan Inspection

```bash
# List plans
python -m backend.cli plan list \
  --project my-project \
  --workspace production

# Show plan details
python -m backend.cli plan show \
  --project my-project \
  --plan-id plan_abc123

# Show resource changes
python -m backend.cli plan changes \
  --project my-project \
  --plan-id plan_abc123 \
  --action create

# Export plan
python -m backend.cli plan export \
  --project my-project \
  --plan-id plan_abc123 \
  --format json \
  --out plan-details.json
```

### Plan Approval

```bash
# Approve plan
python -m backend.cli plan approve \
  --project my-project \
  --plan-id plan_abc123 \
  --comments "LGTM"

# Reject plan
python -m backend.cli plan reject \
  --project my-project \
  --plan-id plan_abc123 \
  --comments "Security concerns"

# Show approval status
python -m backend.cli plan approvals \
  --project my-project \
  --plan-id plan_abc123
```

---

## Frontend Components

### Plan Management Dashboard

**Route:** `/projects?project=<slug>&tab=plans`

**Components:**

#### `PlanList.svelte`
- List of plans with summary (changes, approval status)
- Filter by workspace, status, date
- Generate new plan button

#### `PlanGenerateForm.svelte`
- Workspace selector
- Working directory input
- Plan type selector (standard, destroy, refresh-only)
- Target resources input (optional)
- Variable files selector
- Generate button

#### `PlanDetailView.svelte`
- Plan summary (changes count, approval status)
- Resource changes table
- Security impact indicators
- Cost estimate
- Approval workflow status
- Visual graph (Mermaid)
- Export buttons (JSON, HTML)

#### `PlanResourceChangeTable.svelte`
- Filterable table of resource changes
- Action indicators (create, update, delete, replace)
- Security impact scores
- Cost impact per resource
- Attribute diff viewer on click

#### `PlanDiffViewer.svelte`
- Side-by-side before/after comparison
- Syntax highlighting for HCL attributes
- Highlight added/removed/changed lines

#### `PlanApprovalPanel.svelte`
- List of approvers with status
- Approve/reject buttons
- Comment input
- Approval history timeline

#### `PlanVisualization.svelte`
- Mermaid diagram renderer
- Interactive resource graph
- Dependency arrows
- Color-coded by action type

---

## Storage Layer Extensions

### `backend/storage.py`

```python
def create_plan(
    project_id: str,
    workspace: str,
    working_directory: str,
    plan_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Create plan record."""
    from backend.db.models import TerraformPlan
    import json

    plan = TerraformPlan(
        project_id=project_id,
        workspace=workspace,
        working_directory=working_directory,
        plan_type=plan_data.get('plan_type', 'standard'),
        has_changes=plan_data['has_changes'],
        resource_changes=json.dumps(plan_data['resource_changes']),
        total_resources=plan_data.get('total_resources', 0),
        resources_to_add=plan_data['counts']['create'],
        resources_to_change=plan_data['counts']['update'],
        resources_to_destroy=plan_data['counts']['delete'],
        resources_to_replace=plan_data['counts']['replace'],
        plan_file_path=plan_data.get('plan_file'),
        plan_json_path=plan_data.get('json_file'),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )

    with get_session() as session:
        session.add(plan)
        session.commit()
        return plan.to_dict()
```

---

## Security Considerations

- Encrypt sensitive plan attributes
- Restrict plan approval to authorized users
- Audit all plan approvals
- Expire old plans (24-48 hours)
- Validate plan hasn't changed before apply

---

## Testing Requirements

### Unit Tests
- Test plan generation
- Test plan parsing
- Test security impact scoring
- Test approval workflow

### Integration Tests
- Generate and parse real plan
- Multi-approval workflow
- Expired plan handling

---

## Migration Plan

**Week 1:** Database + Generator
**Week 2:** Parser + Analyzer
**Week 3:** API Endpoints
**Week 4:** CLI Commands
**Week 5:** Frontend Components
**Week 6:** Approval Workflow
**Week 7:** Visualization
**Week 8:** Testing + Polish

---

## Success Metrics

- Generate plans in < 30s
- Parse 1000+ resource changes
- Accurate security scoring
- Approval workflow complete
- Visual diff rendering
- Plan comparison
