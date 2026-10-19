"""Advanced record search (AG-06): filters, sorting, pagination, scoping and the 422 codes."""

import uuid
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event
from sqlalchemy.orm import Session

from app.models import (
    CorrectionReason,
    MemberRole,
    MemberStatus,
    Organization,
    RecordCategory,
    ServiceRecord,
    User,
    UserRole,
    Vehicle,
)
from tests.auth_helpers import add_member, add_user, login
from tests.factories import make_org

ADMIN_SEARCH = "/api/v1/admin/records"
ALL = {"f_cruiser_jan", "f_cruiser_mar", "f_patrol_feb", "f_patrol_fix", "o_camry_apr", "o_unknown_may"}
SORT_KEYS = ["service_date", "created_at", "odometer_km", "vin", "make", "organization_name"]
ITEM_FIELDS = {
    "id", "vin", "make", "model", "model_year", "service_date", "created_at", "category", "work_codes", "odometer_km",
    "organization_id", "organization_name", "staff_name", "notes", "is_mileage_flagged", "corrects_record_id",
    "correction_reason", "corrected_by_id",
}


def org_search(org: Organization | uuid.UUID) -> str:
    org_id = org.id if isinstance(org, Organization) else org
    return f"/api/v1/organizations/{org_id}/records/search"


def add_vehicle(db: Session, vin: str, make: str | None, model: str | None, year: int | None) -> Vehicle:
    vehicle = Vehicle(vin=vin, make=make, model=model, model_year=year)
    db.add(vehicle)
    db.flush()
    return vehicle


def add_record(
    db: Session,
    vehicle: Vehicle,
    org: Organization,
    staff: User,
    *,
    service_date: date,
    odometer_km: int,
    created_at: datetime | None = None,
    category: RecordCategory = RecordCategory.MAINTENANCE,
    work_codes: tuple[str, ...] = ("OIL_CHANGE",),
    flagged: bool = False,
    corrects: ServiceRecord | None = None,
    notes: str | None = None,
) -> ServiceRecord:
    record = ServiceRecord(
        vehicle_id=vehicle.id, organization_id=org.id, staff_id=staff.id, organization_name=org.name,
        staff_name=staff.full_name, category=category, work_codes=list(work_codes), odometer_km=odometer_km,
        service_date=service_date, is_mileage_flagged=flagged, notes=notes,
        corrects_record_id=corrects.id if corrects else None,
        correction_reason=CorrectionReason.ODOMETER if corrects else None,
    )
    if created_at is not None:
        record.created_at = created_at
    db.add(record)
    db.flush()
    return record


def at(month: int, day: int) -> datetime:
    return datetime(2026, month, day, 8, 0, tzinfo=UTC)


@pytest.fixture
def falcon(db: Session) -> Organization:
    return make_org(db, name="Falcon Bay Auto Care")


@pytest.fixture
def oasis(db: Session) -> Organization:
    return make_org(db, name="Oasis Line Motors")


