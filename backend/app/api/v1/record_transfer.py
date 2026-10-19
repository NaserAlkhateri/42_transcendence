"""CSV/JSON export of service records (AG-07). Export reuses the AG-06 search filters and scoping, so a download
is "what the search screen shows, every page"."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.v1.record_search import AdminSearchFilters, SearchFilters
from app.api.v1.records import SUBMITTER_ROLES
from app.auth.dependencies import CurrentUser
from app.auth.permissions import PlatformAdmin, require_org_role
from app.core.errors import ApiError
from app.db.session import get_db
from app.models import Organization, User
from app.services.audit import record_audit
from app.services.record_export import (
    MAX_EXPORT_IDS,
    MAX_EXPORT_ROWS,
    ExportFormat,
    ExportTooLargeError,
    applied_filters,
    export_filename,
    export_rows,
    to_csv,
    to_json,
)
from app.services.record_search import RecordSearchFilters

router = APIRouter(tags=["record export"])

DbSession = Annotated[Session, Depends(get_db)]
FormatQuery = Annotated[ExportFormat, Query(alias="format", description="csv or json")]
SelectedIds = Annotated[
    list[uuid.UUID] | None,
    Query(max_length=MAX_EXPORT_IDS, description="Repeatable. Export only these records; they must still match the scope and filters."),
]

_DOWNLOAD = {
    200: {
        "description": "The file, as an attachment named sijil-records-YYYYMMDD-HHMM.csv or .json (UTC)",
        "content": {"text/csv": {"schema": {"type": "string"}}, "application/json": {"schema": {"type": "object"}}},
    }
}


def _download(
    db: Session, user: User, filters: RecordSearchFilters, export_format: ExportFormat, ids: list[uuid.UUID] | None,
    organization_id: uuid.UUID | None,
) -> Response:
    try:
        rows = export_rows(db, filters, organization_id=organization_id, ids=ids or ())
    except ExportTooLargeError as exc:
        raise ApiError(
            422, "export_too_large",
            f"More than {MAX_EXPORT_ROWS:,} records match. Narrow the filters and export again.",
        ) from exc
    exported_at = datetime.now(UTC)
    if export_format == "csv":
        content, media_type = to_csv(rows), "text/csv"
    else:
        summary = applied_filters(filters, platform=organization_id is None, ids=ids or ())
        content = to_json(rows, exported_at=exported_at, organization_id=organization_id, filters=summary)
        media_type = "application/json"
    scope = "organization" if organization_id else "platform"
    record_audit(
        db, user, "records.exported", scope, organization_id or "all",
        {"format": export_format, "count": len(rows), "scope": scope},
    )
    db.commit()
    return Response(
        content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{export_filename(exported_at, export_format)}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/organizations/{organization_id}/records/export", response_class=Response, responses=_DOWNLOAD)
def export_organization_records(
    organization_id: uuid.UUID,
    user: CurrentUser,  # first, so a guest always gets 401
    db: DbSession,
    filters: SearchFilters,
    export_format: FormatQuery,
    ids: SelectedIds = None,
) -> Response:
    """Download the organization's records that match the search filters, in the search order (up to 5,000)."""
    if db.get(Organization, organization_id) is None:
        raise ApiError(404, "organization_not_found", "Organization not found.")
    require_org_role(db, user, organization_id, SUBMITTER_ROLES)
    return _download(db, user, filters, export_format, ids, organization_id)


@router.get("/admin/records/export", response_class=Response, responses=_DOWNLOAD)
def export_all_records(
    user: PlatformAdmin, db: DbSession, filters: AdminSearchFilters, export_format: FormatQuery, ids: SelectedIds = None
) -> Response:
    """Platform-wide download of the records that match the search filters (up to 5,000)."""
    return _download(db, user, filters, export_format, ids, None)
