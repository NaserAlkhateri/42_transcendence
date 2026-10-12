"""Server-side sessions. The browser holds a random token; the database only stores its SHA-256 hash,
so a leaked sessions table cannot be replayed as cookies."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import User, UserSession, UserStatus


def _now() -> datetime:
    return datetime.now(UTC)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user: User) -> str:
    """Open a session for the user and return the raw token (only ever sent to the client as a cookie)."""
    token = secrets.token_urlsafe(32)
    expires_at = _now() + timedelta(hours=get_settings().session_ttl_hours)
    db.add(UserSession(user_id=user.id, token_hash=_hash_token(token), expires_at=expires_at))
    db.flush()
    return token


def resolve_session(db: Session, token: str) -> tuple[UserSession, User] | None:
    """The live session and its user, or None if the token is unknown, expired, revoked or the user is disabled."""
    row = db.execute(
        select(UserSession, User)
        .join(User, User.id == UserSession.user_id)
        .where(
            UserSession.token_hash == _hash_token(token),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > _now(),
            User.status == UserStatus.ACTIVE,
        )
    ).first()
    return (row[0], row[1]) if row else None


def revoke_session(db: Session, token: str) -> None:
    db.execute(
        update(UserSession)
        .where(UserSession.token_hash == _hash_token(token), UserSession.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


def revoke_other_sessions(db: Session, user_id: uuid.UUID, keep_session_id: uuid.UUID) -> None:
    db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.id != keep_session_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=_now())
    )

