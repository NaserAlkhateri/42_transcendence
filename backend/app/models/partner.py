import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, UUIDPrimaryKey


class ApiKey(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "api_keys"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(100))
    key_prefix: Mapped[str] = mapped_column(String(16), unique=True)  # shown in the UI, used to look the key up
    key_hash: Mapped[str] = mapped_column(String(255))
    scopes: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)
    last_used_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]


class PartnerWatchlist(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "partner_watchlists"
    __table_args__ = (UniqueConstraint("api_key_id", "vehicle_id"),)

    api_key_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("api_keys.id", ondelete="CASCADE"))
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"), index=True)
    preferences: Mapped[dict] = mapped_column(default=dict)