@pytest.fixture
def data(db: Session, falcon: Organization, oasis: Organization) -> dict[str, ServiceRecord]:
    """Six records across two organizations, every created_at distinct so each sort order is fully determined."""
    arjun = add_user(db, "arjun@example.ae", full_name="Arjun Nair")
    khalid = add_user(db, "khalid@example.ae", full_name="Khalid Al Mansoori")
    fatima = add_user(db, "fatima@example.ae", full_name="Fatima Al Zaabi")
    add_member(db, falcon, arjun, MemberRole.ENTITY_STAFF)
    add_member(db, falcon, khalid, MemberRole.ENTITY_ADMIN)
    add_member(db, oasis, fatima, MemberRole.ENTITY_STAFF)

    cruiser = add_vehicle(db, "JTMHX01J5M4012345", "Toyota", "Land Cruiser", 2021)
    patrol = add_vehicle(db, "JN8AY2NY4K9012345", "Nissan", "Patrol", 2019)
    camry = add_vehicle(db, "JTNBK3EK6N3012345", "Toyota", "Camry", 2022)
    unknown = add_vehicle(db, "WDB2030461A123456", None, None, None)

    records: dict[str, ServiceRecord] = {}
    records["f_cruiser_jan"] = add_record(
        db, cruiser, falcon, arjun, service_date=date(2026, 1, 10), odometer_km=20_000, created_at=at(1, 10),
        work_codes=("OIL_CHANGE", "AIR_FILTER"), notes="Customer waited",
    )
    records["f_cruiser_mar"] = add_record(
        db, cruiser, falcon, khalid, service_date=date(2026, 3, 5), odometer_km=25_000, created_at=at(3, 5),
        category=RecordCategory.REPAIR, work_codes=("BRAKE_PADS",),
    )
    records["f_patrol_feb"] = add_record(
        db, patrol, falcon, arjun, service_date=date(2026, 2, 14), odometer_km=88_300, created_at=at(2, 14),
        work_codes=("AC_SERVICE",), flagged=True,
    )
    records["f_patrol_fix"] = add_record(
        db, patrol, falcon, arjun, service_date=date(2026, 2, 14), odometer_km=98_300, created_at=at(2, 15),
        work_codes=("AC_SERVICE",), corrects=records["f_patrol_feb"],
    )
    records["o_camry_apr"] = add_record(
        db, camry, oasis, fatima, service_date=date(2026, 4, 1), odometer_km=40_500, created_at=at(4, 2),
        category=RecordCategory.REPAIR, work_codes=("ENGINE_REPAIR", "GENERAL_INSPECTION"),
    )
    records["o_unknown_may"] = add_record(
        db, unknown, oasis, fatima, service_date=date(2026, 5, 20), odometer_km=150_000, created_at=at(5, 20),
        work_codes=("TYRE_REPLACE",),
    )
    return records


@pytest.fixture
def admin_client(client: TestClient, db: Session, data) -> TestClient:
    add_user(db, "root@example.ae", full_name="Root Admin", role=UserRole.PLATFORM_ADMIN)
    login(client, "root@example.ae")
    return client


@pytest.fixture
def falcon_client(client: TestClient, data) -> TestClient:
    """Signed in as Arjun, entity staff of Falcon Bay Auto Care."""
    login(client, "arjun@example.ae")
    return client


def keys(response, data: dict[str, ServiceRecord]) -> list[str]:
    assert response.status_code == 200, response.text
    by_id = {str(record.id): name for name, record in data.items()}
    return [by_id[item["id"]] for item in response.json()["items"]]


def found(client: TestClient, data, url: str = ADMIN_SEARCH, **params) -> set[str]:
    return set(keys(client.get(url, params={"page_size": 100, **params}), data))


def error_code(response) -> str:
    assert response.status_code == 422, response.text
    return response.json()["error"]["code"]


# --- access and scoping --------------------------------------------------------------------------------------


def test_search_requires_sign_in(client: TestClient, falcon: Organization) -> None:
    for url in (org_search(falcon), ADMIN_SEARCH):
        for params in ({}, {"year_from": 2025, "year_to": 2020, "sort": "price"}):  # auth is checked first
            response = client.get(url, params=params)
            assert response.status_code == 401
            assert response.json()["error"]["code"] == "not_authenticated"


def test_consumers_cannot_search(client: TestClient, db: Session, falcon: Organization) -> None:
    add_user(db, "consumer@example.ae")
    login(client, "consumer@example.ae")
    assert client.get(org_search(falcon)).status_code == 403
    assert client.get(ADMIN_SEARCH).status_code == 403


def test_staff_cannot_search_another_organization(falcon_client: TestClient, oasis: Organization) -> None:
    response = falcon_client.get(org_search(oasis))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


