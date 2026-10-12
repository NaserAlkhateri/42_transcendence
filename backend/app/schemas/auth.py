import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.models import UserRole

PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128

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


class UserOut(BaseModel):
    """The signed-in user's own account. Never includes the password hash or sessions."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    must_change_password: bool
    created_at: datetime


class CsrfToken(BaseModel):
    csrf_token: str
