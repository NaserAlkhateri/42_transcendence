from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.db.session import get_db
from app.main import create_app


def test_health_reports_ok_when_database_answers(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_reports_unreachable_database() -> None:
    app = create_app()
    dead = create_engine("postgresql+psycopg://sijil:sijil@127.0.0.1:1/sijil", connect_args={"connect_timeout": 1})

    def broken_db() -> Iterator[Session]:
        with Session(dead) as session:
            yield session

    app.dependency_overrides[get_db] = broken_db
    with TestClient(app) as test_client:
        response = test_client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "error"}


def test_unknown_route_uses_error_format(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "not_found", "message": "Not Found"}}


def test_api_error_uses_error_format() -> None:
    app = create_app()

    @app.get("/boom")
    def boom() -> None:
        raise ApiError(409, "conflict_demo", "Demo conflict")

    response = TestClient(app).get("/boom")
    assert response.status_code == 409
    assert response.json() == {"error": {"code": "conflict_demo", "message": "Demo conflict"}}


def test_openapi_is_served_under_api_prefix(client: TestClient) -> None:
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Sijil API"
