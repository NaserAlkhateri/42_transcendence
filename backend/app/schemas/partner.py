import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.schemas.vehicle import TimelineRecord

WatchLabel = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
PartnerName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]


class PartnerVehicle(BaseModel):
    """Vehicle summary for partners: facts and history counts only, never owners, staff or notes."""

    vin: str
    make: str | None
    model: str | None
    model_year: int | None
    record_count: int
    flagged_record_count: int
    correction_count: int
    latest_service_date: date | None
    latest_odometer_km: int | None  # from the latest record not replaced by a correction
    last_record_added_at: datetime | None


class PartnerHistory(BaseModel):
    vin: str
    records: list[TimelineRecord]  # the same consumer-safe view as the public timeline, newest first


class WatchCreate(BaseModel):
    vin: Annotated[str, Field(max_length=40, examples=["JTMHX01J5M4012345"])]
    label: WatchLabel | None = Field(default=None, examples=["Policy 2026-00417"])


class WatchReplace(BaseModel):
    """PUT replaces the watch's editable state: its label, and optionally marks everything so far as seen."""

    label: WatchLabel | None = None
    mark_checked: bool = Field(default=False, description="Set last_checked_at to now, so new_record_count drops to 0")


class WatchOut(BaseModel):
    id: uuid.UUID
    vin: str
    label: str | None
    created_at: datetime
    last_checked_at: datetime | None
    new_record_count: int  # records added since last_checked_at (or since the watch was created)
    latest_record_at: datetime | None


class WatchList(BaseModel):
    items: list[WatchOut]
    total: int


class ApiKeyCreate(BaseModel):
    partner_name: PartnerName


class ApiKeyOut(BaseModel):
    id: uuid.UUID
    partner_name: str
    key_prefix: str
    scopes: list[str]
    created_at: datetime
    issued_by: str | None  # the issuing admin's email; None once that account is deleted
    last_used_at: datetime | None
    revoked_at: datetime | None
    watch_count: int


class ApiKeyIssued(BaseModel):
    key: ApiKeyOut
    api_key: str  # the full key, shown once; only its hash is stored
