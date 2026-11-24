from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.db.session import get_db
from app.models import Notification
from app.services.record_notifications import WATCH_RECORD_EVENT

router = APIRouter(prefix="/notifications", tags=["notifications"])


class WatchNotice(BaseModel):
    id: UUID
    event_type: Literal["record.added"]
    vin: str
    record_id: UUID
    created_at: datetime


@router.get("", response_model=list[WatchNotice])
def recent_notifications(user: CurrentUser, db: Annotated[Session, Depends(get_db)]) -> list[WatchNotice]:
    """The user's latest watch alerts, including any missed while the socket was offline."""
    rows = db.scalars(select(Notification).where(
        Notification.user_id == user.id, Notification.event_type == WATCH_RECORD_EVENT,
    ).order_by(Notification.created_at.desc(), Notification.id.desc()).limit(20))
    return [WatchNotice(id=row.id, event_type=WATCH_RECORD_EVENT, created_at=row.created_at,
                        vin=row.payload["vin"], record_id=row.payload["record_id"]) for row in rows]
