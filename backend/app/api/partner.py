"""Public partner API (NA-05), served at /api/partner/v1.

Partners (insurers, marketplaces) call it with an admin-issued key in the X-API-Key header. It is read-only for
vehicle history: no route here can create, change or delete a service record. PUT and DELETE act only on the
partner's own watchlist. Responses carry X-RateLimit-* headers; a burst over the limit gets 429."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.api_keys import SCOPE_VEHICLES_READ, SCOPE_WATCHES_MANAGE, PartnerKey, require_scope
from app.core.config import get_settings
from app.core.errors import ApiError
from app.db.session import get_db
from app.models import ApiKey, PartnerWatchlist, ServiceRecord, Vehicle
from app.schemas.partner import PartnerHistory, PartnerVehicle, WatchCreate, WatchList, WatchOut, WatchReplace
from app.schemas.vehicle import TimelineRecord
from app.services.timeline import TimelineFilters, get_vehicle_timeline
from app.services.vin import InvalidVinError, normalize_vin

PARTNER_PREFIX = "/api/partner/v1"

router = APIRouter(tags=["partner API"])

DbSession = Annotated[Session, Depends(get_db)]


def canonical_vin(raw: str) -> str:
    try:
        return normalize_vin(raw)
    except InvalidVinError as exc:
        raise ApiError(422, "invalid_vin", str(exc)) from exc


def vehicle_with_history(db: Session, raw_vin: str) -> tuple[str, Vehicle, list[ServiceRecord]]:
    vin = canonical_vin(raw_vin)
    vehicle, records = get_vehicle_timeline(db, vin, TimelineFilters(order="desc"))
    if vehicle is None or not records:  # unfiltered, so no records means no history (perhaps only watched)
        raise ApiError(404, "vehicle_not_found", "No history is recorded for this VIN yet. Watch it to hear about the first record.")
    return vin, vehicle, records


@router.get("/vehicles/{vin}", response_model=PartnerVehicle, summary="Vehicle summary")
def vehicle_summary(vin: str, key: PartnerKey, db: DbSession) -> PartnerVehicle:
    require_scope(key, SCOPE_VEHICLES_READ)
    canonical, vehicle, records = vehicle_with_history(db, vin)
    corrected = {r.corrects_record_id for r in records if r.corrects_record_id}
    effective = [r for r in records if r.id not in corrected]
    latest = max(effective, key=lambda r: (r.service_date, r.created_at)) if effective else None
    return PartnerVehicle(
        vin=canonical, make=vehicle.make, model=vehicle.model, model_year=vehicle.model_year,
        record_count=len(records),
        flagged_record_count=sum(r.is_mileage_flagged for r in records),
        correction_count=sum(r.corrects_record_id is not None for r in records),
        latest_service_date=latest.service_date if latest else None,
        latest_odometer_km=latest.odometer_km if latest else None,
        last_record_added_at=max((r.created_at for r in records), default=None),
    )


@router.get("/vehicles/{vin}/history", response_model=PartnerHistory, summary="Vehicle service history")
def vehicle_history(vin: str, key: PartnerKey, db: DbSession) -> PartnerHistory:
    """Every record, newest first. Lower mileage readings are included and flagged; corrections reference the
    record they replace."""
    require_scope(key, SCOPE_VEHICLES_READ)
    canonical, _, records = vehicle_with_history(db, vin)
    return PartnerHistory(vin=canonical, records=[TimelineRecord.model_validate(r) for r in records])


def watch_rows(db: Session, key: ApiKey, watch_id: uuid.UUID | None = None) -> list[WatchOut]:
    since = func.coalesce(PartnerWatchlist.last_checked_at, PartnerWatchlist.created_at)
    new_records = (
        select(func.count()).where(ServiceRecord.vehicle_id == PartnerWatchlist.vehicle_id, ServiceRecord.created_at > since)
        .correlate(PartnerWatchlist).scalar_subquery()
    )
    latest = (
        select(func.max(ServiceRecord.created_at)).where(ServiceRecord.vehicle_id == PartnerWatchlist.vehicle_id)
        .correlate(PartnerWatchlist).scalar_subquery()
    )
    query = (
        select(PartnerWatchlist, Vehicle.vin, new_records, latest)
        .join(Vehicle, Vehicle.id == PartnerWatchlist.vehicle_id)
        .where(PartnerWatchlist.api_key_id == key.id)
        .order_by(PartnerWatchlist.created_at.desc(), PartnerWatchlist.id)
    )
    if watch_id is not None:
        query = query.where(PartnerWatchlist.id == watch_id)
    return [
        WatchOut(
            id=watch.id, vin=vin, label=watch.label, created_at=watch.created_at, last_checked_at=watch.last_checked_at,
            new_record_count=new_count, latest_record_at=latest_at,
        )
        for watch, vin, new_count, latest_at in db.execute(query).all()
    ]


def one_watch(db: Session, key: ApiKey, watch_id: uuid.UUID) -> WatchOut:
    """The partner's own watch. Another partner's watch id answers 404, so ids can't be probed."""
    rows = watch_rows(db, key, watch_id)
    if not rows:
        raise ApiError(404, "watch_not_found", "Watch not found.")
    return rows[0]


