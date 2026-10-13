"""Every model is imported here so Base.metadata (and Alembic) sees all tables."""

from app.models.audit import AuditEvent
from app.models.engagement import Notification, Watchlist
from app.models.enums import (
    AttachmentScope,
    CorrectionReason,
    MemberRole,
    MemberStatus,
    OrganizationKind,
    OrganizationStatus,
    RecordCategory,
    UserRole,
    UserStatus,
)
from app.models.organization import Organization, OrganizationMember
from app.models.partner import ApiKey, PartnerWatchlist
from app.models.user import User, UserSession
from app.models.vehicle import Attachment, ServiceRecord, Vehicle

__all__ = [
    "ApiKey", "Attachment", "AttachmentScope", "AuditEvent", "CorrectionReason", "MemberRole", "MemberStatus", "Notification",
    "Organization", "OrganizationKind", "OrganizationMember", "OrganizationStatus", "PartnerWatchlist",
    "RecordCategory", "ServiceRecord", "User", "UserRole", "UserSession", "UserStatus", "Vehicle", "Watchlist",
]
