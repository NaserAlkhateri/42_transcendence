from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MemberRole, MemberStatus, Organization, OrganizationStatus, ServiceRecord, UserRole, Vehicle
from app.seed import VEHICLES
from app.services import events
from tests.auth_helpers import add_member, add_user, csrf, login
from tests.factories import make_org, make_record, make_vehicle

VIN = "JN8AY2NY4K9012345"


def records_url(org: Organization) -> str:
    return f"/api/v1/organizations/{org.id}/records"


def body(**overrides) -> dict:
    return {
        "vin": VIN, "category": "maintenance", "work_codes": ["OIL_CHANGE", "AIR_FILTER"],
        "odometer_km": 30_000, "service_date": "2026-03-01", **overrides,
    }


@pytest.fixture
def workshop(db: Session) -> Organization:
    return make_org(db, name="Falcon Bay Auto Care")


@pytest.fixture
def staff_client(client: TestClient, db: Session, workshop: Organization) -> TestClient:
    """`client` signed in as active entity staff of the approved `workshop`."""
    user = add_user(db, "arjun@example.ae", full_name="Arjun Nair")
    add_member(db, workshop, user, MemberRole.ENTITY_STAFF)
    login(client, user.email)
    return client


# --- work codes ---------------------------------------------------------------------------------------------


def test_work_code_list_is_public_with_english_and_arabic_labels(client: TestClient) -> None:
    codes = {item["code"]: item for item in client.get("/api/v1/work-codes").json()}
    assert codes["AC_SERVICE"]["label"] == "A/C service"
    assert codes["AC_SERVICE"]["label_ar"]
    assert codes["BATTERY_REPLACE"]["label"] == "Battery replacement"


def test_every_seeded_work_code_is_a_predefined_one(client: TestClient) -> None:
    predefined = {item["code"] for item in client.get("/api/v1/work-codes").json()}
    seeded = {code for vehicle in VEHICLES for record in vehicle.records for code in record.work_codes}
    assert seeded <= predefined


# --- submitting --------------------------------------------------------------------------------------------


def test_staff_record_appears_on_the_public_timeline_without_private_fields(
    staff_client: TestClient, workshop: Organization, db: Session
) -> None:
    response = staff_client.post(
        records_url(workshop), json=body(vin="jn8ay2ny4k9-012345", notes="Customer waited"), headers=csrf(staff_client)
    )

    assert response.status_code == 201
    created = response.json()
    assert created["vin"] == VIN
    assert created["staff_name"] == "Arjun Nair"
    assert created["notes"] == "Customer waited"
    assert created["is_mileage_flagged"] is False
    assert db.scalar(select(Vehicle).where(Vehicle.vin == VIN)) is not None  # first record creates the vehicle

    timeline = staff_client.get(f"/api/v1/vehicles/{VIN}/timeline").json()
    [record] = timeline["records"]
    assert record["organization_name"] == "Falcon Bay Auto Care"
    assert record["work_codes"] == ["OIL_CHANGE", "AIR_FILTER"]
    assert "notes" not in record and "staff_name" not in record


def test_lower_reading_is_accepted_and_flagged(staff_client: TestClient, workshop: Organization, db: Session) -> None:
    staff_client.post(records_url(workshop), json=body(odometer_km=50_000, service_date="2026-01-10"), headers=csrf(staff_client))

    response = staff_client.post(
        records_url(workshop), json=body(odometer_km=40_000, service_date="2026-02-10"), headers=csrf(staff_client)
    )

    assert response.status_code == 201
    assert response.json()["is_mileage_flagged"] is True
    flags = [r["is_mileage_flagged"] for r in staff_client.get(f"/api/v1/vehicles/{VIN}/timeline").json()["records"]]
    assert flags == [True, False]


def test_entity_admin_can_submit(client: TestClient, db: Session, workshop: Organization) -> None:
    admin = add_user(db, "khalid@example.ae", full_name="Khalid Al Mansoori")
    add_member(db, workshop, admin, MemberRole.ENTITY_ADMIN)
    login(client, admin.email)
    assert client.post(records_url(workshop), json=body(), headers=csrf(client)).status_code == 201


