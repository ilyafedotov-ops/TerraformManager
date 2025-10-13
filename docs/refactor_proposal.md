# Refactor Plan: Streamlit → FastAPI + HTMX

Goal: keep the deterministic scanner and generators in `backend/`, but replace the Streamlit UI with a lightweight API + minimal HTML front-end. This enables advanced reporting, persisted configs, knowledge sync from GitHub, and simple embeddings without heavy frameworks or DBs.

## Summary
- Backend stays: `backend/scanner.py`, policies, utils, and generators unchanged.
- New API: FastAPI (small, typed, async-ready) served by Uvicorn.
- Storage: SQLite (via SQLAlchemy ORM), single file `data/app.db`.
- Embeddings: in-process TF‑IDF via scikit‑learn; no vector DB.
- UI: small HTMX-powered HTML from the API root (`/`) to avoid SPA frameworks.
- Knowledge: add a GitHub sync to pull Markdown from policy repos and index them.

## New Modules
- `api/main.py`: FastAPI app exposing routes:
  - `GET /health` – liveness probe
  - `POST /scan` – run scans on provided paths; optional LLM options
  - `GET /reports` – list saved reports
  - `GET /reports/{id}` – raw JSON report
  - `GET /reports/{id}/html` – pretty HTML using `backend/report_html.py`
  - `GET /configs`, `POST /configs`, `GET /configs/{name}` – config CRUD
  - `POST /preview/config-application` – show effect of waivers/thresholds
  - `POST /knowledge/sync` – pull Markdown docs from GitHub
  - `GET /` – minimal HTMX UI for quick usage

- `backend/storage.py`: SQLAlchemy-backed repositories
  - Tables: `configs(name, kind, payload, created_at, updated_at)`, `reports(id, summary, report, created_at)`, and `settings(key, value, updated_at)`
  - JSON payloads stored as text with helper accessors.

- `backend/knowledge_sync.py`: fetches GitHub repo as a zip via `codeload.github.com`, extracts Markdown to `knowledge/external/<repo>`.

- `backend/rag.py` updated:
  - Recursively indexes all Markdown under `knowledge/**`. 
  - Adds optional TF‑IDF retrieval (fallback to keyword scoring if unavailable).

## Advanced Features Covered
- Advanced reporting: persist and list reports; render HTML; export by hitting `/reports/{id}/html`.
- Save configs in a DB: store `tfreview.yaml` as text in SQLite with simple CRUD.
- Embeddings: in-process TF‑IDF using scikit‑learn; no external/vector DB.
- Scan folders: reuse `scan_paths()` which already recurses directories.
- Advanced config preview: apply waivers/thresholds to existing or fresh scans.
- Load policy docs from GitHub: one-call sync for `https://github.com/hashicorp/policy-library-azure-storage-terraform` (default), stored under `knowledge/external/` and consumed by RAG.

## Runbook
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Start API + minimal UI
uvicorn api.main:app --reload --port 8890

# Quick smoke (from another shell)
curl -s http://localhost:8890/health
curl -s -X POST http://localhost:8890/scan -H 'content-type: application/json' \
  -d '{"paths":["sample"],"terraform_validate":false,"save":true}' | jq .id
curl -s http://localhost:8890/reports | jq .

# Sync knowledge from GitHub
curl -s -X POST http://localhost:8890/knowledge/sync | jq .
```

## Migration Strategy
1. Keep Streamlit app for now while standing up the API.
2. Prove parity on scan results and HTML report output.
3. Add config storage and preview on API, then expose HTMX forms.
4. Move remaining useful Streamlit-only helpers into small HTML snippets if needed.
5. Remove Streamlit from default path once API covers daily use-cases.

## Notes
- SQLite is file-based, robust, and bundled with Python; no external DB is required.
- TF‑IDF runs in-process and builds on first use; knowledge sync drops Markdown under `knowledge/external/**` so it is automatically included.
- LLM features remain opt-in and unchanged; API forwards options to `scan_paths()`.
