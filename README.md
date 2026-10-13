*This project has been created as part of the 42 curriculum by amersha, haeltahi, nalkhate, bhajili.*

# Sijil - Vehicle History Platform

> **Starter documentation only.** Replace the four `*_42_LOGIN` placeholders with the real 42 logins and update implementation details as features are built.

## Description
Sijil (سجل, "record") is a UAE-focused vehicle service-history **demo** for the 42 `ft_transcendence` project (subject v21.2), similar to Carfax in the US. Consumers enter a VIN, see the decoded car details and its service timeline, download a vehicle-only PDF and watch VINs for new records. Dealers and workshops register with their business licence; once a platform admin approves them, their staff submit append-only maintenance and repair records in a few clicks. Mileage decreases are **accepted and visibly flagged**; corrections remain linked to the original record. Outside businesses such as insurers can read vehicle histories through a key-protected partner API. This demo has **no official UAE data integration**.

### Key features
- VIN lookup with decoded car details (make, model, year) and a filterable service timeline
- Consumer-safe PDF report with no owner data
- Click-based record submission for approved entities; only the odometer is typed
- Entity verification: business licence upload and platform-admin approval before an entity can write records
- Tamper-resistant history: records are never edited or deleted; corrections are linked records
- Odometer checks: a lower reading than the last one is saved and flagged, inside a locked transaction
- Live updates over WebSocket: new records and notifications appear without a refresh
- Watchlists with in-app alerts
- Partner API with admin-issued, read-only keys and rate limiting
- English and Arabic with full right-to-left layout mirroring

## Read these five files first (contributors)
1. `README.md` - 42 compliance, module points, starting instructions and project conventions.
2. [`doc/ARCHITECTURE.md`](doc/ARCHITECTURE.md) - Stack, services, database, security and deployment contracts.
3. [`doc/FEATURES.md`](doc/FEATURES.md) - Product requirements, roles, flows and acceptance checks.
4. [`doc/TEAM.md`](doc/TEAM.md) - Roles, equally estimated Trello work and three-week delivery gates.
5. [`doc/UAE_MARKET.md`](doc/UAE_MARKET.md) - UAE market rules for UI wording, formats, theme and demo data. Read it before any frontend work.

**Build rule:** Implement the mandatory app and a demonstrable **14 module points** first. Do not claim partial modules. Add tests and documentation as you implement; do not silently alter immutable-history or privacy requirements. Reconcile changes with the PO, PM and Tech Lead.

## Instructions (target deployment)
Prerequisites: Docker Engine/Desktop and Docker Compose. Create `.env` from `.env.example`, fill local secrets and domain/port settings, then run:

```bash
cp .env.example .env
docker compose up --build -d
```

Target: one command starts the app, migrations and dependencies, with Caddy HTTPS. A demo seed process should load safe fictional organizations, staff and vehicle history. Document the exact local HTTPS URL and seed instructions when implemented. The project must work in current stable Chrome with no JavaScript console warnings/errors. The app works fully offline; internet access only adds richer VIN decoding.

## Technical stack and rationale
- **React + Vite + TypeScript + Tailwind:** clear SPA, reusable design components and RTL layout.
- **FastAPI + SQLAlchemy + Alembic + PostgreSQL:** typed APIs, relational integrity, migrations, transactional mileage validation.
- **MinIO:** private storage for entity licence and trade documents; **Celery + Redis:** background and notification jobs.
- **FastAPI WebSockets + Redis pub/sub:** live notifications and timeline updates across all connected users.
- **Docker Compose + Caddy:** single-command launch and HTTPS.
- **VIN decoding:** an offline decoder (manufacturer and model year from the VIN itself), enriched from NHTSA vPIC when the internet is reachable.
- Database tables/relations: `users`, `sessions`, `organizations`, `organization_members`, `organization_documents`, `vehicles`, `service_records`, `watchlists`, `notifications`, `api_keys`, `partner_watchlists`, `audit_events`. Field-level model details and the ERD are in `doc/ARCHITECTURE.md`.

## Team Information and Project Management
Every member is a full-stack developer and owns their features end to end (API + UI + tests) across all three weeks.

| Member | Role | Planned work (end to end) |
| --- | --- | --- |
| Agegnew Mersha | PM + Full-stack Developer | Schema/ORM, VIN timeline, service records + mileage flags, corrections, PDF, advanced search, import/export, sprint coordination |
| Naser | Product Owner + Full-stack Developer (Security) | Auth, users + roles, organizations, members/staff, partner API, security review, policy pages, acceptance |
| Burhan | Technical Lead/Architect + Full-stack Developer (DevOps) | Architecture, Docker/Caddy/HTTPS, licence document uploads, WebSocket live updates, notifications, VIN decoder, CI/backups |
| Hassan | Full-stack Developer (Frontend) + QA Lead | App shell, design system, English/Arabic RTL, watchlist, admin review, entity dashboard, e2e/browser QA |