@pytest.mark.parametrize("email", ["arjun@example.ae", "khalid@example.ae"])
def test_entity_members_cannot_use_the_platform_search(client: TestClient, data, email: str) -> None:
    login(client, email)
    assert client.get(ADMIN_SEARCH).status_code == 403


def test_inactive_member_cannot_search(client: TestClient, db: Session, falcon: Organization) -> None:
    user = add_user(db, "former@example.ae")
    add_member(db, falcon, user, MemberRole.ENTITY_STAFF).status = MemberStatus.INACTIVE
    db.flush()
    login(client, user.email)
    assert client.get(org_search(falcon)).status_code == 403


def test_unknown_organization_is_404(falcon_client: TestClient) -> None:
    response = falcon_client.get(org_search(uuid.uuid4()))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "organization_not_found"


def test_staff_see_only_their_organization_records(falcon_client: TestClient, falcon, oasis, data) -> None:
    expected = {"f_cruiser_jan", "f_cruiser_mar", "f_patrol_feb", "f_patrol_fix"}
    assert found(falcon_client, data, org_search(falcon)) == expected
    # Admin-only filters are ignored on the organization route: the scope cannot be widened.
    widened = found(falcon_client, data, org_search(falcon), organization_id=str(oasis.id), organization="oasis")
    assert widened == expected


def test_entity_admin_can_search_their_organization(client: TestClient, falcon, data) -> None:
    login(client, "khalid@example.ae")
    assert len(found(client, data, org_search(falcon))) == 4


def test_platform_admin_can_search_one_organization(admin_client: TestClient, oasis, data) -> None:
    assert found(admin_client, data, org_search(oasis)) == {"o_camry_apr", "o_unknown_may"}


def test_platform_admin_searches_every_organization(admin_client: TestClient, falcon, data) -> None:
    assert found(admin_client, data) == set(data)
    assert found(admin_client, data, organization_id=str(falcon.id)) == {
        "f_cruiser_jan", "f_cruiser_mar", "f_patrol_feb", "f_patrol_fix",
    }
    assert found(admin_client, data, organization="  OASIS ") == {"o_camry_apr", "o_unknown_may"}
    assert found(admin_client, data, organization_id=str(uuid.uuid4())) == set()


def test_admin_search_keeps_records_of_a_deleted_organization(admin_client: TestClient, db: Session, data) -> None:
    closed = make_org(db, name="Closed Desert Garage")
    staff = add_user(db, "gone@example.ae", full_name="Former Mechanic")
    vehicle = db.get(Vehicle, data["f_cruiser_jan"].vehicle_id)
    add_record(db, vehicle, closed, staff, service_date=date(2026, 6, 1), odometer_km=30_000)
    db.delete(closed)
    db.flush()

    [item] = admin_client.get(ADMIN_SEARCH, params={"organization": "closed desert"}).json()["items"]
    assert item["organization_id"] is None
    assert item["organization_name"] == "Closed Desert Garage"


# --- result shape ----------------------------------------------------------------------------------------------


def test_items_carry_vehicle_facts_private_fields_and_correction_links(falcon_client: TestClient, falcon, data) -> None:
    response = falcon_client.get(org_search(falcon))
    body = response.json()
    assert set(body) == {"items", "total", "page", "page_size"}
    assert (body["total"], body["page"], body["page_size"]) == (4, 1, 20)
    items = {item["id"]: item for item in body["items"]}
    assert all(set(item) == ITEM_FIELDS for item in items.values())

    jan = items[str(data["f_cruiser_jan"].id)]
    assert jan["vin"] == "JTMHX01J5M4012345"
    assert (jan["make"], jan["model"], jan["model_year"]) == ("Toyota", "Land Cruiser", 2021)
    assert jan["service_date"] == "2026-01-10"
    assert jan["category"] == "maintenance"
    assert jan["work_codes"] == ["OIL_CHANGE", "AIR_FILTER"]
    assert jan["odometer_km"] == 20_000
    assert jan["organization_id"] == str(falcon.id)
    assert jan["organization_name"] == "Falcon Bay Auto Care"
    assert jan["staff_name"] == "Arjun Nair"
    assert jan["notes"] == "Customer waited"
    assert jan["corrected_by_id"] is None and jan["corrects_record_id"] is None

    original = items[str(data["f_patrol_feb"].id)]
    correction = items[str(data["f_patrol_fix"].id)]
    assert original["is_mileage_flagged"] is True
    assert original["corrected_by_id"] == correction["id"]
    assert correction["corrects_record_id"] == original["id"]
    assert correction["correction_reason"] == "odometer"


