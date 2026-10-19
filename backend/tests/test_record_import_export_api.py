"""CSV/JSON export and import of service records (AG-07): formats, headers, limits, row-level validation,
all-or-nothing commits, permissions and the export -> import round trip."""

import csv
import io
import json
import re
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.time import uae_today
from app.models import (
    AuditEvent,
    CorrectionReason,
    MemberRole,
    MemberStatus,
    Organization,
    OrganizationStatus,
    RecordCategory,
    ServiceRecord,
    User,
    UserRole,
    Vehicle,
)
from app.services import events, record_export
from app.services.record_import import MAX_IMPORT_BYTES, MAX_IMPORT_ROWS
from tests.auth_helpers import add_member, add_user, csrf, login
from tests.factories import make_org

ADMIN_EXPORT = "/api/v1/admin/records/export"
EXPORT_COLUMNS = [
    "record_id", "vin", "make", "model", "model_year", "service_date", "category", "work_codes", "odometer_km",
    "organization_name", "staff_name", "notes", "is_mileage_flagged", "corrects_record_id", "correction_reason",
    "created_at",
]
HEADER = "vin,service_date,odometer_km,category,work_codes,notes"

CRUISER = "JTMHX01J5M4012345"
PATROL = "JN8AY2NY4K9012345"
CAMRY = "JTNBK3EK6N3012345"
NEW_VIN = "WDB2030461A123456"
OTHER_VIN = "SALGA2BE8KA012345"
THIRD_VIN = "WVWZZZ1KZ6W012345"

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


# --- import helpers ----------------------------------------------------------------------------------------------


def import_url(org: Organization | uuid.UUID, *, dry_run: bool | str = True) -> str:
    org_id = org.id if isinstance(org, Organization) else org
    flag = str(dry_run).lower() if isinstance(dry_run, bool) else dry_run
    return f"/api/v1/organizations/{org_id}/records/import?dry_run={flag}"


def send(
    client: TestClient, org, content: bytes | str, *, content_type: str | None = "text/csv",
    dry_run: bool | str = True, headers: dict[str, str] | None = None,
):
    body = content.encode("utf-8") if isinstance(content, str) else content
    all_headers = {**csrf(client), **({"Content-Type": content_type} if content_type else {}), **(headers or {})}
    return client.post(import_url(org, dry_run=dry_run), content=body, headers=all_headers)


def csv_text(*rows: str, header: str = HEADER) -> str:
    return "\r\n".join([header, *rows]) + "\r\n"


def report(response, status: int = 200) -> dict:
    assert response.status_code == status, response.text
    return response.json()


def errors_by_row(body: dict) -> dict[int, set[tuple[str | None, str]]]:
    return {row["row"]: {(error["field"], error["code"]) for error in row["errors"]} for row in body["rows"]}


def record_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(ServiceRecord))


VALID_ROW = f"{NEW_VIN},2026-03-01,30000,maintenance,OIL_CHANGE;AIR_FILTER,Customer waited"


# --- import: dry run -----------------------------------------------------------------------------------------


def test_dry_run_previews_a_valid_csv_and_writes_nothing(falcon_client: TestClient, db: Session, falcon) -> None:
    before = record_count(db)
    text = csv_text(VALID_ROW, f"{OTHER_VIN},2026-03-02,45000,repair,BRAKE_PADS,")

    body = report(send(falcon_client, falcon, text))

    assert body == {
        "dry_run": True, "format": "csv", "total_rows": 2, "valid_rows": 2, "invalid_rows": 0, "flagged_rows": 0,
        "warnings": [],
        "rows": [
            {"row": 1, "vin": NEW_VIN, "service_date": "2026-03-01", "odometer_km": 30_000, "category": "maintenance",
             "work_codes": ["OIL_CHANGE", "AIR_FILTER"], "status": "ok", "errors": [], "will_be_flagged": False},
            {"row": 2, "vin": OTHER_VIN, "service_date": "2026-03-02", "odometer_km": 45_000, "category": "repair",
             "work_codes": ["BRAKE_PADS"], "status": "ok", "errors": [], "will_be_flagged": False},
        ],
    }
    assert record_count(db) == before
    assert db.scalar(select(Vehicle).where(Vehicle.vin.in_([NEW_VIN, OTHER_VIN]))) is None  # not even vehicles


def test_dry_run_is_the_default(falcon_client: TestClient, db: Session, falcon) -> None:
    before = record_count(db)
    response = falcon_client.post(
        f"/api/v1/organizations/{falcon.id}/records/import", content=csv_text(VALID_ROW).encode(),
        headers={**csrf(falcon_client), "Content-Type": "text/csv"},
    )
    assert report(response)["dry_run"] is True
    assert record_count(db) == before


