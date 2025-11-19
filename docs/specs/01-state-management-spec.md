# State Management Implementation Specification

## Overview
Enable TerraformManager to read, analyze, and operate on Terraform state files from local and remote backends. This closes the critical gap between static code analysis and actual infrastructure state.

## Goals
- Read state files from multiple backend types (local, S3, Azure Storage, GCS, Terraform Cloud)
- Detect drift between state and actual infrastructure
- Identify orphaned and unmanaged resources
- Provide state operation workflows (import, remove, move)
- Scan state files for security issues (sensitive data exposure)
- Track state changes over time

---

## Database Schema

### New Tables

#### `terraform_states`
Stores metadata about imported state files.

```sql
CREATE TABLE terraform_states (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    workspace TEXT NOT NULL DEFAULT 'default',
    backend_type TEXT NOT NULL, -- 'local', 's3', 'azurerm', 'gcs', 'remote'
    backend_config TEXT, -- JSON: {"bucket": "...", "key": "...", "region": "..."}
    serial INTEGER, -- Terraform state serial number
    terraform_version TEXT,
    lineage TEXT, -- State lineage UUID
    resource_count INTEGER,
    output_count INTEGER,
    state_snapshot TEXT, -- Full JSON state (compressed)
    checksum TEXT, -- SHA256 of state content
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
CREATE INDEX idx_terraform_states_project ON terraform_states(project_id);
CREATE INDEX idx_terraform_states_workspace ON terraform_states(project_id, workspace);
```

#### `terraform_state_resources`
Individual resources extracted from state.

```sql
CREATE TABLE terraform_state_resources (
    id TEXT PRIMARY KEY,
    state_id TEXT NOT NULL,
    address TEXT NOT NULL, -- Full resource address: module.foo.aws_instance.bar
    module_address TEXT, -- Module path if nested
    mode TEXT NOT NULL, -- 'managed' or 'data'
    type TEXT NOT NULL, -- Resource type: aws_instance, azurerm_storage_account
    name TEXT NOT NULL,
    provider TEXT NOT NULL,
    schema_version INTEGER,
    attributes TEXT, -- JSON: resource attributes from state
    sensitive_attributes TEXT, -- JSON: list of sensitive attribute paths
    dependencies TEXT, -- JSON: list of resource addresses this depends on
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (state_id) REFERENCES terraform_states(id) ON DELETE CASCADE
);
CREATE INDEX idx_state_resources_state ON terraform_state_resources(state_id);
CREATE INDEX idx_state_resources_type ON terraform_state_resources(type);
CREATE INDEX idx_state_resources_address ON terraform_state_resources(state_id, address);
```

#### `terraform_state_outputs`
Outputs from state.

```sql
CREATE TABLE terraform_state_outputs (
    id TEXT PRIMARY KEY,
    state_id TEXT NOT NULL,
    name TEXT NOT NULL,
    value TEXT, -- JSON encoded value
    sensitive BOOLEAN DEFAULT FALSE,
    type TEXT, -- Output type hint
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (state_id) REFERENCES terraform_states(id) ON DELETE CASCADE
);
CREATE INDEX idx_state_outputs_state ON terraform_state_outputs(state_id);
```

#### `drift_detections`
Drift detection results.

```sql
CREATE TABLE drift_detections (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    state_id TEXT,
    workspace TEXT NOT NULL DEFAULT 'default',
    detection_method TEXT NOT NULL, -- 'plan_comparison', 'cloud_api', 'manual'
    total_drifted INTEGER DEFAULT 0,
    resources_added INTEGER DEFAULT 0,
    resources_modified INTEGER DEFAULT 0,
    resources_deleted INTEGER DEFAULT 0,
    drift_details TEXT, -- JSON: detailed drift information per resource
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (state_id) REFERENCES terraform_states(id) ON DELETE SET NULL
);
CREATE INDEX idx_drift_project ON drift_detections(project_id);
CREATE INDEX idx_drift_detected_at ON drift_detections(detected_at DESC);
```

---

## Backend Architecture

### Module Structure

