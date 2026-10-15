"""Organization system (NA-03), member side: register a business, view it, keep its details up to date
and resubmit after a rejection. Platform-admin review and CRUD live in admin_organizations.py."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.auth.permissions import require_org_role
from app.core.errors import ApiError
from app.db.session import get_db
from app.models import MemberRole, Organization, OrganizationMember, OrganizationStatus, UserRole
from app.schemas.organizations import OrganizationOut, OrganizationRegistration, OrganizationUpdate
from app.services.audit import record_audit
from app.services.organizations import apply_changes, get_organization, licence_taken_error

router = APIRouter(prefix="/organizations", tags=["organizations"])

DbSession = Annotated[Session, Depends(get_db)]
ANY_MEMBER = {MemberRole.ENTITY_ADMIN, MemberRole.ENTITY_STAFF}


@router.post("", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
def register_organization(body: OrganizationRegistration, user: CurrentUser, db: DbSession) -> Organization:
    """Apply as a workshop or dealership. The applicant becomes its entity admin; it stays pending (and cannot
    add records) until a platform admin approves it."""
    if user.role == UserRole.PLATFORM_ADMIN:
        raise ApiError(403, "forbidden", "Platform admins create organizations from the admin page.")
    already_pending = db.scalar(
        select(Organization.id)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(
            OrganizationMember.user_id == user.id,
            OrganizationMember.role == MemberRole.ENTITY_ADMIN,
            Organization.status == OrganizationStatus.PENDING,
        )
        .limit(1)
    )
    if already_pending is not None:
        raise ApiError(409, "registration_pending", "You already have a registration waiting for review.")

    organization = Organization(
        name=body.name, kind=body.kind, registration_number=body.registration_number, emirate=body.emirate,
        status=OrganizationStatus.PENDING,
    )
    db.add(organization)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise licence_taken_error() from exc
    db.add(OrganizationMember(organization_id=organization.id, user_id=user.id, role=MemberRole.ENTITY_ADMIN))
    record_audit(db, user, "organization.registered", "organization", organization.id, {"name": organization.name})
    db.commit()
    return organization


@router.get("/{organization_id}", response_model=OrganizationOut)
def read_organization(organization_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Organization:
    """Members (any role) see their own organization, including why it was rejected."""
    organization = get_organization(db, organization_id)
    require_org_role(db, user, organization_id, ANY_MEMBER)
    return organization


@router.patch("/{organization_id}", response_model=OrganizationOut)
def update_organization(organization_id: uuid.UUID, body: OrganizationUpdate, user: CurrentUser, db: DbSession) -> Organization:
    """Entity admins keep their details current. The licence number is fixed once approved, because it is
    what the platform admin verified; changing it means asking a platform admin."""
    organization = get_organization(db, organization_id)
    require_org_role(db, user, organization_id, {MemberRole.ENTITY_ADMIN}, allow_platform_admin=False)
    if (
        body.registration_number is not None
        and body.registration_number != organization.registration_number
        and organization.status == OrganizationStatus.APPROVED
    ):
        raise ApiError(409, "registration_locked", "The trade licence number of an approved organization cannot be changed.")
    changes = apply_changes(organization, body)
    if changes:
        record_audit(db, user, "organization.updated", "organization", organization.id, {"changes": changes})
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise licence_taken_error() from exc
        db.commit()
    return organization


@router.post("/{organization_id}/resubmit", response_model=OrganizationOut)
def resubmit_organization(organization_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Organization:
    """After fixing what the rejection asked for, send the registration back for review."""
    organization = get_organization(db, organization_id)
    require_org_role(db, user, organization_id, {MemberRole.ENTITY_ADMIN}, allow_platform_admin=False)
    if organization.status != OrganizationStatus.REJECTED:
        raise ApiError(409, "not_rejected", "Only a rejected registration can be resubmitted.")
    organization.status = OrganizationStatus.PENDING
    organization.rejection_reason = None
    record_audit(db, user, "organization.resubmitted", "organization", organization.id, {})
    db.commit()
    return organization

