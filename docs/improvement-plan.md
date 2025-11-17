# TerraformManager Improvement Plan

Detailed follow-up plan derived from the Python review. Tasks are grouped by concern and prioritised (High ▸ Medium ▸ Low). Each task should result in code changes plus accompanying tests/docs where indicated.

## 0. Shared assumptions
- Users interact with Terraform sources through a dedicated workspace directory inside this repository (e.g., `data/projects/<slug>`). All uploads or managed files are copied under that folder, and no API should ever read outside of these managed roots. The plan below assumes upcoming hardening work can rely on this invariant.

## 1. Lock down API `/scan` inputs (Priority: High)
- [ ] Restrict `ScanRequest.paths` to project roots known to the backend. Either:
  - require a `project_id` and resolve paths via `backend.storage` metadata, or
  - validate that each submitted path resides under an allow-listed workspace directory configured via environment/DB.
- [ ] Reject absolute paths, relative components (`..`), symlinks escaping the workspace, and overly large path counts with clear HTTP errors.
- [ ] Extend `scan_paths` context logging to include the resolved project/run identifier so security logs capture the caller intent.
- [ ] Add integration tests in `tests/backend/api/test_scan.py` (or new module) that assert:
  - valid project-scoped scans succeed,
  - out-of-root paths return `400`/`403`,
  - attempts to scan host root or `/etc/passwd` fail without touching the filesystem.
- [ ] Document the hardened behaviour in `README.md` (API usage) and `docs/api.md` if present, calling out how to register scanable roots.

## 2. Correct CORS & credential policy (Priority: High)
- [ ] Replace `allow_origins=["*"]` when `allow_credentials=True` with the actual dashboard hostnames pulled from configuration (env var or DB setting). Consider using FastAPI's `TrustedHostMiddleware` for extra defence.
- [ ] Add regression tests in `tests/api/test_cors.py` that instantiate the app with multiple origins and assert responses contain the expected `Access-Control-Allow-Origin`.
- [ ] Update deployment docs (`README.md`/`docs/deployment.md`) to explain how operators configure allowed origins for each environment.

## 3. Stop leaking configs into `/tmp` (Priority: Medium)
- [ ] Refactor `api.main.preview_config` to use `TemporaryDirectory()` or in-memory YAML loading instead of writing to `/tmp/tfreview.preview.yaml`.
- [ ] Ensure per-request temp files are deleted; add unit tests covering concurrent preview requests to confirm no collisions.
- [ ] Mention the change in release notes or `CHANGELOG.md` (if available) so operators know previews no longer touch shared `/tmp`.

## 4. Clean up `run_terraform_validate` temp usage & visibility (Priority: Medium)
- [ ] Use `TemporaryDirectory()` as a context manager so validation directories are deleted after each run.
- [ ] Preserve relative directory structure when copying `.tf` files to avoid filename collisions (e.g., keep `module/foo/main.tf` layout).
- [ ] Capture `stdout/stderr` from both `terraform init` and `terraform validate`, logging failures via `LOGGER.error` and surfacing them as scanner findings instead of silently dropping them.
- [ ] Add tests under `tests/backend/test_validators.py` that simulate:
  - success path (no findings, temp dir removed),
  - init failure (error propagated to finding + log),
  - validation failure (finding includes tool output).

## 5. Surface rule/IO failures in the scanner (Priority: Medium)
- [ ] In `backend.scanner._scan_file`, wrap each `check` invocation with `LOGGER.exception` so misbehaving rules are reported but do not abort the whole scan; consider tagging findings with a synthetic rule to make issues visible to end users.
- [ ] Allow `_read_file_text` to re-raise unexpected IO errors (or at minimum log them) so missing permissions / encoding bugs are diagnosable.
- [ ] Add tests that mock a rule raising an exception and assert a log entry + optional synthetic finding is produced.

## 6. Improve Terraform fmt error reporting (Priority: Low)
- [ ] Update `_run_terraform_fmt` to run `subprocess.run(..., capture_output=True, text=True)` (or stream via `subprocess.PIPE` + logger) so failures emit actionable diagnostics before exiting.
- [ ] Add CLI tests (could live in `tests/backend/test_cli_fmt.py`) that simulate `terraform fmt` returning non-zero and ensure stderr is surfaced.
- [ ] Document the troubleshooting behaviour in `README.md` (CLI section).

---

**Tracking:** Log progress in `PLAN.md` or task tracker, referencing this document for context. Each completed section should include a link to its PR and test evidence (e.g., `pytest -q`, FastAPI integration tests, manual verification steps).
