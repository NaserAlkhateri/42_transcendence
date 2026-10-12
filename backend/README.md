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