Work is tracked in Trello (Transcendence workspace): `Backlog -> To Do -> In Progress -> Review -> Done`. Daily check-ins, peer reviews and a weekly demo. Every module card carries a checklist copied from the subject; a module is claimed only when every item is ticked. See `doc/TEAM.md` for the 8 planned full-stack tasks per member, test ownership and week-by-week objectives. Record tools/chat channel details and **actual** contributions before final evaluation.

## Features and ownership
Each feature has one end-to-end owner (API + UI + tests):
- **Agegnew:** VIN lookup and timeline, service record submission with mileage flags, corrections, PDF report, advanced search, CSV/JSON import/export.
- **Naser:** signup/login/profile, user CRUD and roles, organization registration/approval/CRUD (incl. delete), members and staff accounts, partner API with admin-issued keys, Privacy Policy/Terms.
- **Burhan:** Docker/Caddy/HTTPS, licence document uploads (MinIO), WebSocket live updates, notifications, VIN decoder.
- **Hassan:** app shell and design system, English/Arabic RTL, watchlist, admin review (flags + audit), entity dashboard.
- **Quality and release:** every member tests their own features; Hassan leads e2e and browser QA, Burhan CI and deploy smoke tests, Agegnew concurrency tests, Naser security tests.

## 42 selected modules and points
**Requirement:** at least **14 module points** (major = 2, minor = 1). Extra validated modules may count toward at most **5 bonus points**. These are **planned**, not yet earned.

| Claimed only when complete | Type | Points | Trello |
| --- | --- | ---: | --- |
| Framework for frontend **and** backend (React, FastAPI) | Major | 2 | HA-01, AG-01 |
| Real-time features using WebSockets | Major | 2 | BU-04 |
| Advanced permissions system (user CRUD, roles, role-based views) | Major | 2 | NA-02 |
| Organization system (CRUD, add/remove members) | Major | 2 | NA-03, NA-04 |
| Public API (secured key, rate limit, docs, 5+ endpoints, GET/POST/PUT/DELETE) | Major | 2 | NA-05 |
| ORM | Minor | 1 | AG-01 |
| Right-to-left language support (Arabic, full mirroring) | Minor | 1 | HA-03 |
| Advanced search (filters, sorting, pagination) | Minor | 1 | AG-06 |
| File upload and management (validation, preview, progress, delete, security) | Minor | 1 | BU-03 |
| Support for additional browsers (Firefox and Edge) | Minor | 1 | HA-07 |
| Custom design system (10+ reusable components) | Minor | 1 | HA-02 |
| Complete notification system for create/update/delete | Minor (stretch) | 1 | BU-05 |
| Data export and import (validation; CSV and JSON) | Minor (stretch) | 1 | AG-07 |
| **Total planned** | **5 majors + 8 minors** | **18** | |

**Core target: 16 points** - the five majors (10) plus ORM, RTL, advanced search, file management, additional browsers and custom design system (6). That leaves a 2-point margin above the required 14 if one module is not validated. **Stretch to 18:** full CRUD notifications (+1) and bulk import/export (+1). Watchlist notifications remain a product feature even if the full notification minor is incomplete.

Not claiming: three-language i18n (English + Arabic only), GDPR minor (its confirmation emails conflict with no SMTP), OAuth, 2FA, or Prometheus/Grafana monitoring. Google login may be considered after core delivery. Do not implement friends/chat or a game just to pursue points.

## Mandatory submission checklist
- [ ] Responsive, accessible frontend; backend and database; secure signup/login with salted/hashed passwords.
- [ ] Multi-user concurrency works, with live updates over WebSocket; frontend/backend validation; HTTPS for **all** external API traffic.
- [ ] Docker deployment uses one command; current Chrome works with no JavaScript warnings/errors.
- [ ] `.env` is ignored by Git and `.env.example` is committed with no real secrets.
- [ ] **Privacy Policy** and **Terms of Service** accessible from the UI with accurate non-placeholder content (including how licence documents are stored and who can see them).
- [ ] Git history shows clear commits, task distribution and contributions from all 4 developers.
- [ ] README records real 42 logins, setup details, stack rationale, up-to-date schema/ERD, features, completed modules, module owners, project management and actual individual contributions.
- [ ] Every claimed module demonstrated end-to-end; no incomplete module counted.

## Resources and AI use
References: the official `ft_transcendence` subject v21.2; [FastAPI documentation](https://fastapi.tiangolo.com/); [SQLAlchemy](https://docs.sqlalchemy.org/); [Alembic](https://alembic.sqlalchemy.org/); [React](https://react.dev/); [Docker Compose](https://docs.docker.com/compose/); [Caddy](https://caddyserver.com/docs/); [NHTSA vPIC API](https://vpic.nhtsa.dot.gov/api/); ISO 3779 (VIN structure).

AI tools may assist with scaffolding, implementation, tests and documentation. Developers must review every generated change, understand its behavior, test it, and be able to explain it during peer evaluation. Before submission, replace this generic note with the **actual tasks and project areas** where AI was used, and document real individual contributions.
