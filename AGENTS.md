# Agent Handbook

## Repository Layout
- `frontend/` — SvelteKit dashboard; rely on `src/lib/api` for typed clients and `src/routes/(app)` for authenticated flows.
- `api/` — FastAPI entrypoint (`api/main.py`) exposing auth, scan/report, generator metadata, blueprint bundling, and knowledge endpoints (docs served under `/docs`).
- `backend/cli.py` — Multi-command CLI (scan, baseline, precommit, docs, auth login, reindex).
- `backend/scanner.py` & `backend/policies/` — Provider-specific rule engines with metadata registry, knowledge linking, and severity gating.
- `backend/costs/` & `backend/drift/` — Infracost wrappers and Terraform plan JSON summarisation feeding report `summary.cost` / `summary.drift`.
- `backend/db/` & `backend/storage.py` — SQLAlchemy models plus persistence helpers for configs, reports, LLM settings, and initialization.
- `backend/knowledge_sync.py` & `backend/rag.py` — Markdown sync (GitHub) and TF-IDF retrieval for knowledge search endpoints.
- `backend/generators/` — Jinja templates, registry (`registry.py`), docs automation, and blueprint rendering (`blueprints.py`).
- `backend/llm_service.py` — Provider validation, caching, and structured response parsing for OpenAI/Azure integrations.
- `knowledge/`, `docs/`, `sample/`, and `tests/backend/` provide explainer content, schemas, regression fixtures, and automated coverage respectively.

## Environment & Tooling
- Python 3.11+ recommended; bootstrap with `python -m venv .venv && source .venv/bin/activate`.
- Install shared dependencies via `pip install -r requirements.txt`; CLI and API share the same stack.
- Optional tooling: Terraform CLI (fmt/validate), [`infracost`](https://www.infracost.io/docs/integrations/cli/) for cost deltas, and [`terraform-docs`](https://terraform-docs.io/) for generator markdown mirroring.
- Frontend uses PNPM: `cd frontend && pnpm install`; dev server runs with `pnpm dev -- --open`.
- FastAPI API runs with `python -m api` (loads uvicorn with auto-reload). For day-to-day development, prefer the supervisor in `scripts/service_manager.py` (`python3 scripts/service_manager.py start all|status|logs api --follow`) so both services and their JSON logs (`logs/api-service.log`, `logs/frontend-service.log`) stay in sync.
- Rebuild the TF-IDF index after adding Markdown knowledge with `python -m backend.cli reindex`.

### Logging
- Structured JSON logging is the default (`backend/utils/logging.py`); tweak verbosity and rotation via `TFM_LOG_*` env vars. Long-running jobs should wrap execution with `log_context` to annotate project/run metadata.
- API requests automatically carry `request_id`, client IP, latency, and user info in the log lines, which live under `logs/terraform-manager.log` (rotating file) plus stdout. Tail with `python3 scripts/service_manager.py logs api --follow` or ship them to your aggregator.

## Working Agreements
- Follow PEP 8 with 4-space indentation, rich type hints on public `backend/` functions, and concise docstrings where behavior is non-obvious.
- Svelte files embrace `script lang="ts"` and Tailwind classes; keep route-level actions in `+page.server.ts` and share layout state through stores (`frontend/src/lib/stores`).
- Keep Jinja templates terraform-native (e.g., `aws_s3_bucket.default`) and document new inputs in the generator metadata.
- Use environment variables for credentials or model keys; never hard-code secrets or commit local secrets files.
- Prefer `rg`/`pytest -q`/`pnpm test` in this repo; avoid destructive git commands unless a maintainer asks explicitly.
- When exposing new generator components, register them in `backend/generators/registry.py` and extend docs via `python -m backend.cli docs`.

## Validation Flow
- Run `python -m backend.cli scan sample --out tmp/report.json` before merge; optionally add `--terraform-validate` when Terraform is installed.
- HTML/CSV artifacts can be produced with `--html-out report.html` and `--patch-out autofix.patch`; attach sanitized outputs to PRs when relevant.
- FastAPI smoke test: `python -m api` then hit `/health`; for auth flows, supply `TFM_API_TOKEN` or JWT tokens described in `api/security.py`.
- Frontend CI parity: `cd frontend && pnpm lint && pnpm check && pnpm test` (Vitest). Align any new endpoints with `frontend/src/lib/api/client.ts`.
- Terraform templates should round-trip through `scripts/render_templates.py` (if added) or manual `terraform fmt && terraform validate` in a temp directory.
- Generator docs: `python -m backend.cli docs --out docs/generators --knowledge-out knowledge/generated` (requires `terraform-docs`; skip reindex locally if unnecessary).

## Collaboration Checklist
- Split work by surface: frontend changes under `frontend/`, API changes touch `api/`, static checks and generators in `backend/`.
- Document new reviewer rules or generator inputs in `docs/` or `knowledge/` and call out reindexing needs.
- Use imperative, scope-prefixed commit messages (`feat(scanner): enforce alb logging`) and keep unrelated work in separate PRs.
- Update README/PLAN when roadmap or feature matrices change; surface manual verification commands in PR descriptions.
- If you add new configuration or secrets, ensure `.env.sample` (if created) reflects them and reference loading helpers in `backend/utils/env.py`.
- When adding blueprint-ready components or knowledge articles, mention whether `/generators/metadata` or `/knowledge/sync` needs to be updated in the release notes.
