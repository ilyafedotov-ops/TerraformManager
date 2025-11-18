# Project Workspace Phase 0 – Flow Audit & IA Validation

## Goals
- Inventory the current TerraformManager flows across frontend routes, API endpoints, and storage helpers to understand how users interact with configs, scans, generators, reports, knowledge, and artifacts.
- Highlight UX and architectural friction that prevents users from working entirely inside a “Project” context.
- Validate the target information architecture (IA) so subsequent backend/frontend changes have a clear blueprint.

## Current Flow Audit

| Surface | Frontend entrypoint(s) | Backend touchpoints | Responsibilities today | Notable gaps |
| --- | --- | --- | --- | --- |
| Projects & Runs | `frontend/src/routes/(app)/projects/+page.svelte` | `api/routes/projects.py`, `backend/storage.py` | CRUD projects, list runs, view artifacts/library, edit metadata. | Project context stops here; other routes ignore the active project or replicate selectors. |
| Review / Scan Upload | `frontend/src/routes/(app)/review/+page.svelte` | `/scan/upload` + `projectState.createRun()` | Upload Terraform archives, trigger scans, optionally log runs. | Scan UX is separate from Projects tab; run logging fails silently if no project selected. |
| Reports | `frontend/src/routes/(app)/reports/+page.svelte` | `/reports`, `/reports/{id}` CRUD + comments | Browse historical scans, edit review metadata, manage comments, download artifacts. | Reports are global; no project filtering or deep links from run history. |
| Config Management | `frontend/src/routes/(app)/configs/+page.svelte` | `/configs*`, `/preview/config-application` | Create/update/delete `tfreview` configs and preview effects. | Configs are shared globally; no association with project baselines. |
| Generator Wizard | `frontend/src/routes/(app)/generate/+page.svelte` | `/generators/*`, `/generators/metadata`, project runs | Multi-step wizard for AWS/Azure templates, includes run logging hook. | Generated files are not routed back into project artifacts automatically unless user manually uploads. |
| Knowledge | `frontend/src/routes/(app)/knowledge/+page.svelte` | `/knowledge/sync`, `/knowledge/search`, `/knowledge/doc` | Search/sync Markdown knowledge and preview docs. | No project scoping; results can’t be pinned to a project’s context or run. |
| Dashboard & Settings | `frontend/src/routes/(app)/dashboard|settings/*` | `/reports`, `/auth/*`, `/settings/llm*` | High-level stats, auth events, LLM provider configuration. | Metrics are global; navigation breadcrumbs ignore project selection. |

### Detailed Findings

#### Projects (current hub)
- UI relies on a dedicated store (`frontend/src/lib/stores/project.ts`) that caches projects, runs, artifacts, library assets, and overview aggregates.
- Projects page mixes overview, run history, artifacts, library, and settings tabs inside one route (`projects/+page.svelte:1-200`). Each tab fetches data lazily through `projectState.*` helpers.
- Library management (diffs, metadata editing) lives here, so promoting generator outputs requires jumping between Generate → Projects.
- Active project selection is stored globally, but no router-level guard enforces that other routes read it.

#### Review / Scan
- Review page handles file uploads, toggles (terraform validate, cost, save), and hits `/scan/upload` (`frontend/src/routes/(app)/review/+page.svelte`). It now blocks submission until a project id/slug is present, preventing anonymous scans from drifting outside the workspace.
- After a scan completes, `projectState.createRun` logs a run and `updateProjectRun` stores summaries. Saved runs now echo the generated `asset_id`/`version_id` and artifact paths straight into the UI with copy-to-clipboard helpers plus toasts referencing the library entry so reviewers can pivot directly into the project library.
- Findings visualization (steps, severity breakdown) is isolated; artifacts panel is separate from project artifacts tree, so users still bounce between this page and the Projects tab for historical context.

#### Reports
- Reports page lists saved runs from `/reports` with filtering, review metadata editing, and comment threads (`frontend/src/routes/(app)/reports/+page.svelte`).
- Artifact previews use `RunArtifactsPanel`, but there is no explicit link between a report and a project; filters operate on global metadata (status, assignee, search).
- Deleting reports or updating review status has no side effects on project run history.

#### Configs
- Config management is completely global (any saved config applies to all runs). Users can preview configs against arbitrary report IDs without any awareness of project scope (`frontend/src/routes/(app)/configs/+page.svelte`).
- There is no place to pin a “default config” for a project, forcing manual bookkeeping.

#### Generator Wizard
- Generator UX is multi-step with bespoke forms per template; results stream back as JSON/TF text (`frontend/src/routes/(app)/generate/+page.svelte`).
- Successful generations show a toast and optionally log a project run, but assets are not automatically published into the project library; users must download files and re-upload under Projects → Artifacts/Library.
- Generator metadata is fetched client-side from `/generators/metadata`, so offline or filtered project metadata is not considered.

#### Knowledge
- Knowledge search defaults to a canned query and is global. Sync actions hit `/knowledge/sync` without project metadata aid.
- There is no mechanism to surface “knowledge relevant to the current project” or to attach articles to runs/artifacts.

#### Dashboard & Settings
- Dashboard stats derive from `/reports` across the workspace and show last-run severity counts (`frontend/src/routes/(app)/dashboard/+page.ts`).
- Settings (LLM, sessions) are configured globally; nothing references project overrides.
- Breadcrumb metadata in `(app)/+layout.server.ts` operates on absolute routes and does not reflect project context.

