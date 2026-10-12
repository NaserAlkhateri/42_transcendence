import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, UUIDPrimaryKey
from app.models.enums import MemberRole, MemberStatus, OrganizationKind, OrganizationStatus, db_enum


class Organization(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[OrganizationKind] = mapped_column(db_enum(OrganizationKind, "organization_kind"))
    registration_number: Mapped[str] = mapped_column(String(64), unique=True)
    emirate: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[OrganizationStatus] = mapped_column(
        db_enum(OrganizationStatus, "organization_status"), default=OrganizationStatus.PENDING, index=True
    )
    approved_at: Mapped[datetime | None]
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class OrganizationMember(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "organization_members"
    __table_args__ = (UniqueConstraint("organization_id", "user_id"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[MemberRole] = mapped_column(db_enum(MemberRole, "member_role"))
    status: Mapped[MemberStatus] = mapped_column(db_enum(MemberStatus, "member_status"), default=MemberStatus.ACTIVE)
