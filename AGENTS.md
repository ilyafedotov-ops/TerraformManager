# Agent Handbook

## Repository Layout
- `frontend/` contains the SvelteKit dashboard; use `src/lib/api` for typed clients and `src/routes/(app)` for authenticated pages.
- `api/` is the FastAPI surface that powers `/scan`, `/reports`, auth flows, and serves the lightweight HTMX UI in `ui/`.
- `backend/` houses reusable engines: `cli.py`, `scanner.py`, `policies/`, `generators/`, `rag.py`, `validators.py`, and shared utilities under `utils/`.
- `knowledge/`, `docs/`, `sample/`, and `tests/backend/` provide explainer content, schemas, regression fixtures, and automated coverage respectively.

## Environment & Tooling
- Python 3.11+ recommended; bootstrap with `python -m venv .venv && source .venv/bin/activate`.
- Install shared dependencies via `pip install -r requirements.txt`; CLI and API share the same stack.
- Frontend uses PNPM: `cd frontend && pnpm install`; dev server runs with `pnpm dev -- --open`.
- FastAPI API runs with `python -m api` (loads uvicorn with auto-reload).
- Rebuild the TF-IDF index after adding Markdown knowledge with `python -m backend.cli reindex`.

## Working Agreements
- Follow PEP 8 with 4-space indentation, rich type hints on public `backend/` functions, and concise docstrings where behavior is non-obvious.
- Svelte files embrace `script lang="ts"` and Tailwind classes; keep route-level actions in `+page.server.ts` and share layout state through stores (`frontend/src/lib/stores`).
- Keep Jinja templates terraform-native (e.g., `aws_s3_bucket.default`) and document new inputs in the generator metadata.
- Use environment variables for credentials or model keys; never hard-code secrets or commit local secrets files.
- Prefer `rg`/`pytest -q`/`pnpm test` in this repo; avoid destructive git commands unless a maintainer asks explicitly.

## Validation Flow
- Run `python -m backend.cli scan sample --out tmp/report.json` before merge; optionally add `--terraform-validate` when Terraform is installed.
- HTML/CSV artifacts can be produced with `--html-out report.html` and `--patch-out autofix.patch`; attach sanitized outputs to PRs when relevant.
- FastAPI smoke test: `python -m api` then hit `/health`; for auth flows, supply `TFM_API_TOKEN` or JWT tokens described in `api/security.py`.
- Frontend CI parity: `cd frontend && pnpm lint && pnpm check && pnpm test` (Vitest). Align any new endpoints with `frontend/src/lib/api/client.ts`.
- Terraform templates should round-trip through `scripts/render_templates.py` (if added) or manual `terraform fmt && terraform validate` in a temp directory.

## Collaboration Checklist
- Split work by surface: frontend changes under `frontend/`, API changes touch `api/`, static checks and generators in `backend/`.
- Document new reviewer rules or generator inputs in `docs/` or `knowledge/` and call out reindexing needs.
- Use imperative, scope-prefixed commit messages (`feat(scanner): enforce alb logging`) and keep unrelated work in separate PRs.
- Update README/PLAN when roadmap or feature matrices change; surface manual verification commands in PR descriptions.
- If you add new configuration or secrets, ensure `.env.sample` (if created) reflects them and reference loading helpers in `backend/utils/env.py`.
