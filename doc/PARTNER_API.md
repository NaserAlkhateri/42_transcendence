# Sijil Partner API

Read vehicle service histories from Sijil and keep a watchlist of VINs, for example to check a car before you insure or list it. Sijil is a **demo**: histories come from workshops and dealerships approved by a Sijil admin. They are not official UAE records.

- **Base URL:** `https://<your Sijil host>/api/partner/v1`
- **Interactive reference:** `https://<your Sijil host>/api/partner/v1/docs` (OpenAPI at `/api/partner/v1/openapi.json`)
- **HTTPS only.** Plain HTTP is not served.

## Getting a key

A Sijil platform admin issues keys from **Admin → API keys**. The key looks like `sjl_1a2b3c4d_…` and is shown **once**, so store it in your secret store. If it leaks, ask for it to be revoked; a revoked key stops working on the next call.

Send it on every request:

```bash
curl -H "X-API-Key: $SIJIL_KEY" https://sijil.example/api/partner/v1/vehicles/JTMHX01J5M4012345
```

Keys are **read-only for vehicle history**. No partner call can create, change or delete a service record. `POST`, `PUT` and `DELETE` act only on your own watchlist.

## Endpoints

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/vehicles/{vin}` | Summary: make, model, year, record counts, latest service date and odometer reading |
| GET | `/vehicles/{vin}/history` | Every service record, newest first |
| GET | `/watches` | Your watched VINs and how many records arrived since you last checked |
| POST | `/watches` | Watch a VIN, with an optional `label` such as your policy number |
| PUT | `/watches/{id}` | Replace a watch's `label`; `mark_checked: true` marks everything so far as seen |
| DELETE | `/watches/{id}` | Stop watching |

VINs are 17 characters. Case, spaces and dashes are ignored (`jtmhx01j5m4-012345` works).

### Vehicle summary

```bash
curl -H "X-API-Key: $SIJIL_KEY" https://sijil.example/api/partner/v1/vehicles/JN8AY2NY4K9012345
```

For the seeded demo Nissan Patrol, which has a flagged mileage drop:

```json
{
  "vin": "JN8AY2NY4K9012345",
  "make": "Nissan", "model": "Patrol", "model_year": 2019,
  "record_count": 3, "flagged_record_count": 1, "correction_count": 0,
  "latest_service_date": "2026-04-11", "latest_odometer_km": 88300,
  "last_record_added_at": "2026-10-15T21:18:24+04:00"
}
```

- `flagged_record_count` counts readings that don't fit the earlier history (for example, a lower odometer reading). These are kept and flagged, never hidden.
- A **correction** is a new record that replaces an earlier, mistaken one. The original stays in the history. `latest_odometer_km` uses the corrected value.
- An unknown VIN answers `404 vehicle_not_found`. You can still watch it.

### History

`GET /vehicles/{vin}/history` returns `{"vin": "...", "records": [...]}`. Each record has `id`, `service_date`, `created_at`, `category` (`maintenance` or `repair`), `work_codes`, `odometer_km`, `organization_name`, `is_mileage_flagged`, `corrects_record_id` and `correction_reason`.

There is no owner, staff or customer data in any partner response.

### Watching VINs

```bash
# Watch a VIN
curl -X POST -H "X-API-Key: $SIJIL_KEY" -H "Content-Type: application/json" \
  -d '{"vin": "JTMHX01J5M4012345", "label": "Policy 2026-00417"}' \
  https://sijil.example/api/partner/v1/watches

# Poll: which VINs have new records?
curl -H "X-API-Key: $SIJIL_KEY" https://sijil.example/api/partner/v1/watches

# After processing one, mark it as checked (and keep or change its label)
curl -X PUT -H "X-API-Key: $SIJIL_KEY" -H "Content-Type: application/json" \
  -d '{"label": "Policy 2026-00417", "mark_checked": true}' \
  https://sijil.example/api/partner/v1/watches/<id>

# Stop watching
curl -X DELETE -H "X-API-Key: $SIJIL_KEY" https://sijil.example/api/partner/v1/watches/<id>
```

Each watch in `GET /watches` has `new_record_count`: the records added since `last_checked_at`, or since you created the watch. `PUT` replaces the label, so send the label again to keep it. One key can watch up to 500 VINs.

## Rate limits

Every response carries:

| Header | Meaning |
| --- | --- |
| `X-RateLimit-Limit` | Requests allowed per window (default 60 per minute, per key) |
| `X-RateLimit-Remaining` | Requests left in the current window |
| `X-RateLimit-Reset` | Seconds until the window resets |

Over the limit you get `429 rate_limited` with `Retry-After` (seconds). Wait that long before retrying. Failed authentication is throttled per client address too.

## Errors

Every error has the same shape:

```json
{"error": {"code": "invalid_api_key", "message": "This API key is not valid."}}
```

| Status | Codes |
| --- | --- |
| 401 | `missing_api_key`, `invalid_api_key` (unknown or revoked) |
| 403 | `insufficient_scope` |
| 404 | `vehicle_not_found`, `watch_not_found` |
| 409 | `already_watching`, `watch_limit_reached` |
| 422 | `invalid_vin`, `validation_error` (with `details`) |
| 429 | `rate_limited` |

## For the Sijil team

- Keys are stored as a SHA-256 hash of the secret part; the 8-character prefix is stored in clear to look keys up and show them in the admin list.
- Rate-limit counters are in process memory, which is correct for the single API container we run. Move them to Redis if the API is ever scaled out.
- Demo key: set `SEED_PARTNER_API_KEY` in `backend/.env` (never committed) and run the seed. It creates "Demo Insurer (fictional)" with that key.
- Admin endpoints: `GET /api/v1/admin/api-keys`, `POST /api/v1/admin/api-keys` (`partner_name`) and `POST /api/v1/admin/api-keys/{id}/revoke`. Each one writes an audit event.
