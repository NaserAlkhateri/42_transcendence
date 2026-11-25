from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ServiceRecord, Watchlist
from app.services import events
from app.services.notifications import Notice, publish_notices, store_notices

WATCH_RECORD_EVENT = "record.added"


def create_watch_notices(db: Session, record: ServiceRecord, vin: str) -> list[Notice]:
    """Store one durable notice per enabled watcher in the same transaction as the record."""
    recipients = select(Watchlist.user_id).where(
        Watchlist.vehicle_id == record.vehicle_id, Watchlist.notifications_enabled.is_(True),
    )
    return store_notices(db, recipients, WATCH_RECORD_EVENT, {"vin": vin, "record_id": str(record.id)})


def publish_record_added(payload: dict, notices: list[Notice]) -> None:
    events.publish("record.added", payload)
    publish_notices(notices)
