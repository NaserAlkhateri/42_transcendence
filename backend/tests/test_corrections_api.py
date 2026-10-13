import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import MemberRole, Organization, ServiceRecord, UserRole, Vehicle
from app.services import events
from tests.auth_helpers import add_member, add_user, csrf, login
from tests.factories import make_org, make_record, make_vehicle

VIN = "JTNBK3EK6N3012345"


def corrections_url(org: Organization, record: ServiceRecord | uuid.UUID) -> str:
    record_id = record.id if isinstance(record, ServiceRecord) else record
    return f"/api/v1/organizations/{org.id}/records/{record_id}/corrections"


def fix(**overrides) -> dict:
    return {
        "correction_reason": "odometer", "category": "maintenance", "work_codes": ["OIL_CHANGE"],
        "odometer_km": 55_000, "service_date": "2026-02-10", **overrides,
    }


@pytest.fixture
def workshop(db: Session) -> Organization:
    return make_org(db, name="Falcon Bay Auto Care")


@pytest.fixture
def staff_client(client: TestClient, db: Session, workshop: Organization) -> TestClient:
    user = add_user(db, "arjun@example.ae", full_name="Arjun Nair")
    add_member(db, workshop, user, MemberRole.ENTITY_STAFF)
    login(client, user.email)
    return client


@pytest.fixture
def history(db: Session, workshop: Organization) -> dict[str, ServiceRecord]:
    """50,000 in January, then a mistyped 500,000 in February (one zero too many)."""
    staff = add_user(db, "seed@example.ae", full_name="Seed Staff")
    vehicle = make_vehicle(db, VIN)
    return {
        "jan": make_record(db, vehicle, workshop, staff, odometer_km=50_000, service_date=date(2026, 1, 10)),
        "typo": make_record(db, vehicle, workshop, staff, odometer_km=500_000, service_date=date(2026, 2, 10)),
    }


def timeline(client: TestClient) -> list[dict]:
    return client.get(f"/api/v1/vehicles/{VIN}/timeline").json()["records"]


def test_correction_keeps_the_original_and_links_to_it(staff_client: TestClient, workshop, history) -> None:
    response = staff_client.post(corrections_url(workshop, history["typo"]), json=fix(), headers=csrf(staff_client))

    assert response.status_code == 201
    correction = response.json()
    assert correction["corrects_record_id"] == str(history["typo"].id)
    assert correction["correction_reason"] == "odometer"
    assert correction["vin"] == VIN
    by_id = {record["id"]: record for record in timeline(staff_client)}
    assert by_id[str(history["typo"].id)]["odometer_km"] == 500_000  # the original is still there, unchanged
    assert by_id[correction["id"]]["correction_reason"] == "odometer"


def test_corrected_reading_no_longer_counts_for_later_flags(staff_client: TestClient, workshop, history) -> None:
    staff_client.post(corrections_url(workshop, history["typo"]), json=fix(), headers=csrf(staff_client))

    later = staff_client.post(
        f"/api/v1/organizations/{workshop.id}/records",
        json={"vin": VIN, "category": "maintenance", "work_codes": ["OIL_CHANGE"], "odometer_km": 60_000, "service_date": "2026-03-10"},
        headers=csrf(staff_client),
    )

    assert later.json()["is_mileage_flagged"] is False  # compared with 55,000, not the mistyped 500,000


def test_a_correction_that_still_does_not_fit_is_flagged(staff_client: TestClient, workshop, history) -> None:
    response = staff_client.post(corrections_url(workshop, history["typo"]), json=fix(odometer_km=45_000), headers=csrf(staff_client))
    assert response.json()["is_mileage_flagged"] is True  # 45,000 after January's 50,000


def test_only_the_organization_that_created_the_record_can_correct_it(client: TestClient, db: Session, history) -> None:
    other = make_org(db, name="Oasis Line Motors")
    user = add_user(db, "joseph@example.ae")
    add_member(db, other, user, MemberRole.ENTITY_ADMIN)
    login(client, user.email)

    response = client.post(corrections_url(other, history["typo"]), json=fix(), headers=csrf(client))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_your_record"


