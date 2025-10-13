# TerraformManager Frontend (SvelteKit)

This workspace hosts the authenticated dashboard that talks to the FastAPI backend. It ships with Tailwind, Notus-inspired components, and typed API clients that mirror the Python routes.

## Prerequisites
- Node 20 LTS (works with PNPM 9.x).
- Backend API running locally via `python -m api` or remote endpoint with compatible auth settings.
- Copy `.env.example` to `.env` when present; otherwise rely on Vite env vars (`VITE_API_BASE`, `VITE_API_TOKEN`) defined locally.

## Install
```bash
pnpm install
```
- Run from the repository root: `cd frontend && pnpm install`.
- Regenerate type bindings after upgrading SvelteKit with `pnpm prepare` (runs `svelte-kit sync`).

## Develop
```bash
pnpm dev -- --open
```
- By default this proxies API calls to `http://localhost:8890`. Adjust `VITE_API_BASE` to point at another host.
- Authenticated routes live under `src/routes/(app)`; token management is centralized in `src/lib/stores/session.ts`.
- Update shared fetch helpers in `src/lib/api/client.ts` when the backend adds endpoints or response fields.

## Checks & Tests
```bash
pnpm check
pnpm lint        # if lint config is added
pnpm test        # Vitest once suites land
```
- `pnpm check` runs Svelte type checks (`svelte-check`). Introduce Vitest suites in `src/lib/__tests__` as the UI grows.
- Run formatting before commit (if Prettier is added). Align Tailwind class orderings with project conventions.

## Build & Preview
```bash
pnpm build
pnpm preview --host
```
- Production build emits the SvelteKit output in `build/`. Ensure API base URLs are set through environment variables during deployment.
- Preview serves the built assets locally; use `--host` for LAN testing with real backend instances.
