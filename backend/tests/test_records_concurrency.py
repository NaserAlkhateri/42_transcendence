"""Two workshops submit for one VIN at the same moment. These tests commit for real (each thread needs its
own connection), so they create uniquely named rows and remove them afterwards."""

import threading
import time
import uuid
from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy import Engine, delete, select, text
from sqlalchemy.orm import Session

from app.models import (
    MemberRole,
    Organization,
    OrganizationKind,
    OrganizationMember,
    OrganizationStatus,
    RecordCategory,
    ServiceRecord,
    User,
    Vehicle,
)
from app.schemas.records import RecordFields
from app.services import records as records_service

VIN = "JTMHX01J5M4099999"


@pytest.fixture
def two_workshops(engine: Engine) -> Iterator[list[tuple[uuid.UUID, uuid.UUID]]]:
    """Committed: two approved workshops with one staff member each, and VIN with a 50,000 km record."""
    pairs: list[tuple[uuid.UUID, uuid.UUID]] = []
    with Session(engine) as session:
        for n in (1, 2):
            org = Organization(
                name=f"Race Workshop {n}", kind=OrganizationKind.WORKSHOP,
                registration_number=f"RACE-{uuid.uuid4().hex[:8]}", status=OrganizationStatus.APPROVED,
            )
            staff = User(email=f"race{n}.{uuid.uuid4().hex[:8]}@example.ae", password_hash="x", full_name=f"Racer {n}")
            session.add_all([org, staff])
            session.flush()
            session.add(OrganizationMember(organization_id=org.id, user_id=staff.id, role=MemberRole.ENTITY_STAFF))
            pairs.append((org.id, staff.id))
        org, staff = session.get(Organization, pairs[0][0]), session.get(User, pairs[0][1])
        records_service.submit_record(
            session, organization=org, staff=staff, vin=VIN,
            fields=RecordFields(category=RecordCategory.MAINTENANCE, work_codes=["OIL_CHANGE"], odometer_km=50_000,
                                service_date=date(2026, 1, 10)),
        )
        session.commit()
    yield pairs
    with engine.begin() as connection:  # history is append-only; lift the trigger only to clean up test rows
        connection.execute(text("ALTER TABLE service_records DISABLE TRIGGER service_records_append_only"))
        vehicle_id = connection.scalar(select(Vehicle.id).where(Vehicle.vin == VIN))
        connection.execute(delete(ServiceRecord).where(ServiceRecord.vehicle_id == vehicle_id))
        connection.execute(text("ALTER TABLE service_records ENABLE TRIGGER service_records_append_only"))
        connection.execute(delete(Vehicle).where(Vehicle.id == vehicle_id))
        org_ids, staff_ids = [org for org, _ in pairs], [staff for _, staff in pairs]
        connection.execute(delete(OrganizationMember).where(OrganizationMember.organization_id.in_(org_ids)))
        connection.execute(delete(User).where(User.id.in_(staff_ids)))
        connection.execute(delete(Organization).where(Organization.id.in_(org_ids)))


def test_simultaneous_submissions_see_each_other_and_flag_exactly_one(engine: Engine, two_workshops, monkeypatch) -> None:
    # Hold each transaction open after it has read the history, so without the row lock both would read the
    # same 50,000 km history, both pass, and neither would notice the other.
    read_history = records_service.effective_readings

    def slow_read(*args, **kwargs):
        rows = read_history(*args, **kwargs)
        time.sleep(0.4)
        return rows

    monkeypatch.setattr(records_service, "effective_readings", slow_read)
    start = threading.Barrier(2)
    flags: dict[int, bool] = {}
    errors: list[BaseException] = []

    def submit(slot: int, km: int, day: date) -> None:
        org_id, staff_id = two_workshops[slot]
        try:
            with Session(engine) as session:
                org, staff = session.get(Organization, org_id), session.get(User, staff_id)
                fields = RecordFields(category=RecordCategory.MAINTENANCE, work_codes=["OIL_CHANGE"], odometer_km=km, service_date=day)
                start.wait()
                record = records_service.submit_record(session, organization=org, staff=staff, vin=VIN, fields=fields)
                session.commit()
                flags[slot] = record.is_mileage_flagged
        except BaseException as exc:  # surface thread failures in the test
            errors.append(exc)

    # 60,000 on 1 Mar and 55,000 on 1 Apr cannot both be right: whichever commits second must be flagged.
    threads = [threading.Thread(target=submit, args=(0, 60_000, date(2026, 3, 1))),
               threading.Thread(target=submit, args=(1, 55_000, date(2026, 4, 1)))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert errors == []
    assert sorted(flags.values()) == [False, True]
    with Session(engine) as session:
        vehicle_id = session.scalar(select(Vehicle.id).where(Vehicle.vin == VIN))
        kms = session.scalars(select(ServiceRecord.odometer_km).where(ServiceRecord.vehicle_id == vehicle_id)).all()
    assert sorted(kms) == [50_000, 55_000, 60_000]  # no lost write


def test_first_record_for_a_new_vin_from_two_workshops_creates_one_vehicle(engine: Engine, two_workshops) -> None:
    new_vin = "JTMHX01J5M4088888"
    start = threading.Barrier(2)
    errors: list[BaseException] = []

    def submit(slot: int) -> None:
        org_id, staff_id = two_workshops[slot]
        try:
            with Session(engine) as session:
                org, staff = session.get(Organization, org_id), session.get(User, staff_id)
                fields = RecordFields(category=RecordCategory.MAINTENANCE, work_codes=["OIL_CHANGE"],
                                      odometer_km=10_000 + slot, service_date=date(2026, 2, 1))
                start.wait()
                records_service.submit_record(session, organization=org, staff=staff, vin=new_vin, fields=fields)
                session.commit()
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=submit, args=(slot,)) for slot in (0, 1)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    try:
        assert errors == []
        with Session(engine) as session:
            assert len(session.scalars(select(Vehicle).where(Vehicle.vin == new_vin)).all()) == 1
    finally:
        with engine.begin() as connection:
            vehicle_id = connection.scalar(select(Vehicle.id).where(Vehicle.vin == new_vin))
            connection.execute(text("ALTER TABLE service_records DISABLE TRIGGER service_records_append_only"))
            connection.execute(delete(ServiceRecord).where(ServiceRecord.vehicle_id == vehicle_id))
            connection.execute(text("ALTER TABLE service_records ENABLE TRIGGER service_records_append_only"))
            connection.execute(delete(Vehicle).where(Vehicle.id == vehicle_id))
