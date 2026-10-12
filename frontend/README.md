# Sijil frontend

React + Vite + TypeScript + Tailwind CSS. Design: `doc/ARCHITECTURE.md`.

This is the minimal scaffold from NA-01 and NA-02: signup, login, logout and profile pages, role-based navigation and the platform-admin Users page (`/admin/users`). HA-01 owns the full app shell, routing and API client and may reshape it.

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
npm test         # vitest unit tests (form validation)
npm run build
```
