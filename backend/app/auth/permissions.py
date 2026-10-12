"""Role and organization-scope checks.

Roles come from two places: users.role (consumer | platform_admin) and organization_members.role
(entity_admin | entity_staff, per organization). A workshop employee is a consumer account with an
active membership, so organization rights are always checked against a specific organization."""

import uuid
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core.errors import ApiError
from app.models import MemberRole, MemberStatus, OrganizationMember, User, UserRole

# Highest first: what the UI shows as a user's role when they hold several.
EFFECTIVE_ROLES = ("platform_admin", "entity_admin", "entity_staff", "consumer")


def effective_role(user: User, memberships: list[OrganizationMember]) -> str:
    if user.role == UserRole.PLATFORM_ADMIN:
        return "platform_admin"
    active = {m.role for m in memberships if m.status == MemberStatus.ACTIVE}
    if MemberRole.ENTITY_ADMIN in active:
        return "entity_admin"
    if MemberRole.ENTITY_STAFF in active:
        return "entity_staff"
    return "consumer"


def require_platform_admin(user: CurrentUser) -> User:
    if user.role != UserRole.PLATFORM_ADMIN:
        raise ApiError(403, "forbidden", "Platform admin access required.")
    return user


PlatformAdmin = Annotated[User, Depends(require_platform_admin)]


def require_org_role(
    db: Session, user: User, organization_id: uuid.UUID, roles: set[MemberRole], *, allow_platform_admin: bool = True
) -> OrganizationMember | None:
    """Allow the action only for an active member of *this* organization holding one of `roles`.
    Returns the membership, or None when a platform admin acts on any organization."""
    if allow_platform_admin and user.role == UserRole.PLATFORM_ADMIN:
        return None
    membership = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user.id,
            OrganizationMember.status == MemberStatus.ACTIVE,
        )
    )
    if membership is None or membership.role not in roles:
        raise ApiError(403, "forbidden", "You do not have permission for this organization.")
    return membership
