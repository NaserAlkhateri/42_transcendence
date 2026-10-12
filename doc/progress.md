# Sijil - Progress

Last updated: 2026-10-12 (end of week 1, day 1). Update this file when a card moves to Review or Done.

Plan and ownership: [`TEAM.md`](TEAM.md). Board: https://trello.com/b/iRrhRK44

## Summary
- **Backend foundation is in place** (AG-01, AG-02 on `main`): FastAPI, full schema with Alembic, demo seed, VIN timeline API.
- **Auth and permissions are built** (NA-01, NA-02, in Review): signup/login/logout with secure sessions and CSRF, user CRUD, roles, role-based views. Both are on branches, not yet merged.
- **A minimal frontend exists** in `frontend/` (React + Vite + TypeScript + Tailwind), added for the NA-01/NA-02 pages. HA-01 can reshape it.
- **Not started:** Docker Compose and Caddy (BU-02), so there is no single-command start yet.
- **Module points earned so far: 0.** Advanced permissions has all checklist items ticked but still needs review and PO sign-off.

## Card status

| Card | Owner | Status | Where |
| --- | --- | --- | --- |
| AG-01 Backend bootstrap, schema, migrations, seed | Agegnew | In Progress | `main` |
| AG-02 VIN lookup and timeline | Agegnew | In Progress | `main` (API only, no page yet) |
| NA-01 Signup, login, logout, profile | Naser | Review | branch `feat/na-01-auth` |
| NA-02 Users, roles, role-based views | Naser | Review | branch `feat/na-02-users-roles` (built on NA-01) |
| BU-01 Architecture and contracts | Burhan | To Do | |
| BU-02 Docker Compose, Caddy, HTTPS | Burhan | To Do | |
| HA-01 Frontend bootstrap and app shell | Hassan | To Do | see "Notes for teammates" |
| HA-02 Custom design system | Hassan | To Do | |
| All other cards (week 2-3) | | Backlog | |

BU-09 (VIN decoder) has no owner on Trello yet; TEAM.md assigns it to Burhan.

## Merge order
1. `feat/na-01-auth`
2. `feat/na-02-users-roles` (contains NA-01's commit, so merge it after)

## What you can build on

### Auth (NA-01)
- Session cookie `sijil_session` (HttpOnly, Secure, SameSite=Lax). Only a hash of the token is stored in `sessions`.
- **CSRF:** every POST/PUT/PATCH/DELETE under `/api/v1` must send the header `X-CSRF-Token` with the value of the `sijil_csrf` cookie. Get the cookie from `GET /api/v1/auth/csrf`. Without it the API answers 403 `csrf_failed`. The partner API (NA-05) will use its own router without this check.
- Endpoints: `/api/v1/auth/{csrf,signup,login,logout}`, `GET/PATCH /api/v1/me`, `POST /api/v1/me/password`.
- Passwords: 10 to 128 characters, Argon2id.

### Permissions (NA-02)
Use these in every new protected route (`backend/app/auth/`):

| Guard | Use it for |
| --- | --- |
| `CurrentUser` | Any signed-in user. Also blocks accounts that still have a temporary password. |
| `PlatformAdmin` | Platform admin only. |
| `require_org_role(db, user, org_id, {MemberRole...})` | Actions inside one organization. The user needs an **active** membership of *that* organization with one of the roles. Platform admins pass. |

Example (submitting a service record, AG-03):

```python
@router.post("/organizations/{org_id}/records")
def submit(org_id: uuid.UUID, body: RecordIn, user: CurrentUser, db: DbSession):
    require_org_role(db, user, org_id, {MemberRole.ENTITY_ADMIN, MemberRole.ENTITY_STAFF})
    ...
```

The approved-organization check is still up to the route. The guard checks membership and role, not organization status.

- `GET /api/v1/me` returns `effective_role` (`platform_admin` > `entity_admin` > `entity_staff` > `consumer`) and `memberships` (organization, role, status). The frontend uses `effective_role` for navigation and route guards.
- Admin user API: `/api/v1/admin/users` (list, search, filter, paginate, view, edit, delete, change membership role). Every edit and delete writes to `audit_events` through `app/services/audit.py:record_audit`. Please use the same helper for your own audit events.

### Frontend (`frontend/`)
- `src/lib/api.ts`: fetch wrapper that sends cookies, adds the CSRF header and turns error responses into `ApiError`.
- `src/auth/`: `useAuth()` gives the current user and `login`/`signup`/`logout`.
- `src/lib/roles.ts`: `hasRole()` and `navItemsFor()`. Add your nav links there, per role.
- `RequireRole` in `src/App.tsx` guards routes by role.
- `src/components/TextField.tsx` is a stopgap until the HA-02 design system.

## Running and testing locally

```bash
cd backend && uv sync && uv run pytest        # needs Docker running, or TEST_DATABASE_URL
cd frontend && npm install && npm run lint && npm test && npm run build
```

Dev setup: run the backend on port 8000 (see `backend/README.md`) and `npm run dev` in `frontend/`. Vite proxies `/api` to the backend. Demo accounts come from `python -m app.seed` and are listed in `backend/README.md`.

Current results on the NA-02 branch: backend 89 tests pass, frontend 8 tests pass, lint and build clean.

## Notes for teammates
- **Hassan (HA-01, HA-02):** `frontend/` was scaffolded early so the auth pages could ship. The app shell, layout and components are yours: restructure freely and keep `lib/api.ts` and the auth context, or replace them with the same behaviour (cookies + CSRF header).
- **Burhan (BU-02):** the session and CSRF cookies are `Secure`, so the stack has to be served over HTTPS through Caddy. Caddy should route `/api/*` to FastAPI and everything else to the frontend build. `COOKIE_SECURE` and `SESSION_TTL_HOURS` are in `backend/.env.example`.
- **Agegnew (AG-03 onward):** use `require_org_role` for record submission. Deleting a user leaves their service records in place, with `staff_id` set to NULL and the stored `staff_name` kept.
- **Seed and test emails:** the email validator rejects reserved domains such as `.test` and `.local`. The seed's `@sijil.demo` addresses are fine. In tests, use `@example.ae`.

## Open items
- Rate limiting on login and signup is planned for NA-06.
- No real-browser check (Chrome console) has been done on the pages yet.
- NA-03 (organizations and approval) depends on BU-03 for licence document uploads.
