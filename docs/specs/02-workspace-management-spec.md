# Workspace Management Implementation Specification

## Purpose & Outcomes
- Manage Terraform workspaces per project so dev/stage/prod can be scanned, compared, and tracked independently.
- Make workspace-aware runs first-class in the database, API, CLI, and frontend, without breaking the current project workspace path helpers.
- Standardize how variables are captured, redacted, and reused per workspace.
- Enable fast drift/comparison signals across workspaces to highlight config skew.

---

## Current Implementation Snapshot
- Database & models: `backend/db/migrations/add_terraform_management_tables.py` already creates `terraform_workspaces`, `workspace_variables`, `workspace_comparisons`, and adds `project_runs.workspace` plus `idx_plans_workspace`. SQLAlchemy models exist in `backend/db/models.py` with `TerraformWorkspace`, `WorkspaceVariable`, and `WorkspaceComparison` (plus workspace column/index on `TerraformPlan`). Timestamps on workspaces are nullable and lack server defaults; there is no active-workspace uniqueness enforcement.
- Persistence helpers: `backend/state/storage.py` exposes `create_workspace`/`list_workspaces` and `create_plan_record` but nothing for update/delete/activate/last_scanned_at or variable/comparison persistence. Values for sensitive variables are redacted in `WorkspaceVariable.to_dict`, but there is no encryption or write path.
- API: `api/routes/state.py` mounts minimal workspace routes (`POST /state/workspaces`, `GET /state/workspaces`) that just call the storage helpers; no select/delete/discover/variables/compare/scan endpoints. Everything is under the state router instead of a dedicated workspaces router.
- CLI & services: No `backend/workspaces` package, no Terraform CLI integration for workspace commands, no multi-workspace scan wrapper, no variable importer, and no comparison utilities. Existing “workspace” wording in `backend/storage.py` only refers to project filesystem roots, not Terraform CLI workspaces.
- Frontend & tests: No UI for Terraform workspaces. Tests cover only project workspace path safety (`tests/test_cli_workspace.py`, `tests/test_scan_routes.py`) and do not exercise Terraform workspace records.

---

## Target Capabilities
- Discover Terraform workspaces within a project root and persist them per working directory.
- Create/select/delete/switch active workspaces via API and CLI, recording selections in the DB.
- Scan multiple workspaces in one request/command and update `last_scanned_at`.
- Track workspace variables (import from tfvars/env/manual), redact sensitive values, and sync into DB.
- Compare workspaces (config/variables/state summaries) and store comparison artifacts.
- Make workspace the default dimension for runs/plans so reports can be filtered by environment.

---

## Data Model & Persistence
- Keep existing tables/models but add server defaults for `created_at`/`selected_at`/`last_scanned_at` and ensure the migration remains idempotent. Enforce one active workspace per `project_id` + `working_directory` by updating others to `is_active=False` when a workspace is selected.
- Expand storage helpers (likely in a new `backend/workspaces/storage.py` or extending `backend/state/storage.py`) to support: get/update/delete workspace records, set active workspace, set `last_scanned_at`, upsert variables (with source + description), import variable batches, and persist comparison summaries.
- Variable handling: store raw values in DB, but always redact `WorkspaceVariable.to_dict()` when `sensitive=True`; avoid logging values. Add a simple `value_hashed` checksum or `value_length` in comparisons to avoid leaking secrets when diffing.
- Ensure `ProjectRun.workspace` and `TerraformPlan.workspace` are populated whenever runs/plans are created (CLI, API, generators) and add lightweight backfill/guardrails in storage paths.

---

## Backend Services
- Create `backend/workspaces/` with:
  - `manager.py`: Terraform CLI wrapper with `list`, `show_current`, `create`, `select`, `delete`, `ensure`. Guard with `shutil.which("terraform")`, capture stdout/stderr/returncode, and short-circuit with actionable errors. Use `resolve_workspace_path` from `backend/storage.py` to keep `working_directory` inside the project workspace. Protect deletion of `default` and restore the prior workspace after operations.
  - `discovery.py` (or functions in `manager.py`): walk the project root for dirs containing `*.tf` (skip `.terraform`, `node_modules`, `frontend`) and attempt `terraform workspace list` when a `.terraform` directory exists or when `terraform` is available; persist discoveries to DB.
  - `scanner.py`: multi-workspace wrapper around `backend.scanner.scan_paths` that switches workspaces, records per-workspace results, and restores the original workspace. Update `last_scanned_at` in storage after each run.
  - `variables.py`: tfvars parser (HCL and JSON) plus import/upsert helpers that mark likely sensitive keys and tag `source` (`tfvars`, `env`, `manual`). Support merge order and masking on output.
  - `comparator.py`: compare configs (provider versions, required versions, backend blocks), variables (present/changed/missing with severity heuristic), and states (pull from stored `terraform_states` by workspace if available; otherwise compare plan summaries). Produce a structured diff payload saved to `workspace_comparisons`.
- Wire orchestration helpers (e.g., `services.py`) to combine DB persistence with Terraform operations: ensure workspace exists in Terraform and DB, sync discoveries, switch active workspace, and perform scans/comparisons atomically.

