import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, UUIDPrimaryKey
from app.models.enums import AttachmentScope, CorrectionReason, RecordCategory, db_enum


class Vehicle(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "vehicles"
    __table_args__ = (CheckConstraint("vin ~ '^[A-HJ-NPR-Z0-9]{17}$'", name="vin_format"),)

    vin: Mapped[str] = mapped_column(String(17), unique=True)
    make: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(64))
    model_year: Mapped[int | None]


class ServiceRecord(UUIDPrimaryKey, CreatedAt, Base):
    """Append-only: the service_records_append_only trigger rejects UPDATE and DELETE, except the
    FK "ON DELETE SET NULL" that runs when the organization or staff user is deleted."""

    __tablename__ = "service_records"
    __table_args__ = (
        CheckConstraint("odometer_km >= 0", name="odometer_non_negative"),
        CheckConstraint("corrects_record_id IS NULL OR corrects_record_id <> id", name="no_self_correction"),
        CheckConstraint("(corrects_record_id IS NULL) = (correction_reason IS NULL)", name="correction_has_reason"),
        Index("ix_service_records_vehicle_timeline", "vehicle_id", "service_date", "created_at"),
    )

    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id", ondelete="RESTRICT"))
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), index=True
    )
    staff_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    # Name snapshots: the one deliberate duplication, so history stays readable after deletions.
    organization_name: Mapped[str] = mapped_column(String(200))
    staff_name: Mapped[str] = mapped_column(String(120))
    category: Mapped[RecordCategory] = mapped_column(db_enum(RecordCategory, "record_category"))
    work_codes: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)
    odometer_km: Mapped[int]
    service_date: Mapped[date]
    is_mileage_flagged: Mapped[bool] = mapped_column(default=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    # Unique: a record is corrected at most once; a later fix corrects the correction (a chain).
    corrects_record_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("service_records.id", ondelete="RESTRICT"), index=True, unique=True
    )
    correction_reason: Mapped[CorrectionReason | None] = mapped_column(db_enum(CorrectionReason, "correction_reason"))


class Attachment(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "attachments"
    __table_args__ = (CheckConstraint("size_bytes > 0", name="size_positive"),)

    service_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("service_records.id", ondelete="RESTRICT"), index=True
    )
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    object_key: Mapped[str] = mapped_column(String(512), unique=True)
    file_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int]
    access_scope: Mapped[AttachmentScope] = mapped_column(
        db_enum(AttachmentScope, "attachment_scope"), default=AttachmentScope.ORGANIZATION
    )
    deleted_at: Mapped[datetime | None]
