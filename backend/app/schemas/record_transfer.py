import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.models import RecordCategory


class ImportRowError(BaseModel):
    field: str | None  # None for a problem with the whole row, e.g. a duplicate
    code: str
    message: str


class ImportRowReport(BaseModel):
    """One data row of an import file. A value is null when that field has an error (see `errors`)."""

    row: int  # CSV: data row number, the header not counted; JSON: position in the list. Both start at 1.
    vin: str | None
    service_date: date | None
    odometer_km: int | None
    category: RecordCategory | None
    work_codes: list[str]
    status: Literal["ok", "error"]
    errors: list[ImportRowError]
    will_be_flagged: bool  # the mileage flag this row would get if the file were imported now


class ImportReport(BaseModel):
    dry_run: bool
    format: Literal["csv", "json"]
    total_rows: int
    valid_rows: int
    invalid_rows: int
    flagged_rows: int  # valid rows that would be flagged
    warnings: list[str]
    rows: list[ImportRowReport]


class ImportResult(BaseModel):
    dry_run: Literal[False] = False
    imported: int
    flagged: int
    record_ids: list[uuid.UUID]  # in file order