# --- filters -----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("vin", "expected"),
    [
        ("hx01j", {"f_cruiser_jan", "f_cruiser_mar"}),  # lower case
        ("jtm-hx 01", {"f_cruiser_jan", "f_cruiser_mar"}),  # separators
        ("HX٠١J", {"f_cruiser_jan", "f_cruiser_mar"}),  # Arabic-Indic digits
        ("HX۰۱J", {"f_cruiser_jan", "f_cruiser_mar"}),  # Extended Arabic-Indic digits
        ("JTMHX01J5M4012345", {"f_cruiser_jan", "f_cruiser_mar"}),  # a full VIN still works
        ("012345", {"f_cruiser_jan", "f_cruiser_mar", "f_patrol_feb", "f_patrol_fix", "o_camry_apr"}),
        ("   ", {"f_cruiser_jan", "f_cruiser_mar", "f_patrol_feb", "f_patrol_fix", "o_camry_apr", "o_unknown_may"}),
        ("ZZZ", set()),
    ],
)
def test_partial_vin(admin_client: TestClient, data, vin: str, expected: set[str]) -> None:
    assert found(admin_client, data, vin=vin) == expected


@pytest.mark.parametrize("vin", ["HXO1", "1Q2", "I", "JT*", "JTM.HX", "ÉTD", "JTMHX01J5M40123456"])
def test_vin_query_with_impossible_characters_or_too_long_is_rejected(admin_client: TestClient, vin: str) -> None:
    assert error_code(admin_client.get(ADMIN_SEARCH, params={"vin": vin})) == "invalid_vin_query"


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"make": "toy"}, {"f_cruiser_jan", "f_cruiser_mar", "o_camry_apr"}),
        ({"make": "NISSAN"}, {"f_patrol_feb", "f_patrol_fix"}),
        ({"model": "cruiser"}, {"f_cruiser_jan", "f_cruiser_mar"}),
        ({"staff": "khalid"}, {"f_cruiser_mar"}),
        ({"staff": " AL ZAABI "}, {"o_camry_apr", "o_unknown_may"}),
        ({"organization": "falcon bay"}, {"f_cruiser_jan", "f_cruiser_mar", "f_patrol_feb", "f_patrol_fix"}),
    ],
)
def test_text_filters_are_case_insensitive_substrings(admin_client: TestClient, data, params, expected) -> None:
    assert found(admin_client, data, **params) == expected


