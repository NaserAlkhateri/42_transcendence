import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.permissions import effective_role
from app.models import Organization, OrganizationMember, User
from app.schemas.auth import MembershipOut, UserOut
from app.schemas.users import AdminUserOut


def memberships_by_user(db: Session, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[tuple[OrganizationMember, Organization]]]:
    """One query for every listed user's memberships (avoids N+1 on the admin list)."""
    grouped: dict[uuid.UUID, list[tuple[OrganizationMember, Organization]]] = defaultdict(list)
    if not user_ids:
        return grouped
    rows = db.execute(
        select(OrganizationMember, Organization)
        .join(Organization, Organization.id == OrganizationMember.organization_id)
        .where(OrganizationMember.user_id.in_(user_ids))
        .order_by(Organization.name)
    ).all()
    for membership, organization in rows:
        grouped[membership.user_id].append((membership, organization))
    return grouped


def _membership_out(membership: OrganizationMember, organization: Organization) -> MembershipOut:
    return MembershipOut(
        id=membership.id,
        organization_id=organization.id,
        organization_name=organization.name,
        organization_status=organization.status,
        role=membership.role,
        status=membership.status,
    )


def to_user_out(db: Session, user: User) -> UserOut:
    pairs = memberships_by_user(db, [user.id])[user.id]
    return UserOut(
        **_base_fields(user),
        effective_role=effective_role(user, [m for m, _ in pairs]),
        memberships=[_membership_out(m, o) for m, o in pairs],
    )


def to_admin_user_outs(db: Session, users: list[User]) -> list[AdminUserOut]:
    grouped = memberships_by_user(db, [user.id for user in users])
    return [
        AdminUserOut(
            **_base_fields(user),
            status=user.status,
            updated_at=user.updated_at,
            effective_role=effective_role(user, [m for m, _ in grouped[user.id]]),
            memberships=[_membership_out(m, o) for m, o in grouped[user.id]],
        )
        for user in users
    ]


def _base_fields(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "must_change_password": user.must_change_password,
        "created_at": user.created_at,
    }
