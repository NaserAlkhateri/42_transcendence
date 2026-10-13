import enum

import sqlalchemy as sa


def db_enum(enum_cls: type[enum.Enum], name: str) -> sa.Enum:
    """Store enum *values* as VARCHAR + CHECK constraint (easier to extend than a native PG enum)."""
    return sa.Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
    )


class UserRole(enum.StrEnum):
    """Platform-level role. Entity roles live on organization_members, so a workshop
    employee is a "consumer" account with an active membership."""

    CONSUMER = "consumer"
    PLATFORM_ADMIN = "platform_admin"


class UserStatus(enum.StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class OrganizationKind(enum.StrEnum):
    DEALERSHIP = "dealership"
    WORKSHOP = "workshop"


class OrganizationStatus(enum.StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class MemberRole(enum.StrEnum):
    ENTITY_ADMIN = "entity_admin"
    ENTITY_STAFF = "entity_staff"


class MemberStatus(enum.StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class RecordCategory(enum.StrEnum):
    MAINTENANCE = "maintenance"
    REPAIR = "repair"


class CorrectionReason(enum.StrEnum):
    """What a correction fixes. A fixed list (not free text) so public reports can show it without personal data."""

    ODOMETER = "odometer"
    SERVICE_DATE = "service_date"
    WORK_DONE = "work_done"
    CATEGORY = "category"
    OTHER = "other"


class AttachmentScope(enum.StrEnum):
    ORGANIZATION = "organization"  # submitting organization + platform admins
    PLATFORM = "platform"  # platform admins only
