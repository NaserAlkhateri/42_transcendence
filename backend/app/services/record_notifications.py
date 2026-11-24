from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, insert, literal, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.models import Notification, ServiceRecord, Watchlist
from app.services import events

WATCH_RECORD_EVENT = "record.added"


@dataclass(frozen=True)
class Notice:
    id: UUID
    user_id: UUID
    created_at: datetime


def create_watch_notices(db: Session, record: ServiceRecord, vin: str) -> list[Notice]:
    """Store one durable notice per enabled watcher in the same transaction as the record."""
    table = Notification.__table__
    recipients = select(
        func.gen_random_uuid(), Watchlist.user_id, literal(WATCH_RECORD_EVENT),
        literal({"vin": vin, "record_id": str(record.id)}, type_=JSONB),
    ).where(Watchlist.vehicle_id == record.vehicle_id, Watchlist.notifications_enabled.is_(True))
    rows = db.execute(insert(table).from_select(["id", "user_id", "event_type", "payload"], recipients)
                      .returning(table.c.id, table.c.user_id, table.c.created_at))
    return [Notice(*row) for row in rows]


def publish_record_added(payload: dict, notices: list[Notice]) -> None:
    events.publish("record.added", payload)
    for notice in notices:
        events.publish("notification.created", {
            "notification_id": str(notice.id), "event_type": WATCH_RECORD_EVENT,
            "created_at": notice.created_at.isoformat(), "user_id": str(notice.user_id),
        })
