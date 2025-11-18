# TerraformManager Implementation Plan & Status

## Vision
- Provide secure-by-default templates (AWS/Azure/Kubernetes) across generators to accelerate infrastructure provisioning.
- Enforce best-practice policies via static analysis with clear remediation guidance.
- Support both interactive wizard generation and CLI/CI review pipelines with optional terraform validation.
- Guarantee that every Terraform source managed by the product lives under a dedicated workspace tree (`data/projects/<slug>/` by default) so uploads, scans, and artifacts never escape the repository-owned directories.

---

# Phase Overview

## Phase A – Platform Core (✅ Completed)
- [x] Finalize `docs/report_schema.json` and CLI output format.
- [x] Add `tfreview.yaml` waivers + severity thresholds (config loader and CLI exit codes).
- [x] Harden initial generators (S3/Storage/K8s Deployment) with secure defaults, tagging, remote state toggles.
- [x] Refactor rule engine into provider modules with metadata registry and RAG explanations.
- [x] Seed knowledge base + link explanations in findings.

### Deliverables
- SvelteKit wizard with AWS/Azure/K8s flows wired to FastAPI endpoints.
- CLI with Terraform validate integration.
- Initial policy coverage (S3 HTTPS/SSE, storage HTTPS, kube runAsNonRoot, etc.).
- Optional terraform validation in tests/CI via `TFM_RUN_TERRAFORM_VALIDATE`.

---

## Phase B – Coverage Expansion (🚧 In Progress)

### Generators (✅ done / 🔄 in progress / ☐ planned)
- **AWS**
  - ✅ `aws_vpc_networking.tf.j2`
  - ✅ `aws_observability_baseline.tf.j2`
  - ✅ `aws_rds_baseline.tf.j2`
  - ✅ `aws_alb_waf.tf.j2`
  - ✅ RDS read replicas / multi-region backups
  - ✅ ALB access logging support (S3 bucket + policy helper)
  - ✅ `aws_ecs_fargate_service.tf.j2`
  - ✅ `aws_eks_irsa_service.tf.j2`
- **Azure**
  - ✅ `azure_storage_account.tf.j2`
  - ✅ `azure_vnet_baseline.tf.j2`
  - ✅ `azure_key_vault.tf.j2`
  - ✅ `azure_diagnostics_baseline.tf.j2`
  - 🔄 Diagnostics bundle expansion:
    - ✅ Auto-attach diagnostic settings for NSGs, subnets, and VNets
    - ✅ Introduce private endpoint helper outputs for storage/account targets
- **Kubernetes**
  - ✅ `k8s_deployment.tf.j2`
  - ✅ `k8s_namespace_baseline.tf.j2`
  - ✅ `k8s_pod_security_baseline.tf.j2`
  - ✅ `k8s_psa_namespaces.tf.j2`
  - ✅ `k8s_argo_cd_baseline.tf.j2`
  - ✅ `k8s_hpa_pdb.tf.j2`
  - ✅ Add PodSecurity Standard (baseline/restricted) namespace templates at scale

### Policy Expansion
- **AWS** – DONE: CloudTrail, Config, RDS encryption/backups/PI, ALB HTTPS, WAF association.
  - ✅ EKS: enforce IMDSv2 + control plane logging coverage.
  - ✅ RDS: ensure deletion protection, enhanced monitoring.
  - ✅ S3: access logging, block public access per account.
  - ✅ ECS: detect Fargate services that assign public IPs to tasks.
  - ✅ EKS IRSA: require trust policies to bind to service accounts and the STS audience.
- **Azure** – DONE: storage HTTPS, KV purge/network, diagnostics.
  - ✅ Mirror diagnostics enforcement for NSGs, VNets, and subnets in reviewer (generator parity).
  - ✅ Storage private endpoint association check (generator + reviewer rule).
  - ✅ Log Analytics workspace health alert rule for diagnostics pipelines.
  - ✅ AKS: enforce Azure Policy add-on and control plane diagnostic log coverage.
