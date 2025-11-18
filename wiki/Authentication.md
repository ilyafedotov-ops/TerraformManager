# Authentication Guide

TerraformManager uses a modern JWT-based authentication system with refresh token rotation and session management.

## Overview

The authentication system provides:
- **Password-based login** with bcrypt hashing
- **JWT access tokens** for API requests (short-lived)
- **Refresh tokens** for session renewal (long-lived, HttpOnly cookies)
- **Session management** with per-device tracking
- **Audit logging** for authentication events
- **Rate limiting** on login attempts
- **CSRF protection** on token refresh

## Authentication Flow

```
┌─────────┐                  ┌─────────┐                  ┌─────────┐
│ Client  │                  │   API   │                  │Database │
└────┬────┘                  └────┬────┘                  └────┬────┘
     │                            │                            │
     │ POST /auth/token           │                            │
     │ (email + password)         │                            │
     ├───────────────────────────>│                            │
     │                            │  Verify credentials        │
     │                            ├───────────────────────────>│
     │                            │<───────────────────────────┤
     │                            │  Create session            │
     │                            ├───────────────────────────>│
     │  access_token,             │                            │
     │  Set-Cookie: refresh_token │                            │
     │<───────────────────────────┤                            │
     │                            │                            │
     │ GET /protected             │                            │
     │ Authorization: Bearer ...  │                            │
     ├───────────────────────────>│                            │
     │                            │  Verify JWT                │
     │  Protected resource        │                            │
     │<───────────────────────────┤                            │
     │                            │                            │
     │ POST /auth/refresh         │                            │
     │ Cookie: refresh_token      │                            │
     │ X-Refresh-Token-CSRF: ...  │                            │
     ├───────────────────────────>│                            │
     │                            │  Verify & rotate           │
     │                            ├───────────────────────────>│
     │  new_access_token,         │                            │
     │  Set-Cookie: new_refresh   │                            │
     │<───────────────────────────┤                            │
```

## API Endpoints

### POST /auth/token (Login)

Authenticate with email and password.

**Request**:
```http
POST /auth/token
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=secret
```

**Response**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 1800,
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_expires_in": 604800,
  "refresh_token_csrf": "abc123..."
}
```

**Sets Cookies**:
- `tm_refresh_token` (HttpOnly, Secure in production)
- `tm_refresh_csrf` (accessible to JavaScript)

### POST /auth/refresh

Refresh access token using refresh token.

**Request**:
```http
POST /auth/refresh
Cookie: tm_refresh_token=<refresh_token>
X-Refresh-Token-CSRF: <csrf_token>
```

**Response**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 1800,
  "refresh_token_csrf": "def456..."
}
```

**Behavior**:
- Rotates refresh token (new cookie set)
- Revokes previous refresh token
- Detects token reuse and revokes family

### POST /auth/logout

Logout and revoke current session.

**Request**:
```http
POST /auth/logout
Authorization: Bearer <access_token>
Cookie: tm_refresh_token=<refresh_token>
```

**Response**:
```json
{
  "message": "Logged out successfully"
}
```

**Behavior**:
- Revokes refresh session
- Clears cookies
- Invalidates access token (client-side)

### GET /auth/me

Get current user information.

**Request**:
```http
GET /auth/me
Authorization: Bearer <access_token>
```

