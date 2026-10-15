"""Organization system (NA-03), platform-admin side: review registrations and create, edit, delete organizations."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import case, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.permissions import PlatformAdmin
from app.core.errors import ApiError
from app.db.session import get_db
from app.models import MemberStatus, Organization, OrganizationKind, OrganizationMember, OrganizationStatus
from app.schemas.organizations import (
    AdminOrganizationDetail,
    Emirate,
    OrganizationPage,
    OrganizationRegistration,
    OrganizationUpdate,
    Rejection,
)
from app.services import events
from app.services.audit import record_audit
from app.services.organizations import (
    apply_changes,
    get_organization,
    licence_taken_error,
    review_payload,
    to_admin_detail,
    to_admin_outs,
)

router = APIRouter(prefix="/admin/organizations", tags=["admin: organizations"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=OrganizationPage)
def list_organizations(
    _: PlatformAdmin,
    db: DbSession,
    q: Annotated[str | None, Query(max_length=200, description="Matches name or trade licence number")] = None,
    org_status: Annotated[OrganizationStatus | None, Query(alias="status")] = None,
    kind: OrganizationKind | None = None,
    emirate: Emirate | None = None,
    page: Annotated[int, Query(ge=1, le=100_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> OrganizationPage:
    """Pending registrations come first, so the review queue is always at the top."""
    conditions = []
    if q and q.strip():
        escaped = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        conditions.append(or_(
            Organization.name.ilike(pattern, escape="\\"), Organization.registration_number.ilike(pattern, escape="\\")
        ))
    if org_status is not None:
        conditions.append(Organization.status == org_status)
    if kind is not None:
        conditions.append(Organization.kind == kind)
    if emirate is not None:
        conditions.append(Organization.emirate == emirate)

    total = db.scalar(select(func.count()).select_from(Organization).where(*conditions)) or 0
    pending_first = case((Organization.status == OrganizationStatus.PENDING, 0), else_=1)
    organizations = db.scalars(
        select(Organization)
        .where(*conditions)
        .order_by(pending_first, Organization.created_at.desc(), Organization.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return OrganizationPage(items=to_admin_outs(db, list(organizations)), total=total, page=page, page_size=page_size)


@router.get("/{organization_id}", response_model=AdminOrganizationDetail)
def get_organization_detail(organization_id: uuid.UUID, _: PlatformAdmin, db: DbSession) -> AdminOrganizationDetail:
    return to_admin_detail(db, get_organization(db, organization_id))


@router.post("", response_model=AdminOrganizationDetail, status_code=status.HTTP_201_CREATED)
def create_organization(body: OrganizationRegistration, admin: PlatformAdmin, db: DbSession) -> AdminOrganizationDetail:
    """An admin-created organization is approved at once: the admin is the one who vetted it.
    It has no members until an admin adds them (NA-04)."""
    now = datetime.now(UTC)
    organization = Organization(
        name=body.name, kind=body.kind, registration_number=body.registration_number, emirate=body.emirate,
        status=OrganizationStatus.APPROVED, approved_at=now, reviewed_at=now,
    )
    db.add(organization)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise licence_taken_error() from exc
    record_audit(db, admin, "organization.created", "organization", organization.id, {"name": organization.name})
    db.commit()
    return to_admin_detail(db, organization)


@router.patch("/{organization_id}", response_model=AdminOrganizationDetail)
def update_organization(
    organization_id: uuid.UUID, body: OrganizationUpdate, admin: PlatformAdmin, db: DbSession
) -> AdminOrganizationDetail:
    """Admins may edit every field, including the licence number of an approved organization."""
    organization = get_organization(db, organization_id)
    changes = apply_changes(organization, body)
    if changes:
        record_audit(db, admin, "organization.updated", "organization", organization.id, {"changes": changes})
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise licence_taken_error() from exc
        db.commit()
    return to_admin_detail(db, organization)


@router.post("/{organization_id}/approve", response_model=AdminOrganizationDetail)
def approve_organization(organization_id: uuid.UUID, admin: PlatformAdmin, db: DbSession) -> AdminOrganizationDetail:
    """Approve a pending (or previously rejected) organization; its active members can then add records."""
    organization = get_organization(db, organization_id)
    if organization.status == OrganizationStatus.APPROVED:
        raise ApiError(409, "already_approved", "This organization is already approved.")
    now = datetime.now(UTC)
    previous = organization.status
    organization.status = OrganizationStatus.APPROVED
    organization.rejection_reason = None
    organization.approved_at = now
    organization.reviewed_at = now
    record_audit(
        db, admin, "organization.approved", "organization", organization.id,
        {"changes": {"status": [str(previous), "approved"]}},
    )
    db.commit()
    events.publish("organization.reviewed", review_payload(organization))
    return to_admin_detail(db, organization)


@router.post("/{organization_id}/reject", response_model=AdminOrganizationDetail)
def reject_organization(
    organization_id: uuid.UUID, body: Rejection, admin: PlatformAdmin, db: DbSession
) -> AdminOrganizationDetail:
    """Reject a pending registration, or withdraw an approval (e.g. the licence turns out to be invalid).
    Members stop being able to add records at once; existing history stays."""
    organization = get_organization(db, organization_id)
    if organization.status == OrganizationStatus.REJECTED:
        raise ApiError(409, "already_rejected", "This organization is already rejected.")
    previous = organization.status
    organization.status = OrganizationStatus.REJECTED
    organization.rejection_reason = body.reason
    organization.approved_at = None
    organization.reviewed_at = datetime.now(UTC)
    record_audit(
        db, admin, "organization.rejected", "organization", organization.id,
        {"changes": {"status": [str(previous), "rejected"]}, "reason": body.reason},
    )
    db.commit()
    events.publish("organization.reviewed", review_payload(organization))
    return to_admin_detail(db, organization)


@router.delete("/{organization_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_organization(organization_id: uuid.UUID, admin: PlatformAdmin, db: DbSession) -> None:
    """Really delete the organization and its memberships (DB cascade). Its service records stay, showing the
    stored organization name with organization_id set to NULL. The member accounts themselves are kept."""
    organization = get_organization(db, organization_id)
    member_count = db.scalar(
        select(func.count()).where(
            OrganizationMember.organization_id == organization.id, OrganizationMember.status == MemberStatus.ACTIVE
        )
    )
    record_audit(
        db, admin, "organization.deleted", "organization", organization.id,
        {
            "name": organization.name,
            "registration_number": organization.registration_number,
            "status": str(organization.status),
            "active_members": member_count,
        },
    )
    db.expunge(organization)
    db.execute(delete(Organization).where(Organization.id == organization_id))
    db.commit()