- **Kubernetes** – DONE: namespace netpol, PDB, privileged/hostPath detection.
  - ✅ Container seccomp profiles / AppArmor annotations.
  - ✅ Horizontal coverage for DaemonSet/StatefulSet runAsNonRoot.

### Tooling / Validation
- ✅ Generator render tests for every template (includes optional terraform validate).
  - 🔄 Sample fixture library per rule for regression testing.
  - 🔄 Add golden fixtures for new generators (terraform plan/validate outputs).

---

## Phase C – Developer Experience & CI Controls (📝 Planned)
- PR comment bot / GitHub App that surfaces top findings with permalinks.
- ✅ Surface severity gating outcomes from `tfreview.yaml` in SvelteKit Review tab.
- ✅ Baseline file generation to suppress legacy noise.
- ✅ `.patch` output for autofixable findings (S3 policies, ALB redirect snippets, etc.).
- ✅ Enhanced reporting (HTML summary) for CI artifacts (trend metrics still pending).

---

## Phase D – Pro Enhancements (📝 Planned)
- Offline embedding-based RAG for richer explanations while preserving air-gap.
- Graph-level checks (resource relationships, cross-stack validation).
- Diff-only scanning for PRs to reduce noise on large repos.
- Terraform Cloud/Atlantis integrations, optional remediation pipelines.

---

# Current Status Summary

## Initiative – Project Workspace UX (🆕 In Progress)
Goal: simplify the entire product around a single “Project” hub so users can create a project and manage configs, scans, reports, generators, and knowledge without jumping between unrelated surfaces. Everything else (CLI, API, frontend, docs) aligns to that mental model.

### Phase 0 – Discovery & Information Architecture
- [x] Audit existing SvelteKit routes (`frontend/src/routes/(app)/*`) and backend endpoints to catalog every user flow touching configs, reviews, generators, knowledge, and artifacts.
- [x] Capture user/jobs-to-be-done from README/docs/support notes and translate them into prioritized use cases for the project workspace.
- [x] Draft an information architecture: `/projects` list, `/projects/:id/summary`, nested tabs (Configurations, Reviews, Reports, Generators, Artifacts, Knowledge, Settings). Validate via mockups/wireframes before coding.

### Phase 1 – Backend Data Model & Storage
- [x] Extend SQLAlchemy models in `backend/db/models.py` (and migrations) with `Project`, `ProjectRun`, `ProjectConfig`, and `ProjectArtifact` tables plus relationships to existing reports/configs.
- [x] Update `backend/storage.py` to provision `data/projects/<slug>/` directories, maintain artifact manifests, and expose helpers for run summaries and project-level counters.
- [x] Backfill existing artifacts/configs into project scope with a data migration script under `scripts/` (log mapping for rollback).

### Phase 2 – API Surface & Aggregates
- [x] Introduce `api/routes/projects.py` with CRUD, summary, run lifecycle, artifact upload/download, and generator/review triggers. Ensure dependencies enforce per-project auth/ownership.
- [x] Add `/projects/:id/summary` aggregate endpoint combining last scan status, drift/cost deltas, config counts, outstanding actions, and linked knowledge snippets.
- [x] Update OpenAPI docs plus `docs/` references and wire router in `api/main.py`. Include request/response models in `api/schemas/projects.py`.

### Phase 3 – CLI & Automation Alignment
- [x] Extend `backend/cli.py` commands (`scan`, `baseline`, `docs`, etc.) to accept `--project-id/--project-slug` and persist outputs in the correct directory tree.
- [x] Add `project create/list/run/upload` subcommands to bootstrap a workspace locally, optionally calling API endpoints for remote state (upload now mirrors the FastAPI artifact endpoints).
- [x] Document CLI workflows in README/knowledge and add regression tests for the new options under `tests/backend/`.

### Phase 4 – Frontend Navigation & State
- [x] Build a global project switcher store in `frontend/src/lib/stores/project.ts` plus derived selectors for summary data; hydrate via `(app)/+layout.server.ts`.
- [x] Refactor navigation so all authenticated routes render under `/projects/:slug/*`; update `src/lib/api` clients to default to the active project.
- [x] Replace fragmented top-level nav with a project-focused sidebar that exposes key actions (Create config, Run review, Upload artifact) contextually.

