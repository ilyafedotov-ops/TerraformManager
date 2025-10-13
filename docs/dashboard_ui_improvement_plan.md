# Terraform Manager Dashboard UI/UX Improvement Plan

Plan derived from Tabler dashboard patterns [/tabler/tabler], Shadboard navigation guidance [/qualiora/shadboard], and Svelte component best‑practice documentation [/websites/svelte_dev].

## Task 1 — Discovery & Audit
- Inventory existing dashboard cards, filters, navigation routes, and shared markup.
- Capture stakeholder priorities (most used views, required quick actions) to shape tab/step enhancements.

## Task 2 — Navigation Refinement
- Organize sidebar links into titled groups with optional badges/icons; add collapsible behaviour for secondary areas. ✅ collapsible state is now stored in `navigationState` so sections persist across route changes.
- Implement a typed `MainNav` Svelte component that consumes structured navigation data. ✅ done
- Lazy-load seldom-used sections with dynamic `import()` to trim the initial bundle. ✅ settings subtree loads on demand

## Task 3 — Dashboard Card Enhancements
- Add tabbed cards for switching between severity/time-range views. ✅ done

## Task 4 — Guided Workflows & Contextual Actions
- Insert a visible step indicator (scan → review → export) for reviewer flow. ✅ done
- Embed primary actions (export, share, drill-down) directly within cards and lists. ✅ Report table and review scan summary now ship as reusable components; knowledge sync controls expose a reusable form with tests. Review summary exports now delegate to the shared `ReportActions` control so the legacy inline buttons are retired.
- Ensure command palette results and per-row menus invoke typed handler props for flexibility. ✅ command palette updated; per-row menus pending enhancements.

## Task 5 — Component & Store Refactor
- Move navigation state (active section, collapse state, shortcuts) into a dedicated store/composable. ✅ active path, sidebar, command palette, and expanded states are unified in `navigationState`
- Relocate severity charts, report lists, knowledge previews into `src/lib/components`. ✅ dashboard severity view (with tests), report table, knowledge results, review scan form/summary, and LLM settings form are reusable components
- Document component props/exports with JSDoc for IDE discoverability. ✅ new dashboard/report/knowledge/review/settings components now include inline JSDoc; legacy widgets still pending review

## Task 6 — Accessibility & Performance Pass
- Verify modals/overlays meet role and tabindex requirements; confirm keyboard control coverage. ✅ Command palette dialog now owns `role="dialog"`, traps focus bidirectionally, restores the triggering control, and exposes `aria-labelledby`.
- Select icon sets that bundle efficiently to avoid Vite pre-bundle slowdowns. ✅ Navigation `Icon` component imports only the handful of Lucide glyphs in use, shrinking the bundle and keeping tree-shaking intact.
- Stream long-running data via SvelteKit load promises to progressive-render heavy views. ✅ done (dashboard stats now return deferred promises with in-component fallbacks).
- Ensure responsive fidelity for new components. ✅ Report table adds horizontal scrolling on narrow screens; knowledge results buttons adapt to full-width on mobile.

## Task 7 — QA & Rollout
- Add Svelte Testing Library coverage for nav toggles, command palette, and new widgets. ✅ coverage landed for StatCard, Tabs, ReportActions, navigation store/command palette behaviour, MainNav expand/click flows, and command palette keyboard interactions.
- Validate mobile responsive behaviour and adjust tap targets/layout where needed.
- Run `pnpm lint`, `pnpm check`, `pnpm test`, and conduct UX review prior to deployment.