---

## API Surface
- Add a dedicated router `api/routes/workspaces.py`, mounted in `api/main.py` with `require_current_user`. Keep project scoping by `project_id` or `project_slug` query params (match state routes) and validate `working_directory` via `resolve_workspace_path`.
- Endpoints:
  - `GET /workspaces`: list workspace records (filter by `working_directory`).
  - `POST /workspaces/discover`: trigger discovery, persist new rows, return discovered map + counts.
  - `POST /workspaces`: create workspace record and optionally call Terraform `workspace new`.
  - `POST /workspaces/{workspace_id}/select`: set active in DB and call Terraform `workspace select`.
  - `DELETE /workspaces/{workspace_id}`: delete DB row and optionally `terraform workspace delete` (skip `default`).
  - `POST /workspaces/scan`: scan one or many workspaces (body: `working_directory`, optional list) and return aggregate stats. Update `last_scanned_at`.
  - `POST /workspaces/compare`: compare two workspaces (types: config/variables/state) and persist a `workspace_comparisons` row.
  - `GET/POST/DELETE /workspaces/{workspace_id}/variables`: list, upsert, delete; support tfvars import via upload or path token.
- Error handling: 404 for missing project/workspace, 400 for Terraform CLI failures or invalid paths, and redact sensitive values in responses. Return structured command output when Terraform is missing to aid debugging.

---

## CLI Surface
- Add `workspace` subcommands in `backend/cli.py` that operate locally (not via HTTP):
  - `workspace discover --project-id|--project-slug --path <dir?>`
  - `workspace list --project-id|--project-slug [--working-dir <relative>]`
  - `workspace create/select/delete --project-id|--project-slug --working-dir <dir> --name <ws>`
  - `workspace scan --project-id|--project-slug --working-dir <dir> [--workspaces a,b] [--config <name>] [--validate] --out <path?>`
  - `workspace compare --project-id|--project-slug --workspace-a <name> --workspace-b <name> [--types config,variables,state] --out <path?>`
  - `workspace vars list/set/unset/import --workspace <id|name> --working-dir <dir> ...`
- Reuse `_resolve_workspace_destination`/`resolve_workspace_paths` to keep I/O inside the project root. Print JSON via `_print_json` and bubble up Terraform stdout/stderr when commands fail.

---

## Frontend Surface
- Add a Workspaces tab under `frontend/src/routes/(app)/projects/[slug]/+page.svelte` (or a dedicated `/workspaces` route) backed by typed clients in `frontend/src/lib/api`.
- Components:
  - `WorkspaceList.svelte`: list with active/default badges, working dir, last scanned, actions (select/delete).
  - `WorkspaceCreateForm.svelte`: working directory selector (pre-populated from discovery), name input, optional "create in Terraform" toggle, copy-from-existing variables checkbox.
  - `WorkspaceSelector.svelte`: compact switcher reused across scan/plan/state forms.
  - `MultiWorkspaceScanPanel.svelte`: checkbox list + aggregate stats + per-workspace findings summary.
  - `WorkspaceComparisonView.svelte`: selectors for two workspaces, type checkboxes, diff table with severity chips and JSON export.
  - `WorkspaceVariablesPanel.svelte`: list/add/import/mask sensitive values, inline edit/delete.
- Follow existing Tailwind + `script lang="ts"` conventions; keep API errors user-friendly and explain when Terraform binary is unavailable.

---

## Security & Reliability
- Keep `working_directory` constrained to the project workspace via `resolve_workspace_path`; reject absolute paths and escapes. Never log variable values; redact sensitive fields in API/CLI output. Protect deletion/switching of `default` unless explicitly forced.
- Handle missing Terraform binary gracefully (status: skipped with reason) and avoid mutating workspaces when commands fail. Ensure DB updates and CLI workspace changes are coordinated (rollback DB activations on CLI failure).
- Enforce project scoping on every query; indexes already exist for project/workspace to avoid cross-project leakage. Consider a lightweight workspace-level permission model once RBAC lands.

---

## Testing & Validation
- Unit tests: manager Terraform command parsing (simulate stdout from `terraform workspace list|show`), active workspace selection logic, tfvars parsing + sensitive detection, comparison diff heuristics, and storage helpers (activate/delete/update timestamps).
- Integration tests: API round-trips for create/list/select/delete/variables, discover endpoint with fake Terraform dir, scan-all returning aggregated stats (mock scan_paths), comparison endpoint persisting rows. CLI smoke tests for list/create/select with mocked Terraform binary.
- Manual checks: run migration, create project, discover workspaces in `sample/`, create/select via CLI and API, import tfvars, run multi-workspace scan, and verify `last_scanned_at`/`workspace` fields on `project_runs` and `terraform_plans`.

---

## Rollout & Acceptance
- Workspace records, variables, and comparisons persist in DB with timestamps and active flags reflecting Terraform CLI state.
- API and CLI can discover, create/select/delete, scan, compare, and manage variables without leaking sensitive data.
- Frontend tab shows workspace lists, selectors, scans, comparisons, and variable management with clear error messages when Terraform is unavailable.
- Workspace is recorded on runs/plans and filters work across dashboards.