**Response**:
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "scopes": ["read", "write"],
  "created_at": "2024-01-15T10:00:00Z",
  "token_expires_at": "2024-01-15T10:30:00Z"
}
```

### GET /auth/sessions

List active sessions for current user.

**Response**:
```json
{
  "sessions": [
    {
      "id": "uuid",
      "device_info": "Mozilla/5.0...",
      "ip_address": "192.168.1.1",
      "created_at": "2024-01-15T10:00:00Z",
      "last_used": "2024-01-15T12:00:00Z",
      "expires_at": "2024-01-22T10:00:00Z",
      "is_current": true
    }
  ]
}
```

### DELETE /auth/sessions/{id}

Revoke a specific session.

**Response**:
```json
{
  "message": "Session revoked successfully"
}
```

### GET /auth/events

Get authentication audit events.

**Response**:
```json
{
  "events": [
    {
      "event_type": "login",
      "timestamp": "2024-01-15T10:00:00Z",
      "ip_address": "192.168.1.1",
      "user_agent": "Mozilla/5.0...",
      "success": true
    }
  ]
}
```

### POST /auth/register

Register new user account.

**Request**:
```json
{
  "email": "newuser@example.com",
  "password": "SecurePass123!",
  "full_name": "John Doe"
}
```

**Response**:
```json
{
  "id": "uuid",
  "email": "newuser@example.com",
  "created_at": "2024-01-15T10:00:00Z"
}
```

---

## Client Integration

### Browser (JavaScript/TypeScript)

```typescript
// Login
async function login(email: string, password: string) {
  const formData = new URLSearchParams();
  formData.append('username', email);
  formData.append('password', password);

  const response = await fetch('http://localhost:8890/auth/token', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: formData,
    credentials: 'include', // Important for cookies
  });

  const data = await response.json();

  // Store access token
  localStorage.setItem('access_token', data.access_token);
  localStorage.setItem('csrf_token', data.refresh_token_csrf);

  return data;
}

// Make authenticated request
async function fetchProtected(url: string) {
  const token = localStorage.getItem('access_token');

  const response = await fetch(url, {
    headers: {
      'Authorization': `Bearer ${token}`,
    },
    credentials: 'include',
  });

  // Handle 401 - refresh token
  if (response.status === 401) {
    await refreshToken();
    // Retry request
    return fetchProtected(url);
  }

  return response.json();
}

// Refresh access token
async function refreshToken() {
  const csrf = localStorage.getItem('csrf_token');

  const response = await fetch('http://localhost:8890/auth/refresh', {
    method: 'POST',
    headers: {
      'X-Refresh-Token-CSRF': csrf,
    },
    credentials: 'include',
  });

  const data = await response.json();
  localStorage.setItem('access_token', data.access_token);
  localStorage.setItem('csrf_token', data.refresh_token_csrf);

  return data;
}
```

### Python CLI

```python
import requests
import json
from pathlib import Path

AUTH_FILE = Path("tm_auth.json")

def login(email: str, password: str, base_url: str):
    """Login and save tokens"""
    response = requests.post(
        f"{base_url}/auth/token",
        data={"username": email, "password": password},
    )
    response.raise_for_status()

    data = response.json()

    # Save tokens
    AUTH_FILE.write_text(json.dumps({
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "csrf_token": data["refresh_token_csrf"],
        "base_url": base_url,
    }))

    return data

def get_headers():
    """Get authorization headers"""
    if not AUTH_FILE.exists():
        raise Exception("Not logged in. Run: auth login")

    auth = json.loads(AUTH_FILE.read_text())

    return {
        "Authorization": f"Bearer {auth['access_token']}"
    }

def refresh_if_needed():
    """Refresh token if expired"""
    # Implement token expiry check and refresh logic
    pass

# Usage
if __name__ == "__main__":
    login("user@example.com", "password", "http://localhost:8890")

    # Make authenticated request
    response = requests.get(
        "http://localhost:8890/projects",
        headers=get_headers()
    )
```

### cURL

```bash
# Login
TOKEN_RESPONSE=$(curl -s -X POST http://localhost:8890/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=secret" \
  -c cookies.txt)

ACCESS_TOKEN=$(echo $TOKEN_RESPONSE | jq -r '.access_token')

# Make authenticated request
curl http://localhost:8890/projects \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -b cookies.txt

# Refresh token
CSRF=$(echo $TOKEN_RESPONSE | jq -r '.refresh_token_csrf')

curl -X POST http://localhost:8890/auth/refresh \
  -H "X-Refresh-Token-CSRF: $CSRF" \
  -b cookies.txt \
  -c cookies.txt
