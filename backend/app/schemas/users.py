from datetime import datetime

from pydantic import BaseModel

from app.models import MemberRole, UserRole, UserStatus
from app.schemas.auth import Email, FullName, UserOut


class AdminUserOut(UserOut):
    status: UserStatus
    updated_at: datetime


class UserPage(BaseModel):
    items: list[AdminUserOut]
    total: int
    page: int
    page_size: int


class AdminUserUpdate(BaseModel):
    """Platform-admin edit. Omitted fields stay unchanged; entity roles are changed per membership."""

    email: Email | None = None
    full_name: FullName | None = None
    role: UserRole | None = None
    status: UserStatus | None = None


class MembershipRoleUpdate(BaseModel):
    role: MemberRole
