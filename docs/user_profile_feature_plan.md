# User Profile Section — Implementation Plan

## Context
- Terraform Manager currently exposes `/auth/me` for token validation and surfaces limited profile metadata (`email`, `scopes`, `expires_in`) inside `frontend/src/hooks.server.ts` and `(app)/+layout.svelte`.
- There is no UI where users can view or update personal details, notification preferences, or change their password; security controls live only under `/settings/sessions`.
- The feature goal is to ship a dedicated “User profile” section (under `/settings/profile`) that allows viewing account details, editing basic attributes, managing preferences, and self-service password rotation, all backed by structured API endpoints.

## Objectives
1. Extend the backend data model and API so user records include display metadata (name, job title, timezone, avatar URL) plus JSON preferences, along with dedicated profile/password update routes.
2. Build a first-class frontend experience for viewing/editing the profile, linked from existing settings navigation and reusing shared auth hooks.
3. Ensure auditing, migrations, documentation, and automated tests cover the new flows.

## Key Deliverables
- Database schema updates with migration helper(s) for new `users` columns.
- Repository/service helpers to update profile data and passwords with audit logging + refresh token hygiene.
- FastAPI routes: enriched `GET /auth/me`, `PUT /auth/me`, and `POST /auth/me/password`.
- SvelteKit route `/(app)/settings/profile` with forms for profile + password management, plus supporting API client methods.
- Docs covering the new endpoints, UI surface, and deployment/migration steps.
- Regression tests (backend + frontend) and verification instructions.

---

## Detailed Tasks

### 1. Backend Foundation
- [ ] **Model changes (`backend/db/models.py`)**
  - Add nullable columns to `User`: `full_name` (String 160), `job_title` (String 160), `timezone` (String 64), `avatar_url` (String 512), `profile_preferences` (JSON default empty dict).
  - Update `User.to_dict()` to include new fields plus ISO-formatted timestamps for `created_at`/`updated_at`.
- [ ] **Repository helpers (`backend/db/repositories/auth.py`)**
  - Implement `update_user_profile(session, user, *, full_name, job_title, timezone, avatar_url, preferences)` that normalises timezone strings (validate via `zoneinfo`), merges preference dicts safely, persists changes, and returns the refreshed user.
  - Implement `change_user_password(session, user, *, new_hash)` used when rotating credentials.
  - Add `get_last_login_at(session, user_id)` that fetches the latest `AuthAudit` row with `event='login_success'`.
  - Extend repository tests in `tests/test_auth_repository.py` to cover the new helpers and ensure preferences round-trip through JSON.

### 2. Token & Audit Plumbing
- [ ] Extend `backend/auth/tokens.py` so profile/password changes record audit events:
  - Emit `auth_repo.record_auth_event(... event="profile_updated")` on `update_user_profile`.
  - Emit `event="password_changed"` when password rotation succeeds, including `session_id` and metadata.
- [ ] Ensure password updates revoke all refresh sessions in the same family except the current session (reuse `token_service.revoke_session` + `list_sessions_by_family`), and optionally issue a new access token when invoked from the API route.

### 3. API Contract
- [ ] **Schema updates (`api/routes/auth.py`)**
  - Expand `UserProfile` model (ids, timestamps, optional fields, preferences dict, `last_login_at`).
  - Introduce `ProfileUpdatePayload` (validators on string length, timezone pattern, avatar URL) and `PasswordChangePayload` (current/new/confirm).
- [ ] **Routes**
  - Update `GET /auth/me` to include richer metadata and call the new repository helper for `last_login_at`.
  - Add `PUT /auth/me` (scopes: `console:read`) that validates the payload, updates the DB via helper functions, and returns the full profile.
  - Add `POST /auth/me/password` (scopes: `console:write`) that:
    1. Verifies `current_password` via `TokenService.verify_password`.
    2. Hashes & saves the new password via `TokenService.hash_password`.
    3. Revokes other refresh sessions.
    4. Returns a simple status payload (`{"status": "password_changed"}`).
- [ ] **Error handling**
  - Use consistent HTTP 400 for validation issues, 401 for bad credentials, 422 for malformed inputs, and include detail strings the frontend can surface.
- [ ] **Tests (`tests/test_auth_routes.py`)**
  - Cover success/failure cases for the new routes, including invalid timezone, wrong current password, and unauthorised calls.

