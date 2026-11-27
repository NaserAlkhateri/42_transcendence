*This project has been created as part of the 42 curriculum by amersha, haeltahi, nalkhate, vlyubick.*

# Sijil - Vehicle History Platform

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
2. [`doc/ARCHITECTURE.md`](doc/ARCHITECTURE.md) - Repository layout, stack, data model, HTTP/WebSocket contracts, security and deployment decisions.
3. [`doc/FEATURES.md`](doc/FEATURES.md) - Product requirements, roles, flows and acceptance checks.
4. [`doc/TEAM.md`](doc/TEAM.md) - Roles, equally estimated Trello work and three-week delivery gates.
5. [`doc/UAE_MARKET.md`](doc/UAE_MARKET.md) - UAE market rules for UI wording, formats, theme and demo data. Read it before any frontend work.

**Build rule:** Implement the mandatory app and a demonstrable **14 module points** first. Do not claim partial modules. Add tests and documentation as you implement; do not silently alter immutable-history or privacy requirements. Reconcile changes with the PO, PM and Tech Lead.

## Instructions

Use Docker Desktop or Docker Engine with the Compose v2 plugin. Start Docker, make sure host ports 80 and 443 are free, and run these commands from the repository root:

```bash
cp .env.example .env
# Set POSTGRES_PASSWORD, MINIO_ROOT_PASSWORD and SEED_DEMO_PASSWORD in .env before starting.
docker compose up --build -d
```

Choose distinct passwords, use at least eight characters for `MINIO_ROOT_PASSWORD`, and keep `.env` local. Quote values containing literal `$` or `#` with single quotes in `.env`. The first build pulls base images and locked dependencies and builds the pinned MinIO Community Edition source. Compose starts PostgreSQL, MinIO and Redis, applies Alembic migrations, loads the fictional demo data, then starts FastAPI and Caddy. `docker compose ps -a` should show healthy `db`, `minio`, `redis` and `api` services, a running `caddy`, and `init` with `Exited (0)`.

### Open the local HTTPS demo

Caddy listens on loopback and creates a local CA for `https://localhost`. Copy the public root certificate once per Compose data volume:

```bash
sijil_tls_dir=$(mktemp -d)
docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt "$sijil_tls_dir/root.crt"
curl --cacert "$sijil_tls_dir/root.crt" --fail https://localhost/health
```