### Phase 5 – Project Workspace Experience
- [x] Implement `/projects` list with tiles showing latest run status, open issues, and quick actions (open dashboard, start scan, upload artifact).
- [x] Build `/projects/:slug/summary` cards for Configurations, Reviews, Reports, Artifacts, Knowledge, and Status. Each card exposes the most recent items, status pills, and CTA buttons.
- [ ] Consolidate Configs, Reviews, and Reports tabs so users can create/edit configs, trigger scans, review outputs, and promote artifacts without leaving the project.
  - 🔄 Reports tab under `/projects/[slug]/reports` now scopes every API query to the active project ID and slug, keeping filters, pagination, and review metadata edits inside the workspace context.
  - 🔄 Review uploads from `/projects/[slug]/review` now send both `project_id` and `project_slug`, ensuring saved scans and runs stay linked to the same workspace routing model.
- [x] Provide inline diff/file-browser components for run artifacts, referencing helper components under `frontend/src/lib/components/artifacts/`.
  - 🔄 Dashboard now embeds `RunArtifactsPanel`, giving direct access to run file browsers, previews, and per-file diffs without leaving the workspace.

### Phase 6 – Knowledge, Guidance, and Notifications
- [x] Surface contextual knowledge articles linked to the project’s generator/policy tags; update `frontend/src/lib/api/knowledge.ts` to filter by project metadata.
  - 🔄 Added `frontend/src/lib/api/knowledge.ts` plus a dashboard knowledge panel that queries `/knowledge/search` using project metadata + generator tags, surfacing tailored remediation docs directly within each project workspace.
- [x] Add guided toasts/checklists for high-value actions (e.g., drift detected → run review). Use the shared notification store for consistent messaging.
  - 🔄 Dashboard now triggers toast guidance whenever the latest run reports drift or open findings, nudging reviewers toward the Review tab.
- [x] Offer embedded help modals describing CLI equivalents and manual verification steps, populated from `docs/` or `knowledge/`.
  - 🔄 Project dashboard now ships with a CLI help modal featuring curated `backend.cli` snippets plus a manual verification checklist sourced from `knowledge/cli-workspace-workflows.md`.

### Phase 7 – Testing, Documentation, and Rollout
- [ ] Expand backend pytest coverage for new project endpoints/storage plus CLI integration tests ensuring artifacts land in project folders.
- [ ] Add Vitest/component tests for the project store, navigation, and summary cards; include Playwright happy-path flows (create project → run review → inspect artifacts).
- [ ] Update `README.md`, `docs/`, and `knowledge/` to highlight the project-centric UX, migration guidance, and reindex/docs steps when adding new generator inputs.
- [ ] Plan rollout/migration checklist: data backfill, feature flag, beta preview, telemetry instrumentation, and comms.

### Delivered To Date
- ✅ Added inline workspace selector banners across generator/review/report flows, artifact upload & delete controls, and inline previews with previous-run context (sets baseline for the new dashboard).

### Frontend Migration (SvelteKit)
- ✅ Scaffolded SvelteKit workspace with Tailwind + Notus integration and environment-aware token storage synced via cookies/localStorage.
- ✅ Auth flows (login/register/forgot) now persist API tokens and honour redirect targets supplied by protected routes.
- ✅ App layout server load enforces token presence, surfaces sign-out control, and mirrors active token metadata in the UI.
- ✅ Implemented typed API client for FastAPI (`frontend/src/lib/api/client.ts`) and wired dashboard/reports views to live reviewer data.
- ✅ Review tab posts multipart uploads to the new `/scan/upload` endpoint and renders live severity summaries plus artifact download links.
- ✅ Knowledge tab now calls `/knowledge/search`, delivering real RAG snippets with score metadata and quick links to Markdown docs.
- ✅ LLM settings page reads/writes `/settings/llm`, supports configuration validation, and exposes live ping feedback.
- ✅ Knowledge tab now includes manual sync controls for `/knowledge/sync`, enabling GitHub Markdown ingestion without leaving the app.
- ✅ First generator (AWS S3 baseline) now available via `/generators/aws/s3` and a SvelteKit form with direct download/copy helpers.
- ✅ Azure Storage generator wired via `/generators/azure/storage-account`, with private endpoint and network rule options in the UI.
- 🔄 Next: hook generator/review forms to new FastAPI endpoints, embed report viewer tables, and surface knowledge/doc metrics once APIs are exposed.

