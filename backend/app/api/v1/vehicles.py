from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.time import uae_now
from app.db.session import get_db
from app.models import RecordCategory
from app.reports.pdf import render_vehicle_report
from app.schemas.vehicle import TimelineRecord, VehicleSummary, VehicleTimeline
from app.services.timeline import TimelineFilters, get_vehicle_timeline, has_history
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
    if vehicle is not None and not records and not has_history(db, vehicle):
        vehicle = None  # only watched so far: keep the "no history yet, offer Watch" contract
    return VehicleTimeline(
        vin=canonical_vin,
        vehicle=VehicleSummary.model_validate(vehicle) if vehicle else None,
        records=[TimelineRecord.model_validate(record) for record in records],
    )


@router.get(
    "/{vin}/report.pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "Bilingual (English/Arabic) PDF report"}},
)
def vehicle_report(vin: str, db: Annotated[Session, Depends(get_db)]) -> Response:
    """Consumer-safe PDF of the full history: vehicle facts, workshops, dates, readings, flags and corrections."""
    try:
        canonical_vin = normalize_vin(vin)
    except InvalidVinError as exc:
        raise ApiError(422, "invalid_vin", str(exc)) from exc
    vehicle, records = get_vehicle_timeline(db, canonical_vin, TimelineFilters())
    if vehicle is None or not records:
        raise ApiError(404, "no_history", "There is no service history for this VIN yet.")
    return Response(
        render_vehicle_report(vehicle, records, generated_at=uae_now()),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="sijil-report-{canonical_vin}.pdf"',
            "Cache-Control": "no-store",
        },
    )

