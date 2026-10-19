# Sijil backend

FastAPI + SQLAlchemy 2 + Alembic on PostgreSQL. Design: `doc/ARCHITECTURE.md`.

## Run locally

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/) and a PostgreSQL 16 database.

```bash
cd backend
uv sync
cp .env.example .env   # then set DATABASE_URL (and SEED_DEMO_PASSWORD for the seed)
uv run uvicorn app.main:app --reload
```

API docs: http://localhost:8000/api/v1/docs · health: http://localhost:8000/health

## Authentication (NA-01)

- Email/password with Argon2id hashes. Signup always creates a `consumer`.
- Server-side sessions: the `sijil_session` cookie (HttpOnly, Secure, SameSite=Lax) holds a random token; only its SHA-256 hash is stored in `sessions`. Logout and password changes revoke sessions.
- CSRF: every POST/PATCH/PUT/DELETE under `/api/v1` must send `X-CSRF-Token` equal to the `sijil_csrf` cookie (get one from `GET /api/v1/auth/csrf`).
- Protected routes use `CurrentUser` from `app.auth.dependencies`; it also blocks accounts with a pending temporary password.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/auth/csrf` | Issue the CSRF cookie |
| GET | `/api/v1/auth/session` | Current user or `null`; always 200, so the SPA's start-up probe logs no error for guests |
| POST | `/api/v1/auth/signup` | Create a consumer account and sign in |
| POST | `/api/v1/auth/login` | Sign in |
| POST | `/api/v1/auth/logout` | Revoke the current session |
| GET / PATCH | `/api/v1/me` | Read / update own profile |
| POST | `/api/v1/me/password` | Change password (signs out other devices) |

Security measures (throttling, session rotation, headers, what Caddy must add) are listed in [`doc/SECURITY.md`](../doc/SECURITY.md).

- `POST /api/v1/admin/users/{id}/reset-password` (platform admin): gives a locked-out user a one-time temporary password and ends their sessions.

## Roles and permissions (NA-02)

Roles: `users.role` is `consumer` or `platform_admin`; `organization_members.role` is `entity_admin` or `entity_staff` per organization. `effective_role` (on `/me` and admin responses) is the highest of these and drives the UI's role-based views. Entity roles only count in an **approved** organization, so a pending registrant still shows as `consumer` (no record tools).

Guards in `app.auth.permissions`, used on every protected route:
- `PlatformAdmin`: dependency that only lets platform admins through.
- `require_org_role(db, user, organization_id, {roles})`: the user must hold one of the roles in an **active** membership of *that* organization (platform admins pass).

| Method | Path | Purpose (platform admin only) |
| --- | --- | --- |
| GET | `/api/v1/admin/users?q=&role=&status=&page=&page_size=` | Search, filter and paginate users |
| GET | `/api/v1/admin/users/{id}` | One user with memberships |
| PATCH | `/api/v1/admin/users/{id}` | Edit name, email, platform role, status (disabling revokes sessions) |
| DELETE | `/api/v1/admin/users/{id}` | Really delete the account; service records keep the staff-name snapshot |
| PATCH | `/api/v1/admin/users/{id}/memberships/{membership_id}` | Switch entity_admin / entity_staff |

Admins cannot demote, disable or delete themselves, so at least one admin always remains. Every edit and delete writes an `audit_events` row.

## Organizations (NA-03)

A workshop or dealership registers and starts **pending**. A platform admin approves or rejects it, and a rejection always has a reason (a database check). Only approved organizations can add records (AG-03).

| Method | Path | Who | Purpose |
| --- | --- | --- | --- |
| POST | `/api/v1/organizations` | Signed-in non-admin | Register: `name`, `kind`, `registration_number` (trade licence, stored upper-case, unique), `emirate`. The applicant becomes its entity admin. One pending registration per user. |
| GET | `/api/v1/organizations/{id}` | Members | Details, status and rejection reason |
| PATCH | `/api/v1/organizations/{id}` | Its entity admins | Edit details. The licence number is locked once approved (409 `registration_locked`). |
| POST | `/api/v1/organizations/{id}/resubmit` | Its entity admins | Rejected -> pending again |
| GET | `/api/v1/admin/organizations?q=&status=&kind=&emirate=&page=&page_size=` | Platform admin | Pending first; member and record counts |
| GET | `/api/v1/admin/organizations/{id}` | Platform admin | Details with members |
| POST | `/api/v1/admin/organizations` | Platform admin | Create; approved at once, no members |
| PATCH | `/api/v1/admin/organizations/{id}` | Platform admin | Edit any field, including the licence number |
| POST | `/api/v1/admin/organizations/{id}/approve` | Platform admin | Pending or rejected -> approved |
| POST | `/api/v1/admin/organizations/{id}/reject` | Platform admin | `reason` (5-500 chars). Also withdraws an approval: records stop, history stays. |
| DELETE | `/api/v1/admin/organizations/{id}` | Platform admin | Really delete it and its memberships. Member accounts stay; service records keep the organization-name snapshot. |

- `emirate` must be one of the seven emirates, in official English spelling (`doc/UAE_MARKET.md`).
- Approve and reject publish `organization.reviewed` (`organization_id`, `name`, `status`, `rejection_reason`) through `app/services/events.py`, for notifications (BU-05).
- Every registration, edit, review, resubmission and deletion writes an `audit_events` row.
- Licence documents (BU-03) are not shown on the review screen yet.

## Organization members and staff accounts (NA-04)

An organization's active entity admins manage its members. Platform admins can do the same for any organization, for example to add the first admin to one they created.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/organizations/{id}/members` | List members |
| POST | `/api/v1/organizations/{id}/members` | Add an existing account: `email`, `role` |
| POST | `/api/v1/organizations/{id}/members/staff-accounts` | Create an account: `email`, `full_name`, `role`. Returns the member and a `temporary_password`, shown once. |
| PATCH | `/api/v1/organizations/{id}/members/{membership_id}` | Change `role` (entity_admin / entity_staff) or `status` (active / inactive) |
| DELETE | `/api/v1/organizations/{id}/members/{membership_id}` | Remove from the organization. The account stays. |

