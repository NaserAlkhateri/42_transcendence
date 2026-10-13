# Sijil - Progress

Last updated: 2026-10-13 (end of week 1, day 2). Update this file when a card moves to Review or Done.

Plan and ownership: [`TEAM.md`](TEAM.md). Board: https://trello.com/b/iRrhRK44

## Summary
- **Week 1 is done for Agegnew, Naser and Hassan.** AG-01, AG-02, NA-01, NA-02, HA-01 and HA-02 are merged on `main` and verified in Chromium against the real backend and seed data.
- **Burhan's week-1 cards have not started** (BU-01 contracts, BU-02 Docker Compose + Caddy). Until BU-02 lands there is no single-command start, which is part of the week-1 demo gate.
- On `main`: backend 94 tests, frontend 67 tests, lint and build clean.
- **Module points earned so far: 0.** Checklists are ticked for Frameworks (HA-01 + AG-01), ORM (AG-01), Advanced permissions (NA-02) and Custom design system (HA-02); each still needs Naser's PO sign-off.

## Card status

| Card | Owner | Status | Notes |
| --- | --- | --- | --- |
| AG-01 Backend bootstrap, schema, migrations, seed | Agegnew | Done | |
| AG-02 VIN lookup and timeline | Agegnew | Done | API + `/vehicles/:vin` page. The Watch button is disabled for signed-in users until HA-04. |
| NA-01 Signup, login, logout, profile | Naser | Done | Follow-ups for NA-06 are on the Trello card |
| NA-02 Users, roles, role-based views | Naser | Done | Turning a consumer into entity staff needs memberships (NA-04) |
| HA-01 Frontend bootstrap and app shell | Hassan | Done | |
| HA-02 Custom design system | Hassan | Done | Follow-ups for HA-08 are on the Trello card |
| BU-01 Architecture and contracts | Burhan | To Do | |
| BU-02 Docker Compose, Caddy, HTTPS | Burhan | To Do | Blocks the week-1 single-command start |
| All other cards (week 2-3) | | Backlog | |

Week-1 review fixes merged on 2026-10-13:
- `GET /api/v1/auth/session` answers 200 with `user: null` for guests, so loading the app no longer prints a 401 in the console.
- Logout lands on `/` and only clears the user once the server confirms. A failed logout says so and keeps you signed in.
- An admin edit that changes the email to a taken one and disables the user in the same request answers 409 (it used to answer 500). `page` on the user list is capped, so a huge value answers 422 instead of 500.
- The admin user list shows its load error instead of a loading row that never ends. A favicon was added, so a clean load logs no 404.

## What you can build on

### Auth (NA-01)
- Session cookie `sijil_session` (HttpOnly, Secure, SameSite=Lax). Only a hash of the token is stored in `sessions`.
- **CSRF:** every POST/PUT/PATCH/DELETE under `/api/v1` must send the header `X-CSRF-Token` with the value of the `sijil_csrf` cookie. Get the cookie from `GET /api/v1/auth/csrf`. Without it the API answers 403 `csrf_failed`. The partner API (NA-05) will use its own router without this check.
- Endpoints: `/api/v1/auth/{csrf,session,signup,login,logout}`, `GET/PATCH /api/v1/me`, `POST /api/v1/me/password`. `GET /auth/session` is the SPA's start-up probe (200 with `user` or `null`); `/me` still answers 401 when signed out.
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
- `src/auth/`: `useAuth()` gives the current user and `login`/`signup`/`logout`. The start-up probe is `GET /api/v1/auth/session`.
- `src/lib/roles.ts`: `hasRole()` and `navItemsFor()`. Add your nav links there, per role.
- `src/routes/guards.tsx`: `RequireAuth`, `RequireGuest` and `RequireRole`.
- `src/components/ui`: the design system (see `doc/DESIGN_SYSTEM.md` and `/design-system`). Build every page from it.
- `src/lib/vin.ts` (`parseVin`) and `src/lib/timeline.ts`: VIN normalization and timeline types. `/vehicles/:vin` is the consumer timeline page.

## Running and testing locally

```bash
cd backend && uv sync && uv run pytest        # needs Docker running, or TEST_DATABASE_URL
cd frontend && npm install && npm run lint && npm test && npm run build
```

Dev setup: run the backend on port 8000 (see `backend/README.md`) and `npm run dev` in `frontend/`. Vite proxies `/api` to the backend. Demo accounts come from `python -m app.seed` and are listed in `backend/README.md`.

Current results on `main`: backend 94 tests pass, frontend 67 tests pass, lint and build clean.

## Notes for teammates
- **Hassan (HA-04):** the Watch button lives in `src/components/WatchVinButton.tsx`. Guests are sent to log in and come back to the VIN. Wire the signed-in state to the watchlist API there.
- **Burhan (BU-02):** the session and CSRF cookies are `Secure`, so the stack has to be served over HTTPS through Caddy. Caddy should route `/api/*` to FastAPI and everything else to the frontend build. `COOKIE_SECURE` and `SESSION_TTL_HOURS` are in `backend/.env.example`.
- **Agegnew (AG-03 onward):** use `require_org_role` for record submission. Deleting a user leaves their service records in place, with `staff_id` set to NULL and the stored `staff_name` kept.
- **Seed and test emails:** the email validator rejects reserved domains such as `.test` and `.local`. The seed's `@sijil.demo` addresses are fine. In tests, use `@example.ae`.

## Open items
- Rate limiting on login and signup is planned for NA-06.
- A wrong-password login still shows the API's 401 in the console. That is the failure path, not a page load.
- NA-03 (organizations and approval) depends on BU-03 for licence document uploads.
