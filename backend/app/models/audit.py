import uuid

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, UUIDPrimaryKey


class AuditEvent(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_target", "target_type", "target_id"),
        Index("ix_audit_events_created_at", "created_at"),
    )

    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    actor_label: Mapped[str] = mapped_column(String(320))  # snapshot so the trail survives user deletion
    action: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[str] = mapped_column(String(64))
    details: Mapped[dict] = mapped_column(default=dict)  # "metadata" is reserved by SQLAlchemy
