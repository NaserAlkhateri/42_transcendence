from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, StrictBool
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core.errors import ApiError
from app.db.session import get_db
from app.models import Notification
from app.services import events

router = APIRouter(prefix="/notifications", tags=["notifications"])
DbSession = Annotated[Session, Depends(get_db)]


class NoticeOut(BaseModel):
    id: UUID
    event_type: str
    created_at: datetime
    read_at: datetime | None
    vin: str | None = None
    record_id: UUID | None = None
    organization_id: UUID | None = None
    organization_name: str | None = None
    status: str | None = None


class Inbox(BaseModel):
    items: list[NoticeOut]
    total: int
    unread_count: int


class ReadState(BaseModel):
    read: StrictBool


def present(row: Notification) -> NoticeOut:
    # Keep internal recipient IDs and arbitrary domain payloads out of the public response.
    fields: tuple[str, ...] = ()
    if row.event_type == "record.added":
        fields = ("vin", "record_id")
    elif row.event_type.startswith(("organization.", "membership.")):
        fields = ("organization_id", "organization_name")
        if row.event_type == "organization.reviewed":
            fields += ("status",)
    return NoticeOut(id=row.id, event_type=row.event_type, created_at=row.created_at, read_at=row.read_at,
                     **{key: row.payload.get(key) for key in fields})


@router.get("", response_model=Inbox)
def inbox(user: CurrentUser, db: DbSession, unread: bool = False,
          page: Annotated[int, Query(ge=1, le=100_000)] = 1,
          page_size: Annotated[int, Query(ge=1, le=50)] = 20) -> Inbox:
    owner = Notification.user_id == user.id
    total, unread_count = db.execute(select(
        func.count(), func.count().filter(Notification.read_at.is_(None)),
    ).select_from(Notification).where(owner)).one()
    query = select(Notification).where(owner)
    if unread:
        query = query.where(Notification.read_at.is_(None))
    rows = db.scalars(query.order_by(Notification.created_at.desc(), Notification.id.desc())
                      .offset((page - 1) * page_size).limit(page_size))
    return Inbox(items=[present(row) for row in rows], total=unread_count if unread else total, unread_count=unread_count)


@router.post("/read-all", status_code=204)
def mark_all_read(user: CurrentUser, db: DbSession) -> None:
    user_id = str(user.id)
    result = db.execute(update(Notification).where(
        Notification.user_id == user.id, Notification.read_at.is_(None),
    ).values(read_at=func.now()))
    changed = result.rowcount > 0
    db.commit()
    if changed:
        events.publish("notification.read_state_changed", {"user_id": user_id})


@router.patch("/{notice_id}", response_model=NoticeOut)
def mark_notice(notice_id: UUID, state: ReadState, user: CurrentUser, db: DbSession) -> NoticeOut:
    row = db.scalar(select(Notification).where(Notification.id == notice_id,
                                               Notification.user_id == user.id).with_for_update())
    if row is None:
        raise ApiError(404, "notification_not_found", "Notification not found.")
    if (row.read_at is not None) == state.read:
        return present(row)
    user_id = str(user.id)
    row.read_at = datetime.now(UTC) if state.read else None
    answer = present(row)
    db.commit()
    events.publish("notification.read_state_changed", {"user_id": user_id})
    return answer
