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
| POST | `/api/v1/auth/signup` | Create a consumer account and sign in |
| POST | `/api/v1/auth/login` | Sign in |
| POST | `/api/v1/auth/logout` | Revoke the current session |
| GET / PATCH | `/api/v1/me` | Read / update own profile |
| POST | `/api/v1/me/password` | Change password (signs out other devices) |

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
| `falcon.admin@sijil.demo` / `falcon.staff@sijil.demo` | Falcon Bay Auto Care (approved workshop) admin / staff |
| `oasis.admin@sijil.demo` / `oasis.staff@sijil.demo` | Oasis Line Motors (approved dealership) admin / staff |
| `sanddune.admin@sijil.demo` | Sand Dune Garage (pending, cannot submit) admin |

Demo VINs: `JTDBR32E720123456` (clean history), `WDDGF4HB1CA654321` (flagged mileage drop), `KMHD841CBMU112233` (correction). `WVWZZZ1KZ6W000001` has no history (try "Watch").
