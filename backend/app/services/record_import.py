"""Bulk import of service records from CSV or JSON (AG-07).

Every row is checked with the record form's own schema (RecordSubmission), so an import and the form accept
exactly the same records. An import is all-or-nothing: one transaction locks every vehicle it touches in VIN
order, checks the rows again under those locks, then appends them in file order through `submit_record`, so each
mileage flag is computed exactly as for a single submission."""

import csv
import io
import json
import re
import uuid
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from pydantic import ValidationError
from pydantic_core import ErrorDetails
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import Organization, RecordCategory, ServiceRecord, User, Vehicle
from app.schemas.record_transfer import ImportReport, ImportRowError, ImportRowReport
from app.schemas.records import MAX_ODOMETER_KM, RecordSubmission
from app.services.record_export import FORMULA_PREFIXES
from app.services.records import effective_readings_by_vin, lock_vehicle, reading_is_inconsistent, submit_record
from app.services.vin import InvalidVinError, normalize_vin

ImportFormat = Literal["csv", "json"]

MAX_IMPORT_BYTES = 512 * 1024
MAX_IMPORT_ROWS = 500
REQUIRED_COLUMNS = ("vin", "service_date", "odometer_km", "category", "work_codes")
OPTIONAL_COLUMNS = ("notes",)
COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS

_REQUIRED_MESSAGES = {
    "vin": "Enter the VIN.",
    "service_date": "Enter the service date.",
    "odometer_km": "Enter the odometer reading.",
    "category": "Enter the category: maintenance or repair.",
    "work_codes": "Enter at least one work code.",
}
_LABELS = {"vin": "VIN", "service_date": "Service date", "odometer_km": "Odometer", "category": "Category",
           "notes": "Notes"}
_ISO_DATE = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
_DAY_FIRST_DATE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")  # never month first
_KILOMETRES = re.compile(r"\d{1,12}|\d{1,3}(?:,\d{3}){1,3}")  # 88300 or 88,300
# NUL, which Postgres text cannot hold, and lone UTF-16 surrogates, which are not text. Decoding catches them as
# raw bytes; this catches them written as JSON \u escapes.
_NOT_TEXT = re.compile("[\x00\ud800-\udfff]")
_ENCODING_MESSAGE = "The file must be UTF-8 text. In Excel, save it as \"CSV UTF-8\"."


@dataclass
class ImportRow:
    """One data row: its raw values in; the checked submission, cleaned values and errors out."""

    number: int
    raw: dict[str, Any]
    errors: list[ImportRowError] = field(default_factory=list)
    submission: RecordSubmission | None = None  # set when the row passed every check of its own
    vin: str | None = None  # canonical
    service_date: date | None = None
    odometer_km: int | None = None
    category: RecordCategory | None = None
    work_codes: list[str] = field(default_factory=list)
    will_be_flagged: bool = False

    @property
    def ok(self) -> bool:
        return not self.errors

    def add_error(self, name: str | None, code: str, message: str) -> None:
        self.errors.append(ImportRowError(field=name, code=code, message=message))

    def failed(self, name: str) -> bool:
        return any(error.field == name for error in self.errors)


@dataclass
class ImportFile:
    format: ImportFormat
    rows: list[ImportRow]
    warnings: list[str]


class ImportInvalidError(Exception):
    """At least one row has an error, so nothing may be written."""


# --- the file ------------------------------------------------------------------------------------------------


def decode_upload(body: bytes) -> str:
    """The request body as text: UTF-8, with or without a byte-order mark."""
    try:
        text = body.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise _invalid_encoding() from exc
    if "\x00" in text:  # UTF-16 or a binary file; Postgres text cannot hold NUL either
        raise _invalid_encoding()
    if not text.strip():
        raise _empty_file()
    return text


def parse_import(file_format: ImportFormat, text: str) -> ImportFile:
    """Read and check every row without touching the database. File-level problems raise ApiError."""
    rows, warnings = _csv_rows(text) if file_format == "csv" else _json_rows(text)
    if not rows:
        raise _empty_file()
    for row in rows:
        _check_row(row, csv_guard=file_format == "csv")
    _mark_duplicates(rows)
    return ImportFile(format=file_format, rows=rows, warnings=warnings)


def _invalid_encoding() -> ApiError:
    return ApiError(422, "invalid_encoding", _ENCODING_MESSAGE)


