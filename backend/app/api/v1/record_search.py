"""Advanced record search (AG-06): workshops and dealerships search their own records, platform admins search
every organization's. Both routes share the `search_filters` dependency, which AG-07's export can reuse."""

import uuid
from dataclasses import replace
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.records import SUBMITTER_ROLES
from app.auth.dependencies import CurrentUser
from app.auth.permissions import PlatformAdmin, require_org_role
from app.core.errors import ApiError
from app.db.session import get_db
from app.models import Organization, RecordCategory
from app.schemas.record_search import RecordSearchItem, RecordSearchPage
from app.schemas.records import MAX_ODOMETER_KM
from app.services.record_search import RecordSearchFilters, RecordType, SortKey, SortOrder, search_records
from app.services.vin import InvalidVinError, normalize_vin_fragment
from app.services.work_codes import BY_CODE

router = APIRouter(tags=["record search"])

DbSession = Annotated[Session, Depends(get_db)]
Page = Annotated[int, Query(ge=1, le=100_000)]  # bounded so OFFSET can never overflow
PageSize = Annotated[int, Query(ge=1, le=100)]
ModelYear = Annotated[int | None, Query(ge=1900, le=2100, description="Vehicle model year, inclusive")]
Odometer = Annotated[int | None, Query(ge=0, le=MAX_ODOMETER_KM, description="Odometer reading in km, inclusive")]
ServiceDate = Annotated[date | None, Query(description="Service date (YYYY-MM-DD), inclusive")]
VinQuery = Annotated[
    str | None,
    Query(max_length=40, description="Part of a VIN; case, spaces, dashes and Arabic-Indic digits are normalized"),
]
WorkCodes = Annotated[list[str] | None, Query(description="Repeatable. Matches records with any of the codes.")]
RecordTypeQuery = Annotated[RecordType, Query(description="original: not a correction; correction: corrects another")]


def _text(value: str | None) -> str | None:
    """Blank means "no filter"."""
    if value is None:
        return None
    if "\x00" in value:  # Postgres text cannot hold NUL, so the query would fail
        raise ApiError(422, "validation_error", "Search text cannot contain control characters.")
    return value.strip() or None


def _check_range(low: Any, high: Any, code: str, message: str) -> None:
    if low is not None and high is not None and low > high:
        raise ApiError(422, code, message)


def search_filters(
    vin: VinQuery = None,
    make: Annotated[str | None, Query(max_length=64)] = None,
    model: Annotated[str | None, Query(max_length=64)] = None,
    staff: Annotated[str | None, Query(max_length=120, description="Staff name")] = None,
    year_from: ModelYear = None,
    year_to: ModelYear = None,
    date_from: ServiceDate = None,
    date_to: ServiceDate = None,
    odometer_min: Odometer = None,
    odometer_max: Odometer = None,
    category: RecordCategory | None = None,
    work_code: WorkCodes = None,
    flagged: Annotated[bool | None, Query(description="Mileage flag")] = None,
    record_type: RecordTypeQuery = "all",
    corrected: Annotated[bool | None, Query(description="Whether a later correction replaces the record")] = None,
    sort: SortKey = "service_date",
    order: SortOrder = "desc",
) -> RecordSearchFilters:
    """The filters and sort order both search routes accept. Text filters are case-insensitive substrings."""
    try:
        vin_fragment = normalize_vin_fragment(vin) if vin else ""
    except InvalidVinError as exc:
        raise ApiError(422, "invalid_vin_query", str(exc)) from exc
    _check_range(year_from, year_to, "invalid_year_range", "Model year: 'from' must not be later than 'to'.")
    _check_range(date_from, date_to, "invalid_date_range", "Service date: 'from' must not be later than 'to'.")
    _check_range(
        odometer_min, odometer_max, "invalid_odometer_range", "Odometer: the minimum must not be more than the maximum."
    )
    # Blank codes are ignored like blank text filters; repeats are dropped, order kept.
    work_codes = tuple(dict.fromkeys(code.strip() for code in work_code or () if code.strip()))
    unknown = [code for code in work_codes if code not in BY_CODE]
    if unknown:
        raise ApiError(422, "unknown_work_code", f"Unknown work code: {', '.join(unknown)}.")
    return RecordSearchFilters(
        vin=vin_fragment or None,
        make=_text(make),
        model=_text(model),
        staff=_text(staff),
        year_from=year_from,
        year_to=year_to,
        date_from=date_from,
        date_to=date_to,
        odometer_min=odometer_min,
        odometer_max=odometer_max,
        category=category,
        work_codes=work_codes,
        flagged=flagged,
        record_type=record_type,
        corrected=corrected,
        sort=sort,
        order=order,
    )


SearchFilters = Annotated[RecordSearchFilters, Depends(search_filters)]


def admin_search_filters(
    filters: SearchFilters,
    organization_id: uuid.UUID | None = None,
    organization: Annotated[str | None, Query(max_length=200, description="Organization name")] = None,
) -> RecordSearchFilters:
    """The shared filters plus the organization ones only a platform-wide search needs."""
    return replace(filters, organization_id=organization_id, organization=_text(organization))


AdminSearchFilters = Annotated[RecordSearchFilters, Depends(admin_search_filters)]


def _page(
    db: Session, filters: RecordSearchFilters, organization_id: uuid.UUID | None, page: int, page_size: int
) -> RecordSearchPage:
    rows, total = search_records(db, filters, organization_id=organization_id, page=page, page_size=page_size)
    items = [RecordSearchItem.model_validate(row) for row in rows]
    return RecordSearchPage(items=items, total=total, page=page, page_size=page_size)


@router.get("/organizations/{organization_id}/records/search", response_model=RecordSearchPage)
def search_organization_records(
    organization_id: uuid.UUID,
    user: CurrentUser,  # first, so a guest always gets 401
    db: DbSession,
    filters: SearchFilters,
    page: Page = 1,
    page_size: PageSize = 20,
) -> RecordSearchPage:
    """Search, sort and page through the organization's own records, with staff names and private notes.
    Newest service date first by default."""
    if db.get(Organization, organization_id) is None:
        raise ApiError(404, "organization_not_found", "Organization not found.")
    require_org_role(db, user, organization_id, SUBMITTER_ROLES)
    return _page(db, filters, organization_id, page, page_size)


@router.get("/admin/records", response_model=RecordSearchPage)
def search_all_records(
    _: PlatformAdmin, db: DbSession, filters: AdminSearchFilters, page: Page = 1, page_size: PageSize = 20
) -> RecordSearchPage:
    """Platform-wide record search, including records of deleted organizations (by their name snapshot)."""
    return _page(db, filters, None, page, page_size)
