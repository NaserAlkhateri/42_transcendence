import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.auth.dependencies import CurrentUser
from app.auth.permissions import PlatformAdmin, require_org_role
from app.core.document_limits import DOCUMENT_MAX_BYTES
from app.core.errors import ApiError
from app.db.session import get_db
from app.models import MemberRole, Organization, OrganizationDocument, User
from app.schemas.documents import DocumentOut
from app.services.audit import record_audit
from app.services.document_storage import get_document_storage
from app.services.documents import MAX_ACTIVE_DOCUMENTS, list_documents, validate_document

router = APIRouter(prefix="/organizations/{organization_id}/documents", tags=["licence documents"])
admin_router = APIRouter(prefix="/admin/organizations/{organization_id}/documents", tags=["licence documents"])
DbSession = Annotated[Session, Depends(get_db)]
ENTITY_ADMIN = {MemberRole.ENTITY_ADMIN}
logger = logging.getLogger(__name__)


def find_document(db: Session, organization_id: uuid.UUID, document_id: uuid.UUID) -> OrganizationDocument:
    document = db.scalar(select(OrganizationDocument).where(
        OrganizationDocument.id == document_id, OrganizationDocument.organization_id == organization_id,
    ))
    if document is None:
        raise ApiError(404, "document_not_found", "Licence document not found.")
    return document


@router.get("", response_model=list[DocumentOut])
def read_documents(organization_id: uuid.UUID, user: CurrentUser, db: DbSession) -> list[OrganizationDocument]:
    require_org_role(db, user, organization_id, ENTITY_ADMIN, allow_platform_admin=False)
    return list_documents(db, organization_id)


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED,
             openapi_extra={"requestBody": {"required": True, "content": {
                 media_type: {"schema": {"type": "string", "format": "binary"}}
                 for media_type in ("application/pdf", "image/png", "image/jpeg")
             }}})
async def upload_document(
    organization_id: uuid.UUID, user: CurrentUser, db: DbSession, request: Request,
    x_file_name: Annotated[str, Header(description="Original file name, percent-encoded UTF-8")],
) -> OrganizationDocument:
    await run_in_threadpool(require_org_role, db, user, organization_id, ENTITY_ADMIN, allow_platform_admin=False)
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > DOCUMENT_MAX_BYTES:
            raise ApiError(413, "payload_too_large", "Choose a file no larger than 5 MiB.")
        body.extend(chunk)
    return await run_in_threadpool(
        save_document, db, user, organization_id, x_file_name, request.headers.get("content-type", ""), bytes(body),
    )


def save_document(
    db: Session, user: User, organization_id: uuid.UUID, encoded_name: str, media_type: str, contents: bytes,
) -> OrganizationDocument:
    file_name = validate_document(encoded_name, media_type, contents)
    # Serialises the file limit and prevents organization deletion during a write.
    if db.scalar(select(Organization.id).where(Organization.id == organization_id).with_for_update()) is None:
        raise ApiError(404, "organization_not_found", "Organization not found.")
    require_org_role(db, user, organization_id, ENTITY_ADMIN, allow_platform_admin=False)
    count = db.scalar(select(func.count()).select_from(OrganizationDocument).where(
        OrganizationDocument.organization_id == organization_id, OrganizationDocument.deleted_at.is_(None),
    ))
    if count is not None and count >= MAX_ACTIVE_DOCUMENTS:
        raise ApiError(409, "too_many_documents", "An organisation can have up to ten active licence documents.")

    storage = get_document_storage()
    document = OrganizationDocument(
        organization_id=organization_id, uploaded_by_id=user.id, object_key=uuid.uuid4().hex,
        file_name=file_name, content_type=media_type, size_bytes=len(contents),
    )
    db.add(document)
    db.flush()
    storage.put(document.object_key, contents, media_type)
    try:
        db.commit()
    except SQLAlchemyError:
        key = document.object_key
        db.rollback()
        try:
            storage.remove(key)
        except ApiError:
            logger.exception("Could not clean up an uncommitted licence document object")
        raise
    return document


def download(document: OrganizationDocument) -> Response:
    if document.deleted_at is not None:
        raise ApiError(404, "document_not_found", "Licence document not found.")
    data = get_document_storage().get(document.object_key, document.size_bytes)
    return Response(data, media_type=document.content_type, headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(document.file_name, safe='')}",
        "Cache-Control": "private, no-store",
        "Content-Security-Policy": "default-src 'none'; sandbox",
    })


@router.get("/{document_id}", response_class=Response)
def read_document(organization_id: uuid.UUID, document_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    require_org_role(db, user, organization_id, ENTITY_ADMIN, allow_platform_admin=False)
    return download(find_document(db, organization_id, document_id))


@admin_router.get("/{document_id}", response_class=Response)
def admin_read_document(organization_id: uuid.UUID, document_id: uuid.UUID, _: PlatformAdmin, db: DbSession) -> Response:
    return download(find_document(db, organization_id, document_id))


@admin_router.delete("/{document_id}", response_model=DocumentOut)
def remove_document(
    organization_id: uuid.UUID, document_id: uuid.UUID, admin: PlatformAdmin, db: DbSession,
) -> OrganizationDocument:
    document = db.scalar(select(OrganizationDocument).where(
        OrganizationDocument.id == document_id, OrganizationDocument.organization_id == organization_id,
    ).with_for_update())
    if document is None:
        raise ApiError(404, "document_not_found", "Licence document not found.")
    if document.deleted_at is None:
        document.deleted_at = datetime.now(UTC)
        record_audit(db, admin, "organization.document_removed", "organization_document", document.id,
                     {"organization_id": str(organization_id)})
        # Hide the document and persist the audit entry before attempting the physical purge.
        db.commit()
    if document.purged_at is None:
        get_document_storage().remove(document.object_key)
        document.purged_at = datetime.now(UTC)
        db.commit()
    return document