### 4. Migration & CLI Support
- [ ] Author a SQLite-safe migration helper (e.g., `scripts/migrations/001_add_user_profile_fields.py`) that adds the new columns if absent; document running it before deploying.
- [ ] Add a CLI command (`python -m backend.cli db migrate-profile`) invoking the helper, along with smoke tests or usage instructions in `README.md`.
- [ ] Ensure `backend/db/session.py:init_models` gracefully handles environments where the new columns already exist (idempotency).

### 5. Frontend API & Types
- [ ] **Type definitions (`frontend/src/lib/api/client.ts`)**
  - Define interfaces for `UserProfile`, `UserPreferences`, `ProfileUpdatePayload`, `PasswordChangePayload`.
  - Implement `getUserProfile`, `updateUserProfile`, and `changePassword` wrappers calling `/auth/me`, `/auth/me` (PUT), and `/auth/me/password`.
- [ ] **Hooks & globals**
  - Update `frontend/src/hooks.server.ts` to read the richer `/auth/me` response and persist `full_name`, `job_title`, `timezone`, etc. on `event.locals.user`.
  - Adjust `frontend/src/app.d.ts` so `App.Locals` / `App.PageData` reference the expanded profile shape.

### 6. Svelte Routes & UI
- [ ] **Navigation**
  - Insert “User Profile” into `frontend/src/lib/navigation/lazy/settings.ts` and update `(app)/+layout.server.ts` breadcrumbs/section metadata to support `/settings/profile`.
- [ ] **Page load (`/(app)/settings/profile/+page.ts`)**
  - Fetch `{ token, user } = await parent()`; if missing token, return empty state; else call `getUserProfile` to ensure fresh data and pass along load errors.
- [ ] **Page UI (`+page.svelte`)**
  - Section 1: Overview card showing avatar, email, scopes, `created_at`, `last_login_at`, and a CTA linking to `/settings/sessions`.
  - Section 2: Editable form (name, title, timezone dropdown, avatar URL, notification toggles) with save button that calls `updateUserProfile`, uses `notifySuccess/notifyError`, and disables while saving.
  - Section 3: Password change form capturing current + new + confirm fields, performing client-side validation (matching passwords, min length), calling `changePassword`, and clearing inputs on success.
  - Reuse `$state` stores, handle API errors (show inline + toast), and follow existing Tailwind/Notus styling conventions from other settings pages.
- [ ] **Shared bits**
  - Optionally create `frontend/src/lib/components/profile/ProfileForm.svelte` and `PasswordCard.svelte` for clarity.
  - Update `(app)/+layout.svelte` header block to display `profile.full_name` (fallback email), `job_title`, timezone chips, and use `avatar_url` if provided.

### 7. Documentation & Enablement
- [ ] Update `README.md` or `docs/auth_jwt_improvement_plan.md` with:
  - New migration command.
  - API endpoint descriptions (`GET/PUT /auth/me`, `POST /auth/me/password`).
  - UI walkthrough screenshots or text for `/settings/profile`.
- [ ] Add a release note / PLAN.md entry mentioning the new profile section and schema requirements.
- [ ] Document reindex or CLI steps if needed (none expected beyond migration).

### 8. QA & Verification
- [ ] Backend: run `pytest -q` (ensure new tests pass) and `python -m backend.cli scan sample --out tmp/report.json` for sanity.
- [ ] Frontend: run `cd frontend && pnpm lint && pnpm check && pnpm test`.
- [ ] Manual checks:
  - Login as a user, visit `/settings/profile`, edit details, confirm persistence after refresh.
  - Change password, ensure other sessions are revoked and login with old password fails.
  - Verify audit logs (`auth_audit_events` table) record both profile and password events.

---

## Risks & Mitigations
- **SQLite schema drift**: Adding columns on existing installs requires explicit migration; mitigate with the helper script + documentation.
- **Timezone validation**: Use `zoneinfo.ZoneInfo` to reject invalid timezones early, avoiding inconsistent data.
- **Session revocation UX**: Password changes log the user out of other devices; surface a toast advising the user to re-login elsewhere.
- **Local storage tokens**: Updating `/auth/me` payload size could impact cookies; ensure no sensitive data beyond display fields is stored client-side.

## Definition of Done
1. New schema + repository logic deployed with documented migration steps.
2. FastAPI endpoints expose/accept the new profile fields and pass automated tests.
3. SvelteKit profile page functions end-to-end (view, edit, change password) and ties into navigation/header.
4. Documentation updated; validation commands executed; no lint/test regressions.