```
backend/
├── state/
│   ├── __init__.py
│   ├── reader.py          # State file reading and parsing
│   ├── backends.py        # Backend-specific implementations
│   ├── analyzer.py        # State analysis and drift detection
│   ├── operations.py      # State operations (import, rm, mv)
│   ├── scanner.py         # Security scanning of state
│   └── models.py          # Pydantic models for state structures
```

### Core Components

#### `backend/state/reader.py`

```python
from pathlib import Path
from typing import Dict, Any, Optional
import json
import gzip
import boto3
from azure.storage.blob import BlobServiceClient
from google.cloud import storage

class StateReader:
    """Read Terraform state from various backends."""

    @staticmethod
    def read_local(path: Path) -> Dict[str, Any]:
        """Read state from local file."""
        content = path.read_bytes()
        if path.suffix == '.gz':
            content = gzip.decompress(content)
        return json.loads(content)

    @staticmethod
    def read_s3(bucket: str, key: str, region: str = 'us-east-1',
                profile: Optional[str] = None) -> Dict[str, Any]:
        """Read state from S3 backend."""
        session = boto3.Session(profile_name=profile, region_name=region)
        s3 = session.client('s3')
        response = s3.get_object(Bucket=bucket, Key=key)
        content = response['Body'].read()
        return json.loads(content)

    @staticmethod
    def read_azurerm(storage_account: str, container: str, key: str,
                     access_key: Optional[str] = None) -> Dict[str, Any]:
        """Read state from Azure Storage backend."""
        conn_str = f"DefaultEndpointsProtocol=https;AccountName={storage_account};AccountKey={access_key}"
        blob_service = BlobServiceClient.from_connection_string(conn_str)
        blob_client = blob_service.get_blob_client(container=container, blob=key)
        content = blob_client.download_blob().readall()
        return json.loads(content)

    @staticmethod
    def read_gcs(bucket: str, prefix: str, credentials_path: Optional[Path] = None) -> Dict[str, Any]:
        """Read state from GCS backend."""
        client = storage.Client.from_service_account_json(credentials_path) if credentials_path else storage.Client()
        bucket_obj = client.bucket(bucket)
        blob = bucket_obj.blob(prefix)
        content = blob.download_as_bytes()
        return json.loads(content)

    @staticmethod
    def read_terraform_cloud(organization: str, workspace: str, token: str) -> Dict[str, Any]:
        """Read state from Terraform Cloud/Enterprise."""
        import httpx
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/vnd.api+json'
        }
        url = f'https://app.terraform.io/api/v2/organizations/{organization}/workspaces/{workspace}/current-state-version'
        response = httpx.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        # Download state from hosted URL
        download_url = data['data']['attributes']['hosted-state-download-url']
        state_response = httpx.get(download_url)
        state_response.raise_for_status()
        return state_response.json()
```

#### `backend/state/backends.py`

```python
from typing import Dict, Any, Protocol
from pathlib import Path
from pydantic import BaseModel

class BackendConfig(BaseModel):
    """Base backend configuration."""
    backend_type: str

class LocalBackendConfig(BackendConfig):
    backend_type: str = 'local'
    path: Path

class S3BackendConfig(BackendConfig):
    backend_type: str = 's3'
    bucket: str
    key: str
    region: str = 'us-east-1'
    profile: str | None = None

class AzureRMBackendConfig(BackendConfig):
    backend_type: str = 'azurerm'
    storage_account_name: str
    container_name: str
    key: str
    access_key: str | None = None  # Or use managed identity

class GCSBackendConfig(BackendConfig):
    backend_type: str = 'gcs'
    bucket: str
    prefix: str
    credentials: Path | None = None

class TerraformCloudBackendConfig(BackendConfig):
    backend_type: str = 'remote'
    organization: str
    workspace: str
    token: str

class BackendProtocol(Protocol):
    """Protocol for backend implementations."""

    def read_state(self, config: BackendConfig) -> Dict[str, Any]:
        """Read state from backend."""
        ...

    def list_workspaces(self, config: BackendConfig) -> list[str]:
        """List available workspaces."""
        ...

def get_backend_reader(backend_type: str) -> BackendProtocol:
    """Factory for backend readers."""
    from backend.state.backends.local import LocalBackend
    from backend.state.backends.s3 import S3Backend
    from backend.state.backends.azurerm import AzureRMBackend

    backends = {
        'local': LocalBackend(),
        's3': S3Backend(),
        'azurerm': AzureRMBackend(),
        'gcs': GCSBackend(),
        'remote': TerraformCloudBackend(),
    }
    return backends[backend_type]
```