def _empty_file() -> ApiError:
    return ApiError(422, "empty_file", "The file has no records.")


def _too_many_rows() -> ApiError:
    return ApiError(422, "too_many_rows", f"A file can hold at most {MAX_IMPORT_ROWS} records. Split it into smaller files.")


def _column_key(name: str) -> str:
    """Header names ignore case and surrounding spaces; inner spaces and dashes count as underscores."""
    return re.sub(r"[\s-]+", "_", name.strip().lower())


def _ignored(kind: str, names: list[str]) -> list[str]:
    if not names:
        return []
    shown = [name[:40] for name in names[:10]]
    more = f" and {len(names) - 10} more" if len(names) > 10 else ""
    return [f"Ignored {kind}: {', '.join(shown)}{more}."]


def _csv_rows(text: str) -> tuple[list[ImportRow], list[str]]:
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        header = next(reader, [])
        keys = [_column_key(name) for name in header]
        counts = Counter(keys)
        repeated = [name for name in COLUMNS if counts[name] > 1]
        if repeated:
            raise ApiError(422, "duplicate_columns", f"Each column can appear once: {', '.join(repeated)}.")
        missing = [name for name in REQUIRED_COLUMNS if name not in keys]
        if missing:
            raise ApiError(
                422, "missing_columns",
                f"Missing required columns: {', '.join(missing)}. The first row must name the columns "
                f"{', '.join(REQUIRED_COLUMNS)} (notes is optional).",
            )
        positions = {key: index for index, key in enumerate(keys) if key in COLUMNS}
        ignored = [name.strip() for name, key in zip(header, keys, strict=True) if key and key not in COLUMNS]
        rows: list[ImportRow] = []
        # Blank lines are skipped but still numbered, so row numbers match the spreadsheet.
        for number, cells in enumerate(reader, start=1):
            if not any(cell.strip() for cell in cells):
                continue
            if len(rows) == MAX_IMPORT_ROWS:
                raise _too_many_rows()
            values = {key: cells[index] if index < len(cells) else None for key, index in positions.items()}
            rows.append(ImportRow(number=number, raw=values))
    except csv.Error as exc:
        raise ApiError(422, "invalid_csv", f"The CSV file could not be read near line {reader.line_num}: {exc}.") from exc
    return rows, _ignored("columns", ignored)


class _JsonObject(dict):
    """A JSON object that also keeps its pairs as written, so a repeated key is not silently dropped."""

    def __init__(self, pairs: list[tuple[str, Any]]) -> None:
        super().__init__(pairs)
        self.pairs = pairs


def _not_text(value: Any) -> bool:
    if isinstance(value, str):
        return _NOT_TEXT.search(value) is not None
    return isinstance(value, list) and any(isinstance(item, str) and _NOT_TEXT.search(item) for item in value)


def _json_rows(text: str) -> tuple[list[ImportRow], list[str]]:
    try:
        data = json.loads(text, object_pairs_hook=_JsonObject)
    except (ValueError, RecursionError) as exc:
        raise ApiError(422, "invalid_json", "The file is not valid JSON.") from exc
    if isinstance(data, dict) and isinstance(data.get("records"), list):
        items = data["records"]  # the shape of an AG-07 JSON export
    elif isinstance(data, list):
        items = data
    else:
        raise ApiError(422, "invalid_json", 'Expected a list of records, or an object with a "records" list.')
    if len(items) > MAX_IMPORT_ROWS:
        raise _too_many_rows()
    rows: list[ImportRow] = []
    ignored: set[str] = set()
    for number, item in enumerate(items, start=1):
        row = ImportRow(number=number, raw={})
        if isinstance(item, _JsonObject):
            for key, value in item.pairs:
                if _not_text(key) or _not_text(value):
                    raise _invalid_encoding()
                name = _column_key(key)
                if name not in COLUMNS:
                    ignored.add(key)
                elif name not in row.raw:
                    row.raw[name] = value
                elif not row.failed(name):  # "vin" and "VIN", or the same key twice
                    row.add_error(name, "duplicate_field", "This field appears more than once in the record.")
        else:
            row.add_error(None, "invalid_row", "Each record must be a JSON object.")
        rows.append(row)
    return rows, _ignored("fields", sorted(ignored))


