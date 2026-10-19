# Sijil - Progress

Last updated: 2026-10-20 (week 3: AG-06 advanced search and AG-07 import/export built; NA-03 to NA-07 merged).

Plan and ownership: [`TEAM.md`](TEAM.md). Board: https://trello.com/b/iRrhRK44

## Summary
- **Week 1 is done for Agegnew, Naser and Hassan.** AG-01, AG-02, NA-01, NA-02, HA-01 and HA-02 are merged on `main` and verified in Chromium against the real backend and seed data.
- **Burhan's week-1 cards have not started** (BU-01 contracts, BU-02 Docker Compose + Caddy). Until BU-02 lands there is no single-command start, which is part of the week-1 demo gate.
- **Week 2 is done for Agegnew:** AG-03 record submission, AG-04 corrections and AG-05 bilingual PDF report are merged and verified in Chromium against the real backend.
- **Week 3 for Agegnew:** AG-06 advanced search (branch `AG-06-advanced-search`) and AG-07 CSV/JSON import and export (branch `AG-07-import-export`, built on AG-06) are built, tested and verified in Chromium against the real backend. All Advanced search items (filters, sorting, pagination) and all Data export/import items (multiple formats, import with validation, bulk operations) are ticked. Both still need a peer review and Naser's PO sign-off. AG-08 (PM) is ongoing.
- **NA-03 organizations is merged** (registration, admin review, create/edit/delete). Showing licence documents on the review screen waits for BU-03.
- **NA-07 Privacy Policy and Terms of Service are in Review** on `feat/na-07-legal-pages` (built on NA-06). Both pages have real Sijil-specific content in English and Arabic (with a language switch and right-to-left layout), are linked from the footer, and are linked where people agree to them (signup, business registration).
- **NA-06 security hardening is in Review** on `feat/na-06-security`. It adds login, signup and password throttling, a new session after a password change, the last-platform-admin lock, platform-admin password resets, security headers, a 1 MB body limit and a cross-organization access test matrix. The full list, and what Caddy (BU-02), uploads (BU-03) and WebSockets (BU-04) must add, is in [`SECURITY.md`](SECURITY.md).
- **NA-05 partner API is merged**: six key-authenticated endpoints at `/api/partner/v1` (vehicle summary and history, watchlist GET/POST/PUT/DELETE), admin-issued and revocable keys, per-key rate limiting with 429, and partner docs (`doc/PARTNER_API.md`, `/api/partner/v1/docs`). All eight Public API checklist items are ticked; it still needs a peer review and Naser's PO sign-off.
- **NA-04 members and staff accounts is merged**: entity admins add and remove members, create staff accounts with a temporary password, and assign entity roles. With NA-03 + NA-04, all four Organization-system checklist items are ticked; the module still needs a peer review and Naser's PO sign-off.
- On `main` (with NA-03): backend 172 tests, frontend 119 tests, lint and build clean. With NA-04: backend 186, frontend 125. With NA-05: backend 209, frontend 130. With NA-06: backend 229, frontend 136. With NA-07: frontend 146. With AG-06 + AG-07: backend 518, frontend 261.
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
| AG-03 Service record submission + mileage flags | Agegnew | Done | `/workshop/records/new`; `record.added` is published for BU-04 |
| AG-04 Corrections linked to originals | Agegnew | Done | `/workshop/corrections`; a record is corrected once (chain to fix a fix) |
| AG-05 Consumer-safe PDF report | Agegnew | Done | English + Arabic; download button on `/vehicles/:vin` |
| AG-06 Advanced search | Agegnew | In Progress (built) | `/workshop/records` (own organisation), `/admin/records` (all). API in `backend/README.md` |
| AG-07 CSV/JSON import and export | Agegnew | In Progress (built) | Export on both search pages; import at `/workshop/records/import`. Privacy Policy updated for downloads |
| AG-08 PM: coordination, demos, README | Agegnew | In Progress | Ongoing until submission |
| NA-03 Organizations: registration, approval, CRUD | Naser | Review (merged) | `/organizations/register`, `/organizations/:id`, `/admin/organizations`. Licence documents on the review screen wait for BU-03. |
| NA-04 Organization members and staff accounts | Naser | Review (merged) | Members panel on `/organizations/:id` (entity admins) and in the admin Manage panel |
| NA-05 Partner API (keys, rate limit, docs) | Naser | Review (merged) | `/admin/api-keys` page; guide in `doc/PARTNER_API.md` |
| NA-06 Security hardening and review | Naser | Review | `doc/SECURITY.md`; admin "Reset password" on `/admin/users` |
| NA-07 Privacy Policy and Terms of Service | Naser | Review | `/privacy`, `/terms` (`?lang=ar` for Arabic); text in `frontend/src/pages/legal/` |
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
- **Everyone (week 2):** `POST /api/v1/organizations/{id}/records` is how history is written. Listen for new records with `app.services.events.subscribe` (`record.added`: VIN, record id, date, flag, corrected id). Burhan's WebSocket (BU-04), Hassan's watchlist alerts (HA-04) and the admin flagged queue (HA-05) can all build on it. Work-code labels (English + Arabic) come from `GET /api/v1/work-codes`.
- **Hassan (HA-04):** the Watch button lives in `src/components/WatchVinButton.tsx`. Guests are sent to log in and come back to the VIN. Wire the signed-in state to the watchlist API there.
- **Burhan (BU-02):** the session and CSRF cookies are `Secure`, so the stack has to be served over HTTPS through Caddy. Caddy should route `/api/*` to FastAPI and everything else to the frontend build. `COOKIE_SECURE` and `SESSION_TTL_HOURS` are in `backend/.env.example`.
- **Agegnew (AG-03 onward):** use `require_org_role` for record submission. Deleting a user leaves their service records in place, with `staff_id` set to NULL and the stored `staff_name` kept.
- **Burhan (BU-03, BU-05):** registration and review are in place (NA-03). For BU-03, add the licence documents to `GET /api/v1/admin/organizations/{id}` and show them in the Manage panel on `/admin/organizations`; members upload from `/organizations/:id`. For BU-05, `organization.reviewed` is published on approve and reject (`organization_id`, `name`, `status`, `rejection_reason`).
- **Hassan (HA-04):** the partner watchlist (`partner_watchlists`) is separate from the consumer one (`watchlists`). Watching a VIN with no history creates its `vehicles` row; the timeline still answers `vehicle: null` until the first record exists (`services/timeline.py:has_history`), so the page keeps offering Watch and hides the PDF button. Use the same helper if the consumer watch creates vehicles too.
- **Everyone: keep the legal pages true.** The Privacy Policy already describes licence documents (BU-03), in-app notifications (BU-05) and VIN decoding through NHTSA vPIC (BU-09), as designed in ARCHITECTURE.md. If your card stores, shows or shares data differently, or adds browser storage (e.g. a language preference in HA-03), update `frontend/src/pages/legal/privacy.ts` / `terms.ts` and `LEGAL_UPDATED` in the same PR. Hassan: the Arabic text needs a native-speaker check in HA-03, and the pages' own language switch can hand over to the app-wide one.
- **Entity roles need an approved organization:** since NA-03, `effective_role` only counts memberships of approved organizations. A pending registrant is `consumer` in the UI, but `require_org_role` still lets them manage their own registration.
- **Hassan (HA-05):** the admin flagged-records queue can reuse AG-06: `GET /api/v1/admin/records?flagged=true` (all filters, sorting and paging) and the `/admin/records` page.
- **Hassan (HA-03):** the new pages `RecordSearchPage.tsx` and `workshop/ImportRecordsPage.tsx` are English only, ready for their strings to move into i18n.
- **Hassan (design system):** AG-06 added an optional `sort` prop to `Table` columns (sets `aria-sort`); it could go in `DESIGN_SYSTEM.md`. `Pagination` prints its total without a thousands separator ("1320 results"). With the extra nav entries, the desktop header wraps onto two lines between 640 and 760 px; moving AppLayout's desktop nav from `sm:` to `md:` fixes it.
- **Everyone:** `src/lib/api.ts` can now send a file as the raw request body (`rawBody`), and `apiResponse()` returns the Response for downloads. `src/lib/download.ts` saves a response as a file. Use them for any new upload or download.
- **Seed and test emails:** the email validator rejects reserved domains such as `.test` and `.local`. The seed's `@sijil.demo` addresses are fine. In tests, use `@example.ae`.

## Open items
- Burhan: when wiring Caddy (BU-02), run uvicorn with `--proxy-headers` so per-IP limits see real clients (doc/SECURITY.md).
- A wrong-password login still shows the API's 401 in the console. That is the failure path, not a page load.
- NA-03's review screen shows no licence documents until BU-03 lands.
- Entity admins can't reset a member's password (by design). Platform admins can, from `/admin/users` (NA-06).
- Records from one import share one `created_at` (the database's `now()` is per transaction), so "newest first" orders a batch by record id, not file order.
- `tests/test_partner_api.py::test_watch_lifecycle_get_post_put_delete` fails on some runs (seen on 2026-10-19 on `main`, then passed). Naser to check whether it is time-dependent.
