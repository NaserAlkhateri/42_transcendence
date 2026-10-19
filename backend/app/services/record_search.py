"""Advanced record search (AG-06): filters, sorting and pagination over service records, either inside one
organization or platform-wide for admins. AG-07's export reuses `build_search_query`, so a download lists the
same rows in the same order as the screen."""

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Literal

from sqlalchemy import ColumnElement, Row, Select, func, select
from sqlalchemy.orm import Session, aliased

from app.models import RecordCategory, ServiceRecord, Vehicle

SortKey = Literal["service_date", "created_at", "odometer_km", "vin", "make", "organization_name"]
SortOrder = Literal["asc", "desc"]
RecordType = Literal["all", "original", "correction"]


@dataclass(frozen=True)
class RecordSearchFilters:
    """Every filter is optional and they are AND-combined. Values arrive already cleaned by the API layer:
    text stripped (None when blank), `vin` an upper-case fragment, `work_codes` known codes.
    The sort order travels with the filters so an export keeps the order of the screen."""

    vin: str | None = None
    make: str | None = None
    model: str | None = None
    staff: str | None = None
    organization: str | None = None  # organization-name snapshot (admin search)
    organization_id: uuid.UUID | None = None  # admin search
    year_from: int | None = None
    year_to: int | None = None
    date_from: date | None = None
    date_to: date | None = None
    odometer_min: int | None = None
    odometer_max: int | None = None
    category: RecordCategory | None = None
    work_codes: tuple[str, ...] = ()  # matches records with any of them
    flagged: bool | None = None
    record_type: RecordType = "all"
    corrected: bool | None = None
    sort: SortKey = "service_date"
    order: SortOrder = "desc"


# The record that corrects a row, if any. corrects_record_id is unique, so this outer join never duplicates rows.
_correction = aliased(ServiceRecord, name="correction")

SEARCH_COLUMNS = (
    ServiceRecord.id,
    Vehicle.vin,
    Vehicle.make,
    Vehicle.model,
    Vehicle.model_year,
    ServiceRecord.service_date,
    ServiceRecord.created_at,
    ServiceRecord.category,
    ServiceRecord.work_codes,
    ServiceRecord.odometer_km,
    ServiceRecord.organization_id,
    ServiceRecord.organization_name,
    ServiceRecord.staff_name,
    ServiceRecord.notes,
    ServiceRecord.is_mileage_flagged,
    ServiceRecord.corrects_record_id,
    ServiceRecord.correction_reason,
    _correction.id.label("corrected_by_id"),
)

# Text sorts ignore case, so "audi" and "Audi" sit together whatever the database collation.
_SORT_COLUMNS = {
    "service_date": ServiceRecord.service_date,
    "created_at": ServiceRecord.created_at,
    "odometer_km": ServiceRecord.odometer_km,
    "vin": Vehicle.vin,
    "make": func.lower(Vehicle.make),
    "organization_name": func.lower(ServiceRecord.organization_name),
}
_NULLABLE_SORTS = {"make"}


def _conditions(filters: RecordSearchFilters, organization_id: uuid.UUID | None) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if organization_id is not None:
        conditions.append(ServiceRecord.organization_id == organization_id)
    if filters.organization_id is not None:
        conditions.append(ServiceRecord.organization_id == filters.organization_id)
    if filters.vin:
        conditions.append(Vehicle.vin.contains(filters.vin, autoescape=True))
    # autoescape: %, _ and the escape character in user input match literally.
    for column, text in (
        (Vehicle.make, filters.make),
        (Vehicle.model, filters.model),
        (ServiceRecord.staff_name, filters.staff),
        (ServiceRecord.organization_name, filters.organization),
    ):
        if text:
            conditions.append(column.icontains(text, autoescape=True))
    if filters.year_from is not None:
        conditions.append(Vehicle.model_year >= filters.year_from)
    if filters.year_to is not None:
        conditions.append(Vehicle.model_year <= filters.year_to)
    if filters.date_from is not None:
        conditions.append(ServiceRecord.service_date >= filters.date_from)
    if filters.date_to is not None:
        conditions.append(ServiceRecord.service_date <= filters.date_to)
    if filters.odometer_min is not None:
        conditions.append(ServiceRecord.odometer_km >= filters.odometer_min)
    if filters.odometer_max is not None:
        conditions.append(ServiceRecord.odometer_km <= filters.odometer_max)
    if filters.category is not None:
        conditions.append(ServiceRecord.category == filters.category)
    if filters.work_codes:
        conditions.append(ServiceRecord.work_codes.overlap(list(filters.work_codes)))
    if filters.flagged is not None:
        conditions.append(ServiceRecord.is_mileage_flagged == filters.flagged)
    if filters.record_type == "original":
        conditions.append(ServiceRecord.corrects_record_id.is_(None))
    elif filters.record_type == "correction":
        conditions.append(ServiceRecord.corrects_record_id.is_not(None))
    if filters.corrected is not None:
        conditions.append(_correction.id.is_not(None) if filters.corrected else _correction.id.is_(None))
    return conditions


def _ordering(filters: RecordSearchFilters) -> list[ColumnElement]:
    """The chosen key, then newest created first, then id: a total order, so pages never overlap or skip rows."""
    column = _SORT_COLUMNS[filters.sort]
    primary = column.asc() if filters.order == "asc" else column.desc()
    if filters.sort in _NULLABLE_SORTS:
        primary = primary.nulls_last()
    ordering = [primary]
    if filters.sort != "created_at":
        ordering.append(ServiceRecord.created_at.desc())
    ordering.append(ServiceRecord.id.asc())
    return ordering


def _filtered(query: Select, filters: RecordSearchFilters, organization_id: uuid.UUID | None) -> Select:
    return (
        query.join(Vehicle, Vehicle.id == ServiceRecord.vehicle_id)
        .outerjoin(_correction, _correction.corrects_record_id == ServiceRecord.id)
        .where(*_conditions(filters, organization_id))
    )


def build_search_query(filters: RecordSearchFilters, *, organization_id: uuid.UUID | None) -> Select:
    """Every matching row (SEARCH_COLUMNS), sorted, without paging. organization_id=None searches all organizations;
    otherwise only that organization's records."""
    query = _filtered(select(*SEARCH_COLUMNS).select_from(ServiceRecord), filters, organization_id)
    return query.order_by(*_ordering(filters))


def search_records(
    db: Session, filters: RecordSearchFilters, *, organization_id: uuid.UUID | None, page: int, page_size: int
) -> tuple[list[Row], int]:
    """One page of results and the number of all matches: two queries, whatever the page size."""
    total = db.scalar(_filtered(select(func.count()).select_from(ServiceRecord), filters, organization_id)) or 0
    query = build_search_query(filters, organization_id=organization_id).offset((page - 1) * page_size).limit(page_size)
    return list(db.execute(query).all()), total
