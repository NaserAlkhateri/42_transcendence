"""Organization system (NA-04): entity admins (and platform admins) add and remove members, create staff
accounts with a temporary password, and assign entity roles within their own organization."""

import secrets
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.auth.passwords import hash_password
from app.auth.permissions import require_org_role
from app.core.errors import ApiError
from app.db.session import get_db
from app.models import MemberRole, MemberStatus, Organization, OrganizationMember, OrganizationStatus, User, UserRole
from app.schemas.organizations import (
    MemberAdd,
    MemberUpdate,
    OrganizationMemberOut,
    StaffAccountCreate,
    StaffAccountCreated,
)
from app.services import events
from app.services.audit import record_audit
from app.services.organizations import get_organization, member_out, members_of, require_another_admin

router = APIRouter(prefix="/organizations/{organization_id}/members", tags=["organization members"])

DbSession = Annotated[Session, Depends(get_db)]
MANAGERS = {MemberRole.ENTITY_ADMIN}


def managed_organization(db: Session, user: User, organization_id: uuid.UUID, *, lock: bool = False) -> Organization:
    """The organization, if `user` is one of its active entity admins or a platform admin. With `lock`, the row
    is locked so concurrent changes can't both remove "the other" admin and leave none."""
    organization = get_organization(db, organization_id)
    require_org_role(db, user, organization_id, MANAGERS)
    if lock:
        db.execute(select(Organization.id).where(Organization.id == organization_id).with_for_update())
    return organization


def require_onboarding_allowed(user: User, organization: Organization) -> None:
    """Only approved organizations take on staff, so an unvetted registration can't mint accounts.
    Platform admins may staff any organization (e.g. one they just created)."""
    if user.role != UserRole.PLATFORM_ADMIN and organization.status != OrganizationStatus.APPROVED:
        raise ApiError(403, "organization_not_approved", "Your organization must be approved before it can add members.")


def get_membership(db: Session, organization_id: uuid.UUID, membership_id: uuid.UUID) -> tuple[OrganizationMember, User]:
    row = db.execute(
        select(OrganizationMember, User)
        .join(User, User.id == OrganizationMember.user_id)
        .where(OrganizationMember.id == membership_id, OrganizationMember.organization_id == organization_id)
    ).first()
    if row is None:
        raise ApiError(404, "membership_not_found", "Member not found in this organization.")
    return row[0], row[1]


def membership_payload(organization: Organization, membership: OrganizationMember) -> dict:
    """For `membership.*` events (notifications, BU-05)."""
    return {
        "organization_id": str(organization.id),
        "organization_name": organization.name,
        "user_id": str(membership.user_id),
        "role": str(membership.role),
        "status": str(membership.status),
    }


def add_membership(db: Session, actor: User, organization: Organization, member: User, role: MemberRole, action: str) -> OrganizationMember:
    membership = OrganizationMember(organization_id=organization.id, user_id=member.id, role=role)
    db.add(membership)
    db.flush()
    record_audit(
        db, actor, action, "organization_member", membership.id,
        {"organization_id": str(organization.id), "user_id": str(member.id), "email": member.email, "role": str(role)},
    )
    return membership


@router.get("", response_model=list[OrganizationMemberOut])
def list_members(organization_id: uuid.UUID, user: CurrentUser, db: DbSession) -> list[OrganizationMemberOut]:
    managed_organization(db, user, organization_id)
    return members_of(db, organization_id)