def test_a_record_is_corrected_once_then_the_correction_is_corrected(staff_client: TestClient, workshop, history) -> None:
    first = staff_client.post(corrections_url(workshop, history["typo"]), json=fix(), headers=csrf(staff_client)).json()

    again = staff_client.post(corrections_url(workshop, history["typo"]), json=fix(odometer_km=56_000), headers=csrf(staff_client))
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "already_corrected"

    chained = staff_client.post(
        corrections_url(workshop, uuid.UUID(first["id"])), json=fix(odometer_km=56_000), headers=csrf(staff_client)
    )
    assert chained.status_code == 201
    assert chained.json()["corrects_record_id"] == first["id"]


@pytest.mark.parametrize(("overrides", "status"), [({"correction_reason": None}, 422), ({"correction_reason": "typo"}, 422)])
def test_a_correction_needs_a_known_reason(staff_client: TestClient, workshop, history, overrides, status) -> None:
    assert staff_client.post(corrections_url(workshop, history["typo"]), json=fix(**overrides), headers=csrf(staff_client)).status_code == status


def test_unknown_record_is_404(staff_client: TestClient, workshop, history) -> None:
    response = staff_client.post(corrections_url(workshop, uuid.uuid4()), json=fix(), headers=csrf(staff_client))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "record_not_found"


@pytest.mark.parametrize("role", [UserRole.CONSUMER, UserRole.PLATFORM_ADMIN])
def test_consumers_and_platform_admins_cannot_correct(client: TestClient, db: Session, workshop, history, role) -> None:
    user = add_user(db, "someone@example.ae", role=role)
    login(client, user.email)
    assert client.post(corrections_url(workshop, history["typo"]), json=fix(), headers=csrf(client)).status_code == 403


def test_correction_publishes_record_added_with_the_link(staff_client: TestClient, workshop, history) -> None:
    received: list[dict] = []
    unsubscribe = events.subscribe(lambda event_type, payload: received.append(payload))
    try:
        staff_client.post(corrections_url(workshop, history["typo"]), json=fix(), headers=csrf(staff_client))
    finally:
        unsubscribe()
    assert [payload["corrects_record_id"] for payload in received] == [str(history["typo"].id)]


# --- the organization's own records for a VIN (to pick the one to correct) ---------------------------------


def test_organization_lists_its_own_records_for_a_vin_with_correction_state(
    staff_client: TestClient, db: Session, workshop, history
) -> None:
    other = make_org(db, name="Oasis Line Motors")
    vehicle = db.get(Vehicle, history["jan"].vehicle_id)
    make_record(db, vehicle, other, add_user(db, "x@example.ae"), odometer_km=70_000, service_date=date(2026, 4, 1))
    correction = staff_client.post(
        corrections_url(workshop, history["typo"]), json=fix(notes="Extra zero", service_date="2026-02-12"), headers=csrf(staff_client)
    ).json()

    listed = staff_client.get(f"/api/v1/organizations/{workshop.id}/records", params={"vin": VIN.lower()}).json()

    assert [r["odometer_km"] for r in listed] == [55_000, 500_000, 50_000]  # newest first, own organization only
    by_id = {r["id"]: r for r in listed}
    assert by_id[str(history["typo"].id)]["corrected_by_id"] == correction["id"]
    assert by_id[correction["id"]]["corrected_by_id"] is None
    assert by_id[correction["id"]]["notes"] == "Extra zero"


def test_listing_needs_membership_and_a_valid_vin(staff_client: TestClient, db: Session, workshop) -> None:
    other = make_org(db, name="Oasis Line Motors")
    assert staff_client.get(f"/api/v1/organizations/{other.id}/records", params={"vin": VIN}).status_code == 403
    response = staff_client.get(f"/api/v1/organizations/{workshop.id}/records", params={"vin": "NOT-A-VIN"})
    assert response.status_code == 422 and response.json()["error"]["code"] == "invalid_vin"

