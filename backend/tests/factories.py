import itertools
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    CorrectionReason,
    Organization,
    OrganizationKind,
    OrganizationStatus,
    RecordCategory,
    ServiceRecord,
    User,
    UserRole,
    Vehicle,
)

_sequence = itertools.count(1)
_AUTO: Any = object()


def make_user(db: Session, *, full_name: str = "Test Staff", role: UserRole = UserRole.CONSUMER) -> User:
    user = User(email=f"user{next(_sequence)}@test.sijil", password_hash="not-a-real-hash", full_name=full_name, role=role)
    db.add(user)
    db.flush()
    return user


def make_org(db: Session, *, name: str = "Test Garage", status: OrganizationStatus = OrganizationStatus.APPROVED) -> Organization:
    org = Organization(
        name=name, kind=OrganizationKind.WORKSHOP, registration_number=f"TEST-{next(_sequence):05d}", status=status,
        emirate="Dubai",
        rejection_reason="Trade licence could not be verified." if status == OrganizationStatus.REJECTED else None,
    )
    db.add(org)
    db.flush()
    return org


def make_vehicle(db: Session, vin: str = "JTDBR32E720123456") -> Vehicle:
    vehicle = Vehicle(vin=vin, make="Toyota", model="Corolla", model_year=2019)
    db.add(vehicle)
    db.flush()
    return vehicle


def make_record(
    db: Session,
    vehicle: Vehicle,
    org: Organization,
    staff: User,
    *,
    odometer_km: int = 10_000,
    service_date: date = date(2026, 1, 15),
    category: RecordCategory = RecordCategory.MAINTENANCE,
    flagged: bool = False,
    corrects: ServiceRecord | None = None,
    reason: CorrectionReason | None = _AUTO,
    notes: str | None = None,
) -> ServiceRecord:
    """`reason` defaults to ODOMETER for a correction and None otherwise; pass it to build an invalid row."""
    if reason is _AUTO:
        reason = CorrectionReason.ODOMETER if corrects else None
    record = ServiceRecord(
        vehicle_id=vehicle.id,
        organization_id=org.id,
        staff_id=staff.id,
        organization_name=org.name,
        staff_name=staff.full_name,
        category=category,
        work_codes=["OIL_CHANGE"],
        odometer_km=odometer_km,
        service_date=service_date,
        is_mileage_flagged=flagged,
        corrects_record_id=corrects.id if corrects else None,
        correction_reason=reason,
        notes=notes,
    )
    db.add(record)
    db.flush()
    return record