# --- one row -------------------------------------------------------------------------------------------------


def _text(row: ImportRow, name: str, *, required: bool) -> str | None:
    """A stripped text value, None when missing or blank. Records an error for other JSON types or when required."""
    value = row.raw.get(name)
    if value is not None and not isinstance(value, str):
        row.add_error(name, "invalid_type", f"{_LABELS[name]} must be text.")
        return None
    value = (value or "").strip() or None
    if value is None and required:
        row.add_error(name, "required", _REQUIRED_MESSAGES[name])
    return value


def _service_date(row: ImportRow) -> date | None:
    text = _text(row, "service_date", required=True)
    if text is None:
        return None
    if match := _ISO_DATE.fullmatch(text):
        year, month, day = match.groups()
    elif match := _DAY_FIRST_DATE.fullmatch(text):
        day, month, year = match.groups()
    else:
        year = month = day = ""
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        row.add_error("service_date", "invalid_date", "Use YYYY-MM-DD or DD/MM/YYYY (day first), e.g. 2026-03-01 or 01/03/2026.")
        return None


def _odometer(row: ImportRow) -> int | None:
    value = row.raw.get("odometer_km")
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if value is None or isinstance(value, str):
        text = _text(row, "odometer_km", required=True)
        if text is None:
            return None
        if _KILOMETRES.fullmatch(text):
            return int(text.replace(",", ""))
    row.add_error("odometer_km", "invalid_number", "Enter the reading in whole kilometres, e.g. 88300 or 88,300.")
    return None


def _work_codes(row: ImportRow) -> list[str] | None:
    value = row.raw.get("work_codes")
    if value is None:
        items: list[Any] = []
    elif isinstance(value, str):
        items = value.split(";")
    elif isinstance(value, list) and all(isinstance(item, str) for item in value):
        items = value
    else:
        row.add_error("work_codes", "invalid_type", "Work codes must be text separated by ; or a list of codes.")
        return None
    codes = [item.strip().upper() for item in items if item.strip()]
    if not codes:
        row.add_error("work_codes", "required", _REQUIRED_MESSAGES["work_codes"])
        return None
    return codes


def _notes(row: ImportRow, *, csv_guard: bool) -> str | None:
    text = _text(row, "notes", required=False)
    if csv_guard and text and len(text) > 1 and text[0] == "'" and text[1:].startswith(FORMULA_PREFIXES):
        return text[1:]  # undo the CSV export's formula guard, so an export imports unchanged
    return text


def _schema_error(name: str, error: ErrorDetails) -> tuple[str, str]:
    """(code, message) for a RecordSubmission error on `name`."""
    message = error["msg"].removeprefix("Value error, ")
    ctx = error.get("ctx", {})
    match name:
        case "vin":
            return "invalid_vin", "A VIN has at most 40 characters, including spaces and dashes."
        case "category":
            return "invalid_category", f"Category must be {' or '.join(category.value for category in RecordCategory)}."
        case "work_codes":
            if error["type"] == "too_long":
                return "invalid_work_code", f"List at most {ctx['max_length']} work codes."
            return "invalid_work_code", message
        case "service_date":
            return "future_date", message
        case "odometer_km":
            return "out_of_range", f"The reading must be between 0 and {MAX_ODOMETER_KM:,} km."
        case "notes" if error["type"] == "string_too_long":
            return "too_long", f"Notes can be at most {ctx['max_length']:,} characters."
    return "invalid_value", message


def _check_row(row: ImportRow, *, csv_guard: bool) -> None:
    """Parse the raw values, then apply the record form's own rules (RecordSubmission) and the VIN check."""
    if any(error.code == "invalid_row" for error in row.errors):  # not a JSON object
        return
    values = {
        "vin": _text(row, "vin", required=True),
        "service_date": _service_date(row),
        "odometer_km": _odometer(row),
        "category": (_text(row, "category", required=True) or "").lower() or None,
        "work_codes": _work_codes(row),
        "notes": _notes(row, csv_guard=csv_guard),
    }
    submission = None
    try:
        submission = RecordSubmission.model_validate({key: value for key, value in values.items() if value is not None})
    except ValidationError as exc:
        for error in exc.errors():
            name = str(error["loc"][0])
            if not row.failed(name):  # a field that could not be parsed is reported once, as such
                row.add_error(name, *_schema_error(name, error))
    if not row.failed("vin"):
        try:
            row.vin = normalize_vin(values["vin"])
        except InvalidVinError as exc:
            row.add_error("vin", "invalid_vin", str(exc))
    if submission is not None and row.ok:
        row.submission = submission
    # Echo the cleaned values of the fields without an error.
    row.service_date = None if row.failed("service_date") else values["service_date"]
    row.odometer_km = None if row.failed("odometer_km") else values["odometer_km"]
    row.category = None if row.failed("category") else RecordCategory(values["category"])
    row.work_codes = [] if row.failed("work_codes") else values["work_codes"]


