import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, UUIDPrimaryKey


class ApiKey(UUIDPrimaryKey, CreatedAt, Base):
    """A partner's key for the public API (NA-05). Keys belong to named partners (insurers, marketplaces),
    not to organizations, and are issued and revoked by platform admins. Only a hash of the secret is stored."""

    __tablename__ = "api_keys"

    partner_name: Mapped[str] = mapped_column(String(120))
    issued_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
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
    label: Mapped[str | None] = mapped_column(String(100))  # the partner's own reference, e.g. a policy number
    preferences: Mapped[dict] = mapped_column(default=dict)
    last_checked_at: Mapped[datetime | None]  # records created after this count as new