@pytest.mark.parametrize("org_status", [OrganizationStatus.PENDING, OrganizationStatus.REJECTED])
def test_organization_that_is_not_approved_cannot_submit(client: TestClient, db: Session, org_status) -> None:
    org = make_org(db, name="Sand Dune Garage", status=org_status)
    user = add_user(db, "omar@example.ae")
    add_member(db, org, user, MemberRole.ENTITY_ADMIN)
    login(client, user.email)

    response = client.post(records_url(org), json=body(), headers=csrf(client))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "organization_not_approved"


def test_staff_cannot_submit_for_another_organization(staff_client: TestClient, db: Session) -> None:
    other = make_org(db, name="Oasis Line Motors")
    assert staff_client.post(records_url(other), json=body(), headers=csrf(staff_client)).status_code == 403


@pytest.mark.parametrize("role", [UserRole.CONSUMER, UserRole.PLATFORM_ADMIN])
def test_consumers_and_platform_admins_cannot_write_history(client: TestClient, db: Session, workshop, role) -> None:
    user = add_user(db, "someone@example.ae", role=role)
    login(client, user.email)
    assert client.post(records_url(workshop), json=body(), headers=csrf(client)).status_code == 403


def test_inactive_membership_cannot_submit(client: TestClient, db: Session, workshop: Organization) -> None:
    user = add_user(db, "former@example.ae")
    add_member(db, workshop, user, MemberRole.ENTITY_STAFF).status = MemberStatus.INACTIVE
    db.flush()
    login(client, user.email)
    assert client.post(records_url(workshop), json=body(), headers=csrf(client)).status_code == 403


def test_submitting_requires_sign_in_and_csrf(staff_client: TestClient, workshop: Organization) -> None:
    assert staff_client.post(records_url(workshop), json=body()).status_code == 403  # no CSRF header
    staff_client.cookies.clear()
    assert staff_client.post(records_url(workshop), json=body(), headers=csrf(staff_client)).status_code == 401


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"vin": "NOT-A-VIN"}, "invalid_vin"),
        ({"work_codes": []}, "validation_error"),
        ({"work_codes": ["OIL_CHANGE", "OIL_CHANGE"]}, "validation_error"),
        ({"work_codes": ["TEST_DRIVE"]}, "validation_error"),
        ({"odometer_km": -1}, "validation_error"),
        ({"odometer_km": 2_000_001}, "validation_error"),
        ({"category": "inspection"}, "validation_error"),
        ({"service_date": (date.today() + timedelta(days=2)).isoformat()}, "validation_error"),
    ],
)
def test_invalid_submissions_are_rejected(staff_client: TestClient, workshop, db: Session, overrides, code) -> None:
    response = staff_client.post(records_url(workshop), json=body(**overrides), headers=csrf(staff_client))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == code
    assert db.scalar(select(ServiceRecord)) is None


def test_record_added_is_published_once_the_record_is_saved(staff_client: TestClient, workshop: Organization) -> None:
    received: list[tuple[str, dict]] = []
    unsubscribe = events.subscribe(lambda event_type, payload: received.append((event_type, payload)))
    try:
        created = staff_client.post(records_url(workshop), json=body(), headers=csrf(staff_client)).json()
    finally:
        unsubscribe()

    assert received == [("record.added", {
        "vin": VIN, "record_id": created["id"], "service_date": "2026-03-01",
        "is_mileage_flagged": False, "corrects_record_id": None,
    })]


def test_rejected_submission_publishes_nothing(staff_client: TestClient, workshop: Organization) -> None:
    received: list[str] = []
    unsubscribe = events.subscribe(lambda event_type, payload: received.append(event_type))
    try:
        staff_client.post(records_url(workshop), json=body(work_codes=[]), headers=csrf(staff_client))
    finally:
        unsubscribe()
    assert received == []


def test_flag_ignores_a_corrected_original(staff_client: TestClient, workshop: Organization, db: Session) -> None:
    # The original 54,000 was a typo corrected to 45,100: a new 50,000 reading fits the effective history.
    staff = add_user(db, "seed.staff@example.ae")
    vehicle = make_vehicle(db, VIN)
    original = make_record(db, vehicle, workshop, staff, odometer_km=54_000, service_date=date(2025, 11, 5))
    make_record(db, vehicle, workshop, staff, odometer_km=45_100, service_date=date(2025, 11, 5), corrects=original)

    response = staff_client.post(
        records_url(workshop), json=body(odometer_km=50_000, service_date="2026-01-20"), headers=csrf(staff_client)
    )

    assert response.json()["is_mileage_flagged"] is False
