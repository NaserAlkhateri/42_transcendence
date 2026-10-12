# Sijil - Architecture and Tech Stack

Status: starter specification for a three-week 42 ft_transcendence v21.2 project.

## Architecture principles
- One deployable FastAPI backend (modular monolith), not microservices.
- All public browser and partner API traffic uses HTTPS through Caddy.
- PostgreSQL owns relational data; MinIO owns private uploads; Redis supports background jobs.
- Service history is append-only. Corrections are new linked events, never edits to the original.
- Live updates (notifications, new records on an open timeline) reach every connected user over WebSocket (wss through Caddy).
- Use demo vehicle data only. Do not imply official UAE, insurer, or government verification.

## Stack
| Layer | Technology | Purpose |
| --- | --- | --- |
| Web UI | React + Vite + TypeScript | Consumer, workshop, and admin interfaces |
| Styling | Tailwind CSS | Responsive UI and Arabic RTL layout |
| Backend | Python + FastAPI | REST APIs, business rules, authorization |
| ORM / migrations | SQLAlchemy 2 + Alembic | PostgreSQL models and schema migrations |
| Main database | PostgreSQL | Users, entities, VINs, history, audit and watchlists |
| Object storage | MinIO | Private photos and supporting documents |
| Jobs | Celery + Redis | Notifications, import processing, optional PDF jobs |
| Real-time | FastAPI WebSockets + Redis pub/sub | Live notifications and timeline updates across connected users |
| Edge / TLS | Caddy | HTTPS and routing to frontend/backend |
| Infrastructure | Docker Compose | Single-command deployment |
| Observability | Prometheus + Grafana | Metrics, dashboards, alerts |
| Testing | pytest + Playwright | Backend, concurrency and end-to-end tests |

## Service layout
```
Browser / approved API partner
             |
          HTTPS
             |
           Caddy
         /       \
   React UI     FastAPI API
                   |  |  \
            PostgreSQL MinIO Redis -- Celery worker
                   |
             Prometheus <- app/exporter metrics
                   |
                Grafana
```
- Caddy serves the React build and routes `/api/*` (including the `/api/v1/ws` WebSocket, upgraded to wss) to FastAPI.
- PostgreSQL, Redis, MinIO, Celery and metrics endpoints are internal to the Compose network; avoid publishing them directly.
- Protect Grafana with authentication and limit access. Configure alerting rules, exporters, dashboards and metrics retention to satisfy the monitoring module.
- Caddy uses a trusted public certificate in hosted environments or a locally trusted certificate for demos.

## Core data model
- `users`: email, password hash, status, account details; **never** include ownership in public vehicle reports.
- `sessions`: authenticated sessions and expiration/revocation.
- `organizations`: dealership/workshop identity, registration, pending/approved/rejected status.
- `organization_members`: user, organization, role (entity_admin/entity_staff), membership status.
- `vehicles`: normalized unique VIN; metadata optional for demo data.
- `service_records`: vehicle, organization, staff, category, predefined work codes, odometer, dates, flags, `corrects_record_id`, created_at. Append-only. `organization_id`/`staff_id` are nullable (`ON DELETE SET NULL`) and the record stores a snapshot of the organization and staff names, so deleting an organization or user never rewrites history (the one deliberate duplicated field).
- `attachments`: service record, object key, file type/size, access scope and deletion/audit status.
- `watchlists`: consumer, vehicle, notifications enabled.
- `notifications`: recipient, event type, payload, read status, created_at.
- `api_keys` / `partner_watchlists`: hashed partner keys, scopes, owner, revocation and rate-limit identity.
- `audit_events`: actor, operation, target, timestamp and relevant change metadata.

Add proper foreign keys, unique constraints, indexes (VIN, records, organization, watchlist), and migrations. Prefer explicit relational constraints over duplicated fields.

## Critical domain logic
1. Validate VIN format and normalize case at both frontend and backend; backend is authoritative.
2. Only an **approved** organization with an **active** authorized staff membership can append service records.
3. On record submission, run a PostgreSQL transaction: find/create vehicle safely, lock its vehicle row (`SELECT ... FOR UPDATE`), compare mileage with the latest effective reading, then append the record and any mileage flag atomically.
4. **Lower mileage is accepted but flagged** (not rejected). Consumer history and PDF display the record and a clear warning. Flagged entries are not silently hidden from history.
5. Corrections append a new event referencing the original; reports display both original and correction. Do not enable UPDATE/DELETE on service history through the app (enforce DB immutability where practical).
6. Organizations, users and files can be **truly deleted** (required by the Organization system, Advanced permissions and File upload modules). Deleting an organization removes it with its memberships, staff access and API keys; deleting a user removes the account and sessions. Their service records stay, showing the stored name snapshot with the reference set to NULL. Every deletion writes an audit event.
7. Approval restricts who can submit records, but does **not** guarantee every submitted claim is true; label demo reports accordingly.

## Security and privacy
- Email/password login only for MVP; use Argon2id hashes and secure, HttpOnly, SameSite cookies with CSRF protection for state-changing requests.
- Backend checks role **and organization scope** on every protected action. No user may grant permissions they do not have.
- Validate payloads on both ends (FastAPI/Pydantic; typed frontend forms). Rate-limit auth and partner endpoints.
- Keep `.env` untracked; commit an `.env.example` with dummy variable names only. Never commit secrets or real credentials.
- Consumer history and PDFs contain only vehicle facts, organization name, timestamps and visible flags. Invoices may contain personal data; **do not publish raw attachments to consumers**.
- MinIO objects remain private and are accessed via authorized backend routes or short-lived scoped links.
- No SMTP/email sending, email verification or email password reset in MVP. Staff onboarding uses admin-created accounts and one-time temporary credentials with forced password change.

## Developer / deployment contract
- API prefix: `/api/v1`; generate an OpenAPI specification from FastAPI. Agree on request and response schemas before building UI pages.
- Public partner API: `/api/partner/v1`, with at least five demonstrated endpoints using GET, POST, PUT and DELETE, secured API keys, scope limits, rate limiting and documentation. Never use history mutation endpoints for the required PUT/DELETE actions.
- WebSocket: `/api/v1/ws`, authenticated with the session cookie. The backend publishes events (e.g. `notification.created`, `record.added`) to Redis pub/sub and every API instance fans them out to the connected clients it serves. Clients reconnect automatically and refetch on reconnect.
- `docker compose up --build -d` must start the full stack; initialization/migration should run automatically or as part of this one command.
- Provide `/health` and metrics collection. Write a seed script with approved demo entities, staff, and vehicle records for evaluation.
- Suggested source layout: `backend/app/{api,auth,models,schemas,services,workers}`, `frontend/src/{components,pages,features}`, `infra/{caddy,prometheus,grafana}`.
- Coordinate interface changes using documented migrations and typed API contracts; review changes in pull requests.
