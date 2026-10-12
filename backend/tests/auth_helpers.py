"""Shared helpers for tests that sign in through the real auth API."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password
from app.models import MemberRole, Organization, OrganizationMember, User, UserRole, UserStatus

PASSWORD = "correct-horse-battery"
_password_hash: str | None = None


def csrf(client: TestClient) -> dict[str, str]:
    """Header echoing the current CSRF cookie, fetching one first if the client has none."""
    if "sijil_csrf" not in client.cookies:
        client.get("/api/v1/auth/csrf")
    return {"X-CSRF-Token": client.cookies["sijil_csrf"]}


def login(client: TestClient, email: str, password: str = PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password}, headers=csrf(client))


def add_user(
    db: Session,
    email: str,
    *,
    full_name: str = "Seeded User",
    role: UserRole = UserRole.CONSUMER,
    status: UserStatus = UserStatus.ACTIVE,
    must_change: bool = False,
) -> User:
    global _password_hash
    if _password_hash is None:  # Argon2 is deliberately slow; hash the shared test password once
        _password_hash = hash_password(PASSWORD)
    user = User(
        email=email, password_hash=_password_hash, full_name=full_name,
        role=role, status=status, must_change_password=must_change,
    )
    db.add(user)
    db.flush()
    return user


def add_member(db: Session, org: Organization, user: User, role: MemberRole) -> OrganizationMember:
    membership = OrganizationMember(organization_id=org.id, user_id=user.id, role=role)
    db.add(membership)
    db.flush()
    return membership