def test_csv_parsing_is_forgiving_about_headers_dates_numbers_and_codes(falcon_client: TestClient, falcon) -> None:
    text = "﻿" + "\r\n".join([
        " VIN , Service Date ,ODOMETER_KM,Category,Work-Codes",
        'wdb-203046 1a123456,05/03/2026,"88,300",Repair, oil_change ; AIR_FILTER ;',
        f'{OTHER_VIN.replace("0", "٠")},1/3/2026,"1,234,567",MAINTENANCE,GENERAL_INSPECTION',
        f"{THIRD_VIN},2026-02-28,0,maintenance,TYRE_ROTATION",
    ])

    body = report(send(falcon_client, falcon, text, content_type="text/csv; charset=utf-8"))

    assert (body["valid_rows"], body["invalid_rows"], body["warnings"]) == (3, 0, [])
    first, second, third = body["rows"]
    assert (first["vin"], first["service_date"], first["odometer_km"]) == (NEW_VIN, "2026-03-05", 88_300)  # day first
    assert (first["category"], first["work_codes"]) == ("repair", ["OIL_CHANGE", "AIR_FILTER"])
    assert (second["vin"], second["service_date"], second["odometer_km"]) == (OTHER_VIN, "2026-03-01", 1_234_567)
    assert (third["service_date"], third["odometer_km"]) == ("2026-02-28", 0)


def test_extra_columns_are_ignored_with_one_warning(falcon_client: TestClient, falcon) -> None:
    text = csv_text(
        f"Toyota,{NEW_VIN},2026-03-01,30000,maintenance,OIL_CHANGE,,red",
        f"Nissan,{OTHER_VIN},2026-03-01,30000,maintenance,OIL_CHANGE,,blue",
        header="make,vin,service_date,odometer_km,category,work_codes,notes,Colour",
    )
    body = report(send(falcon_client, falcon, text))
    assert body["valid_rows"] == 2
    [warning] = body["warnings"]
    assert "make" in warning and "Colour" in warning


def test_notes_column_is_optional(falcon_client: TestClient, falcon) -> None:
    text = csv_text(f"{NEW_VIN},2026-03-01,30000,maintenance,OIL_CHANGE", header="vin,service_date,odometer_km,category,work_codes")
    assert report(send(falcon_client, falcon, text))["valid_rows"] == 1


@pytest.mark.parametrize("wrap", [lambda records: records, lambda records: {"records": records}])
def test_dry_run_accepts_both_json_shapes(falcon_client: TestClient, falcon, wrap) -> None:
    records = [
        {"vin": NEW_VIN, "service_date": "2026-03-01", "odometer_km": 30_000, "category": "maintenance",
         "work_codes": ["OIL_CHANGE"], "notes": None},
        {"vin": OTHER_VIN, "service_date": "01/03/2026", "odometer_km": "88,300", "category": "repair",
         "work_codes": "BRAKE_PADS;BRAKE_DISCS"},
    ]
    body = report(send(falcon_client, falcon, json.dumps(wrap(records)), content_type="application/json"))
    assert (body["format"], body["total_rows"], body["valid_rows"]) == ("json", 2, 2)
    assert [row["row"] for row in body["rows"]] == [1, 2]
    assert body["rows"][1]["work_codes"] == ["BRAKE_PADS", "BRAKE_DISCS"]
    assert body["rows"][1]["odometer_km"] == 88_300
    assert body["rows"][1]["service_date"] == "2026-03-01"


def test_json_rows_with_wrong_types_get_row_errors(falcon_client: TestClient, falcon) -> None:
    payload = [
        "not an object",
        {"vin": 12345, "service_date": 20260301, "odometer_km": True, "category": ["repair"], "work_codes": [1],
         "notes": 5},
        {"vin": NEW_VIN, "service_date": "2026-03-01", "odometer_km": 12.5, "category": "repair",
         "work_codes": {"code": "OIL_CHANGE"}},
        {},
        {"vin": NEW_VIN, "service_date": "2026-03-01", "odometer_km": 30_000, "category": "repair",
         "work_codes": ["OIL_CHANGE"], "colour": "red"},
    ]
    body = report(send(falcon_client, falcon, json.dumps(payload), content_type="application/json"))

    assert (body["total_rows"], body["valid_rows"], body["invalid_rows"]) == (5, 1, 4)
    assert errors_by_row(body) == {
        1: {(None, "invalid_row")},
        2: {("vin", "invalid_type"), ("service_date", "invalid_type"), ("odometer_km", "invalid_number"),
            ("category", "invalid_type"), ("work_codes", "invalid_type"), ("notes", "invalid_type")},
        3: {("odometer_km", "invalid_number"), ("work_codes", "invalid_type")},
        4: {("vin", "required"), ("service_date", "required"), ("odometer_km", "required"), ("category", "required"),
            ("work_codes", "required")},
        5: set(),
    }
    [warning] = body["warnings"]
    assert "colour" in warning


