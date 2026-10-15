import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import MemberStatus, Organization, OrganizationMember, ServiceRecord, User
from app.schemas.organizations import (
    AdminOrganizationDetail,
    AdminOrganizationOut,
    OrganizationMemberOut,
    OrganizationOut,
    OrganizationUpdate,
)


def get_organization(db: Session, organization_id: uuid.UUID) -> Organization:
    organization = db.get(Organization, organization_id)
    if organization is None:
        raise ApiError(404, "organization_not_found", "Organization not found.")
    return organization


def licence_taken_error() -> ApiError:
    return ApiError(409, "registration_number_taken", "An organization with this trade licence number is already registered.")


def apply_changes(organization: Organization, body: OrganizationUpdate) -> dict[str, list[str | None]]:
    """Set the provided fields and return {field: [old, new]} for the audit trail."""
    changes: dict[str, list[str | None]] = {}
    for field in ("name", "kind", "registration_number", "emirate"):
        new = getattr(body, field)
        old = getattr(organization, field)
        if new is not None and new != old:
            changes[field] = [None if old is None else str(old), str(new)]
            setattr(organization, field, new)
    return changes


def to_admin_outs(db: Session, organizations: list[Organization]) -> list[AdminOrganizationOut]:
    """Organizations with their active-member and record counts, in two grouped queries."""
    ids = [organization.id for organization in organizations]
    members: dict[uuid.UUID, int] = {}
    records: dict[uuid.UUID, int] = {}
    if ids:
        members = dict(db.execute(
            select(OrganizationMember.organization_id, func.count())
            .where(OrganizationMember.organization_id.in_(ids), OrganizationMember.status == MemberStatus.ACTIVE)
            .group_by(OrganizationMember.organization_id)
        ).all())
        records = dict(db.execute(
            select(ServiceRecord.organization_id, func.count())
            .where(ServiceRecord.organization_id.in_(ids))
            .group_by(ServiceRecord.organization_id)
        ).all())
    return [
        AdminOrganizationOut(
            **OrganizationOut.model_validate(organization).model_dump(),
            member_count=members.get(organization.id, 0),
            record_count=records.get(organization.id, 0),
        )
        for organization in organizations
    ]


def to_admin_detail(db: Session, organization: Organization) -> AdminOrganizationDetail:
    rows = db.execute(
        select(OrganizationMember, User)
        .join(User, User.id == OrganizationMember.user_id)
        .where(OrganizationMember.organization_id == organization.id)
        .order_by(OrganizationMember.role, User.full_name)
    ).all()
    members = [
        OrganizationMemberOut(
            membership_id=membership.id, user_id=user.id, full_name=user.full_name, email=user.email,
            role=membership.role, status=membership.status,
        )
        for membership, user in rows
    ]
    return AdminOrganizationDetail(**to_admin_outs(db, [organization])[0].model_dump(), members=members)


def review_payload(organization: Organization) -> dict:
    """For `organization.reviewed` events (notifications, BU-05): no licence number or member data."""
    return {
        "organization_id": str(organization.id),
        "name": organization.name,
        "status": str(organization.status),
        "rejection_reason": organization.rejection_reason,
    }