- A staff account starts with `must_change_password`, so it can do nothing but change its password (NA-01) until it does.
- Only **approved** organizations can add members or create accounts (403 `organization_not_approved`), so an unvetted registration can't mint accounts. Platform admins are exempt.
- An organization always keeps at least one active entity admin (409 `last_entity_admin`). This also applies to the admin endpoint `PATCH /admin/users/{id}/memberships/{membership_id}`. Changes lock the organization row, so two admins can't demote each other at the same moment.
- Only entity roles can be granted here. Platform-admin accounts can't join an organization (409 `cannot_add_platform_admin`).
- Entity admins can't reset a member's password: a member may be a personal account they don't own.
- Every change writes an `audit_events` row (never the temporary password) and publishes `membership.added`, `membership.updated` or `membership.removed` (organization id and name, user id, role, status) for notifications (BU-05).

## Partner API (NA-05)

Partners call `/api/partner/v1` with an admin-issued key in `X-API-Key`. The guide for partners is [`doc/PARTNER_API.md`](../doc/PARTNER_API.md), and the interactive reference is at `/api/partner/v1/docs`.

- Six endpoints: `GET /vehicles/{vin}`, `GET /vehicles/{vin}/history`, `GET /watches`, `POST /watches`, `PUT /watches/{id}`, `DELETE /watches/{id}`. None of them can change service history.
- Keys look like `sjl_<8-hex prefix>_<secret>`. The prefix is stored in clear for lookup and display; the secret only as a SHA-256 hash. A missing, unknown or revoked key answers 401.
- Rate limit per key (`PARTNER_RATE_LIMIT` requests per `PARTNER_RATE_WINDOW_SECONDS`, default 60 per 60 s). Responses carry `X-RateLimit-*`; over the limit gives 429 with `Retry-After`. Failed authentication is limited per client IP. The counters are in process memory (`app/services/rate_limit.py`), so move them to Redis if the API is ever scaled out.
- The partner API is outside the cookie/CSRF router: a browser session does not open it.
- Admin: `GET/POST /api/v1/admin/api-keys` and `POST /api/v1/admin/api-keys/{id}/revoke` (platform admin). Issued keys are shown once, and every issue or revoke is audited.
- Demo key: set `SEED_PARTNER_API_KEY` in `.env` and run the seed. It creates "Demo Insurer (fictional)" with that key.

