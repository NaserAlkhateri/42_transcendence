"""CSV/JSON export of service records (AG-07): formats, headers, filters, selection, the row cap, permissions
and audit."""

import csv
import io
import json
import re
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuditEvent,
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
from app.services import record_export
from tests.auth_helpers import add_member, add_user, login
from tests.factories import make_org

ADMIN_EXPORT = "/api/v1/admin/records/export"
EXPORT_COLUMNS = [
    "record_id", "vin", "make", "model", "model_year", "service_date", "category", "work_codes", "odometer_km",
    "organization_name", "staff_name", "notes", "is_mileage_flagged", "corrects_record_id", "correction_reason",
    "created_at",
]

CRUISER = "JTMHX01J5M4012345"
PATROL = "JN8AY2NY4K9012345"
CAMRY = "JTNBK3EK6N3012345"
NEW_VIN = "WDB2030461A123456"

TRICKY_NOTES = 'Customer waited, then said "thanks"\nSecond line'
FORMULA_NOTES = '=HYPERLINK("http://example.com","click")'
ARABIC_NOTES = "تم تغيير الزيت، العميل راضٍ"


# --- helpers and data ------------------------------------------------------------------------------------------


def add_vehicle(db: Session, vin: str, make: str | None = None, model: str | None = None, year: int | None = None) -> Vehicle:
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
    """Four Falcon records (one corrects another) and one Oasis record, each created_at distinct."""
    arjun = add_user(db, "arjun@example.ae", full_name="Arjun Nair")
    khalid = add_user(db, "khalid@example.ae", full_name="Khalid Al Mansoori")
    fatima = add_user(db, "fatima@example.ae", full_name="Fatima Al Zaabi")
    add_member(db, falcon, arjun, MemberRole.ENTITY_STAFF)
    add_member(db, falcon, khalid, MemberRole.ENTITY_ADMIN)
    add_member(db, oasis, fatima, MemberRole.ENTITY_STAFF)

    cruiser = add_vehicle(db, CRUISER, "Toyota", "Land Cruiser", 2021)
    patrol = add_vehicle(db, PATROL, "Nissan", "Patrol", 2019)
    camry = add_vehicle(db, CAMRY, "Toyota", "Camry", 2022)

    records: dict[str, ServiceRecord] = {}
    records["jan"] = add_record(
        db, cruiser, falcon, arjun, service_date=date(2026, 1, 10), odometer_km=20_000, created_at=at(1, 10),
        work_codes=("OIL_CHANGE", "AIR_FILTER"), notes=TRICKY_NOTES,
    )
    records["mar"] = add_record(
        db, cruiser, falcon, khalid, service_date=date(2026, 3, 5), odometer_km=25_000, created_at=at(3, 5),
        category=RecordCategory.REPAIR, work_codes=("BRAKE_PADS",), notes=FORMULA_NOTES,
    )
    records["feb"] = add_record(
        db, patrol, falcon, arjun, service_date=date(2026, 2, 14), odometer_km=88_300, created_at=at(2, 14),
        work_codes=("AC_SERVICE",), flagged=True, notes=ARABIC_NOTES,
    )
    records["fix"] = add_record(
        db, patrol, falcon, arjun, service_date=date(2026, 2, 14), odometer_km=98_300, created_at=at(2, 15),
        work_codes=("AC_SERVICE",), corrects=records["feb"],
    )
    records["camry"] = add_record(
        db, camry, oasis, fatima, service_date=date(2026, 4, 1), odometer_km=40_500, created_at=at(4, 2),
        category=RecordCategory.REPAIR, work_codes=("ENGINE_REPAIR",),
    )
    return records


FALCON_ORDER = ["mar", "fix", "feb", "jan"]  # newest service date first, then newest created


@pytest.fixture
def falcon_client(client: TestClient, data) -> TestClient:
    """Signed in as Arjun, entity staff of Falcon Bay Auto Care."""
    login(client, "arjun@example.ae")
    return client


@pytest.fixture
def admin_client(client: TestClient, db: Session, data) -> TestClient:
    add_user(db, "root@example.ae", full_name="Root Admin", role=UserRole.PLATFORM_ADMIN)
    login(client, "root@example.ae")
    return client