def test_row_errors_carry_row_numbers_fields_and_codes(falcon_client: TestClient, falcon) -> None:
    future = (uae_today() + timedelta(days=2)).isoformat()
    eleven_codes = ";".join(["OIL_CHANGE", "AIR_FILTER", "CABIN_FILTER", "AC_SERVICE", "BATTERY_REPLACE",
                             "TYRE_REPLACE", "TYRE_ROTATION", "WHEEL_ALIGNMENT", "BRAKE_PADS", "BRAKE_DISCS", "COOLANT"])
    text = csv_text(
        f"{NEW_VIN},2026-03-01,30000,maintenance,OIL_CHANGE,",  # 1 fine
        "ABC,2026-03-01,30000,maintenance,OIL_CHANGE,",  # 2
        f"{NEW_VIN},,30001,tuning,OIL_CHANGE,",  # 3
        "",  # 4: a blank line is skipped but still numbered, so numbers match the spreadsheet
        f"{NEW_VIN},31/02/2026,30002,maintenance,OIL_CHANGE,",  # 5
        f"{NEW_VIN},03/25/2026,30003,maintenance,OIL_CHANGE,",  # 6: month first is not accepted
        f"{NEW_VIN},2026-03-01,12.5,maintenance,OIL_CHANGE,",  # 7
        f'{NEW_VIN},2026-03-01,"2,000,001",maintenance,OIL_CHANGE,',  # 8
        f"{NEW_VIN},2026-03-01,30004,maintenance,WINDSCREEN;OIL_CHANGE,",  # 9
        f"{NEW_VIN},2026-03-01,30005,maintenance,OIL_CHANGE;OIL_CHANGE,",  # 10
        f"{NEW_VIN},{future},30006,maintenance,OIL_CHANGE,",  # 11
        f"{NEW_VIN},2026-03-01,30007,maintenance,OIL_CHANGE,{'x' * 1001}",  # 12
        ",2026-03-01,,maintenance, ; ,",  # 13
        f'{NEW_VIN},2026-03-01,"88,30",maintenance,OIL_CHANGE,',  # 14
        f"{NEW_VIN},2026-03-01,-5,maintenance,OIL_CHANGE,",  # 15
        f"{NEW_VIN},2026-03-01,30008,maintenance,{eleven_codes},",  # 16
        f"{NEW_VIN},2026-03-01,99999999999999999999,maintenance,OIL_CHANGE,",  # 17
        f"   ,2026-03-01,30009,  ,OIL_CHANGE,",  # 18: spaces only count as blank
    )

    body = report(send(falcon_client, falcon, text))

    assert (body["total_rows"], body["valid_rows"], body["invalid_rows"]) == (17, 1, 16)
    assert errors_by_row(body) == {
        1: set(),
        2: {("vin", "invalid_vin")},
        3: {("service_date", "required"), ("category", "invalid_category")},
        5: {("service_date", "invalid_date")},
        6: {("service_date", "invalid_date")},
        7: {("odometer_km", "invalid_number")},
        8: {("odometer_km", "out_of_range")},
        9: {("work_codes", "invalid_work_code")},
        10: {("work_codes", "invalid_work_code")},
        11: {("service_date", "future_date")},
        12: {("notes", "too_long")},
        13: {("vin", "required"), ("odometer_km", "required"), ("work_codes", "required")},
        14: {("odometer_km", "invalid_number")},
        15: {("odometer_km", "invalid_number")},
        16: {("work_codes", "invalid_work_code")},
        17: {("odometer_km", "invalid_number")},
        18: {("vin", "required"), ("category", "required")},
    }
    rows = {row["row"]: row for row in body["rows"]}
    assert all(row["status"] == "error" and not row["will_be_flagged"] for n, row in rows.items() if n != 1)
    assert rows[1]["status"] == "ok"
    assert all(error["message"] for row in body["rows"] for error in row["errors"])
    assert "WINDSCREEN" in rows[9]["errors"][0]["message"]
    # Fields with an error come back empty; the others keep their cleaned value.
    assert (rows[3]["vin"], rows[3]["service_date"], rows[3]["odometer_km"], rows[3]["category"]) == (
        NEW_VIN, None, 30_001, None,
    )
    assert rows[3]["work_codes"] == ["OIL_CHANGE"]
    assert rows[8]["odometer_km"] is None
    assert rows[9]["work_codes"] == []
    assert rows[2]["vin"] is None


