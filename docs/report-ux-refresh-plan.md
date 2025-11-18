# Report UX Refresh Plan

This document outlines the detailed tasks required to elevate the TerraformManager report experience across API and SvelteKit surfaces. Tasks are grouped by delivery surface with explicit artifacts and success criteria.

## 1. Backend API & Diff Serialization

- [ ] **1.1 Create structured diff serializer**
  - Implement `backend/drift/serializer.py` that normalizes Terraform plan JSON (`resource_changes`, `output_changes`) using `terraform-json` helpers.
  - Output fields: `address`, `type`, `module_path`, `actions`, `before`, `after`, `before_sensitive`, `after_sensitive`, `action_summary`, `change_reason`.
  - Unit tests in `tests/backend/drift/test_serializer.py` covering create/update/delete/replace, sensitive data, no-change scenarios.

- [ ] **1.2 Integrate serializer with scanning pipeline**
  - In `backend/scanner.py`, call the serializer when plan data is present and add the resulting list under `report["diff"]`.
  - Ensure HTML/CSV exporters read from the new structure when available to avoid duplicating transformation logic.

- [ ] **1.3 Persist structured diff**
  - Adjust `backend/storage.py` `save_report`/`get_report` to store and retrieve the `diff` field without schema flags.
  - Verify backward compatibility for existing records (absence of `diff` should not break readers).

- [ ] **1.4 Add diff API endpoint**
  - Expose `GET /reports/{id}/diff` in `api/main.py` behind auth, returning paginated change sets.
  - Support query params: `action` (create|update|delete|replace|plan-only), `module_path`, `page_size`, `cursor`.
  - Implement pagination helpers in storage layer to slice large diffs efficiently.

- [ ] **1.5 Update existing report endpoints**
  - Include basic diff metadata (change counts) in `GET /reports/{id}` summary payload to support UI overview cards.
  - Extend `/reports` list response with indicator fields (`has_diff`, `total_changes`) for filtering.

- [ ] **1.6 Enhance CLI exports**
  - Update `backend/cli.py` HTML/CSV/patch commands to leverage structured diff; keep unified diff in legacy key for compatibility.
  - Add CLI option (`--diff-json`) to write standalone diff payloads for automation users.

- [ ] **1.7 Backend regression coverage**
  - Add pytest covering new API endpoint, pagination, storage changes, and failure modes (`tests/backend/api/test_report_diff.py`).
  - Update sample fixtures under `tests/backend/data/` to include diffs for UI and docs demos.
  - Run full suite (`pytest -q`) plus targeted coverage for cost/drift modules to ensure no regressions.

## 2. Frontend Report Experience

- [ ] **2.1 Extend API client**
  - Update `frontend/src/lib/api/types.ts` and `client.ts` with typed responses for `GET /reports/{id}/diff` and new summary fields.
  - Introduce cursor-aware fetch helper returning `{ items, nextCursor, total }`.

- [ ] **2.2 Report page data loading**
  - Modify `reports/[id]/+page.ts` to fetch diff summary alongside existing data.
  - Implement lazy loading (SvelteKit `load` + `fetch`) for diff detail requests triggered by the viewer.

- [ ] **2.3 Build diff viewer components**
  - Create `ReportDiffViewer.svelte` handling sidebar filters (action, resource search, module path) and main panel rendering.
  - Integrate CodeMirror diff (split/unified toggle) with syntax highlighting and collapsible before/after JSON.
  - Provide empty/loading/error states; use virtualization for large change lists.

- [ ] **2.4 Refresh findings list**
  - Replace static findings table with a filterable `FindingsList.svelte` using virtual scroll (`svelte-virtual`) and severity/tag chips.
  - Sync filters to URL query params (`page`, `severity`, `text`) for deep-linking.

- [ ] **2.5 Summary sidebar & metrics**
  - Introduce `SummarySidebar.svelte` summarizing severity counts, drift stats, cost, change counts, and run metadata.
  - Ensure responsive behavior with sticky positioning on desktop and collapsible accordion on mobile.

