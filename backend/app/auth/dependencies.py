"""Cookie handling, CSRF and the current-user dependencies every protected route builds on."""

import secrets
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from app.auth.sessions import resolve_session
from app.core.config import get_settings
from app.core.errors import ApiError
from app.db.session import get_db
from app.models import User, UserSession

SESSION_COOKIE = "sijil_session"
CSRF_COOKIE = "sijil_csrf"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def set_csrf_cookie(response: Response) -> str:
    """Double-submit token: readable by our own JS (not HttpOnly), echoed back in the X-CSRF-Token header."""
    token = secrets.token_urlsafe(32)
    response.set_cookie(
        CSRF_COOKIE, token, httponly=False, secure=get_settings().cookie_secure, samesite="lax", path="/"
    )
    return token


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", secure=get_settings().cookie_secure, httponly=True, samesite="lax")


def verify_csrf(request: Request) -> None:
    """Router-level guard: every state-changing /api/v1 request must echo the CSRF cookie in a header.
    A cross-site page can make the browser send our cookies, but it cannot read them to set the header."""
    if request.method in SAFE_METHODS:
        return
    cookie = request.cookies.get(CSRF_COOKIE)
    header = request.headers.get(CSRF_HEADER)
    if not cookie or not header or not secrets.compare_digest(cookie, header):
        raise ApiError(403, "csrf_failed", "Missing or invalid CSRF token. Fetch /api/v1/auth/csrf and retry.")


@dataclass
class Authenticated:
    user: User
    session: UserSession


def get_auth(request: Request, db: Annotated[Session, Depends(get_db)]) -> Authenticated:
    """The signed-in user, even one who still has to change a temporary password."""
    token = request.cookies.get(SESSION_COOKIE)
    resolved = resolve_session(db, token) if token else None
    if resolved is None:
        raise ApiError(401, "not_authenticated", "Sign in to continue.")
    session, user = resolved
    return Authenticated(user=user, session=session)


def require_user(auth: Annotated[Authenticated, Depends(get_auth)]) -> User:
    """Use this on protected routes: also blocks accounts that must replace a temporary password first."""
    if auth.user.must_change_password:
        raise ApiError(403, "password_change_required", "Change your temporary password to continue.")
    return auth.user


CurrentAuth = Annotated[Authenticated, Depends(get_auth)]
CurrentUser = Annotated[User, Depends(require_user)]