## Service records (AG-03)

Active `entity_staff` and `entity_admin` members of an **approved** organization append records. Consumers and platform admins cannot write history. Records are permanent: a mistake is fixed with a correction (AG-04).

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/work-codes` | Predefined work codes with English and Arabic labels (public) |
| POST | `/api/v1/organizations/{id}/records` | Append a record: `vin`, `service_date`, `category`, `work_codes`, `odometer_km`, optional private `notes` |

- One transaction per submission. It creates the vehicle on its first record and locks the vehicle row (`SELECT ... FOR UPDATE`). It then compares the reading with the effective history and inserts the record with its flag. Concurrent submissions for one VIN are serialized, so each flag is computed against everything committed before it (`tests/test_records_concurrency.py`).
- **Mileage flag:** a reading is accepted but flagged when it does not fit the effective history. That means it is lower than the highest reading dated on or before it, or higher than a reading dated after it (a back-dated entry). Records replaced by a correction don't count.
- **Event:** after commit the API publishes `record.added` through `app/services/events.py`, with a consumer-safe payload (VIN, record id, date, flag, corrected id). The WebSocket fan-out (BU-04) subscribes there.
- Errors: 403 `organization_not_approved` / `forbidden`, 422 `invalid_vin` / `validation_error` (unknown or repeated work code, future date, odometer outside 0-2,000,000 km).

## Corrections (AG-04)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/organizations/{id}/records?vin=` | The organization's own records for a VIN, newest first, with private notes and `corrected_by_id` |
| POST | `/api/v1/organizations/{id}/records/{record_id}/corrections` | Append a correction: `correction_reason` (`odometer`, `service_date`, `work_done`, `category`, `other`) plus the corrected record fields |

- Only the organization that created a record can correct it (403 `not_your_record`). The original is never changed, and both appear together on the timeline and in the PDF.
- A record is corrected **once** (a unique database index). To fix a correction, correct the correction. A second attempt gets 409 `already_corrected`.
- The correction's flag is computed against the history it joins, without the original. Later readings are compared with the corrected value, not the mistake.
- The public timeline shows `correction_reason` (a fixed list, so no free text or personal data reaches consumers).

## Record search (AG-06)

| Method | Path | Who | Scope |
| --- | --- | --- | --- |
| GET | `/api/v1/organizations/{id}/records/search` | Active entity admins and staff of that organization; platform admins | That organization's records only |
| GET | `/api/v1/admin/records` | Platform admins | Every organization, including records of deleted ones (by their name snapshot) |

Filters (all optional, combined with AND):

