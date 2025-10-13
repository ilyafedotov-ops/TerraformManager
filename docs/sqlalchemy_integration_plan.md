SQLAlchemy + SQLite Integration Plan
====================================

Task 1 – Introduce SQLAlchemy dependency and configuration scaffold
-------------------------------------------------------------------
- Add `SQLAlchemy>=2.0` to `requirements.txt` and ensure pinned versions align with Python 3.11 support.
- Create a new module (e.g. `backend/db/session.py`) that exposes a lazily initialised `Engine`, `SessionFactory`, and a `get_session()` context helper.
- Configure the engine for SQLite file storage (`sqlite:///data/app.db`) with `future=True`, `echo` controlled by env var, and `connect_args={"check_same_thread": False}` for FastAPI/CLI concurrency.
- Document environment variables or configuration knobs (if any) in `README.md` or existing ops docs.

Task 2 – Model the existing schema with SQLAlchemy ORM
------------------------------------------------------
- Define a shared declarative `Base` (likely `backend/db/models.py`) and map current tables:
  - `Config` (`configs` table) with columns `name`, `kind`, `payload`, timestamps.
  - `Report` (`reports` table) with `id`, `summary`, `report`, `created_at`.
  - `Setting` (`settings` table) with `key`, `value`, `updated_at`.
- Ensure column defaults mirror the present schema (e.g. `CURRENT_TIMESTAMP`) and constrain primary keys exactly as before.
- Implement simple `as_dict()` helpers or use SQLAlchemy inspection to keep storage return shapes unchanged.

Task 3 – Replace sqlite3 helpers with SQLAlchemy-based repositories
-------------------------------------------------------------------
- Refactor `backend/storage.py` to:
  - Import the new Session/Engine utilities and models.
  - Port `init_db`, `upsert_config`, `list_configs`, etc. to use ORM/SQLAlchemy Core statements.
  - Maintain current JSON serialization behaviour for `summary`/`report` fields.
- Provide type-hinted functions returning the same structures expected by API/UI code, adding minimal helper functions if needed.
- Remove direct `sqlite3` usage while keeping backwards compatibility for the on-disk database file.

Task 4 – Wire SQLAlchemy session lifecycle into FastAPI and CLI entrypoints
---------------------------------------------------------------------------
- Ensure `api/main.py` initialises the engine/tables on startup (replacing `init_db` if necessary) and consider per-request session management if future dependency injection is desired.
- Update CLI utilities or other scripts that call `init_db`/storage functions so they leverage the new session helper (e.g. context manager wrappers).
- Audit for multithreading contexts (FastAPI background tasks) and confirm session scope is safe; adjust with scoped session if required.

Task 5 – Testing, migration validation, and documentation updates
-----------------------------------------------------------------
- Add or adapt unit tests under `tests/backend/` to cover CRUD operations through the refactored storage layer.
- Run existing API/CLI smoke commands to confirm regression-free behaviour, noting any necessary fixtures for SQLAlchemy sessions.
- Update relevant docs (`docs/refactor_proposal.md`, `README.md`, or new section) to describe the SQLAlchemy adoption and mention any follow-up actions (e.g., Alembic migrations roadmap).
- Capture manual verification steps (e.g. `python -m backend.cli scan sample`) to ensure maintainers know how to validate the integration.