@pytest.mark.parametrize(
    "params",
    [
        {"make": "%"},
        {"make": "_"},
        {"model": "land%cruiser"},  # unescaped, % would match " "
        {"model": "land_cruiser"},  # unescaped, _ would match " "
        {"staff": "\\"},
        {"organization": "%"},
    ],
)
def test_like_wildcards_in_text_filters_are_literal(admin_client: TestClient, data, params) -> None:
    response = admin_client.get(ADMIN_SEARCH, params=params)
    assert response.status_code == 200
    assert response.json()["total"] == 0


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"year_from": 2021}, {"f_cruiser_jan", "f_cruiser_mar", "o_camry_apr"}),
        ({"year_to": 2021}, {"f_cruiser_jan", "f_cruiser_mar", "f_patrol_feb", "f_patrol_fix"}),
        ({"year_from": 2021, "year_to": 2021}, {"f_cruiser_jan", "f_cruiser_mar"}),
        ({"date_from": "2026-02-14", "date_to": "2026-03-05"}, {"f_patrol_feb", "f_patrol_fix", "f_cruiser_mar"}),
        ({"date_from": "2026-04-01"}, {"o_camry_apr", "o_unknown_may"}),
        ({"date_to": "2026-01-10"}, {"f_cruiser_jan"}),
        ({"date_from": "2026-01-10", "date_to": "2026-01-10"}, {"f_cruiser_jan"}),
        ({"odometer_min": 25_000, "odometer_max": 88_300}, {"f_cruiser_mar", "f_patrol_feb", "o_camry_apr"}),
        ({"odometer_min": 98_300}, {"f_patrol_fix", "o_unknown_may"}),
        ({"odometer_max": 20_000}, {"f_cruiser_jan"}),
        ({"odometer_min": 0, "odometer_max": 0}, set()),
    ],
)
def test_range_filters_are_inclusive(admin_client: TestClient, data, params, expected) -> None:
    assert found(admin_client, data, **params) == expected


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"category": "repair"}, {"f_cruiser_mar", "o_camry_apr"}),
        ({"category": "maintenance"}, {"f_cruiser_jan", "f_patrol_feb", "f_patrol_fix", "o_unknown_may"}),
        ({"work_code": "BRAKE_PADS"}, {"f_cruiser_mar"}),
        ({"work_code": ["BRAKE_PADS", "AIR_FILTER"]}, {"f_cruiser_mar", "f_cruiser_jan"}),
        ({"work_code": ["GENERAL_INSPECTION", "GENERAL_INSPECTION"]}, {"o_camry_apr"}),
        ({"work_code": "SPARK_PLUGS"}, set()),
        ({"flagged": "true"}, {"f_patrol_feb"}),
        ({"flagged": "false"}, {"f_cruiser_jan", "f_cruiser_mar", "f_patrol_fix", "o_camry_apr", "o_unknown_may"}),
        ({"record_type": "correction"}, {"f_patrol_fix"}),
        ({"record_type": "original"}, ALL - {"f_patrol_fix"}),
        ({"record_type": "all"}, ALL),
        ({"corrected": "true"}, {"f_patrol_feb"}),
        ({"corrected": "false"}, {"f_cruiser_jan", "f_cruiser_mar", "f_patrol_fix", "o_camry_apr", "o_unknown_may"}),
    ],
)
def test_choice_filters(admin_client: TestClient, data, params, expected) -> None:
    assert found(admin_client, data, **params) == expected


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"make": "toyota", "category": "repair", "date_from": "2026-03-01"}, {"f_cruiser_mar", "o_camry_apr"}),
        ({"make": "toyota", "category": "repair", "organization": "falcon"}, {"f_cruiser_mar"}),
        ({"vin": "012345", "odometer_min": 30_000, "record_type": "original"}, {"f_patrol_feb", "o_camry_apr"}),
        ({"flagged": "true", "corrected": "false"}, set()),
        ({"staff": "arjun", "work_code": "AC_SERVICE", "corrected": "false"}, {"f_patrol_fix"}),
    ],
)
def test_filters_combine_with_and(admin_client: TestClient, data, params, expected) -> None:
    assert found(admin_client, data, **params) == expected


def test_organization_route_filters_within_its_scope(falcon_client: TestClient, falcon, data) -> None:
    url = org_search(falcon)
    assert found(falcon_client, data, url, work_code="AC_SERVICE", record_type="original") == {"f_patrol_feb"}
    assert found(falcon_client, data, url, category="repair") == {"f_cruiser_mar"}  # not Oasis's Camry repair
    assert found(falcon_client, data, url, make="toyota", year_from=2022) == set()