## Completed (Phase B to date)

---

## Detailed Implementation Plan – Persistent Generator Outputs & Report Library (🆕 Planned)

### Epic A – Backend Persistence & APIs
- [x] **Project-aware generator endpoints**: add `POST /projects/{project_id}/generators/{slug}` + `/blueprints` handlers that wrap existing renderers, enforce project ownership, and create `ProjectRun` rows (kind `generator/<slug>`). Return rendered files plus created asset/version metadata.
- [ ] **Report auto-save in API scans**: update `/scan` + `/scan/upload` to always create a run (when `req.save` true) and persist JSON/HTML outputs via `save_run_artifact` + `register_generated_asset` with `asset_type='scan_report'`.
- [x] **CLI parity hooks**: when CLI generators arrive, allow `backend/cli.py` to accept `--project-id` and forward payloads to the new project-aware endpoints (reuse auth tokens/settings) so automation benefits too.

### Epic B – Storage & Versioning Enhancements
- [x] **Asset bundle manifest**: create `generated_asset_version_files` table storing `{version_id, path, storage_path, checksum, media_type, size}` and update `_create_asset_version` to populate each rendered Terraform file.
- [x] **Workspace layout**: ensure files live under `data/projects/<slug>/library/<asset>/<version>/<path>` for configs and `.../reports/...` for scan artifacts; add helpers to fetch/download manifest entries securely.
- [x] **Diff engine upgrade**: extend `diff_generated_asset_versions` to emit per-file status (added/removed/modified) and unified diffs for Terraform/text files; fall back to metadata-only for binaries.

### Epic C – Validation & Quality Gates
- [x] **Terraform validation service**: implement `backend/terraform_validation.py` to run `terraform fmt -check` + `terraform validate -json` inside a temp dir, capturing diagnostics by file/line/severity.
- [x] **Version metadata columns**: add JSON column `validation_summary` + text `payload_fingerprint` to `GeneratedAssetVersion`; store validation result, generator slug, blueprint id, git commit hash (if provided), and link to originating `ProjectRun`.
- [x] **Force/override workflow**: API should reject promotion on validation failure unless a `force_save` flag is set; responses must include validation details so the UI can guide fixes.

### Epic D – Frontend & UX
- [ ] **Generator wizard updates** (`frontend/src/routes/(app)/projects/[projectId]/generate/+page.svelte`):
  - Add “Destination” step (project selector, naming, auto-save toggle) before review/export.
  - Display validation status + issues, along with quick links (“Open in library”, “Diff vs previous version”).
- [x] **Project Library tab enhancements**:
  - Filter chips for `asset_type` (Terraform configs vs scan reports) and generator slug tags.
  - Manifest viewer & download buttons that call new `/files` endpoints; show validation badges.
  - Diff drawer capable of showing per-file diffs for bundles, reusing upgraded diff API.
- [ ] **Notification hooks**: use the global notification store to surface validation failures, forced saves, and diff generation errors.