| Param | Matches |
| --- | --- |
| `vin` | Part of a VIN, up to 17 characters. Normalized like a full VIN (case, spaces, dashes, Arabic-Indic digits). |
| `make`, `model`, `staff` | Case-insensitive substring. `%`, `_` and `\` are matched literally. |
| `year_from`, `year_to` | Vehicle model year (1900-2100), inclusive |
| `date_from`, `date_to` | Service date (`YYYY-MM-DD`), inclusive |
| `odometer_min`, `odometer_max` | Reading in km (0-2,000,000, the same limit as a record), inclusive |
| `category` | `maintenance` or `repair` |
| `work_code` | Repeatable (`?work_code=OIL_CHANGE&work_code=BRAKE_PADS`); records with **any** of the codes. Blank values are ignored. |
| `flagged` | `true` / `false`: the mileage flag |
| `record_type` | `all` (default), `original` (not a correction) or `correction` |
| `corrected` | `true` / `false`: whether a later correction replaces the record |
| `organization_id`, `organization` | Admin route only: organization id, or a substring of the organization name |

- **Sorting:** `sort` = `service_date` (default), `created_at`, `odometer_km`, `vin`, `make` or `organization_name`; `order` = `desc` (default) or `asc`. Text sorts ignore case, and vehicles without a make come last. Ties are broken by newest `created_at` and then `id`, so pages never repeat or skip a row.
- **Paging:** `page` (1-100,000, default 1) and `page_size` (1-100, default 20). The response is `{items, total, page, page_size}`; `total` counts every match. A page past the end has empty `items` and the real `total`.
- **Items:** `id`, `vin`, `make`, `model`, `model_year`, `service_date`, `created_at`, `category`, `work_codes`, `odometer_km`, `organization_id` (null once the organization is deleted), `organization_name`, `staff_name`, `notes`, `is_mileage_flagged`, `corrects_record_id`, `correction_reason`, `corrected_by_id`. Staff names and notes are included because only members and admins can search.
- **Errors:** 401 `not_authenticated`, 403 `forbidden` (consumers, another organization's staff, non-admins on the admin route), 404 `organization_not_found`, and 422 `invalid_vin_query`, `invalid_year_range`, `invalid_date_range`, `invalid_odometer_range`, `unknown_work_code`, or `validation_error` (unknown `sort`/`order`/`record_type`/`category`, page or odometer bounds, malformed values, a NUL character in a text filter).
- **Queries:** two per request, one for the page and one `COUNT` over the same filters. Vehicle facts and `corrected_by_id` come from joins, so there is no per-row query. `app/services/record_search.py` holds the query builder (`build_search_query`) for AG-07's export, and `app/api/v1/record_search.py` the shared filter dependency.

## Import and export (AG-07)

| Method | Path | Who |
| --- | --- | --- |
| GET | `/api/v1/organizations/{id}/records/export` | Like the organization search: active entity admins and staff of that organization; platform admins |
| GET | `/api/v1/admin/records/export` | Platform admins (every organization) |
| POST | `/api/v1/organizations/{id}/records/import` | Active entity admins and staff of an **approved** organization. Platform admins cannot write history. CSRF header required. |

**Export** downloads what the search screen shows, every page of it, in the same order.

- **Params:** every AG-06 filter plus `sort`/`order` (no paging), `format` (required: `csv` or `json`) and `ids` (optional, repeatable, up to 100 record ids for "export selected"). `ids` only narrows the scope and filters. An id outside them is left out, so nobody can export another organization's record by id.
- **Limit:** 5,000 rows. More matches answer 422 `export_too_large` ("Narrow the filters…"). The file is never cut off.
- **Headers:** `Content-Type: text/csv; charset=utf-8` or `application/json`, `Content-Disposition: attachment; filename="sijil-records-YYYYMMDD-HHMM.csv"` (or `.json`, UTC time), `Cache-Control: no-store`.
- **CSV:** UTF-8 with a BOM (so Excel shows Arabic), CRLF line ends, a header row, then one row per record. The columns are `record_id`, `vin`, `make`, `model`, `model_year`, `service_date` (YYYY-MM-DD), `category`, `work_codes` (joined with `;`), `odometer_km`, `organization_name`, `staff_name`, `notes`, `is_mileage_flagged` (`true`/`false`), `corrects_record_id`, `correction_reason` and `created_at` (ISO 8601 UTC, `Z`). Standard CSV quoting keeps commas, quotes and line breaks in notes. **Formula guard:** a cell that starts with `=`, `+`, `-`, `@`, a tab or a carriage return gets a leading `'`, so a spreadsheet does not run it.
- **JSON:** `{exported_at, scope ("organization" or "platform"), organization_id (null for platform), filters (the applied filters, sort and ids), count, records}`. Records have the CSV fields, with `work_codes` as an array and numbers, booleans and nulls as JSON types. There is no formula guard in JSON.
- **Audit:** `records.exported` with `format`, `count` and `scope`. The target is the organization, or `platform`/`all`. No record contents.
- **Errors:** the search errors (401, 403 `forbidden`, 404 `organization_not_found`, the 422 filter codes), 422 `validation_error` (missing or unknown `format`, more than 100 or malformed `ids`), and 422 `export_too_large`.

