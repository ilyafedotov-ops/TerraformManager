Terraform Configuration Enhancement Plan
========================================

Context
-------
- Current generators cover a rich AWS/Azure/Kubernetes catalog but lack a shared metadata layer, configuration schema, and consistent documentation across templates.
- Reviewer focuses on static rule evaluation; opportunities exist to add idiomatic Terraform quality gates (fmt/validate/tflint), cost impact, and drift insights seen in industry tooling.
- Documentation is mostly hand-written; HashiCorp’s `terraform-docs` CLI supports automated input/output references, while the `pre-commit-terraform` hooks demonstrate how to enforce formatting, validation, security, and cost checks before merge.
- Goal: deliver cohesive improvements spanning generation, review, and documentation to align with best practices surfaced in Terraform core guidance and popular ecosystem tooling (e.g., `terraform-docs`, `pre-commit-terraform`, Infracost).

Task 1 – Generator Metadata & Input Contracts
---------------------------------------------
- **Goals**
  - Establish a registry describing each template (inputs, outputs, compliance tags, provider requirements) to drive UI/CLI discovery.
  - Introduce typed payload validation (pydantic models) to guarantee secure defaults and enforce required fields.
- **Key Activities**
  - Build `backend/generators/registry.py` that maps slugs to template metadata and render functions.
  - Author pydantic schemas per template with defaults mirroring current secure recommendations.
  - Surface metadata to SvelteKit via `/generators/metadata` endpoint for dynamic wizard forms.
- **Outputs**
  - Reusable metadata objects with JSON schema export.
  - Validation errors surfaced consistently across API, CLI, and UI.
- **Dependencies**
  - Coordination with existing FastAPI generator endpoints; minimal risk to scanner components.

Task 2 – Blueprint Composition & Remote State Patterns
------------------------------------------------------
- **Goals**
  - Allow users to compose multi-module blueprints (e.g., VPC + EKS + IRSA) with environment-aware overlays and remote state backends.
  - Encode best practices for backend configuration (S3 + DynamoDB, Azure Storage) and workspace separation.
- **Key Activities**
  - Extend generator service to render module bundles with optional environment matrix (dev/stage/prod).
  - Provide reusable snippets for Terraform `backend` blocks, state locking, and workspaces; expose toggles in generator payloads.
  - Add helper to emit supporting artifacts (variables files, backend.tfvars) alongside `main.tf`.
- **Outputs**
  - Downloadable archives containing orchestrated templates, environment overlays, and backend scaffold.
  - Documentation updates outlining state management strategy per cloud.
- **Dependencies**
  - Relies on Task 1 metadata for dependency ordering and input validation.

Task 3 – Static Validation & Pre-commit Workflow
-----------------------------------------------
- **Goals**
  - Bake in fmt/validate/lint/security checks so generated code and user repos can adopt them effortlessly.
  - Leverage `pre-commit-terraform` hook patterns to provide turnkey `.pre-commit-config.yaml` samples.
- **Key Activities**
  - Integrate Terraform CLI steps (`init`, `fmt`, `validate`) into generator tests and optional user download artifacts.
  - Add optional `tflint`, `tfsec`, and `checkov` execution hooks exposed via CLI flags and documented pre-commit config.
  - Publish sample `.pre-commit-config.yaml` referencing the upstream hooks (`terraform_fmt`, `terraform_validate`, `terraform_docs`, `infracost_breakdown`) per context7 guidance.
- **Outputs**
  - Updated CLI `scan` command and docs instructing how to run the checks locally and in CI.
  - Template repository snippet users can copy into infrastructure repos.
- **Dependencies**
  - Requires CI updates to cache CLI downloads; ensure tests remain deterministic.

Task 4 – Cost & Drift Awareness in Reviews
-----------------------------------------
- **Goals**
  - Surface estimated cost deltas and drift signals during scan/review to prioritize remediation.
  - Integrate Infracost-style breakdowns and optional Terraform plan comparisons.
- **Key Activities**
  - Add optional `--cost` flag to CLI that runs Infracost (using configuration from sample `.infracost.yml`) and attaches results to reports.
  - Extend FastAPI review endpoint to accept Terraform plan JSON, highlighting drifted resources and policy breaches.
  - Update HTML/JSON report schema to include cost summary, drift status, and gating thresholds.
- **Status**
  - ✅ CLI now supports `--cost`/`--cost-usage-file` flags (Infracost integration with HTML + JSON summaries) and `--plan-json` for drift review; FastAPI `/scan` mirrors the new inputs.
- **Outputs**
  - Enhanced report artifacts consumed by SvelteKit dashboard (charts, callouts).
  - Policy rules that can fail builds when cost deltas exceed configured limits.
- **Dependencies**
  - Coordination with Task 3 hook samples; requires documenting Infracost environment setup.

