import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, StringConstraints

from app.models import MemberRole, MemberStatus, OrganizationKind, OrganizationStatus
from app.schemas.auth import Email, FullName

# Official English spellings (doc/UAE_MARKET.md). Addresses are emirate + area; there are no postcodes.
Emirate = Literal["Abu Dhabi", "Dubai", "Sharjah", "Ajman", "Umm Al Quwain", "Ras Al Khaimah", "Fujairah"]

OrganizationName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
# Trade licence number as printed on the licence; stored upper-case so "cn-123" and "CN-123" are one business.
LicenceNumber = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=3, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9/\- ]*$"),
    AfterValidator(str.upper),
]
RejectionReason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=500)]


class OrganizationRegistration(BaseModel):
    """A business applying to join Sijil. It starts pending until a platform admin reviews it."""

    name: OrganizationName
    kind: OrganizationKind
    registration_number: LicenceNumber
    emirate: Emirate


class OrganizationUpdate(BaseModel):
    """Omitted fields stay unchanged."""

    name: OrganizationName | None = None
    kind: OrganizationKind | None = None
    registration_number: LicenceNumber | None = None
    emirate: Emirate | None = None


class Rejection(BaseModel):
    reason: RejectionReason


class OrganizationOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    kind: OrganizationKind
    registration_number: str
    emirate: str | None
    status: OrganizationStatus
    rejection_reason: str | None
    approved_at: datetime | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class OrganizationMemberOut(BaseModel):
    membership_id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    email: str
    role: MemberRole
    status: MemberStatus


class AdminOrganizationOut(OrganizationOut):
    member_count: int
    record_count: int


class AdminOrganizationDetail(AdminOrganizationOut):
    members: list[OrganizationMemberOut]


class OrganizationPage(BaseModel):
    items: list[AdminOrganizationOut]
    total: int
    page: int
    page_size: int



class MemberAdd(BaseModel):
    """Add someone who already has a Sijil account."""

    email: Email
    role: MemberRole


class StaffAccountCreate(BaseModel):
    """Create a new account for a staff member. They sign in with a temporary password and must change it."""

    email: Email
    full_name: FullName
    role: MemberRole = MemberRole.ENTITY_STAFF


class MemberUpdate(BaseModel):
    role: MemberRole | None = None
    status: MemberStatus | None = None


class StaffAccountCreated(BaseModel):
    member: OrganizationMemberOut
    temporary_password: str  # shown once; only its hash is stored