def export_url(org: Organization | uuid.UUID) -> str:
    org_id = org.id if isinstance(org, Organization) else org
    return f"/api/v1/organizations/{org_id}/records/export"


def csv_rows(response) -> list[dict[str, str]]:
    assert response.status_code == 200, response.text
    assert response.content.startswith(b"\xef\xbb\xbf")
    return list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"), newline="")))


def exported_ids(response, data: dict[str, ServiceRecord]) -> list[str]:
    by_id = {str(record.id): name for name, record in data.items()}
    if response.headers["content-type"].startswith("text/csv"):
        return [by_id[row["record_id"]] for row in csv_rows(response)]
    assert response.status_code == 200, response.text
    return [by_id[record["record_id"]] for record in response.json()["records"]]


def error_code(response, status: int = 422) -> str:
    assert response.status_code == status, response.text
    return response.json()["error"]["code"]


def stamp_of(disposition: str, extension: str) -> datetime:
    match = re.fullmatch(rf'attachment; filename="sijil-records-(\d{{8}}-\d{{4}})\.{extension}"', disposition)
    assert match, disposition
    return datetime.strptime(match.group(1), "%Y%m%d-%H%M").replace(tzinfo=UTC)


# --- export: formats -----------------------------------------------------------------------------------------


def test_csv_export_lists_the_organization_records_in_search_order(falcon_client: TestClient, falcon, data) -> None:
    response = falcon_client.get(export_url(falcon), params={"format": "csv"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert response.headers["cache-control"] == "no-store"
    stamp = stamp_of(response.headers["content-disposition"], "csv")
    assert abs(datetime.now(UTC) - stamp) < timedelta(minutes=2)  # UTC, to the minute
    text = response.content.decode("utf-8-sig")
    assert text.split("\r\n")[0] == ",".join(EXPORT_COLUMNS)
    rows = csv_rows(response)
    assert exported_ids(response, data) == FALCON_ORDER
    assert rows[3] == {
        "record_id": str(data["jan"].id), "vin": CRUISER, "make": "Toyota", "model": "Land Cruiser",
        "model_year": "2021", "service_date": "2026-01-10", "category": "maintenance",
        "work_codes": "OIL_CHANGE;AIR_FILTER", "odometer_km": "20000", "organization_name": "Falcon Bay Auto Care",
        "staff_name": "Arjun Nair", "notes": TRICKY_NOTES, "is_mileage_flagged": "false", "corrects_record_id": "",
        "correction_reason": "", "created_at": "2026-01-10T08:00:00Z",
    }
    fix, feb = rows[1], rows[2]
    assert feb["is_mileage_flagged"] == "true"
    assert feb["notes"] == ARABIC_NOTES  # UTF-8 survives
    assert fix["corrects_record_id"] == str(data["feb"].id)
    assert fix["correction_reason"] == "odometer"
    assert fix["notes"] == ""


@pytest.mark.parametrize("notes", ["=1+1", "+971 50 000 0000", "-2+3", "@SUM(A1:A2)", "\tcmd", "\rcmd"])
def test_csv_export_neutralises_spreadsheet_formulas(
    falcon_client: TestClient, db: Session, falcon, data, notes: str
) -> None:
    vehicle = add_vehicle(db, NEW_VIN, "=Make", "@Model", 2020)
    staff = db.scalar(select(User).where(User.email == "arjun@example.ae"))
    record = add_record(db, vehicle, falcon, staff, service_date=date(2026, 6, 1), odometer_km=1_000, notes=notes)

    [row] = csv_rows(falcon_client.get(export_url(falcon), params={"format": "csv", "ids": str(record.id)}))

    assert row["notes"] == "'" + notes
    assert (row["make"], row["model"]) == ("'=Make", "'@Model")


def test_csv_export_guards_the_formula_in_the_demo_notes_but_json_keeps_data_as_is(
    falcon_client: TestClient, falcon, data
) -> None:
    rows = csv_rows(falcon_client.get(export_url(falcon), params={"format": "csv"}))
    assert rows[0]["notes"] == "'" + FORMULA_NOTES
    records = falcon_client.get(export_url(falcon), params={"format": "json"}).json()["records"]
    assert records[0]["notes"] == FORMULA_NOTES


def test_json_export_has_the_documented_shape_and_json_types(falcon_client: TestClient, falcon, data) -> None:
    response = falcon_client.get(export_url(falcon), params={"format": "json"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == "no-store"
    stamp_of(response.headers["content-disposition"], "json")
    body = response.json()
    assert set(body) == {"exported_at", "scope", "organization_id", "filters", "count", "records"}
    assert (body["scope"], body["organization_id"], body["count"]) == ("organization", str(falcon.id), 4)
    exported_at = datetime.fromisoformat(body["exported_at"])
    assert exported_at.utcoffset() == timedelta(0)
    assert abs(datetime.now(UTC) - exported_at) < timedelta(minutes=2)
    assert body["filters"]["sort"] == "service_date" and body["filters"]["order"] == "desc"
    assert body["filters"]["ids"] == []
    assert "organization" not in body["filters"]  # admin-only filters are not part of an organization export
    assert exported_ids(response, data) == FALCON_ORDER
    assert body["records"][3] == {
        "record_id": str(data["jan"].id), "vin": CRUISER, "make": "Toyota", "model": "Land Cruiser",
        "model_year": 2021, "service_date": "2026-01-10", "category": "maintenance",
        "work_codes": ["OIL_CHANGE", "AIR_FILTER"], "odometer_km": 20_000, "organization_name": "Falcon Bay Auto Care",
        "staff_name": "Arjun Nair", "notes": TRICKY_NOTES, "is_mileage_flagged": False, "corrects_record_id": None,
        "correction_reason": None, "created_at": "2026-01-10T08:00:00Z",
    }
    fix = body["records"][1]
    assert fix["notes"] is None
    assert fix["corrects_record_id"] == str(data["feb"].id) and fix["correction_reason"] == "odometer"
    assert body["records"][2]["is_mileage_flagged"] is True


# --- export: filters, sort and selection -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"category": "repair"}, ["mar"]),
        ({"sort": "odometer_km", "order": "asc"}, ["jan", "mar", "feb", "fix"]),
        ({"work_code": "AC_SERVICE", "record_type": "original"}, ["feb"]),
        ({"vin": "hx01j"}, ["mar", "jan"]),
        ({"date_from": "2026-02-01", "date_to": "2026-02-28"}, ["fix", "feb"]),
        ({"flagged": "true"}, ["feb"]),
    ],
)
@pytest.mark.parametrize("export_format", ["csv", "json"])
def test_export_applies_the_search_filters_and_sort(
    falcon_client: TestClient, falcon, data, params, expected, export_format: str
) -> None:
    response = falcon_client.get(export_url(falcon), params={"format": export_format, **params})
    assert exported_ids(response, data) == expected


def test_json_export_records_the_applied_filters(falcon_client: TestClient, falcon, data) -> None:
    params = {"format": "json", "vin": "hx-01j", "category": "repair", "work_code": ["BRAKE_PADS"], "sort": "vin",
              "order": "asc", "date_from": "2026-01-01"}
    filters = falcon_client.get(export_url(falcon), params=params).json()["filters"]
    assert filters["vin"] == "HX01J"
    assert filters["category"] == "repair"
    assert filters["work_codes"] == ["BRAKE_PADS"]
    assert filters["date_from"] == "2026-01-01" and filters["date_to"] is None
    assert (filters["sort"], filters["order"]) == ("vin", "asc")


def test_export_rejects_the_same_invalid_filters_as_search(falcon_client: TestClient, falcon, data) -> None:
    response = falcon_client.get(export_url(falcon), params={"format": "csv", "year_from": 2025, "year_to": 2020})
    assert error_code(response) == "invalid_year_range"
    assert error_code(falcon_client.get(export_url(falcon), params={"format": "csv", "sort": "price"})) == "validation_error"


def test_export_selected_records_only(falcon_client: TestClient, falcon, data) -> None:
    def selected(*names: str, **params) -> list[str]:
        ids = [str(data[name].id) for name in names]
        return exported_ids(falcon_client.get(export_url(falcon), params={"format": "json", "ids": ids, **params}), data)

    assert selected("jan", "feb") == ["feb", "jan"]  # search order, not the order of the ids
    assert selected("jan", "camry") == ["jan"]  # another organization's record is out of scope
    assert selected("camry") == []
    assert selected("jan", "mar", category="repair") == ["mar"]  # ids narrow the filters, never widen them
    unknown = exported_ids(falcon_client.get(export_url(falcon), params={"format": "csv", "ids": str(uuid.uuid4())}), data)
    assert unknown == []


def test_json_export_lists_the_selected_ids_in_its_filters(falcon_client: TestClient, falcon, data) -> None:
    ids = [str(data["jan"].id), str(data["camry"].id)]
    body = falcon_client.get(export_url(falcon), params={"format": "json", "ids": ids}).json()
    assert body["filters"]["ids"] == ids
    assert body["count"] == 1


def test_admin_export_of_selected_records_spans_organizations(admin_client: TestClient, data) -> None:
    ids = [str(data["jan"].id), str(data["camry"].id)]
    response = admin_client.get(ADMIN_EXPORT, params={"format": "json", "ids": ids})
    assert exported_ids(response, data) == ["camry", "jan"]


def test_at_most_100_ids_can_be_selected(falcon_client: TestClient, falcon, data) -> None:
    ids = [str(uuid.uuid4()) for _ in range(101)]
    assert error_code(falcon_client.get(export_url(falcon), params={"format": "csv", "ids": ids})) == "validation_error"
    response = falcon_client.get(export_url(falcon), params={"format": "csv", "ids": ids[:100]})
    assert response.status_code == 200
    assert csv_rows(response) == []


def test_malformed_ids_are_rejected(falcon_client: TestClient, falcon, data) -> None:
    response = falcon_client.get(export_url(falcon), params={"format": "csv", "ids": "not-a-uuid"})
    assert error_code(response) == "validation_error"


def test_empty_export_still_has_the_header(falcon_client: TestClient, falcon, data) -> None:
    response = falcon_client.get(export_url(falcon), params={"format": "csv", "make": "Lamborghini"})
    assert csv_rows(response) == []
    assert response.content.decode("utf-8-sig") == ",".join(EXPORT_COLUMNS) + "\r\n"
    body = falcon_client.get(export_url(falcon), params={"format": "json", "make": "Lamborghini"}).json()
    assert body["count"] == 0 and body["records"] == []


@pytest.mark.parametrize("params", [{}, {"format": "xml"}, {"format": "CSV"}, {"format": ""}])
def test_format_is_required_and_must_be_csv_or_json(falcon_client: TestClient, falcon, data, params) -> None:
    assert error_code(falcon_client.get(export_url(falcon), params=params)) == "validation_error"


def test_more_than_the_cap_is_refused_not_truncated(
    falcon_client: TestClient, db: Session, falcon, data, monkeypatch
) -> None:
    monkeypatch.setattr(record_export, "MAX_EXPORT_ROWS", 3)
    response = falcon_client.get(export_url(falcon), params={"format": "csv"})
    assert error_code(response) == "export_too_large"
    assert "Narrow the filters" in response.json()["error"]["message"]
    assert db.scalar(select(AuditEvent).where(AuditEvent.action == "records.exported")) is None

    assert exported_ids(falcon_client.get(export_url(falcon), params={"format": "csv", "category": "repair"}), data) == ["mar"]
    monkeypatch.setattr(record_export, "MAX_EXPORT_ROWS", 4)
    assert len(exported_ids(falcon_client.get(export_url(falcon), params={"format": "json"}), data)) == 4  # at the cap


def test_the_real_cap_is_5000_rows() -> None:
    assert record_export.MAX_EXPORT_ROWS == 5_000


# --- export: access ---------------------------------------------------------------------------------------------


def test_export_requires_sign_in(client: TestClient, falcon) -> None:
    for url in (export_url(falcon), ADMIN_EXPORT):
        for params in ({"format": "csv"}, {"format": "xml", "year_from": 2025, "year_to": 2020}):  # auth comes first
            assert error_code(client.get(url, params=params), 401) == "not_authenticated"


def test_consumers_cannot_export(client: TestClient, db: Session, falcon) -> None:
    add_user(db, "consumer@example.ae")
    login(client, "consumer@example.ae")
    assert error_code(client.get(export_url(falcon), params={"format": "csv"}), 403) == "forbidden"
    assert error_code(client.get(ADMIN_EXPORT, params={"format": "csv"}), 403) == "forbidden"


def test_staff_cannot_export_another_organization(falcon_client: TestClient, oasis) -> None:
    assert error_code(falcon_client.get(export_url(oasis), params={"format": "csv"}), 403) == "forbidden"


def test_inactive_member_cannot_export(client: TestClient, db: Session, falcon) -> None:
    user = add_user(db, "former@example.ae")
    add_member(db, falcon, user, MemberRole.ENTITY_STAFF).status = MemberStatus.INACTIVE
    db.flush()
    login(client, user.email)
    assert client.get(export_url(falcon), params={"format": "csv"}).status_code == 403


@pytest.mark.parametrize("email", ["arjun@example.ae", "khalid@example.ae"])
def test_entity_members_cannot_use_the_platform_export(client: TestClient, data, email: str) -> None:
    login(client, email)
    assert error_code(client.get(ADMIN_EXPORT, params={"format": "csv"}), 403) == "forbidden"


def test_entity_admin_can_export_their_organization(client: TestClient, falcon, data) -> None:
    login(client, "khalid@example.ae")
    assert len(exported_ids(client.get(export_url(falcon), params={"format": "csv"}), data)) == 4


def test_unknown_organization_is_404(falcon_client: TestClient) -> None:
    response = falcon_client.get(export_url(uuid.uuid4()), params={"format": "csv"})
    assert error_code(response, 404) == "organization_not_found"


def test_platform_admin_exports_one_organization_or_all(admin_client: TestClient, falcon, oasis, data) -> None:
    one = admin_client.get(export_url(oasis), params={"format": "json"})
    assert exported_ids(one, data) == ["camry"]
    assert (one.json()["scope"], one.json()["organization_id"]) == ("organization", str(oasis.id))

    everything = admin_client.get(ADMIN_EXPORT, params={"format": "json"})
    assert exported_ids(everything, data) == ["camry", *FALCON_ORDER]
    assert (everything.json()["scope"], everything.json()["organization_id"]) == ("platform", None)
    assert everything.json()["filters"]["organization_id"] is None

    falcon_only = admin_client.get(ADMIN_EXPORT, params={"format": "csv", "organization_id": str(falcon.id)})
    assert exported_ids(falcon_only, data) == FALCON_ORDER
    assert exported_ids(admin_client.get(ADMIN_EXPORT, params={"format": "csv", "organization": "oasis"}), data) == ["camry"]


def test_exports_are_audited_without_record_contents(admin_client: TestClient, db: Session, falcon, data) -> None:
    admin_client.get(export_url(falcon), params={"format": "csv"})
    admin_client.get(ADMIN_EXPORT, params={"format": "json", "category": "repair"})

    # One test transaction: both rows share created_at, so order by target instead.
    events_ = db.scalars(
        select(AuditEvent).where(AuditEvent.action == "records.exported").order_by(AuditEvent.target_type)
    ).all()
    assert [(e.target_type, e.target_id, e.details) for e in events_] == [
        ("organization", str(falcon.id), {"format": "csv", "count": 4, "scope": "organization"}),
        ("platform", "all", {"format": "json", "count": 2, "scope": "platform"}),
    ]
    assert all(e.actor_label == "root@example.ae" for e in events_)


def test_staff_export_is_audited_under_their_name(falcon_client: TestClient, db: Session, falcon, data) -> None:
    falcon_client.get(export_url(falcon), params={"format": "json", "ids": str(data["jan"].id)})
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "records.exported"))
    assert event.actor_label == "arjun@example.ae"
    assert event.details == {"format": "json", "count": 1, "scope": "organization"}
    assert CRUISER not in json.dumps(event.details) and "Customer" not in json.dumps(event.details)
