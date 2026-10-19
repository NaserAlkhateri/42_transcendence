"""CSV and JSON downloads of service records (AG-07). The rows come from the AG-06 search query, so an export
lists exactly what the search screen shows, every page of it, in the same order."""

import csv
import io
import json
import uuid
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, date, datetime
from typing import Any, Literal

from sqlalchemy import Row
from sqlalchemy.orm import Session

from app.models import ServiceRecord
from app.services.record_search import RecordSearchFilters, build_search_query

ExportFormat = Literal["csv", "json"]

MAX_EXPORT_ROWS = 5_000
MAX_EXPORT_IDS = 100
EXPORT_COLUMNS = (
    "record_id",
    "vin",
    "make",
    "model",
    "model_year",
    "service_date",
    "category",
    "work_codes",
    "odometer_km",
    "organization_name",
    "staff_name",
    "notes",
    "is_mileage_flagged",
    "corrects_record_id",
    "correction_reason",
    "created_at",
)
# A spreadsheet treats a cell starting with one of these as a formula (CSV injection), so such cells get a
# leading apostrophe. The importer takes it off again.
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


class ExportTooLargeError(Exception):
    """More than MAX_EXPORT_ROWS records match: the caller must narrow the filters, never get a cut-off file."""


def export_rows(
    db: Session, filters: RecordSearchFilters, *, organization_id: uuid.UUID | None, ids: Sequence[uuid.UUID] = ()
) -> list[Row]:
    """Every matching row in search order. `ids` only narrows the scope and filters, it never widens them."""
    query = build_search_query(filters, organization_id=organization_id)
    if ids:
        query = query.where(ServiceRecord.id.in_(ids))
    rows = list(db.execute(query.limit(MAX_EXPORT_ROWS + 1)).all())
    if len(rows) > MAX_EXPORT_ROWS:
        raise ExportTooLargeError
    return rows


def utc_iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


def export_record(row: Row) -> dict[str, Any]:
    """One record with JSON types; the CSV writer flattens it."""
    return {
        "record_id": str(row.id),
        "vin": row.vin,
        "make": row.make,
        "model": row.model,
        "model_year": row.model_year,
        "service_date": row.service_date.isoformat(),
        "category": str(row.category),
        "work_codes": list(row.work_codes),
        "odometer_km": row.odometer_km,
        "organization_name": row.organization_name,
        "staff_name": row.staff_name,
        "notes": row.notes,
        "is_mileage_flagged": row.is_mileage_flagged,
        "corrects_record_id": str(row.corrects_record_id) if row.corrects_record_id else None,
        "correction_reason": str(row.correction_reason) if row.correction_reason else None,
        "created_at": utc_iso(row.created_at),
    }


def _csv_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        value = ";".join(value)
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


def to_csv(rows: Sequence[Row]) -> bytes:
    """UTF-8 with a BOM so Excel shows Arabic correctly. csv quoting keeps commas, quotes and line breaks intact."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(EXPORT_COLUMNS)
    for row in rows:
        record = export_record(row)
        writer.writerow([_csv_cell(record[column]) for column in EXPORT_COLUMNS])
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def applied_filters(filters: RecordSearchFilters, *, platform: bool, ids: Sequence[uuid.UUID]) -> dict[str, Any]:
    """The filters, sort and selection behind an export, for the JSON file's header."""
    summary = asdict(filters)
    if not platform:  # the organization filters only exist on the platform-wide route
        del summary["organization"], summary["organization_id"]
    summary["work_codes"] = list(filters.work_codes)
    summary["ids"] = [str(record_id) for record_id in ids]
    return summary


def _json_value(value: object) -> str:
    if isinstance(value, date | uuid.UUID):
        return str(value)
    raise TypeError(f"Cannot export {type(value).__name__}")


def to_json(
    rows: Sequence[Row], *, exported_at: datetime, organization_id: uuid.UUID | None, filters: dict[str, Any]
) -> bytes:
    payload = {
        "exported_at": utc_iso(exported_at),
        "scope": "platform" if organization_id is None else "organization",
        "organization_id": str(organization_id) if organization_id else None,
        "filters": filters,
        "count": len(rows),
        "records": [export_record(row) for row in rows],
    }
    return json.dumps(payload, ensure_ascii=False, default=_json_value).encode("utf-8")


def export_filename(exported_at: datetime, export_format: ExportFormat) -> str:
    return f"sijil-records-{exported_at.astimezone(UTC):%Y%m%d-%H%M}.{export_format}"