**Import** checks a file (`dry_run=true`, the default) or imports it (`dry_run=false`).

- **The file is the raw request body** (no multipart), with `Content-Type: text/csv` or `application/json`. A charset parameter is ignored. The body must be UTF-8 (a BOM is fine), at most **512 KB** (524,288 bytes) and at most **500 records**. The size limit is applied while the body is read, so it also holds when `Content-Length` is missing or wrong.
- **CSV:** the first row names the columns. `vin`, `service_date`, `odometer_km`, `category` and `work_codes` are required; `notes` is optional. Column names ignore case and surrounding spaces, and spaces or dashes inside count as underscores. Other columns are ignored, with one warning, so an AG-07 export works as a template. Blank lines are skipped. The delimiter is a comma.
- **JSON:** an array of objects, or `{"records": [...]}` (the shape of an AG-07 JSON export). It uses the same field names. `work_codes` is an array or a `;`-separated string, and `odometer_km` a number or text. An item that is not an object is a row error.
- **Values:**
  - **VIN:** normalized like the form (case, spaces, dashes, Arabic-Indic digits).
  - **service_date:** `YYYY-MM-DD` or `DD/MM/YYYY`. Day first, never month first.
  - **odometer_km:** whole km, with optional thousands commas (`88,300`).
  - **category:** `maintenance` or `repair`, in any case.
  - **work_codes:** separated by `;`. Any case; blanks are ignored.
  - **notes:** optional. In CSV, a leading `'` before `=`, `+`, `-`, `@`, a tab or a carriage return is removed, which undoes the export's formula guard.

  Each row is then checked with `RecordSubmission`, the form's own schema: known and unique codes (at most 10), no future date, 0-2,000,000 km, notes up to 1,000 characters.
- **Row numbers:** in CSV, the data row number without the header, so row 1 is the line after the header. Blank lines still count, so row *n* is line *n* + 1 of the file and row *n* + 1 of the spreadsheet (a note with line breaks takes more file lines but stays one spreadsheet row). In JSON, the position in the list, starting at 1.
- **Duplicates:** `duplicate_in_file` means a later row has the same VIN, date and reading as an earlier one. `already_recorded` means the row equals a record of this organization on VIN, date, reading and category (corrected records included), which stops accidental double imports.
- **Dry run (200):** `{dry_run: true, format, total_rows, valid_rows, invalid_rows, flagged_rows, warnings: [str], rows: [{row, vin, service_date, odometer_km, category, work_codes, status ("ok" or "error"), errors: [{field (null for the whole row), code, message}], will_be_flagged}]}`.
  - A field with an error comes back as null (or `[]` for work codes).
  - `will_be_flagged` predicts the mileage flag against the stored history plus the earlier valid rows of the file.
  - The dry run reads only: no locks, no writes.
- **Import (201):** `{dry_run: false, imported, flagged, record_ids}`, with record ids in file order. It is all or nothing, in one transaction:
  1. It locks every vehicle in the file in VIN order, creating new ones. Imports that share vehicles then wait for each other instead of deadlocking (`tests/test_record_import_concurrency.py`).
  2. It checks the rows again under those locks.
  3. It appends them in file order through `submit_record`, so each flag is computed exactly as for a single submission.
  4. It commits, publishes `record.added` for each record, and audits `records.imported` with `count`, `flagged` and `format`.

  If any row has an error, the answer is 422 `import_invalid`, with the same report in `error.details`, and nothing is written.

