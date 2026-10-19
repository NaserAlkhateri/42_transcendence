"""CSV/JSON export and import of service records (AG-07). Export reuses the AG-06 search filters and scoping, so
a download is "what the search screen shows, every page". Import is a dry run by default; a real import writes
every row or none."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from app.api.v1.record_search import AdminSearchFilters, SearchFilters
from app.api.v1.records import SUBMITTER_ROLES, record_added_payload, submitting_organization
from app.auth.dependencies import CurrentUser
from app.auth.permissions import PlatformAdmin, require_org_role
from app.core.errors import ApiError, error_body
from app.db.session import get_db
from app.models import Organization, User
from app.schemas.record_transfer import ImportReport, ImportResult
from app.services import events
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
from app.services.record_import import (
    MAX_IMPORT_BYTES,
    ImportFormat,
    ImportInvalidError,
    check_import,
    decode_upload,
    import_report,
    parse_import,
    save_import,
)
from app.services.record_search import RecordSearchFilters

router = APIRouter(tags=["record import and export"])

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


def importing_organization(organization_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Organization:
    return submitting_organization(db, user, organization_id)


@dataclass
class Upload:
    format: ImportFormat
    text: str


_MEDIA_TYPES: dict[str, ImportFormat] = {"text/csv": "csv", "application/json": "json"}


async def read_upload(request: Request) -> Upload:
    """The raw request body (no multipart), capped at 512 KB even when Content-Length is missing or wrong."""
    media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media_type not in _MEDIA_TYPES:
        raise ApiError(415, "unsupported_media_type", "Send the file as text/csv or application/json.")
    too_large = ApiError(413, "payload_too_large", f"The file is larger than {MAX_IMPORT_BYTES // 1024} KB. Split it into smaller files.")
    length = request.headers.get("content-length", "")
    if length.isdigit() and int(length) > MAX_IMPORT_BYTES:
        raise too_large
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_IMPORT_BYTES:
            raise too_large
    return Upload(format=_MEDIA_TYPES[media_type], text=decode_upload(bytes(body)))


_IMPORT_BODY = {
    "requestBody": {
        "required": True,
        "description": "The file itself as the request body, at most 512 KB and 500 records.",
        "content": {"text/csv": {"schema": {"type": "string"}}, "application/json": {"schema": {"type": "array", "items": {"type": "object"}}}},
    }
}


@router.post(
    "/organizations/{organization_id}/records/import",
    response_model=None,
    responses={200: {"model": ImportReport}, 201: {"model": ImportResult}},
    openapi_extra=_IMPORT_BODY,
)
def import_records(
    user: CurrentUser,
    db: DbSession,
    organization: Annotated[Organization, Depends(importing_organization)],  # before the body is read
    upload: Annotated[Upload, Depends(read_upload)],
    dry_run: Annotated[bool, Query(description="true (default): check and preview only. false: import all rows or none.")] = True,
) -> JSONResponse:
    """Check a CSV or JSON file of records (dry run), or import it. A real import is all-or-nothing: any row
    error answers 422 import_invalid with the report and writes nothing."""
    file = parse_import(upload.format, upload.text)
    if dry_run:
        check_import(db, organization.id, file)
        return JSONResponse(import_report(file, dry_run=True).model_dump(mode="json"))
    try:
        saved = save_import(db, organization=organization, staff=user, file=file)
    except ImportInvalidError:
        db.rollback()  # releases the vehicle locks and drops vehicles created for this attempt
        report = import_report(file, dry_run=False)
        message = f"{report.invalid_rows} of {report.total_rows} rows have errors. Nothing was imported."
        body = error_body("import_invalid", message)
        body["error"]["details"] = report.model_dump(mode="json")  # the same report as a dry run
        return JSONResponse(status_code=422, content=body)
    flagged = sum(record.is_mileage_flagged for record, _ in saved)
    record_audit(
        db, user, "records.imported", "organization", organization.id,
        {"count": len(saved), "flagged": flagged, "format": file.format},
    )
    db.commit()
    for record, vin in saved:
        events.publish("record.added", record_added_payload(record, vin))
    result = ImportResult(imported=len(saved), flagged=flagged, record_ids=[record.id for record, _ in saved])
    return JSONResponse(status_code=201, content=result.model_dump(mode="json"))
