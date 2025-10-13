Authentication & JWT Hardening Plan
===================================

Context
-------
- Current auth flow relies on an environment password (`TFM_API_TOKEN`) with no user store; access/refresh JWTs are issued using shared secrets and refresh cookies.
- Tokens embed `api_token` but lack JTI rotation, device tracking, or revocation. Refresh cookies are long-lived and not bound to clients.
- Best practices for small FastAPI services (per FastAPI Best Practices + fastapi-jwt references) emphasise: hashed credentials, scoped tokens with short TTL, refresh rotation, structured dependency injection, and auditability.

Task 1 – Requirements & Secrets Baseline
----------------------------------------
1. Catalogue existing auth environment variables and defaults (`TFM_API_TOKEN`, `TFM_JWT_SECRET`, etc.); document required overrides in README/docs.
2. Introduce a typed `AuthSettings` via `pydantic_settings` covering secrets, expiry windows, cookie flags, and optional issuer/audience claims.
3. Define target JWT expirations (e.g., 15 min access, 7 day refresh) and enforce secure defaults (secure cookies in prod, `SameSite=lax`, optional `DOMAIN`).

Task 2 – Data Model & Persistence
---------------------------------
1. Add SQLAlchemy models in `backend/db/models.py`:
   - `User`: id, email, hashed password, active flag, role/scopes, created/updated timestamps.
   - `RefreshSession`: id/jti, user_id FK, token_hash, expires_at, user_agent/ip metadata, revoked_at.
   - Optional `AuthAudit` table for structured event logging (superseding flat file).
2. Generate corresponding CRUD helpers in a new module (e.g., `backend/db/repositories/auth.py`) for user lookup, session creation, revocation, and audit writes.
3. Provide lightweight seed/bootstrap path for initial admin user (CLI command or documented manual SQL script).

Task 3 – Password & Token Utilities
-----------------------------------
1. Introduce password hashing/verification with Passlib (`bcrypt`) and add unit tests.
2. Refactor `api/security.py` into a service module that:
   - Issues access/refresh tokens with unique `jti`, `iss`, `aud`, and optional `nbf`.
   - Supports rotation: every `/auth/refresh` call mints a new refresh JTI and invalidates the previous record.
   - Validates tokens against stored session records (`RefreshSession`), rejecting revoked/expired entries.
3. Centralise error handling via custom exceptions (e.g., `InvalidCredentials`, `TokenRevoked`, `TokenReuse`) and map to HTTP responses.

Task 4 – API Route Enhancements
-------------------------------
1. `POST /auth/token`:
   - Authenticate against the user table (email/password), enforce active flag, and limit scopes to those assigned.
   - Record refresh session metadata (user agent, IP if available) and set HttpOnly cookie (optionally dual cookie for CSRF token).
   - Return access token + session summary (id, expires_in).
2. `POST /auth/refresh`:
   - Require refresh token cookie and optional anti-CSRF header; verify against DB and rotate tokens.
   - Implement refresh reuse detection (revoke entire token family and force re-login).
3. `POST /auth/logout`:
   - Delete refresh cookie and mark session revoked (applies to both client-supplied tokens and active DB records).
4. `GET /auth/me`:
   - Return profile info (email, scopes, session metadata) sourced from DB, ensuring dependency caches the loaded user.
5. Provide optional endpoints:
   - ✅ `/auth/sessions` to list active refresh sessions per user.
   - ✅ `/auth/sessions/{id}` to revoke a specific session (helps with “logout other devices”).

Task 5 – Authorization Dependency & API Token Backwards Compatibility
----------------------------------------------------------------------
1. Replace the header-only `require_api_token` with a unified dependency that:
   - Accepts bearer JWTs, validates via new service, and injects `CurrentUser` model.
   - Falls back to legacy API token header when enabled (for automation) but issues warnings/deprecation notice.
2. Update all FastAPI routes + UI views to consume `CurrentUser`, enforcing scope checks via dependency parameters (`Security(get_current_user, scopes=[...])`).
3. Ensure background task audit logging uses structured DB records (or new logging helper).

Task 6 – Frontend & CLI Adjustments
-----------------------------------
1. Update SvelteKit login flow to post credentials, store access token (in memory/local storage), and rely on refresh cookie for silent refresh.
2. Adjust API client to append bearer tokens from the refreshed session; handle 401 by triggering refresh or redirect to login.
3. Update CLI authentication helpers (if any) to support username/password or personal access tokens.

Task 7 – Observability, Rate Limiting & Docs
--------------------------------------------
1. Implement login throttling/backoff (e.g., simple in-memory counter or Redis-backed limiter).
2. Instrument authentication events (success/failure) via structured logging and optional metrics hook.
3. Refresh documentation:
   - README quick start (admin bootstrap, login flow).
   - New `docs/authentication.md` covering token lifecycle, session management, environment knobs.
4. Add automated tests:
   - Unit tests for password hashing & token service (including rotation/reuse scenarios).
   - API tests for login/refresh/logout/me flows, including failure paths (bad password, revoked token, expired refresh).

Task 8 – Migration & Rollout
----------------------------
1. Provide a migration script that:
   - Creates required tables.
   - Seeds the initial admin user (prompt or env-provided password) to avoid lockout.
2. Define rollback strategy (disable new auth by setting feature flag to revert to legacy env token temporarily).
3. Communicate upgrade steps in `docs/CHANGELOG.md` (or README) and flag breaking changes (legacy API token usage, cookie requirements).

Appendix – Optional Future Enhancements
---------------------------------------
- Integrate TOTP/OTP or SSO for stronger auth.
- Support fine-grained RBAC with policy definitions stored in DB.
- Implement WebAuthn for passwordless admin access.
