Authentication Overview
=======================

Terraform Manager now uses a SQLAlchemy-backed authentication system with hashed passwords, scoped JWTs, and refresh-token rotation. This document summarises the flow, environment variables you can tune, and integration tips for clients.


Quick Summary
-------------

- Users authenticate with email + password (`POST /auth/token`).
- The response returns:
  - `access_token` – short-lived bearer JWT for API requests.
  - `refresh_token` – HTTP-only cookie (`tm_refresh_token`) for session renewal.
  - `anti_csrf_token` – echoed in header `X-Refresh-Token-CSRF` during refresh calls.
- Active sessions can be reviewed via `GET /auth/sessions` and revoked per-device with `DELETE /auth/sessions/{id}`.
- Recent authentication activity is available via `GET /auth/events` and rendered in the SvelteKit dashboard.
- Clients retain the refresh cookie and anti-CSRF token; the server sets/rotates both.
- Legacy deployments may still rely on `TFM_API_TOKEN`. When supplied via header (`Authorization: Bearer ...` / `X-API-Token`), the server provisions a service user automatically. Plan to migrate to password auth.


Environment Variables
---------------------

| Variable | Default | Description |
| --- | --- | --- |
| `TFM_API_TOKEN` / `API_TOKEN` | `local-dev` | Legacy single-password for service access. |
| `TFM_JWT_SECRET` | `dev-secret-change-me` | Symmetric signing key for access tokens. |
| `TFM_REFRESH_SECRET` | falls back to access secret | Optional distinct secret for refresh tokens. |
| `TFM_ACCESS_TOKEN_MINUTES` | `30` | Access token lifespan in minutes. |
| `TFM_REFRESH_TOKEN_MINUTES` | `10080` | Refresh token lifespan (minutes). |
| `TFM_COOKIE_SECURE` | `false` | Emit `Secure` cookies when `true`. Enable in production. |
| `TFM_COOKIE_DOMAIN` | unset | Optional cookie domain attribute. |
| `TFM_COOKIE_SAMESITE` | `lax` | SameSite policy for refresh cookies. |
| `TFM_AUTH_REFRESH_COOKIE` | `tm_refresh_token` | Cookie name storing the refresh JWT. |
| `TFM_SERVICE_USER_EMAIL` | `service@local` | Email used for the bootstrap service user (legacy token flow). |


REST Flow
---------

1. **Login (`POST /auth/token`)**
   - Body: `username`, `password`, optional `scope`.
   - Response body includes `access_token`, `refresh_token`, `refresh_expires_in`, `anti_csrf_token`.
   - Refresh token is also set via cookie `tm_refresh_token`; anti-CSRF is in both cookie `tm_refresh_csrf` and header `X-Refresh-Token-CSRF`.

2. **Authenticated Requests**
   - Send `Authorization: Bearer <access_token>`.
   - Refresh cookie is sent automatically by the browser/HTTP client.

3. **Refresh (`POST /auth/refresh`)**
   - Requires `tm_refresh_token` cookie.
   - Must include header `X-Refresh-Token-CSRF: <value>`.
   - Returns new tokens, rotates cookie + anti-CSRF value, and revokes the previous refresh session.
- Re-using an old refresh token triggers family revocation and yields HTTP 401.
- Password login is rate-limited (5 failures per minute by default). Repeated failures return HTTP 429 with `Retry-After`.

4. **Logout (`POST /auth/logout`)**
   - Revokes the active refresh session and clears cookies.

5. **Profile (`GET /auth/me`)**
   - Returns email, scopes, and expiry metadata for the authenticated user.

6. **Session management**
   - `GET /auth/sessions` lists active refresh sessions tied to the authenticated user, including metadata (IP, last used).
   - `DELETE /auth/sessions/{id}` revokes an individual session, immediately logging out that device.

7. **Activity (`GET /auth/events`)**
   - Returns recent authentication events (login, refresh, revocation) scoped to the current user, including IP/user agent metadata for investigation.


Testing & Automation
--------------------

- **FastAPI**: `tests/test_auth_routes.py` demonstrates password login, refresh rotation, and reuse detection using a temporary SQLite DB.
- **SvelteKit**: The frontend stores `tm_api_token` (access token) client-side and relies on the refresh cookie + `tm_refresh_csrf` to silently rotate tokens. Hooks automatically refresh when required.
- **CLI / Scripts**: Run `python -m backend.cli auth login --email you@example.com` to store credentials in `tm_auth.json` (respecting `TFM_API_BASE`). Future authenticated CLI commands can re-use this file without prompting for credentials.


Future Enhancements
-------------------

- CLI login command issuing tokens for automation workflows.
- Rate-limiting / lockout on repeated failures.
- Optional MFA (TOTP/WebAuthn) and SSO integration hooks.