@router.get("/watches", response_model=WatchList, summary="List your watched VINs")
def list_watches(key: PartnerKey, db: DbSession) -> WatchList:
    """Poll this to see which VINs have new records (`new_record_count` > 0), then PUT `mark_checked`."""
    require_scope(key, SCOPE_WATCHES_MANAGE)
    items = watch_rows(db, key)
    return WatchList(items=items, total=len(items))


@router.post("/watches", response_model=WatchOut, status_code=status.HTTP_201_CREATED, summary="Watch a VIN")
def create_watch(body: WatchCreate, key: PartnerKey, db: DbSession) -> WatchOut:
    """Watch any valid VIN, including one with no history yet."""
    require_scope(key, SCOPE_WATCHES_MANAGE)
    vin = canonical_vin(body.vin)
    count = db.scalar(select(func.count()).where(PartnerWatchlist.api_key_id == key.id)) or 0
    if count >= get_settings().partner_max_watches:
        raise ApiError(409, "watch_limit_reached", "This key already watches the maximum number of VINs.")
    vehicle = db.scalar(select(Vehicle).where(Vehicle.vin == vin))
    if vehicle is None:
        vehicle = Vehicle(vin=vin)
        db.add(vehicle)
        try:
            db.flush()
        except IntegrityError:  # someone recorded this VIN at the same moment
            db.rollback()
            vehicle = db.scalar(select(Vehicle).where(Vehicle.vin == vin))
    already = db.scalar(
        select(PartnerWatchlist.id).where(PartnerWatchlist.api_key_id == key.id, PartnerWatchlist.vehicle_id == vehicle.id)
    )
    if already is not None:
        raise ApiError(409, "already_watching", "You already watch this VIN.")
    watch = PartnerWatchlist(api_key_id=key.id, vehicle_id=vehicle.id, label=body.label)
    db.add(watch)
    db.commit()
    return one_watch(db, key, watch.id)


@router.put("/watches/{watch_id}", response_model=WatchOut, summary="Update a watch")
def replace_watch(watch_id: uuid.UUID, body: WatchReplace, key: PartnerKey, db: DbSession) -> WatchOut:
    require_scope(key, SCOPE_WATCHES_MANAGE)
    one_watch(db, key, watch_id)
    watch = db.get(PartnerWatchlist, watch_id)
    watch.label = body.label
    if body.mark_checked:
        watch.last_checked_at = datetime.now(UTC)
    db.commit()
    return one_watch(db, key, watch_id)


@router.delete("/watches/{watch_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Stop watching a VIN")
def delete_watch(watch_id: uuid.UUID, key: PartnerKey, db: DbSession) -> None:
    require_scope(key, SCOPE_WATCHES_MANAGE)
    one_watch(db, key, watch_id)
    db.delete(db.get(PartnerWatchlist, watch_id))
    db.commit()