def test_duplicate_rows_in_one_file_are_errors(falcon_client: TestClient, falcon) -> None:
    text = csv_text(
        f"{NEW_VIN},2026-03-01,30000,maintenance,OIL_CHANGE,",
        f"{OTHER_VIN},2026-03-01,30000,maintenance,OIL_CHANGE,",  # another vehicle: fine
        'wdb-2030461a123456,01/03/2026,"30,000",repair,BRAKE_PADS,',  # row 1 again, written differently
        f"{NEW_VIN},2026-03-01,30000,maintenance,OIL_CHANGE,",
    )
    body = report(send(falcon_client, falcon, text))
    assert errors_by_row(body) == {1: set(), 2: set(), 3: {(None, "duplicate_in_file")}, 4: {(None, "duplicate_in_file")}}
    assert "row 1" in body["rows"][2]["errors"][0]["message"]


def test_rows_this_organization_already_recorded_are_errors(falcon_client: TestClient, falcon, data) -> None:
    text = csv_text(
        f"{CRUISER},2026-01-10,20000,maintenance,TYRE_ROTATION,",  # Falcon's January record
        f"{PATROL},14/02/2026,\"88,300\",maintenance,AC_SERVICE,",  # a corrected original still counts
        f"{CAMRY},2026-04-01,40500,repair,ENGINE_REPAIR,",  # Oasis's record, not Falcon's
    )
    body = report(send(falcon_client, falcon, text))
    assert errors_by_row(body) == {1: {(None, "already_recorded")}, 2: {(None, "already_recorded")}, 3: set()}

    other_category = csv_text(f"{CRUISER},2026-01-10,20000,repair,BRAKE_PADS,")
    assert report(send(falcon_client, falcon, other_category))["valid_rows"] == 1


def flag_file(*, with_invalid_row: bool) -> str:
    rows = [
        f"{NEW_VIN},2026-02-10,40000,maintenance,OIL_CHANGE,rollback",  # below the stored 50,000
        f"{NEW_VIN},2026-03-01,60000,maintenance,OIL_CHANGE,fits",
        f"{NEW_VIN},2026-02-01,70000,maintenance,OIL_CHANGE,back-dated",  # above later readings in this file
        f"{NEW_VIN},2026-04-01,90000,tuning,OIL_CHANGE,invalid",  # ignored: would make the next row a rollback
        f"{NEW_VIN},2026-05-01,80000,maintenance,OIL_CHANGE,fits",
        f"{OTHER_VIN},2026-01-05,1000,maintenance,OIL_CHANGE,new vehicle",
    ]
    if not with_invalid_row:
        del rows[3]
    return csv_text(*rows)


@pytest.fixture
def stored_50000(db: Session, falcon: Organization, data) -> None:
    """NEW_VIN already has a 50,000 km record from 10 January (committed, like real history)."""
    staff = db.scalar(select(User).where(User.email == "khalid@example.ae"))
    add_record(db, add_vehicle(db, NEW_VIN), falcon, staff, service_date=date(2026, 1, 10), odometer_km=50_000)
    db.commit()


def test_dry_run_predicts_mileage_flags_against_history_and_earlier_rows(
    falcon_client: TestClient, falcon, stored_50000
) -> None:
    body = report(send(falcon_client, falcon, flag_file(with_invalid_row=True)))
    assert [row["will_be_flagged"] for row in body["rows"]] == [True, False, True, False, False, False]
    assert [row["status"] for row in body["rows"]] == ["ok", "ok", "ok", "error", "ok", "ok"]
    assert (body["valid_rows"], body["invalid_rows"], body["flagged_rows"]) == (5, 1, 2)


def test_a_500_row_file_is_accepted(falcon_client: TestClient, falcon) -> None:
    rows = [f"{NEW_VIN},2026-01-01,{n},maintenance,OIL_CHANGE," for n in range(MAX_IMPORT_ROWS)]
    body = report(send(falcon_client, falcon, csv_text(*rows)))
    assert (body["total_rows"], body["valid_rows"], body["flagged_rows"]) == (500, 500, 0)


# --- import: file-level errors ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "content_type",
    ["text/plain", "application/xml", "multipart/form-data; boundary=x", "application/x-www-form-urlencoded",
     "application/vnd.ms-excel", None],
)
def test_other_content_types_are_415(falcon_client: TestClient, falcon, content_type) -> None:
    response = send(falcon_client, falcon, csv_text(VALID_ROW), content_type=content_type)
    assert error_code(response, 415) == "unsupported_media_type"


@pytest.mark.parametrize("content_type", ["text/csv; charset=utf-8", "TEXT/CSV", "text/csv;charset=UTF-8"])
def test_csv_content_type_parameters_and_case_are_accepted(falcon_client: TestClient, falcon, content_type) -> None:
    assert report(send(falcon_client, falcon, csv_text(VALID_ROW), content_type=content_type))["valid_rows"] == 1


def test_json_content_type_with_charset_is_accepted(falcon_client: TestClient, falcon) -> None:
    payload = json.dumps([{"vin": NEW_VIN, "service_date": "2026-03-01", "odometer_km": 1, "category": "repair",
                           "work_codes": ["OIL_CHANGE"]}])
    body = report(send(falcon_client, falcon, payload, content_type="application/json; charset=utf-8"))
    assert body["format"] == "json"