### Epic E – Testing, Docs, and Rollout
- [x] **Backend tests**: add pytest coverage for generator persistence, diff manifests, validation success/failure, and scan auto-save flows. Include fixtures in `tests/backend/`.
- [ ] **Frontend tests**: extend Vitest coverage for project store actions + generator page, plus Playwright smoke test (generate config → verify library entry).
- [x] **Documentation & migration**: update `README.md`, `docs/`, and `knowledge/` explaining the new workflow, project directory layout, and validation behavior; provide migration steps for existing assets.
- [ ] **Telemetry/Observability**: emit structured logs (`backend/utils/logging.py`) noting generator slugs, project ids, validation status, and asset ids for easier monitoring post-rollout.
- **AWS Generators**: `aws_vpc_networking`, `aws_observability_baseline`, `aws_rds_baseline`, `aws_alb_waf`, `aws_rds_multi_region`, `aws_ecs_fargate_service`, `aws_eks_irsa_service`.
- **Azure Generators**: `azure_storage_account`, `azure_vnet_baseline`, `azure_key_vault`, `azure_diagnostics_baseline`.
- **Kubernetes Generators**: `k8s_namespace_baseline`, `k8s_hpa_pdb`, `k8s_pod_security_baseline`.
- **Policy Engine**: Expanded AWS/Azure/K8s rule coverage with metadata + knowledge references.
- **CI/Test Enhancements**: Generator render tests with optional `terraform validate`, README updates, and workflow split across backend unit/integration suites, frontend PNPM checks, and reviewer scan artifacts.

## Active / Upcoming Work
- **Azure Diagnostics Sprint**: integration + CLI smoke tests now cover auto-target coverage via `tests/test_cli_integration.py`.
- **Kubernetes Hardening**: ensure policy rules remain robust for DaemonSet/StatefulSet (fixtures in integration tests complete) and explore namespace baseline coverage.
- **AWS Reliability Enhancements**: scanner covers RDS and S3 guardrails, including backup-plan copy enforcement and multi-region replica fixtures; next polish shared log bucket guidance and explore automated drift remediation samples.
- **Testing Enablement**: added Azure diagnostics integration fixtures (complete + missing, now covering health alerts) and prototyped combined-template `terraform validate` smoke tests (see `tests/test_terraform_validate_smoke.py`).
- **CLI Parity & Validation Overrides**: UI/API generator runs now surface validation summaries (with force-save overrides) and the CLI exposes `python -m backend.cli project generator` so automation can hit the same endpoints and persist assets/runs.

## Backlog / Future Ideas
- Azure AKS enhancements (Azure Policy add-on, diagnostics for control plane).
- Kubernetes GitOps add-ons (Flux/ArgoCD advanced scenarios) and additional multi-namespace policy automation.
- Phase C items: PR bots, severity gates, baseline file generator.
- Phase D items: embedding RAG, graph analytics, diff scanning.

---

# References
- **Knowledge Base**: `knowledge/` contains curated best practices referenced in findings.
- **Sample Fixtures**: `sample/` holds insecure snippets for regression testing.
- **CI Workflow**: `.github/workflows/terraform-review.yml` now installs `requirements-dev.txt` (to pull in pytest), caches pip/terraform artifacts, runs backend unit + integration jobs before the Terraform reviewer scan (scoped to `sample/`), and adds a parallel frontend PNPM lint/check/test job.

## Completed (as of now)
- **AWS Generators**
  - `aws_vpc_networking.tf.j2`: secure VPC with flow logs/NAT.
  - `aws_observability_baseline.tf.j2`: CloudTrail + Config baseline.
  - `aws_rds_baseline.tf.j2`: encrypted RDS with backups, Performance Insights.
  - `aws_rds_multi_region.tf.j2`: cross-region replica with AWS Backup copy rule.
  - `aws_alb_waf.tf.j2`: HTTPS ALB with ACM cert, HTTP redirect, WAFv2.
  - `aws_ecs_fargate_service.tf.j2`: private Fargate service with CloudWatch logs, ECS Exec, and IAM scaffolding.
  - `aws_eks_irsa_service.tf.j2`: namespace + IRSA role/service account pairing with pod security labels.
- **Azure Generators**
  - `azure_storage_account.tf.j2`: secure storage with firewall toggle and optional private endpoint generator.
  - `azure_vnet_baseline.tf.j2`: VNet + flow logs/diagnostics.
  - `azure_key_vault.tf.j2`: purge-protected KV with private endpoint.
  - `azure_diagnostics_baseline.tf.j2`: Log Analytics + diagnostic settings with optional ingestion health alert and archive storage.