The response should report `status` and `database` as `ok`. Follow the [Caddy local HTTPS instructions](https://caddyserver.com/docs/running#local-https-with-docker) to trust that certificate in your browser or system, then open [https://localhost](https://localhost) in Chrome. The API docs are at [https://localhost/api/v1/docs](https://localhost/api/v1/docs) and partner docs at [https://localhost/api/partner/v1/docs](https://localhost/api/partner/v1/docs). Try VIN `JTMHX01J5M4012345` or sign in as `consumer@sijil.demo` with the demo password from `.env`. See [the demo account list](backend/README.md#database-and-demo-data) for other roles and VINs. On an existing database the seed preserves existing users' passwords and data.

`docker compose logs init minio redis api caddy` shows startup errors. `docker compose down` stops the stack and preserves the database, licence documents and local CA in Docker volumes. Caddy is the only service with host ports. It redirects HTTP to HTTPS, serves the React build, and proxies `/api/*`, including `wss://localhost/api/v1/ws`, and `/health` to FastAPI.

For a hosted instance, set `SIJIL_HOST` to the public DNS hostname, set `SIJIL_BIND_IP` to the appropriate host interface, and set `SEED_DEMO_DATA=false` before the first start. Point DNS to the host and open TCP 80 and 443 so Caddy can obtain a public certificate. Use a fresh database for hosting. Turning the seed off on an existing demo database leaves the previous demo users in place.

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
| Veronika | Technical Lead/Architect + Full-stack Developer (DevOps) | Architecture, Docker/Caddy/HTTPS, licence document uploads, WebSocket live updates, notifications, VIN decoder, CI/backups |
| Hassan | Full-stack Developer (Frontend) + QA Lead | App shell, design system, English/Arabic RTL, watchlist, admin review, entity dashboard, e2e/browser QA |

Work is tracked in Trello (Transcendence workspace): `Backlog -> To Do -> In Progress -> Review -> Done`. Daily check-ins, peer reviews and a weekly demo. Every module card carries a checklist copied from the subject; a module is claimed only when every item is ticked. See `doc/TEAM.md` for the 8 planned full-stack tasks per member, test ownership and week-by-week objectives. Record tools/chat channel details and **actual** contributions before final evaluation.

### Actual individual contributions
Each member keeps their own entry up to date as their cards finish.

- **Agegnew (PM + full-stack):**
  - Backend foundation (AG-01): FastAPI app, the full database schema with Alembic migrations, the append-only trigger on service records, and the demo seed.
  - VIN lookup (AG-02): VIN normalisation and the consumer timeline API and page.
  - Record submission (AG-03): one locked transaction per record that decides the mileage flag, with concurrency tests.
  - Corrections (AG-04): each correction is linked to its original record.
  - PDF report (AG-05): consumer-safe, in English and Arabic.
  - Advanced search (AG-06) and CSV/JSON import and export (AG-07), described under "Module notes" below.
  - Project management: set up the Trello board and cards, coordinated the weekly plan, and tracked progress in [`doc/progress.md`](doc/progress.md).
- **Veronika (Technical Lead + full-stack):** VE-02 Docker Compose deployment, Caddy HTTPS and same-origin routing, automatic migrations and demo seed, and deployment documentation.
  - VE-03 private licence document uploads, preview and platform-admin review, with audited removal and role tests.
  - VE-04 authenticated WebSocket fan-out over Redis, live vehicle timeline and watch alerts, and recovery after disconnects.
  - VE-05 notification centre, persistent read/unread state, cross-session badge updates, and notices for relevant business and account changes.

## Features and ownership
Each feature has one end-to-end owner (API + UI + tests):
- **Agegnew:** VIN lookup and timeline, service record submission with mileage flags, corrections, PDF report, advanced search, CSV/JSON import/export.
- **Naser:** signup/login/profile, user CRUD and roles, organization registration/approval/CRUD (incl. delete), members and staff accounts, partner API with admin-issued keys, Privacy Policy/Terms.
- **Veronika:** Docker/Caddy/HTTPS, licence document uploads (MinIO), WebSocket live updates, notifications, VIN decoder.
- **Hassan:** app shell and design system, English/Arabic RTL, watchlist, admin review (flags + audit), entity dashboard.
- **Quality and release:** every member tests their own features; Hassan leads e2e and browser QA, Veronika CI and deploy smoke tests, Agegnew concurrency tests, Naser security tests.

## 42 selected modules and points
**Requirement:** at least **14 module points** (major = 2, minor = 1). Extra validated modules may count toward at most **5 bonus points**. These are **planned**, not yet earned.

| Claimed only when complete | Type | Points | Trello |
| --- | --- | ---: | --- |
| Framework for frontend **and** backend (React, FastAPI) | Major | 2 | HA-01, AG-01 |
| Real-time features using WebSockets | Major | 2 | VE-04 |
| Advanced permissions system (user CRUD, roles, role-based views) | Major | 2 | NA-02 |
| Organization system (CRUD, add/remove members) | Major | 2 | NA-03, NA-04 |
| Public API (secured key, rate limit, docs, 5+ endpoints, GET/POST/PUT/DELETE) | Major | 2 | NA-05 |
| ORM | Minor | 1 | AG-01 |
| Right-to-left language support (Arabic, full mirroring) | Minor | 1 | HA-03 |
| Advanced search (filters, sorting, pagination) | Minor | 1 | AG-06 |
| File upload and management (validation, preview, progress, delete, security) | Minor | 1 | VE-03 |
| Support for additional browsers (Firefox and Edge) | Minor | 1 | HA-07 |
| Custom design system (10+ reusable components) | Minor | 1 | HA-02 |
| Complete notification system for create/update/delete | Minor (stretch) | 1 | VE-05 |
| Data export and import (validation; CSV and JSON) | Minor (stretch) | 1 | AG-07 |
| **Total planned** | **5 majors + 8 minors** | **18** | |

**Core target: 16 points** - the five majors (10) plus ORM, RTL, advanced search, file management, additional browsers and custom design system (6). That leaves a 2-point margin above the required 14 if one module is not validated. **Stretch to 18:** full CRUD notifications (+1) and bulk import/export (+1). Watchlist notifications remain a product feature even if the full notification minor is incomplete.

Not claiming: three-language i18n (English + Arabic only), GDPR minor (its confirmation emails conflict with no SMTP), OAuth, 2FA, or Prometheus/Grafana monitoring. Google login may be considered after core delivery. Do not implement friends/chat or a game just to pursue points.

### Module notes
Each module owner adds how their module is built and how to demonstrate it. API details are in [`backend/README.md`](backend/README.md).

**File upload and management (VE-03, Veronika):** register a demo business and select a fictional PDF, JPEG or PNG licence document. Use the registration form to preview the file and submit it with visible upload progress. On the organisation page its entity admin can upload, preview and download. Sign in as `admin@sijil.demo`, open the business in Administration → Organisations, and preview or remove the document. The organisation page shows **Document removed** after removal. PDF preview shows the first page. Download the document to review every page. The archived [MinIO Community Edition](https://github.com/minio/minio) is pinned for this demo and isolated from the host; use a maintained private S3-compatible service for production.

**Notification centre (VE-05, Veronika):** open **Notifications** after the VE-04 demo and choose **Unread**, **Mark as read**, **Mark as unread** or **Mark all as read**. A second session for the same user updates without a refresh. To demonstrate creation, update and deletion outside the watchlist, add an existing account to an approved organisation, change its membership, and remove it. That account receives all three notices. See [the API guide](backend/README.md#notification-centre-ve-05) for event and recipient rules.

**Real-time features (VE-04, Veronika):** Sign in as `consumer@sijil.demo` and open VIN `JTMHX01J5M4012345`. This demo account already watches that VIN. In a separate browser session, sign in as `falcon.staff@sijil.demo`, then submit a record for that VIN in **New service record**. The consumer's timeline and notification badge update without a page refresh. Take the consumer window offline, submit another record from the workshop window, then bring the consumer window back online. The socket resubscribes and the timeline and recent notifications catch up through REST. See the [WebSocket contract](contracts/websocket.asyncapi.json).

**Advanced search (AG-06, Agegnew):** workshops and platform admins need to find records across many cars, not one VIN at a time.
- **Pages:** workshop staff search their own organisation's records at `/workshop/records`. Platform admins search every organisation at `/admin/records`.
- **Filters:** part of a VIN, make, model, model year, service date, odometer range, category, work codes, mileage flag, originals or corrections, corrected or not, staff name, and organisation (admins only).
- **Sorting:** six columns, with fixed tie-breakers so a record never appears on two pages or is skipped.
- **Pagination:** page and page size, with the total number of matches.
- **Shareable searches:** the search lives in the URL, so a link, refresh or Back keeps it.
- **Demo:** sign in as workshop staff, filter by make and the mileage flag, sort by odometer, then change page and page size.

**Data export and import (AG-07, Agegnew):** workshops moving from paper or another system need to load their history in bulk, and both workshops and admins need their data out.
- **Export:** the current search (all pages) or only the selected rows, as CSV or JSON.
  - The CSV opens correctly in Excel, including Arabic text, and cells that could run as spreadsheet formulas are neutralised.
  - Every download is written to the audit log.
- **Import:** a CSV or JSON file goes through a check step first. The preview shows errors per row and field (bad VIN, date, work code, duplicates, records already entered) and which rows will get a mileage flag.
  - The import itself is all or nothing: one transaction locks the affected cars in a fixed order, so it can't deadlock with other imports.
  - Each row is saved through the same submission code as the single-record form, so flags are computed the same way.
- **Bulk operations:** importing up to 500 rows at once, and selecting rows on the search page to export them together.
- **Demo:** on `/workshop/records/import`, download the template, check a file that contains errors, fix it and import it. Then export the new records from `/workshop/records`.

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

For VE-02, AI assisted with drafting the Dockerfiles, Compose and Caddy configuration, the startup instructions, and the deployment checks. For VE-03, it assisted with the document API, storage integration, upload and preview UI, and verification. For VE-04, it assisted with wiring Redis, the authenticated WebSocket API, reconnect and refresh behaviour, and testing. For VE-05, it assisted with the notification API, recipient rules, inbox UI and tests. Record other AI use here as those changes are reviewed. Each contributor should be able to explain their implementation and checks during peer evaluation.
