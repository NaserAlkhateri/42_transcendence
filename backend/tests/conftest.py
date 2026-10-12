import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.main import create_app

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """TEST_DATABASE_URL if set, otherwise a throwaway Postgres 16 container (Docker must be running)."""
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        yield url
        return
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16-alpine", driver="psycopg") as postgres:
        yield postgres.get_connection_url()


@pytest.fixture(scope="session")
def alembic_cfg(database_url: str) -> Config:
    config = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(BACKEND_DIR, "alembic"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    config.attributes["configure_logger"] = False
    return config


@pytest.fixture(scope="session")
def engine(database_url: str, alembic_cfg: Config) -> Iterator[Engine]:
    command.upgrade(alembic_cfg, "head")
    engine = create_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    """A session inside an outer transaction that is rolled back after each test."""
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
