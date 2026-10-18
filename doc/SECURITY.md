# Sijil - Security

What protects Sijil today, where it lives in the code, and what the rest of the stack (Caddy, uploads, WebSockets) still has to provide. Owner: Naser (NA-06). Keep this file in step with the code.

## Accounts and sessions

| Measure | Where |
| --- | --- |
| Passwords hashed with **Argon2id** (salted, RFC 9106 parameters), 10-128 characters | `app/auth/passwords.py`, `app/schemas/auth.py` |
| Login answers the same for an unknown email, a wrong password and a disabled account, and spends the same Argon2 time on each | `app/api/v1/auth.py` |
| Server-side sessions: a random 256-bit token in an **HttpOnly, Secure, SameSite=Lax** cookie; only its SHA-256 hash is stored | `app/auth/sessions.py`, `app/auth/dependencies.py` |
| Sessions end on logout, expiry (7 days), disabling the account, deleting it, or an admin password reset | same |
| A **new session** after a password change; every other session is revoked | `POST /api/v1/me/password` |
| Signing in again replaces the browser's previous session | `POST /api/v1/auth/login` |
| **CSRF**: every POST/PUT/PATCH/DELETE under `/api/v1` needs `X-CSRF-Token` equal to the `sijil_csrf` cookie (double submit); the token rotates on sign-in | `verify_csrf` in `app/auth/dependencies.py` |
| Temporary passwords (new staff, admin reset) must be replaced before the account can do anything else | `CurrentUser` / `must_change_password` |

**Known and accepted:** signup answers 409 when an email is already registered. Without email verification there is no way to hide that and still tell a real user why signup failed. Signups are rate-limited per IP instead.

## Throttling

| What | Limit (defaults) | Answer |
| --- | --- | --- |
| Login attempts per IP | 30 per 15 min | 429 + `Retry-After` |
| Failed logins per email | 10 per 15 min, then that email is locked for the window | 429, also for emails that don't exist |
| Signups per IP | 10 per hour | 429 |
| Wrong current password on `/me/password`, per user | 10 per 15 min | 429 |
| Partner API, per key | 60 per minute, with `X-RateLimit-*` headers | 429 |
| Failed partner authentication, per IP | 60 per minute | 429 |

The limits are settings (`app/core/config.py`, documented in `backend/.env.example`). Counters live in process memory (`app/services/rate_limit.py`), which is correct for one API container; move them to Redis before running several.

**Behind Caddy, uvicorn must run with `--proxy-headers --forwarded-allow-ips=<caddy>`.** Otherwise every request appears to come from Caddy's address, and one attacker locks everyone out of the per-IP limits.

## Authorization

- Every protected route checks the role **and the organization**: `CurrentUser`, `PlatformAdmin` and `require_org_role` in `app/auth/`. The UI hides what a role can't use, but the API decides.
- Entity roles count only in an **approved** organization and only for an **active** membership.
- Nobody grants a role they don't hold: entity admins can assign entity roles in their own organization only, and platform roles are changed by platform admins only.
- There is always at least one active **platform admin** and, per organization, one active **entity admin**. Both checks lock the rows they count, so two admins removing each other at the same moment can't leave none (`tests/test_security.py`, `tests/test_members_api.py`).
- Only platform admins reset passwords. An entity admin can't: a member may be someone's personal account.
- `tests/test_cross_org_access.py` calls every organization-scoped route as another organization's admin and expects 403 with nothing changed.
- Service history is append-only. A database trigger refuses UPDATE and DELETE, and partner keys are read-only for vehicle data.

## Input validation

- **Backend:** every request body is a Pydantic model with bounded strings and lists and enums for fixed choices. Query parameters are bounded too: page sizes, page numbers and search length. VINs are normalized and validated on the server. Errors use one shape: `{"error": {"code", "message", "details?"}}`.
- **Frontend:** every form checks its fields before calling the API, mirroring the backend rules (`src/lib/validation.ts`, `src/lib/organizations.ts`, `src/lib/apiKeys.ts`). A 422 from the server is shown next to the field, with a readable summary (`errorMessage`, `serverFieldErrors` in `src/lib/api.ts`).
- JSON request bodies over 1 MB answer 413 (`MAX_REQUEST_BYTES`).
- Database access goes through SQLAlchemy with bound parameters. `LIKE` searches escape `%` and `_`.

## Privacy in responses

- Consumer timelines, PDFs and partner responses carry vehicle facts, the organization name, dates, mileage flags and correction reasons. They never carry owner, staff or customer data, or private notes (`tests/test_report_pdf.py`, `tests/test_partner_api.py`).
- Passwords, password hashes, session tokens and API key secrets never appear in responses or audit events. Temporary passwords and new API keys are shown once.
- Unexpected errors answer `500 internal_error` without details; the stack trace goes to the server log only.

## HTTP

Every API response carries:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: same-origin`
- `Cache-Control: no-store`

JSON responses also carry `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`. When `COOKIE_SECURE=true`, which is the default and required in deployment, responses carry `Strict-Transport-Security` (`app/core/security.py`).

## Still to do in other cards

| Card | Needed |
| --- | --- |
| **BU-02** Caddy | HTTPS for every browser and partner connection, with HTTP redirected to HTTPS. The same security headers for the frontend's static files, plus a CSP for the app, e.g. `default-src 'self'; frame-ancestors 'none'`. `request_body max_size` as a second limit. Run uvicorn with `--proxy-headers` (see Throttling). Keep PostgreSQL, Redis and MinIO off the public network. |
| **BU-04** WebSockets | `wss://` only. Authenticate with the session cookie and check `Origin` on connect. Send a user only events they may see (watched VINs, their organization). Re-check the session on reconnect. |
| **BU-03** Uploads | Check type by content (magic bytes), not only by extension. Cap the size on both ends. Store objects privately in MinIO under random names. Serve them only through an authorized route or a short-lived link, with `Content-Disposition: attachment`. Only platform admins delete, with an audit event. Uploads need their own limit above `MAX_REQUEST_BYTES`. |
| **BU-08** CI | Run `pytest`, `npm test`, lint and `npm audit` on every PR. |

## Reporting

Found a problem? Tell the team in the project channel rather than opening a public issue, and include steps to reproduce.
