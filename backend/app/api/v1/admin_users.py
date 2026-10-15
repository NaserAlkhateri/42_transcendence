"""Platform-admin user management (Advanced permissions module): view, edit, delete users and manage roles."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import and_, delete, exists, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.permissions import PlatformAdmin
from app.core.errors import ApiError
from app.db.session import get_db
from app.models import (
    MemberRole,
    MemberStatus,
    Organization,
    OrganizationMember,
    OrganizationStatus,
    User,
    UserRole,
    UserSession,
    UserStatus,
)
from app.schemas.auth import EffectiveRole
from app.schemas.users import AdminUserOut, AdminUserUpdate, MembershipRoleUpdate, UserPage
from app.services.audit import record_audit
from app.services.users import to_admin_user_outs

router = APIRouter(prefix="/admin/users", tags=["admin: users"])

DbSession = Annotated[Session, Depends(get_db)]


def _has_active_membership(*roles: MemberRole):
    """Active membership with one of `roles` in an approved organization (matches permissions.effective_role)."""
    return exists().where(
        OrganizationMember.user_id == User.id,
        OrganizationMember.status == MemberStatus.ACTIVE,
        OrganizationMember.role.in_(roles),
        Organization.id == OrganizationMember.organization_id,
        Organization.status == OrganizationStatus.APPROVED,
    )


def _role_filter(role: EffectiveRole):
    """SQL condition matching permissions.effective_role, so the filter agrees with what the UI shows."""
    is_consumer_account = User.role == UserRole.CONSUMER
    if role == "platform_admin":
        return User.role == UserRole.PLATFORM_ADMIN
    if role == "entity_admin":
        return and_(is_consumer_account, _has_active_membership(MemberRole.ENTITY_ADMIN))
    if role == "entity_staff":
        return and_(
            is_consumer_account,
            _has_active_membership(MemberRole.ENTITY_STAFF),
            ~_has_active_membership(MemberRole.ENTITY_ADMIN),
        )
    return and_(is_consumer_account, ~_has_active_membership(MemberRole.ENTITY_ADMIN, MemberRole.ENTITY_STAFF))


def _get_user(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise ApiError(404, "user_not_found", "User not found.")
    return user


@router.get("", response_model=UserPage)
def list_users(
    _: PlatformAdmin,
    db: DbSession,
    q: Annotated[str | None, Query(max_length=320, description="Matches email or name")] = None,
    role: EffectiveRole | None = None,
    user_status: Annotated[UserStatus | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1, le=100_000)] = 1,  # bounded so OFFSET can never overflow
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> UserPage:
    conditions = []
    if q and q.strip():
        escaped = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        conditions.append(or_(User.email.ilike(pattern, escape="\\"), User.full_name.ilike(pattern, escape="\\")))
    if role is not None:
        conditions.append(_role_filter(role))
    if user_status is not None:
        conditions.append(User.status == user_status)

    total = db.scalar(select(func.count()).select_from(User).where(*conditions)) or 0
    users = db.scalars(
        select(User)
        .where(*conditions)
        .order_by(User.created_at.desc(), User.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return UserPage(items=to_admin_user_outs(db, list(users)), total=total, page=page, page_size=page_size)


@router.get("/{user_id}", response_model=AdminUserOut)
def get_user(user_id: uuid.UUID, _: PlatformAdmin, db: DbSession) -> AdminUserOut:
    return to_admin_user_outs(db, [_get_user(db, user_id)])[0]


@router.patch("/{user_id}", response_model=AdminUserOut)
def update_user(user_id: uuid.UUID, body: AdminUserUpdate, admin: PlatformAdmin, db: DbSession) -> AdminUserOut:
    user = _get_user(db, user_id)
    if user.id == admin.id and (
        (body.role is not None and body.role != UserRole.PLATFORM_ADMIN)
        or (body.status is not None and body.status != UserStatus.ACTIVE)
    ):
        # Keeps at least one working platform admin and stops an accidental self-lockout.
        raise ApiError(409, "cannot_demote_self", "You cannot remove your own admin role or disable yourself.")

    changes: dict[str, list] = {}
    for field in ("email", "full_name", "role", "status"):
        new = getattr(body, field)
        old = getattr(user, field)
        if new is not None and new != old:
            changes[field] = [str(old), str(new)]
            setattr(user, field, new)
    if not changes:
        return to_admin_user_outs(db, [user])[0]

    record_audit(db, admin, "user.updated", "user", user.id, {"changes": changes})
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(409, "email_taken", "An account with this email already exists.") from exc
    # After the flush, so a taken email surfaces above as 409 instead of failing inside this statement's autoflush.
    if "status" in changes and user.status == UserStatus.DISABLED:  # don't let old sessions revive on re-enable
        db.execute(
            update(UserSession)
            .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
            .values(revoked_at=func.now())
        )
    db.commit()
    return to_admin_user_outs(db, [user])[0]


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: uuid.UUID, admin: PlatformAdmin, db: DbSession) -> None:
    """Really delete the account: sessions, memberships, watchlists and notifications go with it (DB cascades).
    Service records keep the stored staff-name snapshot with staff_id set to NULL."""
    user = _get_user(db, user_id)
    if user.id == admin.id:
        raise ApiError(409, "cannot_delete_self", "You cannot delete your own account.")
    record_audit(
        db, admin, "user.deleted", "user", user.id,
        {"email": user.email, "full_name": user.full_name, "role": str(user.role)},
    )
    db.expunge(user)
    db.execute(delete(User).where(User.id == user_id))
    db.commit()


@router.patch("/{user_id}/memberships/{membership_id}", response_model=AdminUserOut)
def update_membership_role(
    user_id: uuid.UUID, membership_id: uuid.UUID, body: MembershipRoleUpdate, admin: PlatformAdmin, db: DbSession
) -> AdminUserOut:
    """Switch a member between entity_admin and entity_staff. Adding/removing members is NA-04."""
    user = _get_user(db, user_id)
    membership = db.scalar(
        select(OrganizationMember).where(OrganizationMember.id == membership_id, OrganizationMember.user_id == user.id)
    )
    if membership is None:
        raise ApiError(404, "membership_not_found", "Membership not found for this user.")
    if membership.role != body.role:
        record_audit(
            db, admin, "membership.role_changed", "organization_member", membership.id,
            {"user_id": str(user.id), "organization_id": str(membership.organization_id),
             "changes": {"role": [str(membership.role), str(body.role)]}},
        )
        membership.role = body.role
        db.commit()
    return to_admin_user_outs(db, [user])[0]
