# Sijil backend

FastAPI + SQLAlchemy 2 + Alembic on PostgreSQL. Design: `doc/ARCHITECTURE.md`.

## Run locally

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/) and a PostgreSQL 16 database.

```bash
cd backend
uv sync
export DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/sijil
uv run uvicorn app.main:app --reload
```

API docs: http://localhost:8000/api/v1/docs · health: http://localhost:8000/health

## Tests

Docker must be running: the suite starts a throwaway Postgres 16 container. To use an existing empty database instead, set `TEST_DATABASE_URL`.

```bash
cd backend
uv run pytest
```
