*This project has been created as part of the 42 curriculum by AGEGNEW_42_LOGIN, HASAN_42_LOGIN, NASER_42_LOGIN, BURHAN_42_LOGIN.*

# Sijil - Vehicle History Platform

> **Starter documentation only.** Replace the four `*_42_LOGIN` placeholders with the real 42 logins and update implementation details as features are built.

## Description
Sijil is a UAE-focused vehicle service-history **demo** for the 42 `ft_transcendence` project (subject v21.2). Consumers look up VIN history, download vehicle-only PDFs and watch VINs. Approved dealers/workshops submit append-only maintenance and repair records; a platform admin approves entities and reviews flags. Mileage decreases are **accepted and visibly flagged**; corrections remain linked to the original record. This demo has **no official UAE data integration**.

## Read these four files first (Claude Code and contributors)
1. `README.md` - 42 compliance, module points, starting instructions and project conventions.
2. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) - Stack, services, database, security and deployment contracts.
3. [`docs/FEATURES.md`](docs/FEATURES.md) - Product requirements, roles, flows and acceptance checks.
4. [`docs/TEAM.md`](docs/TEAM.md) - Roles, equally estimated Trello work and three-week delivery gates.

**Build rule:** Implement the mandatory app and a demonstrable **14 module points** first. Do not claim partial modules. Add tests and documentation as you implement; do not silently alter immutable-history or privacy requirements. Reconcile changes with the PO, PM and Tech Lead.

## Instructions (target deployment)
Prerequisites: Docker Engine/Desktop and Docker Compose. Create `.env` from `.env.example`, fill local secrets and domain/port settings, then run:

```bash
cp .env.example .env
docker compose up --build -d
```

Target: one command starts the app, migrations and dependencies, with Caddy HTTPS. A demo seed process should load safe fictional organizations, staff and vehicle history. Document the exact local HTTPS URL and seed instructions when implemented. The project must work in current stable Chrome with no JavaScript console warnings/errors.

## Technical stack and rationale
- **React + Vite + TypeScript + Tailwind:** clear SPA, reusable design components and RTL layout.
- **FastAPI + SQLAlchemy + Alembic + PostgreSQL:** typed APIs, relational integrity, migrations, transactional mileage validation.
- **MinIO:** private supporting evidence; **Celery + Redis:** background and notification jobs.
- **FastAPI WebSockets + Redis pub/sub:** live notifications and timeline updates across all connected users.
- **Docker Compose + Caddy:** single-command launch and HTTPS; **Prometheus + Grafana:** metrics, dashboards and alerts.
- Database tables/relations: `users`, `sessions`, `organizations`, `organization_members`, `vehicles`, `service_records`, `attachments`, `watchlists`, `notifications`, `api_keys`, `partner_watchlists`, `audit_events`. Field-level model details are in `docs/ARCHITECTURE.md`; update with an ERD during implementation.

## Team Information and Project Management
Every member is a full-stack developer and owns their features end to end (API + UI + tests) across all three weeks.

| Member | Role | Planned work (end to end) |
| --- | --- | --- |
| Agegnew Mersha | PM + Full-stack Developer | Schema/ORM, VIN timeline, service records + mileage flags, corrections, PDF, advanced search, import/export, sprint coordination |
| Naser | Product Owner + Full-stack Developer (Security) | Auth, users + roles, organizations, members/staff, partner API, security review, policy pages, acceptance |
| Burhan | Technical Lead/Architect + Full-stack Developer (DevOps) | Architecture, Docker/Caddy/HTTPS, file uploads, WebSocket live updates, notifications, monitoring, CI/backups |
| Hasan | Full-stack Developer (Frontend) + QA Lead | App shell, design system, English/Arabic RTL, watchlist, admin review, entity dashboard, e2e/browser QA |

Work is tracked in Trello (Transcendence workspace): `Backlog -> To Do -> In Progress -> Review -> Done`. Daily check-ins, peer reviews and a weekly demo. See `docs/TEAM.md` for the 8 planned full-stack tasks per member, test ownership and week-by-week objectives. Record tools/chat channel details and **actual** contributions before final evaluation.