#### `backend/state/analyzer.py`

```python
from typing import Dict, Any, List
from dataclasses import dataclass

@dataclass
class DriftResult:
    """Drift detection result."""
    resource_address: str
    drift_type: str  # 'added', 'modified', 'deleted', 'unmanaged'
    changes: Dict[str, Any]
    severity: str  # 'critical', 'high', 'medium', 'low'

class StateAnalyzer:
    """Analyze Terraform state for issues and drift."""

    def detect_sensitive_data(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Scan state for exposed sensitive data."""
        findings = []

        for resource in state.get('resources', []):
            for instance in resource.get('instances', []):
                attrs = instance.get('attributes', {})
                sensitive_attrs = instance.get('sensitive_attributes', [])

                # Check for hardcoded secrets
                for key, value in attrs.items():
                    if isinstance(value, str):
                        if self._looks_like_secret(key, value):
                            findings.append({
                                'resource': f"{resource['type']}.{resource['name']}",
                                'attribute': key,
                                'issue': 'potential_secret_exposure',
                                'severity': 'critical'
                            })

        return findings

    def detect_orphaned_resources(self, state: Dict[str, Any],
                                  actual_resources: List[str]) -> List[str]:
        """Find resources in state but deleted from cloud."""
        state_addresses = {
            f"{r['type']}.{r['name']}"
            for r in state.get('resources', [])
        }
        return list(state_addresses - set(actual_resources))

    def detect_unmanaged_resources(self, state: Dict[str, Any],
                                   actual_resources: List[str]) -> List[str]:
        """Find resources in cloud but not in state."""
        state_addresses = {
            f"{r['type']}.{r['name']}"
            for r in state.get('resources', [])
        }
        return list(set(actual_resources) - state_addresses)

    def compare_states(self, old_state: Dict[str, Any],
                      new_state: Dict[str, Any]) -> List[DriftResult]:
        """Compare two state versions to detect drift."""
        drifts = []

        old_resources = {r['address']: r for r in self._extract_resources(old_state)}
        new_resources = {r['address']: r for r in self._extract_resources(new_state)}

        # Detect additions
        for addr in new_resources.keys() - old_resources.keys():
            drifts.append(DriftResult(
                resource_address=addr,
                drift_type='added',
                changes={'action': 'create'},
                severity='medium'
            ))

        # Detect deletions
        for addr in old_resources.keys() - new_resources.keys():
            drifts.append(DriftResult(
                resource_address=addr,
                drift_type='deleted',
                changes={'action': 'destroy'},
                severity='high'
            ))

        # Detect modifications
        for addr in old_resources.keys() & new_resources.keys():
            old_attrs = old_resources[addr]['attributes']
            new_attrs = new_resources[addr]['attributes']

            if old_attrs != new_attrs:
                changes = self._diff_attributes(old_attrs, new_attrs)
                drifts.append(DriftResult(
                    resource_address=addr,
                    drift_type='modified',
                    changes=changes,
                    severity=self._assess_change_severity(changes)
                ))

        return drifts

    @staticmethod
    def _looks_like_secret(key: str, value: str) -> bool:
        """Heuristic to detect potential secrets."""
        secret_keywords = ['password', 'secret', 'token', 'key', 'credential']
        if any(kw in key.lower() for kw in secret_keywords):
            if len(value) > 16 and not value.startswith('arn:'):
                return True
        return False

    @staticmethod
    def _extract_resources(state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract flat list of resources from state."""
        resources = []
        for resource in state.get('resources', []):
            for instance in resource.get('instances', []):
                resources.append({
                    'address': f"{resource['type']}.{resource['name']}",
                    'type': resource['type'],
                    'provider': resource.get('provider'),
                    'attributes': instance.get('attributes', {})
                })
        return resources

    @staticmethod
    def _diff_attributes(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
        """Compute attribute-level diff."""
        changes = {}
        all_keys = set(old.keys()) | set(new.keys())

        for key in all_keys:
            old_val = old.get(key)
            new_val = new.get(key)
            if old_val != new_val:
                changes[key] = {'before': old_val, 'after': new_val}

        return changes

    @staticmethod
    def _assess_change_severity(changes: Dict[str, Any]) -> str:
        """Assess severity of attribute changes."""
        critical_attrs = ['encryption', 'public_access', 'security_group', 'iam_role']

        for key in changes.keys():
            if any(attr in key.lower() for attr in critical_attrs):
                return 'critical'

        return 'medium' if len(changes) > 5 else 'low'
```