def test_a_file_over_512_kb_is_413(falcon_client: TestClient, falcon) -> None:
    body = csv_text(VALID_ROW).encode() + b"\n" * MAX_IMPORT_BYTES
    assert error_code(send(falcon_client, falcon, body), 413) == "payload_too_large"


def test_a_file_over_512_kb_is_413_without_a_content_length(falcon_client: TestClient, falcon) -> None:
    chunks = iter([csv_text(VALID_ROW).encode()] + [b"\n" * 65_536] * 9)
    response = falcon_client.post(
        import_url(falcon), content=chunks, headers={**csrf(falcon_client), "Content-Type": "text/csv"}
    )
    assert "content-length" not in response.request.headers
    assert error_code(response, 413) == "payload_too_large"


def test_a_content_length_that_lies_does_not_lift_the_limit(falcon_client: TestClient, falcon) -> None:
    response = send(falcon_client, falcon, b"\n" * (MAX_IMPORT_BYTES + 1), headers={"Content-Length": "10"})
    assert response.request.headers["content-length"] == "10"
    assert error_code(response, 413) == "payload_too_large"


def test_a_file_of_exactly_512_kb_is_read(falcon_client: TestClient, falcon) -> None:
    head = csv_text(VALID_ROW).encode()
    body = head + b"\n" * (MAX_IMPORT_BYTES - len(head))
    assert len(body) == MAX_IMPORT_BYTES == 512 * 1024
    assert report(send(falcon_client, falcon, body))["total_rows"] == 1


@pytest.mark.parametrize(
    "body",
    [
        "vin,notes\r\nX,Garage é\r\n".encode("latin-1"),
        HEADER.encode("utf-16"),  # with a BOM
        HEADER.encode("utf-16-le"),  # without: valid UTF-8 bytes, but full of NUL characters
        b"vin,service_date\x00\r\n",
    ],
)
def test_files_that_are_not_utf8_text_are_rejected(falcon_client: TestClient, falcon, body: bytes) -> None:
    response = send(falcon_client, falcon, body)
    assert error_code(response) == "invalid_encoding"
    assert "UTF-8" in response.json()["error"]["message"]


@pytest.mark.parametrize(
    ("body", "content_type"),
    [
        (b"", "text/csv"),
        (b"\xef\xbb\xbf", "text/csv"),
        (b"  \r\n\r\n", "text/csv"),
        (HEADER + "\r\n", "text/csv"),  # a header and no records
        (HEADER + "\r\n,,,,,\r\n\r\n", "text/csv"),
        (b"", "application/json"),
        ("[]", "application/json"),
        ('{"records": []}', "application/json"),
    ],
)
def test_empty_files_are_rejected(falcon_client: TestClient, falcon, body, content_type: str) -> None:
    assert error_code(send(falcon_client, falcon, body, content_type=content_type)) == "empty_file"


def test_missing_required_columns_are_listed(falcon_client: TestClient, falcon) -> None:
    response = send(falcon_client, falcon, csv_text(f"{NEW_VIN},2026-03-01,1,", header="VIN,service_date,odometer_km,notes"))
    assert error_code(response) == "missing_columns"
    message = response.json()["error"]["message"]
    assert "category" in message and "work_codes" in message


def test_a_file_without_a_header_row_is_missing_columns(falcon_client: TestClient, falcon) -> None:
    response = send(falcon_client, falcon, VALID_ROW + "\r\n" + VALID_ROW + "\r\n")
    assert error_code(response) == "missing_columns"


def test_a_column_named_twice_is_rejected(falcon_client: TestClient, falcon) -> None:
    response = send(falcon_client, falcon, csv_text(VALID_ROW + f",{OTHER_VIN}", header=HEADER + ",VIN"))
    assert error_code(response) == "duplicate_columns"
    assert "vin" in response.json()["error"]["message"]


def test_a_huge_header_is_handled_quickly(falcon_client: TestClient, falcon) -> None:
    header = ",".join(["vin"] * 100_000)  # 400 KB of one repeated column name
    assert error_code(send(falcon_client, falcon, header + "\r\n")) == "duplicate_columns"
    header = ",".join(f"c{n}" for n in range(60_000)) + ",vin,service_date,odometer_km,category,work_codes"
    row = "," * 60_000 + VALID_ROW.rsplit(",", 1)[0]
    body = report(send(falcon_client, falcon, header + "\r\n" + row + "\r\n"))
    assert body["valid_rows"] == 1
    assert "and 59990 more" in body["warnings"][0]


