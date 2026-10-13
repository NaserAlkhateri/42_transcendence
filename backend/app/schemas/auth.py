import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, EmailStr, Field, StringConstraints

from app.models import MemberRole, MemberStatus, OrganizationStatus, UserRole

PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128

EffectiveRole = Literal["platform_admin", "entity_admin", "entity_staff", "consumer"]

# The users table enforces lower-case emails; normalise here so "Ali@X.ae" and "ali@x.ae" are one account.
Email = Annotated[EmailStr, Field(max_length=320), AfterValidator(str.lower)]
Password = Annotated[str, Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)]
FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class SignupRequest(BaseModel):
    email: Email
    password: Password
    full_name: FullName


class LoginRequest(BaseModel):
    email: Email
    password: Annotated[str, Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)]


class ProfileUpdate(BaseModel):
    full_name: FullName


class PasswordChange(BaseModel):
    current_password: Annotated[str, Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)]
    new_password: Password


class MembershipOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    organization_name: str
    organization_status: OrganizationStatus
    role: MemberRole
    status: MemberStatus


class UserOut(BaseModel):
    """A user account as its owner sees it. Never includes the password hash or sessions.
    `role` is the platform role; `effective_role` folds in active memberships for role-based views."""

    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    effective_role: EffectiveRole
    must_change_password: bool
    created_at: datetime
    memberships: list[MembershipOut]


class CsrfToken(BaseModel):
    csrf_token: str


class SessionState(BaseModel):
    """GET /auth/session: who is signed in, if anyone."""

    user: UserOut | None