#### `backend/state/operations.py`

```python
from pathlib import Path
import subprocess
from typing import List

class StateOperations:
    """Execute Terraform state operations."""

    @staticmethod
    def import_resource(working_dir: Path, address: str,
                       resource_id: str, workspace: str = 'default') -> bool:
        """Import existing resource into state."""
        cmd = ['terraform', 'workspace', 'select', workspace]
        subprocess.run(cmd, cwd=working_dir, check=True, capture_output=True)

        cmd = ['terraform', 'import', address, resource_id]
        result = subprocess.run(cmd, cwd=working_dir, capture_output=True, text=True)
        return result.returncode == 0

    @staticmethod
    def remove_resource(working_dir: Path, address: str,
                       workspace: str = 'default') -> bool:
        """Remove resource from state."""
        cmd = ['terraform', 'workspace', 'select', workspace]
        subprocess.run(cmd, cwd=working_dir, check=True, capture_output=True)

        cmd = ['terraform', 'state', 'rm', address]
        result = subprocess.run(cmd, cwd=working_dir, capture_output=True, text=True)
        return result.returncode == 0

    @staticmethod
    def move_resource(working_dir: Path, source: str, destination: str,
                     workspace: str = 'default') -> bool:
        """Move/rename resource in state."""
        cmd = ['terraform', 'workspace', 'select', workspace]
        subprocess.run(cmd, cwd=working_dir, check=True, capture_output=True)

        cmd = ['terraform', 'state', 'mv', source, destination]
        result = subprocess.run(cmd, cwd=working_dir, capture_output=True, text=True)
        return result.returncode == 0

    @staticmethod
    def list_resources(working_dir: Path, workspace: str = 'default') -> List[str]:
        """List all resources in state."""
        cmd = ['terraform', 'workspace', 'select', workspace]
        subprocess.run(cmd, cwd=working_dir, check=True, capture_output=True)

        cmd = ['terraform', 'state', 'list']
        result = subprocess.run(cmd, cwd=working_dir, capture_output=True, text=True, check=True)
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
```

---

## API Endpoints

### State Import & Reading

#### `POST /projects/{project_id}/state/import`
Import state file from backend.

**Request:**
```json
{
  "workspace": "production",
  "backend": {
    "type": "s3",
    "bucket": "my-terraform-state",
    "key": "prod/terraform.tfstate",
    "region": "us-east-1"
  },
  "credentials": {
    "profile": "prod-account"
  }
}
```

**Response:**
```json
{
  "state_id": "state_abc123",
  "serial": 42,
  "terraform_version": "1.7.0",
  "resource_count": 127,
  "output_count": 8,
  "imported_at": "2025-01-19T10:30:00Z"
}
```

#### `GET /projects/{project_id}/state`
List imported states for project.

**Query Params:** `workspace` (optional)

**Response:**
```json
{
  "states": [
    {
      "id": "state_abc123",
      "workspace": "production",
      "backend_type": "s3",
      "serial": 42,
      "resource_count": 127,
      "imported_at": "2025-01-19T10:30:00Z"
    }
  ]
}
```

#### `GET /projects/{project_id}/state/{state_id}`
Get state details.

**Response:**
```json
{
  "id": "state_abc123",
  "workspace": "production",
  "backend_type": "s3",
  "backend_config": {
    "bucket": "my-terraform-state",
    "key": "prod/terraform.tfstate",
    "region": "us-east-1"
  },
  "serial": 42,
  "terraform_version": "1.7.0",
  "lineage": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "resource_count": 127,
  "output_count": 8,
  "checksum": "sha256:abc123...",
  "imported_at": "2025-01-19T10:30:00Z"
}
```

