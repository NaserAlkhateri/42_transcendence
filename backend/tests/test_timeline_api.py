from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import Organization, RecordCategory, ServiceRecord
from tests.factories import make_org, make_record, make_user, make_vehicle

VIN = "JTDBR32E720123456"
URL = f"/api/v1/vehicles/{VIN}/timeline"
SAFE_FIELDS = {
    "id", "service_date", "created_at", "category", "work_codes", "odometer_km",
    "organization_name", "is_mileage_flagged", "corrects_record_id", "correction_reason",
}


@pytest.fixture
def history(db: Session) -> dict[str, ServiceRecord]:
    org = make_org(db, name="Falcon Bay Auto Care")
    staff = make_user(db, full_name="Omar Technician")
    vehicle = make_vehicle(db, VIN)
    return {
        "first": make_record(db, vehicle, org, staff, odometer_km=10_000, service_date=date(2026, 1, 10)),
        "repair": make_record(
            db, vehicle, org, staff, odometer_km=25_000, service_date=date(2026, 3, 5),
            category=RecordCategory.REPAIR, notes="Customer Ahmed, +971 50 000 0000",
        ),
        "flagged": make_record(db, vehicle, org, staff, odometer_km=20_000, service_date=date(2026, 5, 20), flagged=True),
    }


def odometers(response) -> list[int]:
    return [record["odometer_km"] for record in response.json()["records"]]


def test_timeline_returns_records_newest_first(client: TestClient, history) -> None:
    response = client.get(URL)
    assert response.status_code == 200
    body = response.json()
    assert body["vin"] == VIN
    assert body["vehicle"] == {"vin": VIN, "make": "Toyota", "model": "Corolla", "model_year": 2019}
    assert odometers(response) == [20_000, 25_000, 10_000]
    assert body["records"][0]["is_mileage_flagged"] is True


def test_timeline_oldest_first(client: TestClient, history) -> None:
    assert odometers(client.get(URL, params={"order": "asc"})) == [10_000, 25_000, 20_000]


def test_timeline_normalizes_vin_in_path(client: TestClient, history) -> None:
    response = client.get("/api/v1/vehicles/jtd-br32e720123456/timeline")
    assert response.status_code == 200
    assert response.json()["vin"] == VIN
    assert len(response.json()["records"]) == 3


def test_timeline_filters_by_category_flag_and_dates(client: TestClient, history) -> None:
    assert odometers(client.get(URL, params={"category": "repair"})) == [25_000]
    assert odometers(client.get(URL, params={"flagged": "true"})) == [20_000]
    assert odometers(client.get(URL, params={"flagged": "false"})) == [25_000, 10_000]
    assert odometers(client.get(URL, params={"from": "2026-02-01", "to": "2026-04-30"})) == [25_000]


def test_timeline_is_consumer_safe(client: TestClient, history) -> None:
    response = client.get(URL)
    for record in response.json()["records"]:
        assert set(record) == SAFE_FIELDS
    assert "Ahmed" not in response.text
    assert "Omar Technician" not in response.text


def test_timeline_keeps_history_after_organization_is_deleted(client: TestClient, db: Session, history) -> None:
    db.execute(delete(Organization).where(Organization.id == history["first"].organization_id))
    db.expire_all()
    response = client.get(URL)
    assert response.status_code == 200
    assert [r["organization_name"] for r in response.json()["records"]] == ["Falcon Bay Auto Care"] * 3


def test_unknown_but_valid_vin_returns_empty_timeline(client: TestClient) -> None:
    response = client.get("/api/v1/vehicles/WVWZZZ1KZ6W000001/timeline")
    assert response.status_code == 200
    assert response.json() == {"vin": "WVWZZZ1KZ6W000001", "vehicle": None, "records": []}


def test_invalid_vin_returns_error(client: TestClient) -> None:
    response = client.get("/api/v1/vehicles/NOT-A-VIN/timeline")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_vin"


def test_reversed_date_range_is_rejected(client: TestClient, history) -> None:
    response = client.get(URL, params={"from": "2026-05-01", "to": "2026-01-01"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_date_range"


def test_bad_query_value_uses_error_format(client: TestClient, history) -> None:
    response = client.get(URL, params={"category": "oil"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["details"][0]["loc"] == ["query", "category"]
