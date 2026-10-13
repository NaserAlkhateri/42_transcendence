# Sijil frontend

React 19 + Vite + TypeScript + Tailwind CSS 4, routed with React Router 7. Design: `doc/ARCHITECTURE.md`.

## Run locally

Requires Node 20+ and the backend running on `http://localhost:8000` (see `backend/README.md`). The dev server proxies `/api` to it, so cookies stay same-origin.

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173
```

## Checks

```bash
npm run lint
npm test         # vitest unit tests
npm run build    # type-check + production build
```

## Structure

```
src/
  App.tsx               route table (lazy-loaded pages) inside the error boundary and auth provider
  layouts/AppLayout.tsx app shell: skip link, header + role-based nav (mobile menu), session notice, footer
  routes/guards.tsx     RequireAuth, RequireGuest, RequireRole
  auth/                 AuthProvider + useAuth(): current user, login/signup/logout, session-expiry flag
  lib/api.ts            typed API client (see below)
  lib/roles.ts          role labels, hasRole(), navItemsFor() — add nav links here
  lib/redirect.ts       safeRedirect(): only in-app paths after login
  lib/useDocumentTitle  per-page <title>
  pages/                one file per page
  components/           shared UI (HA-02 design system replaces TextField)
```

## Adding a page

1. Create `src/pages/MyPage.tsx` and call `useDocumentTitle('My page')`.
2. Add a lazy route in `App.tsx`, wrapped in `RequireAuth` or `RequireRole` as needed.
3. If it belongs in the header, add it to `navItemsFor()` in `lib/roles.ts` for the right roles.

Guards only hide UI. The backend re-checks every permission.

## API client (`lib/api.ts`)

```ts
import { http, ApiError, errorMessage, serverFieldErrors } from '../lib/api'

const user = await http.get<User>('/me')
await http.patch<User>('/me', { full_name: 'Sara' })
await http.delete(`/admin/users/${id}`)
```

- Prefixes `/api/v1`, sends the session cookie, and adds `X-CSRF-Token` (from the `sijil_csrf` cookie, fetched from `/auth/csrf` if missing) on POST/PUT/PATCH/DELETE.
- Every failure is an `ApiError` with `status`, `code`, `message` and `details`: backend error envelopes, network errors (`status 0`, `network_error`) and timeouts (`timeout`, default 15 s, `timeoutMs` to change).
- `serverFieldErrors(error, { full_name: 'fullName' })` maps 422 details onto form fields; `errorMessage(error)` gives a user-facing string.
- Pass `signal` to cancel on unmount; a cancelled request rejects with the abort error, not an `ApiError`.
- A 401 from any call signs the user out and shows "Your session has ended" in the shell. Calls where 401 is an expected answer (the initial `/me` probe, login) pass `silent401: true`.