## Features and ownership
Each feature has one end-to-end owner (API + UI + tests):
- **Agegnew:** VIN lookup and timeline, service record submission with mileage flags, corrections, PDF report, advanced search, CSV/JSON import/export.
- **Naser:** signup/login/profile, user CRUD and roles, organization registration/approval/CRUD (incl. delete), members and staff accounts, partner API, Privacy Policy/Terms.
- **Burhan:** Docker/Caddy/HTTPS, file uploads (MinIO), WebSocket live updates, notifications, Prometheus/Grafana monitoring.
- **Hasan:** app shell and design system, English/Arabic RTL, watchlist, admin review (flags + audit), entity dashboard.
- **Quality and release:** every member tests their own features; Hasan leads e2e and browser QA, Burhan CI and deploy smoke tests, Agegnew concurrency tests, Naser security tests.

## 42 selected modules and points
**Requirement:** at least **14 module points** (major = 2, minor = 1). Extra validated modules may count toward at most **5 bonus points**. These are **planned**, not yet earned.

| Claimed only when complete | Type | Points |
| --- | --- | ---: |
| Framework for frontend **and** backend | Major | 2 |
| Advanced user permissions + user CRUD | Major | 2 |
| Organization CRUD and membership management | Major | 2 |
| Secure public API (5+ endpoints; GET/POST/PUT/DELETE; rate limit/docs) | Major | 2 |
| Prometheus + Grafana monitoring (exporters, dashboards, alerts, security) | Major (stretch) | 2 |
| ORM | Minor | 1 |
| RTL with complete Arabic layout mirroring | Minor | 1 |
| Advanced search (filters, sorting, pagination) | Minor | 1 |
| File upload and management (validation, preview, progress, delete, security) | Minor | 1 |
| Complete in-app CRUD notifications | Minor (stretch) | 1 |
| Bulk data import/export (validation; multiple export formats) | Minor (stretch) | 1 |
| Two additional browsers (Firefox and Edge) | Minor | 1 |
| Custom design system (10+ reusable components) | Minor | 1 |
| **Total planned** | **5 majors + 8 minors** | **18** |

**Core 14-point target:** first four majors (8) plus ORM, RTL, advanced search, file management, additional browsers and custom design system (6). **Stretch to 18:** monitoring major (+2), full CRUD notifications (+1), bulk import/export (+1). Watchlist notifications remain a product feature even if the full notification minor is incomplete.

Not claiming: three-language i18n (English + Arabic only), GDPR minor (its confirmation emails conflict with no SMTP), OAuth, or 2FA until completely implemented. Google login may be considered after core delivery. Do not implement friends/chat or a game just to pursue points.

## Mandatory submission checklist
- [ ] Responsive, accessible frontend; backend and database; secure signup/login with salted/hashed passwords.
- [ ] Multi-user concurrency works, with live updates over WebSocket; frontend/backend validation; HTTPS for **all** external API traffic.
- [ ] Docker deployment uses one command; current Chrome works with no JavaScript warnings/errors.
- [ ] `.env` is ignored by Git and `.env.example` is committed with no real secrets.
- [ ] **Privacy Policy** and **Terms of Service** accessible from the UI with accurate non-placeholder content.
- [ ] Git history shows clear commits, task distribution and contributions from all 4 developers.
- [ ] README records real 42 logins, setup details, stack rationale, up-to-date schema/ERD, features, completed modules, module owners, project management and actual individual contributions.
- [ ] Every claimed module demonstrated end-to-end; no incomplete module counted.

## Resources and AI use
References: the official `ft_transcendence` subject v21.2; [FastAPI documentation](https://fastapi.tiangolo.com/); [SQLAlchemy](https://docs.sqlalchemy.org/); [Alembic](https://alembic.sqlalchemy.org/); [React](https://react.dev/); [Docker Compose](https://docs.docker.com/compose/); [Caddy](https://caddyserver.com/docs/); [Prometheus](https://prometheus.io/docs/); [Grafana](https://grafana.com/docs/).

AI tools such as Claude Code may assist with scaffolding, implementation, tests and documentation. Developers must review every generated change, understand its behavior, test it, and be able to explain it during peer evaluation. Before submission, replace this generic note with the **actual tasks and project areas** where AI was used, and document real individual contributions.