- **Kubernetes Generators**
  - `k8s_namespace_baseline.tf.j2`: quotas, limit ranges, labels.
  - `k8s_hpa_pdb.tf.j2`: autoscaler and PDB.
  - `k8s_pod_security_baseline.tf.j2`: PSP/PSA labeling and RBAC.
- **Policy Engine**
  - AWS: Added rules for RDS encryption/backups/PI, CloudTrail, Config, ALB HTTPS, WAF association, ALB access logging, EKS IMDSv2 enforcement, ECS Fargate public IP detection, and EKS IRSA trust scoping.
  - Azure: Added rules for storage HTTPS, KV purge/network, diagnostics presence.
  - Kubernetes: Added rules for namespace network policy, PDB, privileged containers, hostPath, etc.
- **CI/Test Enhancements**
  - Generator render tests with optional `terraform validate` (controlled via `TFM_RUN_TERRAFORM_VALIDATE`).
  - README updated with new templates and validation instructions.

## In Progress / Next Targets
- Expand Azure baselines to include automated diagnostic coverage for NSGs/VNets/subnets and capture private endpoint requirements in the wizard.
- Add Kubernetes rules/tests for additional PodSecurity admission constraints (seccomp/AppArmor, DaemonSet/StatefulSet inheritance).
- Finalize AWS reliability work: polish shared-bucket access logging guidance and add doc/examples for centralized buckets.
- Explore auto-remediation or patch outputs for common findings (Phase C item).

## Backlog Ideas (beyond Phase B)
- Azure AKS advanced checks (Azure Policy add-on enforcement, diagnostics).
- AWS regional guardrails (config conformance packs) and extended ALB logging scenarios.
- Kubernetes PodSecurity admission baseline for multiple namespaces.
- Phase C/D items: PR comment bot, severity gating, embedding-based RAG, diff-only scanning.

---

## Frontend Migration Roadmap (SvelteKit + FastAPI Integration)

### 1. Layout & Navigation Baseline (🎨 Theming)
- Align root `+layout.svelte` with Notus Svelte shell (header, sidebar, responsive grid) and populate shared nav state via `+layout.server.ts` load functions, following the SvelteKit layout data flow (`/sveltejs/kit` routing docs).
- Establish protected layout wrapper that redirects unauthenticated users pre-render using typed `LayoutServerLoad` guards; ensure tokens persist in cookies/localStorage hybrid store.
- Draft initial Notus-based designs for Login, Register, Forgot Password, Settings, Dashboard, Review, Knowledge, and Generator screens with consistent spacing/typography tokens.

### 2. Auth & Session Wiring (🔐 FastAPI)
- Extend FastAPI auth handlers to return OAuth2-compliant tokens and reuse shared dependencies (`Security`, `SecurityScopes`) for role-based gating per FastAPI security docs.
- Implement refresh-token rotation and background activity logging leveraging FastAPI `BackgroundTasks` for audit trails.
- Wire SvelteKit form actions to `/auth/*` endpoints with optimistic UI states and error surfaces aligned to Notus alerts.

### 3. App Shell Features (🧭 UX Consistency)
- Centralize page breadcrumbs, tab descriptors, and action buttons through layout-level data stores to minimize per-page duplication (per SvelteKit `load` inheritance guidance).
- Add global toast/notification bus and surface asynchronous job states (e.g., `/knowledge/sync` status) with focus on keyboard accessibility.
- Provide skeleton/loading states using Notus components while server `load` functions resolve.

### 4. Generator Flows (⚙️ Templates)
- Complete Kubernetes generator wiring inside `frontend/src/routes/(app)/generate/+page.svelte` once backend renderer lands; extend `generators` array with K8s metadata and dynamic form sections.
- Support multi-step wizard pattern (source, options, review) using SvelteKit progressive enhancement: `+page.server.ts` actions to call FastAPI generator endpoints and stream Terraform artifacts.
- Validate generated bundles by piping FastAPI responses through Terraform CLI smoke tests; apply `moved` blocks in Terraform modules when refactoring template directories to preserve state (`/hashicorp/terraform` planning docs).