#### `GET /projects/{project_id}/state/{state_id}/resources`
List resources in state.

**Query Params:**
- `type` (optional) - Filter by resource type
- `module` (optional) - Filter by module path
- `search` (optional) - Search resource names/addresses

**Response:**
```json
{
  "resources": [
    {
      "address": "aws_s3_bucket.data",
      "type": "aws_s3_bucket",
      "name": "data",
      "provider": "registry.terraform.io/hashicorp/aws",
      "module_address": null,
      "dependencies": ["aws_kms_key.s3_key"]
    }
  ],
  "total": 127
}
```

#### `GET /projects/{project_id}/state/{state_id}/resources/{address}`
Get resource details from state.

**Response:**
```json
{
  "address": "aws_s3_bucket.data",
  "type": "aws_s3_bucket",
  "name": "data",
  "provider": "registry.terraform.io/hashicorp/aws",
  "schema_version": 0,
  "attributes": {
    "bucket": "my-data-bucket",
    "acl": "private",
    "versioning": {"enabled": true}
  },
  "sensitive_attributes": ["tags.secret_value"],
  "dependencies": ["aws_kms_key.s3_key"]
}
```

### Drift Detection

#### `POST /projects/{project_id}/state/{state_id}/drift-detect`
Detect drift for state.

**Request:**
```json
{
  "method": "plan_comparison",
  "plan_path": "runs/run_xyz/terraform.plan.json"
}
```

**Response:**
```json
{
  "drift_id": "drift_def456",
  "total_drifted": 3,
  "resources_added": 1,
  "resources_modified": 2,
  "resources_deleted": 0,
  "detected_at": "2025-01-19T11:00:00Z"
}
```

#### `GET /projects/{project_id}/drift`
List drift detections.

**Response:**
```json
{
  "detections": [
    {
      "id": "drift_def456",
      "workspace": "production",
      "total_drifted": 3,
      "detected_at": "2025-01-19T11:00:00Z"
    }
  ]
}
```

#### `GET /projects/{project_id}/drift/{drift_id}`
Get drift details.

**Response:**
```json
{
  "id": "drift_def456",
  "workspace": "production",
  "total_drifted": 3,
  "resources_added": 1,
  "resources_modified": 2,
  "resources_deleted": 0,
  "drift_details": [
    {
      "resource": "aws_security_group.app",
      "drift_type": "modified",
      "severity": "critical",
      "changes": {
        "ingress.0.cidr_blocks": {
          "before": ["10.0.0.0/8"],
          "after": ["0.0.0.0/0"]
        }
      }
    }
  ],
  "detected_at": "2025-01-19T11:00:00Z"
}
```

### State Operations

#### `POST /projects/{project_id}/state/operations/import`
Import existing resource into state.

**Request:**
```json
{
  "workspace": "production",
  "resource_address": "aws_s3_bucket.legacy",
  "resource_id": "my-legacy-bucket",
  "working_directory": "terraform/prod"
}
```

**Response:**
```json
{
  "success": true,
  "resource_address": "aws_s3_bucket.legacy",
  "message": "Resource imported successfully"
}
```

#### `POST /projects/{project_id}/state/operations/remove`
Remove resource from state.

**Request:**
```json
{
  "workspace": "production",
  "resource_address": "aws_instance.old_server",
  "working_directory": "terraform/prod"
}
```

#### `POST /projects/{project_id}/state/operations/move`
Move/rename resource in state.

**Request:**
```json
{
  "workspace": "production",
  "source": "aws_instance.old",
  "destination": "aws_instance.new",
  "working_directory": "terraform/prod"
}
```

### State Security Scan

#### `POST /projects/{project_id}/state/{state_id}/scan`
Scan state for security issues.

**Response:**
```json
{
  "scan_id": "scan_ghi789",
  "findings": [
    {
      "resource": "aws_db_instance.main",
      "attribute": "password",
      "issue": "potential_secret_exposure",
      "severity": "critical",
      "recommendation": "Use AWS Secrets Manager reference"
    }
  ],
  "total_findings": 1,
  "scanned_at": "2025-01-19T11:30:00Z"
}
```

---

## CLI Commands

### State Import