def _mark_duplicates(rows: list[ImportRow]) -> None:
    """A later row with the same VIN, date and reading as an earlier one is an error."""
    first: dict[tuple[str, date, int], int] = {}
    for row in rows:
        if row.vin is None or row.service_date is None or row.odometer_km is None:
            continue
        key = (row.vin, row.service_date, row.odometer_km)
        if key in first:
            row.add_error(None, "duplicate_in_file", f"Same VIN, service date and odometer reading as row {first[key]}.")
        else:
            first[key] = row.number


# --- against the stored history --------------------------------------------------------------------------------


def check_import(db: Session, organization_id: uuid.UUID, file: ImportFile) -> None:
    """Mark rows the organization already recorded and predict each valid row's mileage flag against the stored
    history plus the earlier valid rows of the file. Reads only; `save_import` calls it under the vehicle locks."""
    vins = sorted({row.vin for row in file.rows if row.vin})
    if not vins:
        return
    recorded = set(
        db.execute(
            select(Vehicle.vin, ServiceRecord.service_date, ServiceRecord.odometer_km, ServiceRecord.category)
            .join(Vehicle, Vehicle.id == ServiceRecord.vehicle_id)
            .where(ServiceRecord.organization_id == organization_id, Vehicle.vin.in_(vins))
        ).tuples()
    )
    for row in file.rows:
        if (row.vin, row.service_date, row.odometer_km, row.category) in recorded:
            row.add_error(
                None, "already_recorded",
                "Your organization has already recorded this service (same VIN, date, odometer reading and category).",
            )
    histories = effective_readings_by_vin(db, vins)
    for row in file.rows:
        if row.ok:
            history = histories.setdefault(row.vin, [])
            row.will_be_flagged = reading_is_inconsistent(history, row.service_date, row.odometer_km)
            history.append((row.service_date, row.odometer_km))


def lock_vehicles(db: Session, vins: Iterable[str]) -> None:
    """Lock (creating if needed) every vehicle in VIN order. Imports that share vehicles then take the locks in
    the same order and wait for each other instead of deadlocking; a single submission only ever holds one."""
    for vin in sorted(set(vins)):
        lock_vehicle(db, vin)


def save_import(db: Session, *, organization: Organization, staff: User, file: ImportFile) -> list[tuple[ServiceRecord, str]]:
    """Append every row or none: raises ImportInvalidError if any row fails, and the caller must then roll back.
    Returns (record, canonical VIN) in file order; the caller commits."""
    if all(row.ok for row in file.rows):
        lock_vehicles(db, [row.vin for row in file.rows if row.vin])
    check_import(db, organization.id, file)  # again under the locks, so nothing changed since the check
    if not all(row.ok for row in file.rows):
        raise ImportInvalidError
    return [
        (submit_record(db, organization=organization, staff=staff, vin=row.vin, fields=row.submission), row.vin)
        for row in file.rows
        if row.vin and row.submission
    ]


def import_report(file: ImportFile, *, dry_run: bool) -> ImportReport:
    rows = [
        ImportRowReport(
            row=row.number, vin=row.vin, service_date=row.service_date, odometer_km=row.odometer_km,
            category=row.category, work_codes=row.work_codes, status="ok" if row.ok else "error", errors=row.errors,
            will_be_flagged=row.will_be_flagged,
        )
        for row in file.rows
    ]
    valid = sum(row.ok for row in file.rows)
    return ImportReport(
        dry_run=dry_run, format=file.format, total_rows=len(rows), valid_rows=valid, invalid_rows=len(rows) - valid,
        flagged_rows=sum(row.ok and row.will_be_flagged for row in file.rows), warnings=file.warnings, rows=rows,
    )
