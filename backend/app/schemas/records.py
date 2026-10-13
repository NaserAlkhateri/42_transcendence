import uuid
from datetime import date
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.core.time import uae_today
from app.models import CorrectionReason, RecordCategory
from app.schemas.vehicle import TimelineRecord
from app.services.work_codes import BY_CODE

MAX_ODOMETER_KM = 2_000_000


class RecordFields(BaseModel):
    """What staff enter for a record or a correction. Notes stay private to the organization and admins."""

    category: RecordCategory
    work_codes: Annotated[list[str], Field(min_length=1, max_length=10)]
    odometer_km: Annotated[int, Field(ge=0, le=MAX_ODOMETER_KM)]
    service_date: date
    notes: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=1000)] = None

    @field_validator("work_codes")
    @classmethod
    def known_and_unique(cls, codes: list[str]) -> list[str]:
        unknown = [code for code in codes if code not in BY_CODE]
        if unknown:
            raise ValueError(f"Unknown work code: {', '.join(unknown)}.")
        if len(set(codes)) != len(codes):
            raise ValueError("Each work code can be listed once.")
        return codes

    @field_validator("service_date")
    @classmethod
    def not_in_the_future(cls, value: date) -> date:
        if value > uae_today():
            raise ValueError("The service date cannot be in the future.")
        return value

    @field_validator("notes")
    @classmethod
    def blank_is_none(cls, value: str | None) -> str | None:
        return value or None


class RecordSubmission(RecordFields):
    vin: Annotated[str, Field(max_length=40)]  # normalized by the route, which answers invalid_vin


class CorrectionSubmission(RecordFields):
    """The corrected values for an earlier record, and what the correction fixes."""

    correction_reason: CorrectionReason


class WorkCodeOut(BaseModel):
    code: str
    label: str
    label_ar: str


class OrgRecordOut(TimelineRecord):
    """A record as its own organization sees it: the public fields plus VIN, staff name and private notes."""

    vin: str
    staff_name: str
    notes: str | None
    corrected_by_id: uuid.UUID | None = None  # set once another record corrects this one
