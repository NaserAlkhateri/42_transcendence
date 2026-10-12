from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.db.session import get_db
from app.models import RecordCategory
from app.schemas.vehicle import TimelineRecord, VehicleSummary, VehicleTimeline
from app.services.timeline import TimelineFilters, get_vehicle_timeline
from app.services.vin import InvalidVinError, normalize_vin

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.get("/{vin}/timeline", response_model=VehicleTimeline)
def vehicle_timeline(
    vin: str,
    db: Annotated[Session, Depends(get_db)],
    category: RecordCategory | None = None,
    flagged: bool | None = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    order: Literal["asc", "desc"] = "desc",
) -> VehicleTimeline:
    """Consumer-safe service history for one VIN. Lower mileage readings are included and flagged, never hidden."""
    try:
        canonical_vin = normalize_vin(vin)
    except InvalidVinError as exc:
        raise ApiError(422, "invalid_vin", str(exc)) from exc
    if date_from is not None and date_to is not None and date_from > date_to:
        raise ApiError(422, "invalid_date_range", "'from' must be on or before 'to'.")

    vehicle, records = get_vehicle_timeline(
        db, canonical_vin, TimelineFilters(category, flagged, date_from, date_to, order)
    )
    return VehicleTimeline(
        vin=canonical_vin,
        vehicle=VehicleSummary.model_validate(vehicle) if vehicle else None,
        records=[TimelineRecord.model_validate(record) for record in records],
    )