def test_more_than_500_rows_is_rejected(falcon_client: TestClient, falcon) -> None:
    rows = [f"{NEW_VIN},2026-01-01,{n},maintenance,OIL_CHANGE," for n in range(MAX_IMPORT_ROWS + 1)]
    assert error_code(send(falcon_client, falcon, csv_text(*rows))) == "too_many_rows"
    records = [{"vin": NEW_VIN, "service_date": "2026-01-01", "odometer_km": n, "category": "repair",
                "work_codes": ["OIL_CHANGE"]} for n in range(MAX_IMPORT_ROWS + 1)]
    response = send(falcon_client, falcon, json.dumps(records), content_type="application/json")
    assert error_code(response) == "too_many_rows"


@pytest.mark.parametrize(
    "body",
    ["{not json", "42", '"text"', '{"records": "x"}', '{"data": []}', pytest.param("[" * 100_000, id="deep"), "[1e999, 1"],
)
def test_malformed_json_is_rejected(falcon_client: TestClient, falcon, body: str) -> None:
    assert error_code(send(falcon_client, falcon, body, content_type="application/json")) == "invalid_json"


@pytest.mark.parametrize("bad", [f'{NEW_VIN},2026-03-01,1,repair,"OIL_CHANGE', f'{NEW_VIN},2026-03-01,1,repair,"OIL"X'])
def test_malformed_csv_quoting_is_rejected(falcon_client: TestClient, falcon, bad: str) -> None:
    text = HEADER.rsplit(",", 1)[0] + "\r\n" + bad
    assert error_code(send(falcon_client, falcon, text)) == "invalid_csv"


# --- import: commit --------------------------------------------------------------------------------------------


def test_commit_imports_every_row_with_the_predicted_flags(
    falcon_client: TestClient, db: Session, falcon, stored_50000
) -> None:
    text = flag_file(with_invalid_row=False)
    preview = report(send(falcon_client, falcon, text))
    received: list[tuple[str, dict]] = []
    unsubscribe = events.subscribe(lambda event_type, payload: received.append((event_type, payload)))
    try:
        response = send(falcon_client, falcon, text, dry_run=False)
    finally:
        unsubscribe()

    body = report(response, 201)
    assert set(body) == {"dry_run", "imported", "flagged", "record_ids"}
    assert (body["dry_run"], body["imported"], body["flagged"]) == (False, 5, 2)
    records = [db.get(ServiceRecord, uuid.UUID(record_id)) for record_id in body["record_ids"]]
    assert [record.is_mileage_flagged for record in records] == [row["will_be_flagged"] for row in preview["rows"]]
    assert [record.odometer_km for record in records] == [40_000, 60_000, 70_000, 80_000, 1_000]  # file order
    assert [record.notes for record in records] == ["rollback", "fits", "back-dated", "fits", "new vehicle"]
    assert all(
        (r.organization_id, r.organization_name, r.staff_name, r.category, r.work_codes, r.corrects_record_id)
        == (falcon.id, "Falcon Bay Auto Care", "Arjun Nair", RecordCategory.MAINTENANCE, ["OIL_CHANGE"], None)
        for r in records
    )
    assert db.scalar(select(Vehicle).where(Vehicle.vin == OTHER_VIN)) is not None  # first record creates it

    assert [event_type for event_type, _ in received] == ["record.added"] * 5
    assert received[0][1] == {
        "vin": NEW_VIN, "record_id": body["record_ids"][0], "service_date": "2026-02-10",
        "is_mileage_flagged": True, "corrects_record_id": None,
    }
    assert [payload["record_id"] for _, payload in received] == body["record_ids"]

    audit = db.scalar(select(AuditEvent).where(AuditEvent.action == "records.imported"))
    assert (audit.actor_label, audit.target_type, audit.target_id) == ("arjun@example.ae", "organization", str(falcon.id))
    assert audit.details == {"count": 5, "flagged": 2, "format": "csv"}


def test_commit_of_json_works_too(falcon_client: TestClient, db: Session, falcon) -> None:
    payload = {"records": [{"vin": NEW_VIN, "service_date": "2026-03-01", "odometer_km": 30_000,
                            "category": "repair", "work_codes": "BRAKE_PADS", "notes": "  Squeaking  "}]}
    body = report(send(falcon_client, falcon, json.dumps(payload), content_type="application/json", dry_run=False), 201)
    record = db.get(ServiceRecord, uuid.UUID(body["record_ids"][0]))
    assert (record.category, record.work_codes, record.notes) == (RecordCategory.REPAIR, ["BRAKE_PADS"], "Squeaking")
    audit = db.scalar(select(AuditEvent).where(AuditEvent.action == "records.imported"))
    assert audit.details == {"count": 1, "flagged": 0, "format": "json"}