### 5. Knowledge Management UX (📚 RAG Enhancements)
- Surface `/knowledge/sync` completion as success/error toasts and log raw sync results in activity history.
- Introduce Markdown preview modal for search hits, loading content via SvelteKit server load and caching in the store for offline-friendly behavior.
- Extend upload pipeline with drag-and-drop dropzone, progress indicators, and FastAPI background indexing feedback.

### 6. Review & Reporting (🛡️ Scan Experience)
- Migrate scan upload flow to SvelteKit form actions with streaming progress feedback; confirm FastAPI dependencies enforce CORS and token scopes.
- Embed findings tables with column grouping (severity/resource/rule) and link to knowledge docs; cache recent uploads in IndexedDB for quick revisit.
- Provide diff viewer component using existing backend diff utilities and align styles with Notus code blocks.

### 7. Settings & Admin (⚙️ Control Plane)
- Build settings subsections (LLM config, tokens, Terraform hooks) using nested routes under `/settings` with layout-supplied section metadata.
- Integrate feature flags for beta generators; guard via FastAPI role-based dependencies and expose toggles in UI.
- Add webhook/API key management page, ensuring secrets masked client-side and retrieved from FastAPI only when necessary.

### 8. Testing & Quality Gates (✅ Confidence)
- Author Playwright flows covering auth, generator submissions (AWS, Azure, K8s), and knowledge sync; run in CI alongside backend tests.
- Create contract tests for FastAPI endpoints (auth, generators, knowledge) verifying scope requirements, leveraging dependency override patterns.
- Maintain Terraform regression safety net by running `python -m backend.cli scan sample --out tmp/report.json` plus targeted `terraform validate` runs after template updates.

### 9. Documentation & Enablement (📝 Change Management)
- Update README/docs with SvelteKit setup, Notus theme usage, auth flow diagrams, and generator walkthroughs; include screenshots from new pages.
- Add knowledge base articles covering Azure generator usage and new workflows; reindex via `python -m backend.cli reindex`.
- Publish migration guide outlining the Streamlit ➜ SvelteKit decommission, deployment steps, and testing expectations for contributors.

---

## Immediate Implementation Steps (🔜 Sprint Focus)

### A. Prototype Notus App Shell & Auth Views
- ✅ Refined `frontend/src/routes/+layout.svelte` and `(app)/+layout.svelte` to honour Notus layout patterns, hydrate sidebar/header state from server data, and redirect unauthenticated users via shared layouts.
- ✅ Added `frontend/src/hooks.server.ts` to populate `event.locals.user` / `token` from cookies and surface them in `(app)/+layout.server.ts` for avatar + expiry metadata; clears invalid tokens on logout.
- ✅ Flesh out `(auth)` child pages (`register`, `forgot-password`) with Notus forms, SvelteKit form actions, and FastAPI-backed workflows while `login` leverages progressive enhancement to hit `/auth/token`.

### B. Expand FastAPI Auth & Session Contract
- ✅ Introduced `api/routes/auth.py` with OAuth2 password flow, JWT access tokens, rotating refresh-token HttpOnly cookies, and shared helpers in `api/security.py`.
- ✅ Updated shared dependency (`require_api_token`) to trust JWT claims, added `/auth/me` + `/auth/logout`, and wired audit logging via `BackgroundTasks` for login/refresh/logout events.
- ✅ Expose new auth events in UI once activity/history surfaces are designed.

### C. Prepare Terraform Generator Safety Nets
- When duplicating or refactoring templates for the new UI flows, add `moved` blocks in Terraform modules as needed so downstream users can run `terraform apply` without state loss (per `/hashicorp/terraform` planning guidance).
- Extend generator smoke tests to cover new Kubernetes flows once UI wiring lands, ensuring `terraform validate` passes for generated archives.

### D. UX Enhancements to Support Upcoming Work
- ✅ Add a reusable toast/notification store in `frontend/src/lib/stores/notifications.ts` to announce outcomes (knowledge sync success, auth errors). Trigger from `/knowledge/sync` calls and generator submissions.
- ✅ Define breadcrumb metadata within `(app)/+layout.svelte` using layout data to drive titles/subtitles across routes.