```

---

## Security Features

### Password Hashing
- bcrypt with salt rounds (Passlib)
- Passwords never stored in plaintext
- Minimum password strength enforced

### Token Security
- **Access tokens**: Short-lived (30 minutes default)
- **Refresh tokens**: Long-lived (7 days default), HttpOnly cookies
- **Separate secrets**: Different keys for access and refresh
- **Token rotation**: New refresh token on each refresh

### CSRF Protection
- Anti-CSRF token required for refresh
- Validated on every refresh request
- Rotated with refresh token

### Rate Limiting
- Login attempts: 5 per minute per IP
- Refresh: 10 per minute
- Register: 3 per minute
- Returns `429 Too Many Requests` with `Retry-After` header

### Session Management
- Per-device session tracking
- IP address and user agent logging
- Manual revocation support
- Automatic cleanup of expired sessions

### Audit Logging
- All authentication events logged
- Failed login attempts tracked
- Session creation/revocation recorded
- IP and timestamp captured

---

## Configuration

See [Configuration Reference](Configuration) for all auth-related environment variables.

### Token Lifetimes

```bash
# Short-lived access tokens (15 minutes)
export TFM_ACCESS_TOKEN_MINUTES=15

# Long-lived refresh tokens (30 days)
export TFM_REFRESH_TOKEN_MINUTES=43200
```

### Cookie Security

```bash
# Production settings
export TFM_COOKIE_SECURE=true        # HTTPS only
export TFM_COOKIE_SAMESITE=strict    # Strict CSRF protection
export TFM_COOKIE_DOMAIN=example.com # Cookie domain
```

### JWT Secrets

```bash
# Generate secure secrets
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Set different secrets for access and refresh
export TFM_JWT_SECRET=<access-token-secret>
export TFM_REFRESH_SECRET=<refresh-token-secret>
```

---

## Troubleshooting

### Cookie Not Set

**Problem**: Refresh token cookie not appearing in browser

**Solutions**:
1. Set `TFM_COOKIE_SECURE=false` for local development (HTTP)
2. Use HTTPS in production with `TFM_COOKIE_SECURE=true`
3. Check browser console for cookie errors
4. Verify `credentials: 'include'` in fetch requests

### Token Refresh Fails

**Problem**: 401 errors on `/auth/refresh`

**Solutions**:
1. Verify CSRF token is sent in `X-Refresh-Token-CSRF` header
2. Check refresh cookie is sent (browser DevTools → Network)
3. Ensure token hasn't expired
4. Verify CORS configuration allows credentials

### Rate Limited

**Problem**: 429 errors on login

**Solutions**:
1. Wait for rate limit window to expire
2. Check `Retry-After` header for wait time
3. Implement exponential backoff in client
4. Review failed login attempts

### Session Revoked

**Problem**: "Session revoked" error

**Possible Causes**:
1. Token reuse detected (security feature)
2. Session manually revoked via `/auth/sessions/{id}`
3. Session expired
4. Server restart with different secrets

**Solution**: Login again to create new session

---

## Best Practices

1. **Store tokens securely**:
   - Access token: In-memory or secure storage
   - Refresh token: HttpOnly cookie (handled by browser)
   - Never in localStorage for sensitive apps

2. **Implement token refresh**:
   - Refresh before expiry (5 minutes before)
   - Handle 401 responses automatically
   - Retry failed requests after refresh

3. **Handle logout properly**:
   - Call `/auth/logout` endpoint
   - Clear client-side token storage
   - Redirect to login page

4. **Use HTTPS in production**:
   - Set `TFM_COOKIE_SECURE=true`
   - Configure SSL/TLS certificates
   - Use `SameSite=strict` for maximum security

5. **Monitor sessions**:
   - Show active sessions in user dashboard
   - Allow users to revoke devices
   - Notify on new device login (future)

6. **Rotate secrets regularly**:
   - Change JWT secrets periodically
   - Invalidate all sessions on rotation
   - Use secret management tools (Vault, etc.)

---

## Legacy API Token

For backward compatibility, TerraformManager supports a legacy API token:

```bash
export TFM_API_TOKEN=your-secret-token
```

**Usage**:
```http
Authorization: Bearer your-secret-token
```
or
```http
X-API-Token: your-secret-token
```

**Note**: Migrate to JWT authentication. Legacy tokens will be deprecated.

---

## Next Steps

- [Configuration Reference](Configuration) - Auth environment variables
- [API Reference](API-Reference) - Complete auth endpoint docs
- [Development Guide](Development) - Extend authentication
- [Troubleshooting](Troubleshooting) - Common auth issues