# --- validation errors ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("params", "code"),
    [
        ({"year_from": 2022, "year_to": 2021}, "invalid_year_range"),
        ({"date_from": "2026-03-02", "date_to": "2026-03-01"}, "invalid_date_range"),
        ({"odometer_min": 10_001, "odometer_max": 10_000}, "invalid_odometer_range"),
        ({"work_code": ["OIL_CHANGE", "WINDSCREEN"]}, "unknown_work_code"),
        ({"work_code": "oil_change"}, "unknown_work_code"),
        ({"vin": "O0O"}, "invalid_vin_query"),
        ({"sort": "price"}, "validation_error"),
        ({"order": "up"}, "validation_error"),
        ({"record_type": "deleted"}, "validation_error"),
        ({"category": "tuning"}, "validation_error"),
        ({"flagged": "maybe"}, "validation_error"),
        ({"odometer_min": -1}, "validation_error"),
        ({"date_from": "11/04/2026"}, "validation_error"),
        ({"organization_id": "not-a-uuid"}, "validation_error"),
    ],
)
def test_invalid_queries_get_422_with_a_code(admin_client: TestClient, params, code: str) -> None:
    assert error_code(admin_client.get(ADMIN_SEARCH, params=params)) == code


def test_range_errors_also_apply_on_the_organization_route(falcon_client: TestClient, falcon) -> None:
    response = falcon_client.get(org_search(falcon), params={"year_from": 2025, "year_to": 2020})
    assert error_code(response) == "invalid_year_range"
    assert response.json()["error"]["message"]


def test_unknown_work_code_message_names_the_code(admin_client: TestClient) -> None:
    response = admin_client.get(ADMIN_SEARCH, params={"work_code": "WINDSCREEN"})
    assert "WINDSCREEN" in response.json()["error"]["message"]


# --- sorting ------------------------------------------------------------------------------------------------------


def expected_order(data: dict[str, ServiceRecord], db: Session, sort: str, order: str) -> list[str]:
    """The documented order: the sort key (nulls last, text without case), then newest created first, then id."""
    vehicles = {record.vehicle_id: db.get(Vehicle, record.vehicle_id) for record in data.values()}

    def value(name: str):
        record = data[name]
        vehicle = vehicles[record.vehicle_id]
        return {
            "service_date": record.service_date,
            "created_at": record.created_at,
            "odometer_km": record.odometer_km,
            "vin": vehicle.vin,
            "make": vehicle.make.lower() if vehicle.make else None,
            "organization_name": record.organization_name.lower(),
        }[sort]

    names = sorted(data, key=lambda name: data[name].id)
    names.sort(key=lambda name: data[name].created_at, reverse=True)
    present = [name for name in names if value(name) is not None]
    missing = [name for name in names if value(name) is None]
    present.sort(key=value, reverse=order == "desc")
    return present + missing


@pytest.mark.parametrize("order", ["asc", "desc"])
@pytest.mark.parametrize("sort", SORT_KEYS)
def test_every_sort_key_in_both_directions(admin_client: TestClient, db: Session, data, sort: str, order: str) -> None:
    response = admin_client.get(ADMIN_SEARCH, params={"sort": sort, "order": order})
    assert keys(response, data) == expected_order(data, db, sort, order)


def test_default_order_is_newest_service_date_first(admin_client: TestClient, db: Session, data) -> None:
    order = keys(admin_client.get(ADMIN_SEARCH), data)
    assert order == expected_order(data, db, "service_date", "desc")
    # Same service date: the later-created correction comes first.
    assert order.index("f_patrol_fix") < order.index("f_patrol_feb")


def test_vehicles_without_a_make_sort_last_both_ways(admin_client: TestClient, data) -> None:
    for order in ("asc", "desc"):
        response = admin_client.get(ADMIN_SEARCH, params={"sort": "make", "order": order})
        assert keys(response, data)[-1] == "o_unknown_may"