def test_only_csv_notes_lose_the_export_formula_guard(falcon_client: TestClient, db: Session, falcon) -> None:
    text = csv_text(f"{NEW_VIN},2026-03-01,30000,repair,BRAKE_PADS,'=1+1", f"{OTHER_VIN},2026-03-01,1,repair,BRAKE_PADS,'quoted'")
    csv_ids = report(send(falcon_client, falcon, text, dry_run=False), 201)["record_ids"]
    payload = [{"vin": THIRD_VIN, "service_date": "2026-03-01", "odometer_km": 1, "category": "repair",
                "work_codes": ["BRAKE_PADS"], "notes": "'=1+1"}]
    json_ids = report(send(falcon_client, falcon, json.dumps(payload), content_type="application/json", dry_run=False), 201)["record_ids"]
    notes = [db.get(ServiceRecord, uuid.UUID(record_id)).notes for record_id in csv_ids + json_ids]
    assert notes == ["=1+1", "'quoted'", "'=1+1"]  # JSON exports carry no guard, so JSON notes are kept as sent


def test_commit_with_any_invalid_row_writes_nothing(falcon_client: TestClient, db: Session, falcon, data) -> None:
    before = record_count(db)
    text = csv_text(VALID_ROW, "ABC,2026-03-01,30000,maintenance,OIL_CHANGE,")
    received: list[str] = []
    unsubscribe = events.subscribe(lambda event_type, payload: received.append(event_type))
    try:
        response = send(falcon_client, falcon, text, dry_run=False)
    finally:
        unsubscribe()

    assert error_code(response) == "import_invalid"
    error = response.json()["error"]
    assert "Nothing was imported" in error["message"]
    details = error["details"]
    assert (details["dry_run"], details["total_rows"], details["valid_rows"], details["invalid_rows"]) == (False, 2, 1, 1)
    assert errors_by_row(details) == {1: set(), 2: {("vin", "invalid_vin")}}
    assert record_count(db) == before
    assert db.scalar(select(Vehicle).where(Vehicle.vin == NEW_VIN)) is None
    assert received == []
    assert db.scalar(select(AuditEvent).where(AuditEvent.action == "records.imported")) is None


def test_commit_stopped_by_an_existing_record_leaves_no_vehicles_behind(
    falcon_client: TestClient, db: Session, falcon, data
) -> None:
    before = record_count(db)
    text = csv_text(f"{OTHER_VIN},2026-03-01,1000,maintenance,OIL_CHANGE,", f"{CRUISER},2026-01-10,20000,maintenance,OIL_CHANGE,")
    response = send(falcon_client, falcon, text, dry_run=False)
    assert error_code(response) == "import_invalid"
    assert errors_by_row(response.json()["error"]["details"]) == {1: set(), 2: {(None, "already_recorded")}}
    assert record_count(db) == before
    assert db.scalar(select(Vehicle).where(Vehicle.vin == OTHER_VIN)) is None  # locked for the attempt, rolled back


def test_importing_the_same_file_twice_is_stopped(falcon_client: TestClient, falcon) -> None:
    text = csv_text(VALID_ROW)
    report(send(falcon_client, falcon, text, dry_run=False), 201)
    again = send(falcon_client, falcon, text, dry_run=False)
    assert error_code(again) == "import_invalid"
    assert errors_by_row(again.json()["error"]["details"]) == {1: {(None, "already_recorded")}}


def test_dry_run_must_be_a_boolean(falcon_client: TestClient, falcon) -> None:
    assert error_code(send(falcon_client, falcon, csv_text(VALID_ROW), dry_run="maybe")) == "validation_error"


def test_file_errors_also_stop_a_commit(falcon_client: TestClient, db: Session, falcon) -> None:
    before = record_count(db)
    assert error_code(send(falcon_client, falcon, HEADER + "\r\n", dry_run=False)) == "empty_file"
    assert error_code(send(falcon_client, falcon, csv_text(VALID_ROW), content_type="text/plain", dry_run=False), 415)
    assert record_count(db) == before


# --- import: access ----------------------------------------------------------------------------------------------


def test_import_requires_sign_in(client: TestClient, falcon) -> None:
    assert error_code(send(client, falcon, csv_text(VALID_ROW)), 401) == "not_authenticated"


def test_import_requires_the_csrf_header(falcon_client: TestClient, falcon) -> None:
    response = falcon_client.post(
        import_url(falcon), content=csv_text(VALID_ROW).encode(), headers={"Content-Type": "text/csv"}
    )
    assert error_code(response, 403) == "csrf_failed"


@pytest.mark.parametrize("role", [UserRole.CONSUMER, UserRole.PLATFORM_ADMIN])
def test_consumers_and_platform_admins_cannot_import(client: TestClient, db: Session, falcon, role) -> None:
    add_user(db, "someone@example.ae", role=role)
    login(client, "someone@example.ae")
    assert error_code(send(client, falcon, csv_text(VALID_ROW)), 403) == "forbidden"