@router.post("", response_model=OrganizationMemberOut, status_code=status.HTTP_201_CREATED)
def add_member(organization_id: uuid.UUID, body: MemberAdd, user: CurrentUser, db: DbSession) -> OrganizationMemberOut:
    """Add someone who already has an account (e.g. a consumer who now works here)."""
    organization = managed_organization(db, user, organization_id)
    require_onboarding_allowed(user, organization)
    member = db.scalar(select(User).where(User.email == body.email))
    if member is None:
        raise ApiError(404, "user_not_found", "No account uses this email. Create a staff account instead.")
    if member.role == UserRole.PLATFORM_ADMIN:
        raise ApiError(409, "cannot_add_platform_admin", "Platform admins cannot join an organization.")
    already = db.scalar(
        select(OrganizationMember.id).where(
            OrganizationMember.organization_id == organization_id, OrganizationMember.user_id == member.id
        )
    )
    if already is not None:
        raise ApiError(409, "already_member", "This person is already a member.")
    membership = add_membership(db, user, organization, member, body.role, "membership.added")
    db.commit()
    events.publish("membership.added", membership_payload(organization, membership))
    return member_out(membership, member)


@router.post("/staff-accounts", response_model=StaffAccountCreated, status_code=status.HTTP_201_CREATED)
def create_staff_account(
    organization_id: uuid.UUID, body: StaffAccountCreate, user: CurrentUser, db: DbSession
) -> StaffAccountCreated:
    """Create a new account and its membership. The temporary password is returned once; the staff member must
    replace it before doing anything else (must_change_password, enforced by CurrentUser)."""
    organization = managed_organization(db, user, organization_id)
    require_onboarding_allowed(user, organization)
    temporary_password = secrets.token_urlsafe(12)  # 16 URL-safe characters, ~96 bits
    member = User(
        email=body.email, full_name=body.full_name, password_hash=hash_password(temporary_password),
        role=UserRole.CONSUMER, must_change_password=True,
    )
    db.add(member)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(409, "email_taken", "An account with this email already exists. Add it as a member instead.") from exc
    membership = add_membership(db, user, organization, member, body.role, "membership.staff_account_created")
    db.commit()
    events.publish("membership.added", membership_payload(organization, membership))
    return StaffAccountCreated(member=member_out(membership, member), temporary_password=temporary_password)


@router.patch("/{membership_id}", response_model=OrganizationMemberOut)
def update_member(
    organization_id: uuid.UUID, membership_id: uuid.UUID, body: MemberUpdate, user: CurrentUser, db: DbSession
) -> OrganizationMemberOut:
    """Switch between entity_admin and entity_staff, or deactivate/reactivate a member. Entity admins can only
    grant roles they hold themselves, inside their own organization."""
    organization = managed_organization(db, user, organization_id, lock=True)
    membership, member = get_membership(db, organization_id, membership_id)
    demoting = body.role == MemberRole.ENTITY_STAFF or body.status == MemberStatus.INACTIVE
    if demoting:
        require_another_admin(db, membership)
    changes: dict[str, list[str]] = {}
    for field in ("role", "status"):
        new = getattr(body, field)
        if new is not None and new != getattr(membership, field):
            changes[field] = [str(getattr(membership, field)), str(new)]
            setattr(membership, field, new)
    if changes:
        record_audit(
            db, user, "membership.updated", "organization_member", membership.id,
            {"organization_id": str(organization.id), "user_id": str(member.id), "changes": changes},
        )
        db.commit()
        events.publish("membership.updated", membership_payload(organization, membership))
    return member_out(membership, member)


@router.delete("/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(organization_id: uuid.UUID, membership_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    """Remove someone from the organization. Their account stays (as a consumer); records they submitted keep
    their name. Deleting the account itself is a platform-admin action (NA-02)."""
    organization = managed_organization(db, user, organization_id, lock=True)
    membership, member = get_membership(db, organization_id, membership_id)
    require_another_admin(db, membership)
    payload = membership_payload(organization, membership)
    record_audit(
        db, user, "membership.removed", "organization_member", membership.id,
        {"organization_id": str(organization.id), "user_id": str(member.id), "email": member.email,
         "role": str(membership.role)},
    )
    db.execute(delete(OrganizationMember).where(OrganizationMember.id == membership.id))
    db.commit()
    events.publish("membership.removed", payload)
