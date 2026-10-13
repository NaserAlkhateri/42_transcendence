"""Appending service records: one transaction per submission that locks the vehicle row, decides the
mileage flag against the effective history and inserts the record, so concurrent submissions for one VIN
are serialized and every flag is computed against everything committed before it."""

import uuid
from collections.abc import Iterable
from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import CorrectionReason, Organization, ServiceRecord, User, Vehicle
from app.schemas.records import RecordFields


def reading_is_inconsistent(history: Iterable[tuple[date, int]], service_date: date, odometer_km: int) -> bool:
    """True when the reading does not fit the effective history: lower than the highest reading dated on or
    before `service_date` (a rollback), or higher than a reading dated after it (a back-dated entry)."""
    readings = list(history)
    earlier = [km for day, km in readings if day <= service_date]
    later = [km for day, km in readings if day > service_date]
    return (bool(earlier) and odometer_km < max(earlier)) or (bool(later) and odometer_km > min(later))


def lock_vehicle(db: Session, vin: str) -> Vehicle:
    """Get or create the vehicle for a canonical VIN and hold its row lock until the transaction ends."""
    db.execute(pg_insert(Vehicle).values(id=uuid.uuid4(), vin=vin).on_conflict_do_nothing(index_elements=["vin"]))
    return db.scalars(select(Vehicle).where(Vehicle.vin == vin).with_for_update()).one()


def effective_readings(db: Session, vehicle_id: uuid.UUID, *, excluding: uuid.UUID | None = None) -> list[tuple[date, int]]:
    """(service_date, odometer_km) of the vehicle's records that no correction replaces. `excluding` drops a
    record about to be corrected, so the correction is compared with the history it will be part of."""
    corrected = select(ServiceRecord.corrects_record_id).where(ServiceRecord.corrects_record_id.is_not(None))
    query = select(ServiceRecord.service_date, ServiceRecord.odometer_km).where(
        ServiceRecord.vehicle_id == vehicle_id, ServiceRecord.id.not_in(corrected)
    )
    if excluding is not None:
        query = query.where(ServiceRecord.id != excluding)
    return [(row.service_date, row.odometer_km) for row in db.execute(query)]


def submit_record(db: Session, *, organization: Organization, staff: User, vin: str, fields: RecordFields) -> ServiceRecord:
    """Append a record (the caller commits). `vin` must already be canonical."""
    vehicle = lock_vehicle(db, vin)
    flagged = reading_is_inconsistent(effective_readings(db, vehicle.id), fields.service_date, fields.odometer_km)
    record = ServiceRecord(
        vehicle_id=vehicle.id,
        organization_id=organization.id,
        staff_id=staff.id,
        organization_name=organization.name,
        staff_name=staff.full_name,
        category=fields.category,
        work_codes=fields.work_codes,
        odometer_km=fields.odometer_km,
        service_date=fields.service_date,
        is_mileage_flagged=flagged,
        notes=fields.notes,
    )
    db.add(record)
    db.flush()
    return record


class AlreadyCorrectedError(Exception):
    """The record already has a correction: correct that correction instead."""


def submit_correction(
    db: Session, *, organization: Organization, staff: User, original: ServiceRecord, fields: RecordFields,
    reason: CorrectionReason,
) -> ServiceRecord:
    """Append a correction of `original` (the caller commits and has checked the organization owns it).
    The flag compares the corrected values with the history the correction joins, without the original."""
    vehicle = db.scalars(select(Vehicle).where(Vehicle.id == original.vehicle_id).with_for_update()).one()
    if db.scalar(select(ServiceRecord.id).where(ServiceRecord.corrects_record_id == original.id)) is not None:
        raise AlreadyCorrectedError
    history = effective_readings(db, vehicle.id, excluding=original.id)
    record = ServiceRecord(
        vehicle_id=vehicle.id,
        organization_id=organization.id,
        staff_id=staff.id,
        organization_name=organization.name,
        staff_name=staff.full_name,
        category=fields.category,
        work_codes=fields.work_codes,
        odometer_km=fields.odometer_km,
        service_date=fields.service_date,
        is_mileage_flagged=reading_is_inconsistent(history, fields.service_date, fields.odometer_km),
        notes=fields.notes,
        corrects_record_id=original.id,
        correction_reason=reason,
    )
    db.add(record)
    db.flush()
    return record