| Row error `code` | Field | Meaning |
| --- | --- | --- |
| `required` | any required field | Missing or blank |
| `invalid_vin` | `vin` | Not a valid VIN |
| `invalid_date` / `future_date` | `service_date` | Not YYYY-MM-DD or DD/MM/YYYY, not a real date, or in the future |
| `invalid_number` / `out_of_range` | `odometer_km` | Not whole km, or outside 0-2,000,000 |
| `invalid_category` | `category` | Not maintenance or repair |
| `invalid_work_code` | `work_codes` | Unknown, repeated, or more than 10 |
| `too_long` | `notes` | Over 1,000 characters |
| `invalid_type` | any | JSON value of the wrong type |
| `invalid_row` | null | JSON item that is not an object |
| `duplicate_in_file` / `already_recorded` | null | See Duplicates |

| File error | Status |
| --- | --- |
| `unsupported_media_type` (not text/csv or application/json) | 415 |
| `payload_too_large` (over 512 KB) | 413 |
| `invalid_encoding` (not UTF-8, or contains NUL), `empty_file` (no records, also a header-only CSV), `invalid_csv` (broken quoting), `invalid_json` (not JSON, or not a list / `{"records": [...]}`), `missing_columns` (lists them), `duplicate_columns`, `too_many_rows` (over 500), `import_invalid` (`dry_run=false` only), `validation_error` (`dry_run` not a boolean) | 422 |
| `csrf_failed`, `forbidden`, `organization_not_approved` | 403 |
| `not_authenticated` | 401 |
| `organization_not_found` | 404 |

## PDF report (AG-05)

`GET /api/v1/vehicles/{vin}/report.pdf` (public, like the timeline) downloads `sijil-report-{VIN}.pdf`. A VIN without history gets 404 `no_history`.

- **Bilingual:** English on the left, Arabic on the right, for the title, vehicle facts and every record. Arabic is shaped with HarfBuzz (`uharfbuzz`) through `fpdf2`, in bundled Noto Sans / Noto Sans Arabic fonts (`app/reports/fonts`, SIL Open Font License), so it renders the same offline.
- **Contents:**
  - The full history, newest first, whatever filters the page has.
  - For each record: date, category, odometer, workshop, work done, mileage warnings, and each correction directly above the original it replaces, with its reason.
  - Vehicle facts and the latest effective reading.
  - A "not an official record" notice on every page.
- **Consumer-safe:** no staff names, private notes or attachments (`tests/test_report_pdf.py` checks this).
- The Arabic wording follows `doc/UAE_MARKET.md` and is reviewed by a native speaker during HA-03.

## Tests

Docker must be running: the suite starts a throwaway Postgres 16 container. To use an existing empty database instead, set `TEST_DATABASE_URL`.

```bash
cd backend
uv run pytest
```

## Database and demo data

```bash
cd backend
uv run alembic upgrade head
SEED_DEMO_PASSWORD=choose-a-demo-password uv run python -m app.seed
```

The seed is safe to run on every start. All data is fictional. Every demo account uses `SEED_DEMO_PASSWORD`:

| Account | Role |
| --- | --- |
| `admin@sijil.demo` | Platform admin |
| `consumer@sijil.demo` | Consumer |
| `falcon.admin@sijil.demo` / `falcon.staff@sijil.demo` | Falcon Bay Auto Care (approved workshop, Dubai) admin / staff |
| `oasis.admin@sijil.demo` / `oasis.staff@sijil.demo` | Oasis Line Motors (approved dealership, Abu Dhabi) admin / staff |
| `sanddune.admin@sijil.demo` | Sand Dune Garage (pending, Sharjah, cannot submit) admin |

Demo VINs (common UAE cars): `JTMHX01J5M4012345` 2021 Toyota Land Cruiser (clean history), `JN8AY2NY4K9012345` 2019 Nissan Patrol (flagged mileage drop), `JTNBK3EK6N3012345` 2022 Toyota Camry (correction). `MDHBN7AD0P0012345` (2023 Nissan Sunny) has no history (try "Watch").