Task 5 – Documentation Automation & Knowledge Sync
--------------------------------------------------
- **Goals**
  - Autogenerate module usage docs leveraging `terraform-docs`, ensuring inputs/outputs stay current.
  - Keep knowledge base aligned with generator updates and flag reindexing needs.
- **Key Activities**
  - Embed `terraform-docs` into generator pipeline (per CLI usage references) to emit README sections for each template and inject into `docs/generators/`.
  - Create `.terraform-docs.yml` config supporting replace/inject modes for repo-wide consistency.
  - Extend knowledge sync CLI to tag new docs and trigger `backend.cli reindex` when generator metadata changes.
- **Status**
  - ✅ Added `.terraform-docs.yml`, `backend.generators.docs.generate_docs`, and `terraform-manager-cli docs` command that renders metadata-driven docs via `terraform-docs`, mirrors them to `knowledge/generated/`, and refreshes the knowledge index.
- **Outputs**
  - Standardized documentation for every template (inputs, outputs, requirements) linked from UI.
  - Contributor guide detailing documentation workflow and tooling setup.
- **Dependencies**
  - Task 1 metadata provides source-of-truth for inputs/outputs; automation consumes it.

Task 6 – Reviewer Rule Expansion & False-Positive Guardrails
-----------------------------------------------------------
- **Goals**
  - Broaden rule coverage to align with newly generated blueprints and reduce noise via context-aware suppression.
  - Inject best-practice validations (e.g., lifecycle `create_before_destroy`, tagging, logging) derived from HashiCorp guidance.
- **Key Activities**
  - Map each template to corresponding policy checks; add cross-resource validations (log buckets referenced by multiple modules, IRSA trust scoping).
  - Implement waiver heuristics (per-resource baseline, environment tags) to avoid duplicate findings across composed stacks.
  - Enhance remediation hints with links to knowledge articles and generator options.
- **Status**
  - ✅ Added Terraform backend hygiene checks for S3/Azure remote state and enforced CloudWatch log retention; metadata + knowledge docs updated to guide remediations.
- **Outputs**
  - Updated `policies/` modules with metadata pointing back to template recommendations.
  - Regression fixtures confirming both positive and negative scenarios for new blueprints.
- **Dependencies**
  - Relies on Task 2 composition stories to understand multi-module context.

Task 7 – Testing & Release Process
----------------------------------
- **Goals**
  - Ensure every generator blueprint and reviewer rule ships with deterministic tests, golden fixtures, and optional Terratest smoke coverage.
  - Streamline release notes capturing generator/reviewer/doc changes.
- **Key Activities**
  - Expand `tests/test_generators_render.py` with composition scenarios and terraform plan snapshots (store sanitized outputs under `tests/backend/fixtures`).
  - Introduce lightweight Terratest harness (Go) for critical modules (e.g., VPC + EKS) executed in CI weekly or on-demand.
  - Automate changelog entries summarizing new templates, rules, and docs updates.
- **Status**
  - ✅ Added unit coverage for blueprint bundles, Infracost/drift integration, and policy regressions; CLI docs command now exercised by tests to guard automation flows.
- **Outputs**
  - Stable test suite guarding against regression in template composition and validation flows.
  - Documented release checklist covering CLI, API, UI, and knowledge updates.
- **Dependencies**
  - Builds on preceding tasks; testing artifacts should reference metadata registry and doc automation results.

Task 8 – Frontend & UX Integration
----------------------------------
- **Goals**
  - Reflect new capabilities in the SvelteKit dashboard with guided flows, inline validation, and richer report visualizations.
  - Provide onboarding and quickstart experiences for generator bundles and review enhancements.
- **Key Activities**
  - Update `frontend/src/lib/api` clients to consume metadata, cost, and drift fields.
  - Add wizard steps for environment matrices, remote state selection, and pre-commit export downloads.
  - Enhance report views with cost charts, drift tables, and documentation links generated in Task 5.
- **Status**
  - ✅ API client exposes `includeCost`/`planPath` parameters and SvelteKit’s report screen now renders cost/drift summaries alongside findings.
- **Outputs**
  - UX that surfaces the improved Terraform workflow end-to-end (generate → cost/drift review → document → validate → report).
  - Tutorials or walkthroughs embedded in docs/UI pointing to new features (see `docs/reviewer_cost_drift.md`).
- **Dependencies**
  - Requires backend endpoints from Tasks 1–5; coordinate release sequencing to avoid broken links.

Next Steps
----------
- Socialize the plan with maintainers, confirm prioritization, and slot tasks into upcoming phases (align with Phase C/D roadmap).
- Begin Task 1 implementation to unlock subsequent workstreams; track progress in `PLAN.md` and cross-link new documentation.