### Pain Points Summarised
1. **Project context leakage** – only the Projects tab is fully project-aware; Review now enforces project selection before uploads, but other feature routes still merely display a banner, so actions outside Projects can still miss context.
2. **Artifact duplication** – generator outputs and scan artifacts require manual promotion or uploading, leading to scattered assets and difficulty tracing lineage.
3. **Global settings without overrides** – configs, knowledge sync, dashboards, and LLM settings lack project scoping, so teams cannot tailor thresholds or docs per project.
4. **Navigation fragmentation** – breadcrumbs and route structure are feature-centric instead of project-centric, so users constantly pivot between tabs and lose context.

## Validated Information Architecture

### Top-Level Navigation
1. **Projects List (`/projects`)**
   - Cards summarizing latest run status, drift/cost deltas, outstanding tasks, and quick actions (open, run review, upload artifact).
   - Supports search/filter by owner, tags, or severity to scale beyond small deployments.
2. **Project Workspace (`/projects?project=<slug>&tab=overview`)**
   - Persistent sidebar with project switcher and shortcuts to Create Config, Run Review, Generate Blueprint, Upload Artifact.
   - Tabs (or nested routes) within the project host all workflow-specific UIs:
     - **Overview** – KPIs, last scan summary, drift/cost callouts, “next recommended actions”, and shortcuts into other tabs.
     - **Configurations** – Manage project-scoped reviewer configs/baselines, attach default `tfreview` profile, show preview results for the project’s latest runs.
     - **Reviews & Reports** – Unified timeline of manual uploads and CLI-ingested reports filtered to the project; inline severity charts, review metadata, comments, and artifact previews.
     - **Generators & Blueprints** – Launch generators pre-populated with project metadata, track generated bundles, and promote directly into the project library.
     - **Artifacts & Library** – Tree view of raw run artifacts plus curated library assets (diffs, metadata editing, version history) consolidated into one surface.
     - **Knowledge & Activity** – Contextual knowledge recommendations based on project tags + chronological activity feed (auth events, knowledge syncs, run status changes).
     - **Settings** – Project-specific metadata (owners, tags, environments), default configs, feature flags, and integrations.

### Data & API Contracts
- Every config, run, artifact, generated asset, and knowledge bookmark references a `project_id`.
- `/projects/:id/summary` returns aggregated counts (runs, configs, artifacts), latest severity/cost/drift deltas, and active guidance; this powers nav badges and Overview cards.
- `/projects/:id/actions/*` endpoints create configs, trigger scans, or launch generators scoped to the project so the UI doesn’t juggle global endpoints.
- CLI gains `--project-id/slug` to ensure automation publishes to the same directories.

### Coverage Mapping

| Existing Flow | Future IA Home | Notes |
| --- | --- | --- |
| Scan uploads (`/review`) | Project → Reviews tab (wizard) | Inline file upload retained but enforces project selection; results auto-link to run timeline. |
| Saved reports (`/reports`) | Project → Reviews tab + Workspace dashboards | Global reports view becomes an aggregate of project timelines with filters. |
| Config management (`/configs`) | Project → Configurations tab (with global fallback) | Users can set project defaults while still accessing global templates. |
| Generators (`/generate`) | Project → Generators tab + quick actions | Wizard pre-seeded with project metadata; outputs stored automatically under project artifacts/library. |
| Knowledge search (`/knowledge`) | Project → Knowledge tab (contextual) + global search modal | Tag-based suggestions plus manual search keep relevant docs within reach. |
| Dashboard (`/dashboard`) | Project Overview + Global Insights page | Workspace-level stats remain but emphasize drilling into projects. |

This IA ensures every workflow starts by selecting a project, keeps related artifacts in one place, and reduces mental overhead for users managing multiple environments.

## Next Steps
1. Socialize this audit + IA with stakeholders to confirm priorities.
2. Identify backend schema deltas (ProjectConfig, ProjectArtifact, etc.) needed to support project-scoped data.
3. Define migration scripts for existing configs/reports to adopt `project_id`s.
4. Break work into milestones aligned with the Phase 1–7 plan already captured in `PLAN.md`.

## Implementation Progress (Phase 1 snapshot)
- **Persistence**: Added `ProjectConfig` and `ProjectArtifact` SQLAlchemy models plus helper APIs so every saved config and artifact is tied to a project. Storage helpers now expose CRUD utilities, pagination, metadata tagging, and summary counts.
- **API Surface**: The FastAPI `projects` router now provides `/projects/{id}/configs/*`, `/projects/{id}/artifacts/*`, and `/projects/{id}/runs/{run}/artifacts/sync` endpoints so the frontend can manage configs, metadata, and re-index runs entirely through the project scope. Overview responses surface config/artifact counts and recent activity.
- **Projects UI & Stores**: The Svelte project store and dashboard now consume the new APIs—overview cards expose config/artifact KPIs, the Projects page includes dedicated “Configs”, “Run files”, and “Artifacts” tabs, and users can create/update/delete project configs, edit artifact metadata, paginate results, and trigger run-specific syncs without leaving the workspace.
- **CLI Integration**: `terraform-manager-cli scan` accepts `--project-id/--project-slug` (plus run label/kind/metadata) to log CLI scans directly into project runs and automatically promote generated artifacts into the project workspace.
- **Backfill tooling**: `scripts/backfill_project_scope.py` seeds per-project configs from existing workspace baselines and indexes historical run artifacts. Run `python scripts/backfill_project_scope.py --help` for options like `--default-config` and `--projects-root`.
