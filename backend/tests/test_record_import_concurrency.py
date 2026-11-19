"""Two workshops import files that share vehicles at the same moment. These tests commit for real (each thread
needs its own connection), so they create uniquely named rows and remove them afterwards."""

import threading
import time
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, delete, func, select, text
from sqlalchemy.orm import Session

from app.models import (
    MemberRole,
    Organization,
    OrganizationKind,
    OrganizationMember,
    OrganizationStatus,
    ServiceRecord,
    User,
    Vehicle,
)
from app.services import record_import

VINS = ("JTMHX01J5M4066661", "JTMHX01J5M4066662", "JTMHX01J5M4066663")


@pytest.fixture
def two_workshops(engine: Engine) -> Iterator[list[tuple[uuid.UUID, uuid.UUID]]]:
    """Committed: two approved workshops with one staff member each."""
    pairs: list[tuple[uuid.UUID, uuid.UUID]] = []
    with Session(engine) as session:
        for n in (1, 2):
            org = Organization(
                name=f"Import Workshop {n}", kind=OrganizationKind.WORKSHOP,
                registration_number=f"IMP-{uuid.uuid4().hex[:8]}", status=OrganizationStatus.APPROVED,
            )
            staff = User(email=f"import{n}.{uuid.uuid4().hex[:8]}@example.ae", password_hash="x", full_name=f"Importer {n}")
            session.add_all([org, staff])
            session.flush()
            session.add(OrganizationMember(organization_id=org.id, user_id=staff.id, role=MemberRole.ENTITY_STAFF))
            pairs.append((org.id, staff.id))
        session.commit()
    yield pairs
    with engine.begin() as connection:  # history is append-only; lift the trigger only to clean up test rows
        vehicle_ids = connection.scalars(select(Vehicle.id).where(Vehicle.vin.in_(VINS))).all()
        connection.execute(text("ALTER TABLE service_records DISABLE TRIGGER service_records_append_only"))
        connection.execute(delete(ServiceRecord).where(ServiceRecord.vehicle_id.in_(vehicle_ids)))
        connection.execute(text("ALTER TABLE service_records ENABLE TRIGGER service_records_append_only"))
        connection.execute(delete(Vehicle).where(Vehicle.id.in_(vehicle_ids)))
        org_ids, staff_ids = [org for org, _ in pairs], [staff for _, staff in pairs]
        connection.execute(delete(OrganizationMember).where(OrganizationMember.organization_id.in_(org_ids)))
        connection.execute(delete(User).where(User.id.in_(staff_ids)))
        connection.execute(delete(Organization).where(Organization.id.in_(org_ids)))


def test_imports_listing_shared_vehicles_in_opposite_orders_do_not_deadlock(
    engine: Engine, two_workshops, monkeypatch
) -> None:
    # Hold every vehicle lock a moment, so two imports that locked in file order would each hold a vehicle the
    # other needs. Locking in VIN order makes the second import wait for the first instead.
    lock = record_import.lock_vehicle

    def slow_lock(db: Session, vin: str) -> Vehicle:
        vehicle = lock(db, vin)
        time.sleep(0.3)
        return vehicle

    monkeypatch.setattr(record_import, "lock_vehicle", slow_lock)
    start = threading.Barrier(2)
    imported: dict[int, int] = {}
    errors: list[BaseException] = []

    def run(slot: int, vins: tuple[str, ...]) -> None:
        org_id, staff_id = two_workshops[slot]
        rows = [f"{vin},2026-03-0{slot + 1},{10_000 * (slot + 1) + n},maintenance,OIL_CHANGE," for n, vin in enumerate(vins)]
        csv_text = "\r\n".join(["vin,service_date,odometer_km,category,work_codes,notes", *rows])
        try:
            with Session(engine) as session:
                org, staff = session.get(Organization, org_id), session.get(User, staff_id)
                parsed = record_import.parse_import("csv", csv_text)
                start.wait()
                saved = record_import.save_import(session, organization=org, staff=staff, file=parsed)
                session.commit()
                imported[slot] = len(saved)
        except BaseException as exc:  # surface thread failures in the test
            errors.append(exc)

    threads = [threading.Thread(target=run, args=(0, VINS)), threading.Thread(target=run, args=(1, VINS[::-1]))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert errors == []
    assert imported == {0: 3, 1: 3}
    with Session(engine) as session:
        count = session.scalar(
            select(func.count())
            .select_from(ServiceRecord)
            .join(Vehicle, Vehicle.id == ServiceRecord.vehicle_id)
            .where(Vehicle.vin.in_(VINS))
        )
    assert count == 6
