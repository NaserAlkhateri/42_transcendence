import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models import CorrectionReason, RecordCategory


class VehicleSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    vin: str
    make: str | None
    model: str | None
    model_year: int | None


class TimelineRecord(BaseModel):
    """Consumer-safe view of a service record: vehicle facts, organization name, dates and flags only.
    Notes, staff names and attachments are deliberately absent."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    service_date: date
    created_at: datetime
    category: RecordCategory
    work_codes: list[str]
    odometer_km: int
    organization_name: str
    is_mileage_flagged: bool
    corrects_record_id: uuid.UUID | None
    correction_reason: CorrectionReason | None  # a fixed list, so it is safe to show publicly


class VehicleTimeline(BaseModel):
    vin: str
    vehicle: VehicleSummary | None  # None: valid VIN with no history yet, the UI offers "Watch"
    records: list[TimelineRecord]
