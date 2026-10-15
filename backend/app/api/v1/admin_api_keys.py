"""Platform admins issue and revoke partner API keys (NA-05). A key is shown once, at issue time."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.api_keys import DEFAULT_SCOPES, generate_key
from app.auth.permissions import PlatformAdmin
from app.core.errors import ApiError
from app.db.session import get_db
from app.models import ApiKey, PartnerWatchlist, User
from app.schemas.partner import ApiKeyCreate, ApiKeyIssued, ApiKeyOut
from app.services.audit import record_audit

router = APIRouter(prefix="/admin/api-keys", tags=["admin: partner API keys"])

DbSession = Annotated[Session, Depends(get_db)]


def key_outs(db: Session, key_id: uuid.UUID | None = None) -> list[ApiKeyOut]:
    watch_count = (
        select(func.count()).where(PartnerWatchlist.api_key_id == ApiKey.id).correlate(ApiKey).scalar_subquery()
    )
    query = (
        select(ApiKey, User.email, watch_count)
        .outerjoin(User, User.id == ApiKey.issued_by_id)
        .order_by(ApiKey.revoked_at.is_not(None), ApiKey.created_at.desc(), ApiKey.id)  # active keys first
    )
    if key_id is not None:
        query = query.where(ApiKey.id == key_id)
    return [
        ApiKeyOut(
            id=key.id, partner_name=key.partner_name, key_prefix=key.key_prefix, scopes=key.scopes,
            created_at=key.created_at, issued_by=email, last_used_at=key.last_used_at, revoked_at=key.revoked_at,
            watch_count=watches,
        )
        for key, email, watches in db.execute(query).all()
    ]


@router.get("", response_model=list[ApiKeyOut])
def list_keys(_: PlatformAdmin, db: DbSession) -> list[ApiKeyOut]:
    return key_outs(db)


@router.post("", response_model=ApiKeyIssued, status_code=status.HTTP_201_CREATED)
def issue_key(body: ApiKeyCreate, admin: PlatformAdmin, db: DbSession) -> ApiKeyIssued:
    """Issue a key for a named partner. The full key is in this response only; store it somewhere safe."""
    generated = generate_key()
    key = ApiKey(
        partner_name=body.partner_name, issued_by_id=admin.id, key_prefix=generated.prefix,
        key_hash=generated.secret_hash, scopes=list(DEFAULT_SCOPES),
    )
    db.add(key)
    db.flush()
    record_audit(db, admin, "api_key.issued", "api_key", key.id, {"partner_name": key.partner_name, "key_prefix": key.key_prefix})
    db.commit()
    return ApiKeyIssued(key=key_outs(db, key.id)[0], api_key=generated.full_key)


@router.post("/{key_id}/revoke", response_model=ApiKeyOut)
def revoke_key(key_id: uuid.UUID, admin: PlatformAdmin, db: DbSession) -> ApiKeyOut:
    """Revoke at once: the next call with this key answers 401. Its watchlist is kept for the audit trail."""
    key = db.get(ApiKey, key_id)
    if key is None:
        raise ApiError(404, "api_key_not_found", "API key not found.")
    if key.revoked_at is not None:
        raise ApiError(409, "already_revoked", "This key is already revoked.")
    key.revoked_at = datetime.now(UTC)
    record_audit(db, admin, "api_key.revoked", "api_key", key.id, {"partner_name": key.partner_name, "key_prefix": key.key_prefix})
    db.commit()
    return key_outs(db, key.id)[0]
