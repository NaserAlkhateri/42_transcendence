from dataclasses import dataclass
from datetime import date
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RecordCategory, ServiceRecord, Vehicle


@dataclass(frozen=True)
class TimelineFilters:
    category: RecordCategory | None = None
    flagged: bool | None = None
    date_from: date | None = None
    date_to: date | None = None
    order: Literal["asc", "desc"] = "desc"


def get_vehicle_timeline(db: Session, vin: str, filters: TimelineFilters) -> tuple[Vehicle | None, list[ServiceRecord]]:
    """Return the vehicle (None if it was never recorded) and its filtered records, ordered by service date.
    `vin` must already be normalized."""
    vehicle = db.scalar(select(Vehicle).where(Vehicle.vin == vin))
    if vehicle is None:
        return None, []

    query = select(ServiceRecord).where(ServiceRecord.vehicle_id == vehicle.id)
    if filters.category is not None:
        query = query.where(ServiceRecord.category == filters.category)
    if filters.flagged is not None:
        query = query.where(ServiceRecord.is_mileage_flagged == filters.flagged)
    if filters.date_from is not None:
        query = query.where(ServiceRecord.service_date >= filters.date_from)
    if filters.date_to is not None:
        query = query.where(ServiceRecord.service_date <= filters.date_to)

    columns = (ServiceRecord.service_date, ServiceRecord.created_at, ServiceRecord.id)
    query = query.order_by(*(c.asc() if filters.order == "asc" else c.desc() for c in columns))
    return vehicle, list(db.scalars(query))