```bash
# Import state from S3
python -m backend.cli state import \
  --project my-project \
  --workspace production \
  --backend s3 \
  --bucket my-terraform-state \
  --key prod/terraform.tfstate \
  --region us-east-1

# Import from local file
python -m backend.cli state import \
  --project my-project \
  --workspace default \
  --backend local \
  --path ./terraform.tfstate

# Import from Terraform Cloud
python -m backend.cli state import \
  --project my-project \
  --backend remote \
  --organization myorg \
  --workspace prod-app \
  --token $TFC_TOKEN
```

### State Inspection

```bash
# List states
python -m backend.cli state list --project my-project

# Show state details
python -m backend.cli state show \
  --project my-project \
  --state-id state_abc123

# List resources in state
python -m backend.cli state resources \
  --project my-project \
  --state-id state_abc123 \
  --type aws_s3_bucket

# Show resource from state
python -m backend.cli state resource \
  --project my-project \
  --state-id state_abc123 \
  --address aws_s3_bucket.data
```

### Drift Detection

```bash
# Detect drift using plan comparison
python -m backend.cli state drift \
  --project my-project \
  --state-id state_abc123 \
  --plan runs/run_xyz/terraform.plan.json

# Show drift details
python -m backend.cli drift show \
  --project my-project \
  --drift-id drift_def456

# Export drift report
python -m backend.cli drift export \
  --project my-project \
  --drift-id drift_def456 \
  --format json \
  --out drift-report.json
```

### State Operations

```bash
# Import resource
python -m backend.cli state operation import \
  --project my-project \
  --workspace production \
  --address aws_s3_bucket.legacy \
  --id my-legacy-bucket \
  --working-dir terraform/prod

# Remove resource
python -m backend.cli state operation remove \
  --project my-project \
  --workspace production \
  --address aws_instance.old_server \
  --working-dir terraform/prod

# Move resource
python -m backend.cli state operation move \
  --project my-project \
  --workspace production \
  --source aws_instance.old \
  --destination aws_instance.new \
  --working-dir terraform/prod
```

### State Security Scan

```bash
# Scan state for security issues
python -m backend.cli state scan \
  --project my-project \
  --state-id state_abc123 \
  --out state-security-report.json
```

---

## Frontend Components

### State Management Dashboard

**Route:** `/projects?project=<slug>&tab=state`

**Components:**

#### `StateList.svelte`
- Display imported states with metadata (workspace, backend, resource count)
- Import new state button
- Refresh state button
- Filter by workspace

#### `StateImportForm.svelte`
- Backend type selector (local, S3, Azure, GCS, Terraform Cloud)
- Dynamic form fields based on backend type
- Credential input (profiles, tokens, keys)
- Workspace selector
- Test connection button
- Import button

#### `StateResourceBrowser.svelte`
- Tree view of resources (grouped by module)
- Search and filter by type
- Resource detail view on click
- Show dependencies graph
- Sensitive attribute masking

#### `StateDriftView.svelte`
- Drift detection history
- Run drift detection button
- Drift details table (resource, type, changes, severity)
- Visual diff for modified resources
- Export drift report

#### `StateOperationsPanel.svelte`
- Import resource workflow
  - Resource address input
  - Cloud resource ID input
  - Generate import command
  - Execute import
- Remove resource workflow
- Move resource workflow

### State Security Findings

**Component:** `StateSecurityFindings.svelte`
- List of security findings from state scan
- Severity indicators
- Remediation recommendations
- Filter by severity/resource type

---

## Storage Layer

### `backend/storage.py` Extensions

