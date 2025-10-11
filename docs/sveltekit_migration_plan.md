# SvelteKit + TypeScript Migration Plan

## Goals and Guardrails
- Replace the Streamlit UI (`app.py`) and FastAPI/Jinja HTML (`api/ui.py`, `ui/templates/…`) with a single SvelteKit + TypeScript front end while retaining the existing Python backend.
- Preserve feature parity for the Generate, Review, Knowledge, Reports, Configs, Settings, and new Auth pages documented in `README.md` and required for future enhancements.
- Adopt the [Notus Svelte](https://www.creative-tim.com/learning-lab/svelte/overview/notus) design system as the baseline theme for page layouts, navigation, typography, and form components. Customize tokens minimally to align with existing TerraformManager branding.
- Keep Terraform generation logic, scanning rules, and knowledge-base processing in Python; the new frontend should consume them via HTTP APIs.
- Support local developer ergonomics comparable to today (simple `npm run dev` + `python -m api`) and prepare for production builds alongside the FastAPI service.

## Current Frontend Footprint (What We Are Replacing)

### Streamlit App (`app.py`)
- Three primary tabs (`🧰 Generate`, `🔍 Review`, `📚 Knowledge`) containing complex forms, uploaders, and result views.
- Direct imports from `backend.*` modules; Streamlit runs generation templates synchronously and writes artifacts to `generated/`.
- Review tab persists uploaded files under `.uploads/`, optionally shells out to `terraform validate`, and renders findings with remediation/AI details.
- Knowledge tab performs local TF-IDF retrieval (`backend.rag.retrieve`) and renders results inline.

### FastAPI + Jinja (`api/ui.py`, `ui/templates/…`)
- Routes for dashboard, scan workflow, configs, reports, report viewer, knowledge sync, and LLM settings—all rendered server-side with HTMX enhancements.
- Uses shared CSS (`ui/static/app.css`) and Tailwind-inspired utility classes embedded in templates.
- Javascript snippets trigger `/scan`, `/configs/*`, `/knowledge/sync`, etc., via fetch/HTMX calls to FastAPI JSON endpoints (`api/main.py`).
- Authentication (optional API token) is handled manually via localStorage -> Authorization header for HTMX/fetch requests.

### Shared Assets
- Icons, logos, and styling tokens under `ui/static/`.
- Markdown knowledge articles (`knowledge/`) indexed by Python services.
- Sample Terraform fixtures under `sample/` used both in Streamlit and API flows.

### Backend APIs Already Available
- `POST /scan`, `GET /reports/*`, `POST /preview/config-application`, `POST /knowledge/sync`, config CRUD, and LLM settings endpoints (see `api/main.py`).
- Missing APIs: Terraform template generation, knowledge search (`backend.rag.retrieve`), and zipped upload handling for ad-hoc scans.

## Target SvelteKit Architecture

### Project Bootstrap
- Scaffold a SvelteKit TypeScript project (`npx sv create frontend --template skeleton?` per `/sveltejs/kit` docs) rooted at `frontend/`.
- Enable TypeScript/ESLint/Prettier during initializer; default `vitePreprocess()` covers TS support in Svelte (`svelte.config.js` ref. `/sveltejs/kit` topic “typescript”).
- Package manager: adopt `pnpm` (to match upstream SvelteKit tooling) or `npm` if wider team preference dictates; document commands in `README.md`.

### Routing Strategy
- Use grouped routes to separate authenticated “app shell” from misc pages (`src/routes/(app)/…`, referencing grouped layout guidance from `/sveltejs/kit` docs on advanced routing). Dedicated `(auth)` group for login/onboarding utilizes Notus Svelte authentication templates.
- Proposed route map:
  - `(app)/+layout.svelte`: nav shell, API token banner, global toasts/spinner.
  - `(app)/dashboard/+page.(server.)ts`: dashboards for report stats (mirrors `ui/templates/dashboard.html`).
  - `(app)/generate/+page.svelte`: wizard with tabs/steps for AWS/Azure/K8s generators (mirrors Streamlit forms).
  - `(app)/review/+page.svelte`: upload flow, scan options, results table, download actions.
  - `(app)/reports/+page.svelte` & `(app)/reports/[id]/+page.svelte`: list & detail viewer including HTML/CSV download.
  - `(app)/configs/+page.svelte`: CRUD for review configs and previews.
  - `(app)/knowledge/+page.svelte`: search interface + sync controls.
  - `(app)/settings/llm/+page.svelte`: manage provider/model/test actions.
- Auth & marketing routes:
  - `(auth)/login/+page.svelte`: primary login screen styled with Notus Svelte hero/auth block.
  - `(auth)/register/+page.svelte` and `(auth)/forgot-password/+page.svelte`: optional flows for future identity integration; initially wired to local token storage guidance.
  - `landing/+page.svelte`: optional marketing/overview page using Notus Svelte landing layout, can redirect to `/auth/login` when auth required.
- Add `+layout.server.ts` or `+page.server.ts` where SSR data loading is necessary (e.g., dashboards pulling `/reports`).

### Component & State Layer
- Build reusable components under `src/lib/components`:
  - Form primitives (text input, checkbox, select) modeled after current UI semantics.
  - Upload list, severity meters, knowledge result cards.
  - API token modal + persisted store (Svelte writable stores).
- Centralize backend calls in `src/lib/api` with typed wrappers (TypeScript interfaces mapping to FastAPI schemas in `docs/report_schema.json` and Pydantic models).
- For optimistic UI updates (e.g., deleting configs), leverage SvelteKit form actions or `submit().updates()` per `/sveltejs/kit` remote functions guidance.

### Styling & Design System
- Adopt Notus Svelte’s Tailwind-based theme: install the package, import base styles, and scaffold layouts/forms using its component catalog (navbar, sidebar, auth cards, tables).
- Map existing TerraformManager palette to Tailwind config overrides so Notus components reflect current brand accents (replace `tm-*` CSS variables).
- Extract reusable typography/spacing tokens from Notus defaults into `tailwind.config.cjs` for consistency across app/auth sections.
- Implement dark-mode toggle using Notus’ built-in variants; ensure accessibility contrast parity with legacy UI.

### Authentication / API Token Handling
- Mirror existing localStorage approach with a dedicated store (`src/lib/stores/auth.ts`) that injects the token into fetch calls.
- Provide UI for setting/removing the token and persist to `localStorage` via Svelte `onMount`.
- Consider future enhancement: cookie-based session or OAuth if backend evolves.

### Integration with Python Services
- Development: run `npm run dev -- --open` (frontend) alongside `python -m api --reload` on port 8787. Configure Vite proxy to forward `/api/*` or call absolute URLs.
- Production: generate static build (`npm run build`) and either:
  1. Serve built assets via FastAPI’s StaticFiles mount; or
  2. Deploy separately behind a reverse proxy (document trade-offs).
- Assess if FastAPI should expose `/app` prefix for SvelteKit static assets to avoid path clashes with existing `/ui` routes.

## Required Backend Enhancements
- **Template Generation API**: Add FastAPI endpoints (e.g., `POST /generators/aws/s3`) that accept the same payloads Streamlit collects, render via `jinja2.Template`, and respond with `{filename, content}` for direct download or zipped bundles. This keeps business logic in Python.
- **Ad-hoc Scan Upload API**: ✅ Implemented as `POST /scan/upload`, accepting multipart form data (`.tf` or `.zip`) and routing to `scan_paths` while optionally saving reports.
- **Knowledge Search API**: Expose `GET /knowledge/search?q=&top_k=` returning passages from `backend.rag.retrieve`. Needed for the Knowledge tab search UI.
- **Report Viewer JSON**: Optionally enrich `/reports/{id}` with flattened finding summaries (severity, remediation) to power table views without re-parsing HTML.
- **LLM Settings Validation**: Confirm existing `/settings/llm/test` output aligns with UI needs; expand schema if extra metadata is required for TypeScript typing.
- **CORS Review**: Ensure CORS middleware allows SvelteKit dev server origin (currently `allow_origins=['*']` so fine) and tighten for prod if necessary.
- **Streaming/Progress** (Optional): Evaluate SSE or WebSocket for long-running scans to improve UX beyond polling.

## Migration Phases

### Phase 0 – Discovery & Stabilization
1. Catalogue Streamlit form fields and default values for each generator (`app.py` sections around lines 1000–3360).
2. Extract existing CSS variables (the `CUSTOM_PAGE_STYLE` block) into reusable tokens.
3. Confirm FastAPI endpoints cover all data flows; define gaps noted above.

### Phase 1 – Project Scaffold & Tooling
1. `npx sv create frontend` with TypeScript, ESLint, Playwright, and Vitest enabled (per `/sveltejs/kit` quick-start snippet).
2. Configure `pnpm` or `npm` scripts (`dev`, `build`, `preview`, `check`, `test`).
3. Add `@sveltejs/adapter-auto` for dev and determine deployment adapter (likely static + FastAPI static hosting).
4. Install Tailwind + Notus Svelte theme assets; configure global CSS pipeline and import Notus base styles.

### Phase 2 – Shared Layout & Infrastructure
1. Build `(auth)/+layout.svelte` (Notus Svelte auth shell) and `(app)/+layout.svelte` with sidebar/topbar mirroring current navigation but leveraging Notus components.
2. Implement API client module with fetch wrappers that inject API token headers.
3. Integrate universal loading indicator and toast notifications.
4. Add auth/token management UI and guard routes if token is required.

### Phase 3 – Port Existing Jinja Pages
1. **Dashboard**: Fetch `/reports` summary, compute severity counts on server (`+page.server.ts`) for SSR.
2. **Scan Page**: Implement form with options, call new upload/scan endpoints, show severity metrics, and render cURL snippet (client-side generation).
3. **Reports List & Detail**: Mirror table view, add download buttons (JSON/CSV/HTML). Use `load` functions for SSR data fetching.
4. **Configs**: Build CRUD UI with inline editing and preview (calls existing `/configs/*` + `/preview/config-application` endpoints).
5. **Knowledge Sync**: Provide manual sync controls + results history (call `/knowledge/sync`).
6. **Settings**: Manage LLM provider/model toggles, run `test` endpoint, display status using Notus Svelte form layouts.
7. **Auth Pages**: Implement login/register/forgot-password flows reusing Notus Svelte auth templates; hook into token storage until backend auth is formalized.

**Status (2025-02-14)**
- ✅ Dashboard and reports routes now source live data via SSR loaders (`frontend/src/routes/(app)/dashboard/+page.ts`, `frontend/src/routes/(app)/reports/+page.ts`).
- ✅ API client module (`frontend/src/lib/api/client.ts`) centralizes authenticated fetch logic, sharing the cookie-backed token from the app layout.
- ✅ Auth layouts persist tokens to both cookie + `localStorage`, support redirect-on-auth, and expose sign-out UI.
- ✅ `POST /scan/upload` supports multipart Terraform uploads; review tab consumes the endpoint with live summaries and artifact downloads.
- ✅ Knowledge tab consumes `/knowledge/search` and displays scored snippets with Markdown shortcuts.
- ✅ LLM settings page reads/writes `/settings/llm` and `/settings/llm/test`, surfacing validation + live ping results.
- ✅ Added `/generators/aws/s3` endpoint and SvelteKit form to emit hardened S3 baselines with optional remote state backend.
- 🔄 Remaining: configs CRUD, knowledge sync orchestration, and generator wizard integration with future template APIs.

### Phase 4 – Port Streamlit-Only Functionality
1. **Generate Wizards**: For each blueprint (AWS S3, ALB/WAF, RDS, VPC, EKS, Azure KV, Azure Diagnostics, Kubernetes modules), replicate form layout in Svelte components. Serialize payload to template generation API.
2. **AI Assistance Controls**: Map provider/model toggles to backend LLM settings API. Provide context on required env vars.
3. **Report Findings Display**: Build structured findings view using response from `/scan` or `/reports/{id}`. Support download of diff snippets and AI explanations.
4. **Knowledge Search**: Connect to new search API, render markdown previews, handle truncation logic.

### Phase 5 – Hardening & Parity
1. Cross-check every button/workflow between old UI and new SvelteKit implementation (use `sample/` fixtures).
2. Implement Playwright smoke tests covering scan flow, report viewing, generator form validation.
3. Add Vitest unit tests for helper utilities (API clients, stores).
4. Wire SvelteKit `npm run build` output into Docker build (multi-stage: build Node assets, copy into FastAPI image).

### Phase 6 – Cutover & Cleanup
1. Update `README.md` and `docs/` to describe new frontend setup (`npm run dev`) and remove Streamlit instructions once deprecated.
2. Deprecate `app.py` and `ui/templates` in stages; keep behind feature flag until SvelteKit passes regression checks.
3. Remove redundant CSS/JS assets once SvelteKit ship is stable.
4. Archive Streamlit-specific knowledge (note in CHANGELOG/AGENTS.md).

## Testing & QA Strategy
- Maintain existing Python unit/integration tests (`pytest`, `backend.cli scan sample`) during migration.
- Add frontend linting (`npm run check` -> SvelteKit type + ESLint) in CI.
- Create Playwright regression hits:
  1. Load dashboard -> verify stats render with fixtures.
  2. Run scan against `sample/` using new upload flow -> confirm severity counts.
  3. Generate Terraform baseline -> validate download matches template output.
  4. Knowledge search -> ensure markdown results show expected content.
- Evaluate component-level tests via Vitest + Testing Library for form validation logic.

## Developer Workflow Updates
- Document combined dev server instructions (`python -m api` + `npm run dev -- --host`). Add Vite proxy config pointing `/api` to FastAPI if convenient.
- Update Dockerfile to include Node build stage (install deps, `npm run build`, copy `build/` to FastAPI image under `/app/static/frontend`).
- Consider `docker-compose` updates to mount frontend source for HMR in development.

## Risks & Mitigations
- **API Gaps**: Missing endpoints (generator, knowledge search) block UI parity. Mitigate by prioritizing backend tasks before UI-port.
- **State Divergence**: Avoid duplicating business logic in frontend by delegating validation/rendering to Python when possible (e.g., rely on backend to compute report summaries).
- **Large Forms Complexity**: Use schema-driven forms (JSON definitions) or shared components to reduce duplication across AWS/Azure/K8s generators.
- **Performance**: Ensure heavy operations (TF-IDF, scans) remain server-side; front end should poll/progress rather than blocking.
- **Cutover Risk**: Run both UIs in parallel until new SvelteKit interface is accepted; add feature flag/config to toggle default landing page.

## Open Questions
- Should generators return downloadable ZIPs for multi-file assets? Currently they write to disk; need desired UX for browsers.
- How to handle extremely large scan uploads? Might require chunking or direct path selection (as today) instead of file upload.
- Will we require auth beyond tokens (e.g., OAuth) as part of migration? Plan assumes no change.
- Should knowledge search adopt streaming results or adhere to current synchronous approach?

## References
- `/sveltejs/kit` documentation on project scaffolding (`npx sv create …`) and grouped layouts, retrieved via Context7.
- `/sveltejs/kit` TypeScript guidance (`vitePreprocess`, `tsconfig` include paths) for consistent typings across `src/` and tests.
- FastAPI request-form/file handling docs (Context7 `/fastapi/fastapi`) to inform review upload endpoint design.
- Existing TerraformManager README and backend modules (`app.py`, `api/ui.py`, `api/main.py`) for source-of-truth behaviors.