def test_organization_route_sorts_too(falcon_client: TestClient, falcon, data) -> None:
    response = falcon_client.get(org_search(falcon), params={"sort": "odometer_km", "order": "asc"})
    assert keys(response, data) == ["f_cruiser_jan", "f_cruiser_mar", "f_patrol_feb", "f_patrol_fix"]


# --- pagination ---------------------------------------------------------------------------------------------------


def test_pages_split_the_results_and_total_counts_every_match(admin_client: TestClient, db: Session, data) -> None:
    full = expected_order(data, db, "service_date", "desc")

    pages = [admin_client.get(ADMIN_SEARCH, params={"page": page, "page_size": 4}).json() for page in (1, 2, 3)]

    assert [p["total"] for p in pages] == [6, 6, 6]
    assert [p["page"] for p in pages] == [1, 2, 3]
    assert [p["page_size"] for p in pages] == [4, 4, 4]
    by_id = {str(record.id): name for name, record in data.items()}
    assert [by_id[i["id"]] for i in pages[0]["items"]] == full[:4]
    assert [by_id[i["id"]] for i in pages[1]["items"]] == full[4:]  # last page is partial
    assert pages[2]["items"] == []  # beyond the last page


def test_total_reflects_filters_not_the_page(admin_client: TestClient, data) -> None:
    body = admin_client.get(ADMIN_SEARCH, params={"make": "toyota", "page_size": 1}).json()
    assert body["total"] == 3
    assert len(body["items"]) == 1


@pytest.mark.parametrize(
    "params", [{"page": 0}, {"page": 100_001}, {"page_size": 0}, {"page_size": 101}, {"page": "two"}]
)
def test_page_bounds(admin_client: TestClient, params) -> None:
    assert error_code(admin_client.get(ADMIN_SEARCH, params=params)) == "validation_error"


def test_largest_page_size_and_page_are_accepted(admin_client: TestClient) -> None:
    assert admin_client.get(ADMIN_SEARCH, params={"page_size": 100}).status_code == 200
    response = admin_client.get(ADMIN_SEARCH, params={"page": 100_000, "page_size": 100})
    assert response.status_code == 200
    assert response.json()["items"] == [] and response.json()["total"] == 6


@pytest.mark.parametrize("sort", ["service_date", "make", "organization_name", "created_at"])
def test_ties_never_repeat_or_skip_rows_across_pages(client: TestClient, db: Session, falcon, sort: str) -> None:
    staff = add_user(db, "tied@example.ae", full_name="Tied Staff")
    add_member(db, falcon, staff, MemberRole.ENTITY_STAFF)
    vehicle = add_vehicle(db, "JTMHX01J5M4099999", "Toyota", "Land Cruiser", 2021)
    # Same date, make, organization and (one transaction) the same created_at: only the id tells them apart.
    ids = {str(add_record(db, vehicle, falcon, staff, service_date=date(2026, 2, 1), odometer_km=1000 * n).id)
           for n in range(7)}
    login(client, staff.email)

    url = org_search(falcon)
    full = [i["id"] for i in client.get(url, params={"sort": sort, "page_size": 100}).json()["items"]]
    paged = [
        item["id"]
        for page in (1, 2, 3)
        for item in client.get(url, params={"sort": sort, "page": page, "page_size": 3}).json()["items"]
    ]
    assert paged == full
    assert set(paged) == ids and len(paged) == 7


# --- performance --------------------------------------------------------------------------------------------------


def test_one_query_for_the_page_and_one_count_whatever_the_page_size(
    admin_client: TestClient, engine: Engine, data
) -> None:
    statements: list[str] = []

    def capture(conn, cursor, statement, parameters, context, executemany) -> None:
        if "service_records" in statement:
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        response = admin_client.get(ADMIN_SEARCH, params={"page_size": 100})
    finally:
        event.remove(engine, "before_cursor_execute", capture)

    assert len(response.json()["items"]) == 6
    assert len(statements) == 2, statements
    assert sum("count(" in s.lower() for s in statements) == 1
