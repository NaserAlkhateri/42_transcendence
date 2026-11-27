from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, insert, literal, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.models import MemberStatus, Notification, Organization, OrganizationMember, User, UserRole, UserStatus
from app.services import events


@dataclass(frozen=True)
class Notice:
    id: UUID
    user_id: UUID
    created_at: datetime
    event_type: str


def store_notices(db: Session, recipients: Select, event_type: str, payload: dict) -> list[Notice]:
    """Write recipient snapshots in the same transaction as the action that caused them."""
    recipient = recipients.subquery()
    recipient_id, = recipient.c
    table = Notification.__table__
    rows = db.execute(insert(table).from_select(
        ["id", "user_id", "event_type", "payload"],
        select(func.gen_random_uuid(), recipient_id, literal(event_type), literal(payload, type_=JSONB)),
    ).returning(table.c.id, table.c.user_id, table.c.created_at, table.c.event_type))
    return [Notice(*row) for row in rows]


def organization_notices(
    db: Session, organization: Organization, event_type: str, *, actor_id: UUID,
) -> list[Notice]:
    if event_type in {"organization.registered", "organization.resubmitted"}:
        recipients = select(User.id).where(User.role == UserRole.PLATFORM_ADMIN, User.status == UserStatus.ACTIVE,
                                           User.id != actor_id)
    else:
        recipients = select(OrganizationMember.user_id).where(
            OrganizationMember.organization_id == organization.id, OrganizationMember.status == MemberStatus.ACTIVE,
            OrganizationMember.user_id != actor_id,
        )
    payload = {"organization_id": str(organization.id), "organization_name": organization.name}
    if event_type == "organization.reviewed":
        payload["status"] = str(organization.status)
    return store_notices(db, recipients, event_type, payload)


def member_notice(db: Session, organization: Organization, user_id: UUID, event_type: str) -> list[Notice]:
    return store_notices(db, select(User.id).where(User.id == user_id), event_type, {
        "organization_id": str(organization.id), "organization_name": organization.name,
    })


def account_notice(db: Session, user_id: UUID, event_type: str) -> list[Notice]:
    return store_notices(db, select(User.id).where(User.id == user_id), event_type, {})


def publish_notices(notices: Iterable[Notice]) -> None:
    for notice in notices:
        events.publish("notification.created", {
            "notification_id": str(notice.id), "event_type": notice.event_type,
            "created_at": notice.created_at.isoformat(), "user_id": str(notice.user_id),
        })
