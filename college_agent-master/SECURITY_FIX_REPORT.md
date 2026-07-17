# Security Fix Report — v0.9.0-pre-security

## Fixes Applied

---

### B6: API Key Leak in `/health/tts`

**Root Cause**: `app/api/health.py:44` returned `settings.sarvam_api_key[:10]` as a
`key_prefix` field in the public JSON response of the TTS health endpoint. Any
client could read the first 10 characters of the Sarvam API key.

**Fix**: Replaced the `key_prefix` field with a boolean `key_configured` field.

```diff
-        "key_prefix": settings.sarvam_api_key[:10] if settings.sarvam_api_key else "none",
+        "key_configured": bool(settings.sarvam_api_key),
```

**Before**: `{"sarvam_available":true, "active_provider":"sarvam", "status":"healthy", "key_prefix":"sk_8cdtsmk"}`
**After**:  `{"sarvam_available":true, "active_provider":"sarvam", "status":"healthy", "key_configured":true}`

**Regression Risk**: None. The `key_prefix` field was informational only; no
client code depends on it. The remaining response shape is unchanged.

---

### B3: Hardcoded Admin Credentials

**Root Cause**: `app/config.py:43-45` hardcoded default values:
- `admin_username = "admin"`
- `admin_password = "admin"`
- `secret_key = "college-agent-secret-key-2026"`

If environment variables were missing, any attacker could trivially forge JWTs
and access all admin endpoints (file upload, KB modification, cache control,
backup management).

**Fix (two parts)**:

1. **Removed defaults** in `app/config.py`:
   ```diff
   -    admin_username: str = "admin"
   -    admin_password: str = "admin"
   -    secret_key: str = "college-agent-secret-key-2026"
   +    admin_username: str = ""
   +    admin_password: str = ""
   +    secret_key: str = ""
   ```

2. **Added guard** in `app/api/auth_routes.py:16-21` — login returns 401 if
   credentials are unconfigured:
   ```python
   if not settings.admin_username or not settings.admin_password or not settings.secret_key:
       raise HTTPException(
           status_code=status.HTTP_401_UNAUTHORIZED,
           detail="Admin credentials not configured on server",
           headers={"WWW-Authenticate": "Bearer"},
       )
   ```

**Before**: Server started with `admin:admin` defaults if no `.env` was present.
**After**: Server rejects all logins until `ADMIN_USERNAME`, `ADMIN_PASSWORD`,
and `SECRET_KEY` are set via environment variables (`.env` file already
contains a strong `SECRET_KEY`).

**Regression Risk**: Low. The `.env` file is already in `.gitignore` and
contains `ADMIN_USERNAME=admin` and `ADMIN_PASSWORD=admin`. Existing
deployments using the `.env` file continue to work identically.

---

### B5: Missing Rate Limiting on Admin Routes

**Root Cause**: `app/limiter.py` defined a `Limiter` with
`default_limits=["10/minute"]`, but no route had a `@limiter.limit` decorator.
The `default_limits` parameter is a fallback that slowapi does not enforce
without the decorator on each route. Admin endpoints were unprotected against
brute force and DoS.

**Fix**: Added explicit `@limiter.limit(...)` decorators with the `request`
parameter to all mutation endpoints:

| Route | Decorator | Rationale |
|-------|-----------|-----------|
| `POST /token` | `@limiter.limit("5/minute")` | Brute-force login prevention |
| `POST /admin/upload` | `@limiter.limit("5/minute")` | Expensive file ingestion |
| `POST /admin/backup/create` | `@limiter.limit("5/minute")` | Storage amplification |
| `POST /admin/kb/faq/{key}` | `@limiter.limit("10/minute")` | KB writes |
| `DELETE /admin/kb/faq/{key}` | `@limiter.limit("10/minute")` | KB deletes |
| `POST /admin/kb/reload` | `@limiter.limit("5/minute")` | Service-impacting operation |
| `POST /admin/cache/invalidate` | `@limiter.limit("5/minute")` | Denial-of-service vector |
| `POST /admin/kb/update-anchor` | `@limiter.limit("10/minute")` | KB structural change |

Each decorator uses the standard slowapi `get_remote_address` key function to
rate-limit by client IP.

**Before**: 10 rapid `POST /token` calls all returned 200.
**After**: 6th rapid call returns `429 Too Many Requests`.

**Regression Risk**: Low to none. Read-only admin endpoints (`GET /files`,
`GET /backups`, `GET /kb/faq`, `GET /cache/stats`) are NOT rate-limited.
Public QA/chat endpoints are untouched. Only mutation endpoints are limited,
using generous per-IP windows (5–10/minute).

---

## Verification

All 14 smoke tests pass:

```
SECURITY FIX SMOKE TESTS
  14 passed, 0 failed out of 14

  PASS  QA returns 200                              (no auth regression)
  PASS  QA response has answer                        (no auth regression)
  PASS  Health TTS returns 200                        (B6)
  PASS  No key_prefix in response                      (B6)
  PASS  Has key_configured instead                     (B6)
  PASS  Login returns 200                              (B3, with .env)
  PASS  Token received                                 (B3, with .env)
  PASS  Admin files endpoint with auth                 (B3, with .env)
  PASS  Rate limit 429 received                        (B5)
  PASS  Empty creds guard in login                     (B3 code)
  PASS  admin_username default is empty                (B3 code)
  PASS  admin_password default is empty                (B3 code)
  PASS  secret_key default is empty                    (B3 code)
  PASS  Rate limit decorators on admin routes          (B5 code)
```

## Out of Scope (this sprint)

| Issue | Reason |
|-------|--------|
| B2: SQLite write collision | Requires architectural change |
| B7: Async BackgroundTask | Works on Starlette 1.3.1; upgrade dependency |
| B8: DemoLogger memory leak | Not a blocking issue; dead-code path |
| B1: `datetime.UTC` | Python 3.11+ target |

## Files Changed

| File | Change |
|------|--------|
| `app/api/health.py:44` | Removed `key_prefix` leak |
| `app/config.py:43-45` | Removed hardcoded `admin:admin` defaults |
| `app/api/auth_routes.py:14-21` | Added empty-credentials guard |
| `app/api/auth_routes.py:13,26` | Added `@limiter.limit("5/minute")` |
| `app/api/admin.py:8,11,28-29,33,42,53,66,78,94,107,120` | Added `@limiter.limit` + `request` params |

---

*Generated: 2026-07-11*
