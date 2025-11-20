# State Management Implementation Specification

## Purpose & Outcomes
- Ingest and persist Terraform state files from supported backends (local, S3, Azure Blob, GCS, Terraform Cloud) using the existing `backend/state` foundation.
- Provide read/export APIs for state metadata, resources, and outputs with drift summaries against plan JSON.
- Enable safe snapshot mutations (remove/move addresses) in the stored copy without invoking Terraform apply.
- Surface the feature through API, CLI, and frontend so projects can audit real infrastructure alongside static code analysis.

---

## Current Implementation Snapshot
- Backend modules already exist:
  - `backend/state/backends.py` fetches state bytes for local/S3/Azure/GCS/remote backends (uses optional `boto3`, `azure-storage-blob`, `google-cloud-storage`, `httpx`).
  - `backend/state/models.py` defines Pydantic backend configs, the `TerraformStateDocument`, drift summary, and request payload models.
  - `backend/state/analyzer.py` parses JSON bytes into normalized resources/outputs, computes checksum/size, and compares state to plan JSON.
  - `backend/state/storage.py` contains persistence helpers (persist state, list, drift records, workspace/plan helpers) but depends on SQLAlchemy models that do not yet exist.
  - `backend/state/operations.py` wraps import/list/export/drift and mutation flows against a DB session.
- Data/migrations:
  - `backend/db/migrations/add_terraform_management_tables.py` creates `terraform_states`, `terraform_state_resources`, `terraform_state_outputs`, and `drift_detections` (plus workspace/plan tables). It is not wired into `init_db` and there are no SQLAlchemy models in `backend/db/models.py`.
- API:
  - `api/routes/state.py` exposes endpoints for import, list/detail, resources, outputs, export, drift (plan compare), mutations, workspace CRUD, and plan metadata. The router is not mounted in `api/main.py`, and without models the import will fail.
- CLI:
  - No state commands are present in `backend/cli.py`; only a helper `import_state_from_path` exists.
- Tests:
  - `tests/test_state_analyzer.py` and `tests/test_state_operations.py` cover parsing, drift summary, and snapshot mutations but currently fail because the SQLAlchemy models/tables are missing.
- Dependencies:
  - Cloud backend SDKs are referenced but absent from `requirements.txt` / `requirements-dev.txt`; imports rely on runtime availability.

---

## Target Capabilities
- Import tfstate from supported backends and persist snapshot, metadata, resources, and outputs per project/workspace.
- List states per project/workspace, page through resources, and export full JSON snapshots.
- Compare a stored state with a Terraform plan JSON to record drift summary rows.
- Mutate stored snapshots to remove or move addresses (DB-only) with checksum/version updates.
- Expose the feature via authenticated API, CLI subcommands, and a frontend state tab under project views.
- Keep credential handling and logging safe (no secret persistence or leakage).

---

## Data Model & Persistence
- Add SQLAlchemy models in `backend/db/models.py` mirroring the migration schema:
  - `TerraformState` with fields: `id`, `project_id`, `workspace`, `backend_type`, `backend_config` (JSON/dict), `serial`, `terraform_version`, `lineage`, `resource_count`, `output_count`, `state_snapshot` (JSON string), `checksum`, `imported_at`, `created_at`. Provide `to_dict(include_snapshot: bool = False)` with snapshot gated.
  - `TerraformStateResource` with foreign key to state and fields: `address`, `module_address`, `mode`, `type`, `name`, `provider`, `index_label`, `schema_version`, `attributes`, `sensitive_attributes`, `dependencies`.
  - `TerraformStateOutput` with foreign key to state and fields: `name`, `value`, `sensitive`, `type_hint`.
  - `DriftDetection` with `project_id`, optional `state_id`, `workspace`, `detection_method`, counts, and `drift_details`.
  - Create relationships for cascade delete and indexes defined in the migration.
- Wire creation:
  - Extend `init_models`/`Base.metadata` to include the new models.
  - Ensure `init_db` runs the migration helper in `backend/db/migrations/add_terraform_management_tables.py` or rely on SQLAlchemy metadata after models are added (keep migration idempotent).
- Persistence behavior (`backend/state/storage.py`):
  - Store `state_snapshot` as a sorted JSON string (current code uses `json.dumps`).
  - Keep checksum computed from raw bytes; update counts/version/lineage on every mutation (`_persist_state_snapshot` already recalculates).
  - Maintain pagination support for resource listing (limit/offset) and add optional filters (type/module search) if needed later.

---

## Backend Services
- Backends:
  - Keep existing fetchers; add clearer error messages and optional gzip decoding if the fetched payload is compressed.
  - Add import guards that point users to install extras when SDKs are missing; add dependency extras (see below).
  - Accept optional endpoint overrides (`endpoint_url` for S3, `hostname` for Terraform Cloud) and propagate timeouts.