```python
def import_terraform_state(
    project_id: str,
    workspace: str,
    backend_config: Dict[str, Any],
    state_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Import and persist Terraform state."""
    from backend.state.reader import StateReader
    from backend.db.models import TerraformState, TerraformStateResource
    import json
    import hashlib
    import gzip

    # Compress state snapshot
    state_json = json.dumps(state_data)
    compressed = gzip.compress(state_json.encode())
    checksum = hashlib.sha256(state_json.encode()).hexdigest()

    state = TerraformState(
        project_id=project_id,
        workspace=workspace,
        backend_type=backend_config['type'],
        backend_config=json.dumps(backend_config),
        serial=state_data.get('serial'),
        terraform_version=state_data.get('terraform_version'),
        lineage=state_data.get('lineage'),
        resource_count=len(state_data.get('resources', [])),
        output_count=len(state_data.get('outputs', {})),
        state_snapshot=compressed,
        checksum=checksum,
    )

    with get_session() as session:
        session.add(state)
        session.flush()

        # Extract and store resources
        for resource in state_data.get('resources', []):
            for instance in resource.get('instances', []):
                state_resource = TerraformStateResource(
                    state_id=state.id,
                    address=f"{resource['type']}.{resource['name']}",
                    module_address=resource.get('module'),
                    mode=resource['mode'],
                    type=resource['type'],
                    name=resource['name'],
                    provider=resource['provider'],
                    schema_version=resource.get('schema_version'),
                    attributes=json.dumps(instance.get('attributes', {})),
                    sensitive_attributes=json.dumps(instance.get('sensitive_attributes', [])),
                    dependencies=json.dumps(instance.get('dependencies', [])),
                )
                session.add(state_resource)

        session.commit()
        return state.to_dict()

def get_terraform_state(state_id: str) -> Dict[str, Any] | None:
    """Retrieve state by ID."""
    with get_session() as session:
        state = session.query(TerraformState).filter_by(id=state_id).first()
        return state.to_dict() if state else None

def list_terraform_states(project_id: str, workspace: str | None = None) -> List[Dict[str, Any]]:
    """List states for project."""
    with get_session() as session:
        query = session.query(TerraformState).filter_by(project_id=project_id)
        if workspace:
            query = query.filter_by(workspace=workspace)
        return [s.to_dict() for s in query.all()]
```

---

## Security Considerations

### Credential Management
- Never log or persist cloud credentials
- Support credential chains (env vars, profiles, instance roles)
- Encrypt sensitive backend config (access keys, tokens)
- Use time-limited tokens (AWS STS, Azure managed identity)

### State File Security
- Compress state snapshots (reduce storage)
- Checksum validation on read
- Mask sensitive attributes in API responses
- Audit log for state access

### Access Control
- Require `state:read` scope to view state
- Require `state:write` scope for operations
- Require `state:import` scope for backend access
- Project-level permissions

---

## Testing Requirements

### Unit Tests

```python
# tests/test_state_reader.py
def test_read_local_state():
    """Test reading local state file."""

def test_read_s3_state():
    """Test reading from S3 with mocked boto3."""

def test_parse_state_resources():
    """Test extracting resources from state."""

# tests/test_state_analyzer.py
def test_detect_sensitive_data():
    """Test finding exposed secrets in state."""

def test_compare_states_detect_drift():
    """Test drift detection between states."""

def test_detect_orphaned_resources():
    """Test finding orphaned resources."""
```

### Integration Tests

```python
# tests/integration/test_state_import.py
def test_import_state_from_local():
    """Test full state import workflow."""

def test_drift_detection_with_plan():
    """Test drift detection with plan JSON."""

def test_state_operation_import():
    """Test terraform import execution."""
```

---

## Migration Plan

### Phase 1: Database Schema (Week 1)
- Create migration script for new tables
- Add indexes and foreign keys
- Update SQLAlchemy models

### Phase 2: Backend Core (Weeks 2-3)
- Implement `StateReader` for all backends
- Implement `StateAnalyzer`
- Add storage layer functions
- Write unit tests

### Phase 3: API Endpoints (Week 4)
- Implement state import/list/get endpoints
- Implement drift detection endpoints
- Implement state operations endpoints
- Add API tests

### Phase 4: CLI Commands (Week 5)
- Add state CLI commands
- Add drift CLI commands
- Add state operations CLI commands
- Integration tests

### Phase 5: Frontend (Weeks 6-7)
- Build state management dashboard
- State import form
- Resource browser
- Drift visualization
- E2E tests

### Phase 6: Documentation & Polish (Week 8)
- User documentation
- API documentation
- Example workflows
- Performance optimization

---

## Success Metrics

- Import state from S3/Azure/GCS/Local
- Detect drift with 95%+ accuracy
- Import/remove/move resources via CLI/API
- Scan state for security issues
- Display resource browser with 1000+ resources
- Response time < 2s for state operations