- [ ] **2.6 Accessibility & semantics**
  - Audit all tables/cards to keep semantic `<table>` structure with overflow wrappers per W3C guidance.
  - Add keyboard interactions for diff navigation, collapsible sections, and ensure focus management on modal/drawer open.

- [ ] **2.7 Frontend tests & stories**
  - Add Vitest tests for diff viewer filtering, pagination, and state transitions under `frontend/src/routes/(app)/reports/__tests__/`.
  - Create mock route (`frontend/src/routes/(app)/reports/mock/+page.svelte`) to iterate with sample JSON.
  - Integrate Playwright E2E coverage for critical flows: loading report detail, diff filters, finding navigation (`pnpm test:e2e`).
  - Enable accessibility snapshots with `@axe-core/playwright` on key routes.

## 3. Review Workflow Enhancements

- [ ] **3.1 Adopt SvelteKit form actions**
  - Move upload handling to `review/+page.server.ts` using form actions; ensure server-side fetch posts to FastAPI.
  - Apply `use:enhance` on the client for progressive enhancement, preserving current validation.

- [ ] **3.2 UI/UX polish**
  - [x] Inline step indicators and contextual tooltips guide reviewers through upload → review → export, and saved scans now surface inline asset/version metadata with copy helpers.
  - [x] Success toasts announce the library asset id/version created by `/scan/upload`; validation failures still raise error toasts with actionable text.
  - [x] Drag-and-drop upload affordances plus skeleton loaders keep the experience responsive while scans run.

- [ ] **3.3 Project run logging helper**
  - Extract run logging into `$lib/stores/projectRuns.ts` shared by review/report pages; handle missing token/project gracefully.

- [ ] **3.4 Styling consistency**
  - Enable `@tailwindcss/forms` (strategy `'class'`) in `frontend/tailwind.config.cjs`.
  - Define shared form control classes (`form-input`, `form-select`, error states) and apply across review page.
  - Add component tests verifying form validation states and toast notifications using Vitest/MSW.

## 4. Documentation & Operational Updates

- [ ] **4.1 User-facing docs**
  - Update `docs/reports.md` describing new diff endpoint, UI capabilities, and download options.
  - Document review workflow changes and form usage in `docs/review.md` (or create if missing).

- [ ] **4.2 Release notes & roadmap**
  - Add summary to `PLAN.md` and note manual verification steps.
  - Call out any required infrastructure tooling (e.g., ensure `terraform` binary availability for diff parsing).

- [ ] **4.3 Sample data & demos**
  - Add enriched sample report JSON (with diff + findings) under `sample/reports/` for demos/tests.
  - Capture screenshots or animated GIFs of the refreshed UI for README/marketing.

- [ ] **4.4 QA checklist**
  - Compose validation script: run scan (`python -m backend.cli scan sample --out tmp/report.json --html-out tmp/report.html`), open `/reports/{id}` in UI, exercise diff filters, confirm accessibility checks (`pnpm lint`, `pnpm check`, `pnpm test`, `pytest -q`).
  - Run `pnpm lint:css` / `pnpm format` (if configured) to ensure styling consistency, and capture Lighthouse report for the report detail route.

- [ ] **4.5 Deployment considerations**
  - Ensure API response size limits are respected (compression, pagination).
  - Coordinate rollout order: deploy backend first (no breaking schema flags), then ship frontend using new endpoints.

## 5. Dependencies & Sequence

1. Complete backend serialization (Section 1.1–1.4) so API contracts exist.
2. Update storage/CLI (Section 1.5–1.6) to keep downstream tools aligned.
3. Land frontend data fetching and diff viewer (Section 2) once endpoints are available.
4. Modernize review workflow (Section 3) in parallel, ensuring API token handling remains consistent.
5. Finalize docs, QA, and release notes (Section 4) before merge.