- Parser & analyzer:
  - `parse_state_bytes` should remain the single entry to normalize resources/outputs and compute checksum/size.
  - Keep drift summary focussed on counts/state-only/plan-only lists; avoid heavy diffing for now to keep it fast.
- Operations:
  - `import_state` should persist via `persist_state_document` and return lightweight metadata.
  - `remove_state_resources` / `move_state_resource` mutate the stored snapshot only; ensure address normalization matches analyzer output and returns updated metadata.
  - `detect_drift_from_plan` records drift summary rows when `record_result=True`.
- Dependencies:
  - Add optional extras to `requirements.txt` or `requirements-dev.txt` (e.g., `state-s3`, `state-azure`, `state-gcs`) containing `boto3`, `azure-storage-blob`, `google-cloud-storage`, and `httpx`. Document how to install them for users who need remote backends.

---

## API Surface
- Mount `api/routes/state.py` in `api/main.py` to make endpoints reachable.
- Endpoints to support (already implemented in the router):
  - `POST /state/import` with `StateImportRequest`: imports a state via backend config.
  - `GET /state?project_id|project_slug&workspace=`: list state metadata.
  - `GET /state/{state_id}`: state detail; `include_snapshot` flag for full JSON.
  - `GET /state/{state_id}/resources?limit=&offset=`: paginated resources.
  - `GET /state/{state_id}/outputs`: outputs list.
  - `GET /state/{state_id}/export`: raw snapshot JSON download.
  - `POST /state/{state_id}/drift/plan`: compare to plan JSON and optionally record.
  - `POST /state/{state_id}/operations/remove` and `/move`: mutate stored snapshot.
  - Workspace/plan helper routes (`/state/workspaces`, `/state/plans`) for parity with plan/workspace specs.
- Apply auth via `require_current_user`; consider scope-based checks later when RBAC lands.
- Return consistent error codes: 404 for missing state/project, 400 for mutation errors/backend fetch errors.
- Logging: use `backend.utils.logging` to add request_id/project/workspace context in the handlers.

---

## CLI Surface
- Add a `state` command group in `backend/cli.py` that calls the backend/state operations directly (not via HTTP):
  - `state import --project <id|slug> --workspace <name> --backend <type> [backend-specific flags]`
  - `state list --project <id|slug> [--workspace <name>]`
  - `state show --state-id <id> [--include-snapshot]`
  - `state export --state-id <id> --out <path>`
  - `state resources --state-id <id> [--limit 200 --offset 0]`
  - `state outputs --state-id <id>`
  - `state drift --state-id <id> --plan <plan-json-path> [--record-result]`
  - `state rm --state-id <id> --address ...` and `state mv --state-id <id> --from ... --to ...`
- Reuse `session_scope` and existing request models; print JSON results through `_print_json`.

---

## Frontend Surface
- Add a project-level State tab (under `frontend/src/routes/(app)/projects/[slug]`):
  - State list card with workspace/back-end badges and imported_at/serial/resource_count.
  - Detail view showing outputs, resources (paginated list with search/filter by type/module), and checksum/version metadata.
  - Drift pane that shows last plan comparison summary and a button to run a new comparison from uploaded plan JSON.
  - Mutations panel to remove/move addresses with confirmation.
- Use typed clients in `frontend/src/lib/api` pointing to the new endpoints; keep Svelte files TypeScript-first with Tailwind classes per repo conventions.

---

## Security, Privacy, and Reliability
- Do not persist credentials; backend configs stored in DB should exclude tokens/keys when possible (use profiles/env/IMDS).
- Mask sensitive attributes in responses (they are already captured separately in state resources).
- Enforce project scoping on every query; include workspace in index filters to avoid cross-project leakage.
- Add checksum verification before persisting and after mutations to detect accidental corruption.
- Make backend fetch timeouts explicit and avoid logging state payloads.

---

## Testing & Validation
- Unit tests:
  - Update `tests/test_state_analyzer.py` and `tests/test_state_operations.py` to use the new models and ensure they pass once models are added.
  - Add backend reader tests with mocked SDKs for each backend.
  - Add storage tests for `persist_state_document`, list/export, drift record creation, and mutation helpers.
- Integration tests:
  - API tests for import/list/detail/resources/outputs/export/drift/mutations with an in-memory DB.
  - CLI smoke tests for `state import/list/show/export` using local backend.
- Manual checks:
  - Run migration `python -m backend.db.migrations.add_terraform_management_tables`.
  - Import a sample `sample/terraform.tfstate`, list resources, export snapshot, and run drift vs a plan fixture.

---

## Rollout & Acceptance
- Database contains the new tables and SQLAlchemy models; `init_db` creates them automatically.
- State routes are reachable and return data for a locally imported tfstate.
- CLI commands exist and operate against the local DB without errors.
- Optional backend dependencies are documented and load without crashing the app when absent.
- Tests covering state parsing, persistence, and mutations pass.