def test_staff_cannot_import_into_another_organization(client: TestClient, falcon, data) -> None:
    login(client, "fatima@example.ae")
    assert error_code(send(client, falcon, csv_text(VALID_ROW)), 403) == "forbidden"


def test_permission_is_checked_before_the_file_is_read(client: TestClient, falcon, data) -> None:
    login(client, "fatima@example.ae")
    assert error_code(send(client, falcon, csv_text(VALID_ROW), content_type="text/plain"), 403) == "forbidden"
    assert error_code(send(client, falcon, b"\n" * (MAX_IMPORT_BYTES + 1)), 403) == "forbidden"


@pytest.mark.parametrize("org_status", [OrganizationStatus.PENDING, OrganizationStatus.REJECTED])
def test_organizations_that_are_not_approved_cannot_import(client: TestClient, db: Session, org_status) -> None:
    org = make_org(db, name="Sand Dune Garage", status=org_status)
    user = add_user(db, "omar@example.ae")
    add_member(db, org, user, MemberRole.ENTITY_ADMIN)
    login(client, user.email)
    assert error_code(send(client, org, csv_text(VALID_ROW)), 403) == "organization_not_approved"


def test_inactive_member_cannot_import(client: TestClient, db: Session, falcon) -> None:
    user = add_user(db, "former@example.ae")
    add_member(db, falcon, user, MemberRole.ENTITY_STAFF).status = MemberStatus.INACTIVE
    db.flush()
    login(client, user.email)
    assert error_code(send(client, falcon, csv_text(VALID_ROW)), 403) == "forbidden"


def test_entity_admin_can_import(client: TestClient, falcon, data) -> None:
    login(client, "khalid@example.ae")
    assert report(send(client, falcon, csv_text(VALID_ROW), dry_run=False), 201)["imported"] == 1


def test_import_into_an_unknown_organization_is_404(falcon_client: TestClient) -> None:
    assert error_code(send(falcon_client, uuid.uuid4(), csv_text(VALID_ROW)), 404) == "organization_not_found"


# --- export -> import round trip ---------------------------------------------------------------------------------


def test_a_csv_export_imports_into_another_organization(client: TestClient, db: Session, falcon, oasis, data) -> None:
    login(client, "arjun@example.ae")
    exported = client.get(export_url(falcon), params={"format": "csv"})
    assert exported.status_code == 200
    login(client, "fatima@example.ae")

    preview = report(send(client, oasis, exported.content))
    assert (preview["total_rows"], preview["valid_rows"], preview["invalid_rows"]) == (4, 4, 0)
    [warning] = preview["warnings"]  # the export's extra columns
    assert "record_id" in warning and "staff_name" in warning

    result = report(send(client, oasis, exported.content, dry_run=False), 201)
    assert result["imported"] == 4
    imported = [db.get(ServiceRecord, uuid.UUID(record_id)) for record_id in result["record_ids"]]
    originals = [data[name] for name in FALCON_ORDER]
    for new, old in zip(imported, originals, strict=True):
        assert (new.vehicle_id, new.service_date, new.odometer_km, new.category, new.work_codes, new.notes) == (
            old.vehicle_id, old.service_date, old.odometer_km, old.category, old.work_codes, old.notes,
        )
        assert new.organization_id == oasis.id and new.staff_name == "Fatima Al Zaabi"
    # Commas, quotes, line breaks, Arabic and the formula guard all survived the trip.
    assert {record.notes for record in imported} == {FORMULA_NOTES, ARABIC_NOTES, TRICKY_NOTES, None}

    again = report(send(client, oasis, exported.content))
    assert {code for row in errors_by_row(again).values() for _, code in row} == {"already_recorded"}


def test_an_organization_re_importing_its_own_export_is_stopped(falcon_client: TestClient, falcon, data) -> None:
    exported = falcon_client.get(export_url(falcon), params={"format": "csv"})
    body = report(send(falcon_client, falcon, exported.content))
    assert body["invalid_rows"] == 4
    assert all(row == {(None, "already_recorded")} for row in errors_by_row(body).values())


def test_a_filtered_json_export_imports_as_json(client: TestClient, db: Session, falcon, oasis, data) -> None:
    login(client, "arjun@example.ae")
    exported = client.get(export_url(falcon), params={"format": "json", "category": "repair"})
    login(client, "fatima@example.ae")

    preview = report(send(client, oasis, exported.content, content_type="application/json"))
    assert (preview["total_rows"], preview["valid_rows"]) == (1, 1)
    assert preview["rows"][0]["work_codes"] == ["BRAKE_PADS"]
    result = report(send(client, oasis, exported.content, content_type="application/json", dry_run=False), 201)
    assert db.get(ServiceRecord, uuid.UUID(result["record_ids"][0])).notes == FORMULA_NOTES
