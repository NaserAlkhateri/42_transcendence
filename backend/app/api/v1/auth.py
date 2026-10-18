from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    SESSION_COOKIE,
    CurrentAuth,
    CurrentUser,
    clear_session_cookie,
    set_csrf_cookie,
    set_session_cookie,
)
from app.auth.passwords import burn_verify_time, hash_password, verify_password
from app.auth.sessions import create_session, resolve_session, revoke_all_sessions, revoke_session
from app.auth.throttle import (
    check_login_allowed,
    check_password_attempt_allowed,
    check_signup_allowed,
    record_login_failure,
    record_login_success,
    record_password_failure,
)
from app.core.errors import ApiError
from app.db.session import get_db
from app.models import User, UserRole, UserStatus
from app.schemas.auth import (
    CsrfToken,
    LoginRequest,
    PasswordChange,
    ProfileUpdate,
    SessionState,
    SignupRequest,
    UserOut,
)
from app.services.audit import record_audit
from app.services.users import to_user_out

router = APIRouter(prefix="/auth", tags=["auth"])
me_router = APIRouter(prefix="/me", tags=["profile"])

DbSession = Annotated[Session, Depends(get_db)]


def _start_session(db: Session, response: Response, user: User) -> None:
    set_session_cookie(response, create_session(db, user))
    set_csrf_cookie(response)  # rotate on sign-in so a pre-login token can't be fixed by an attacker


@router.get("/csrf", response_model=CsrfToken)
def csrf_token(response: Response) -> CsrfToken:
    """Issue the CSRF cookie. Clients call this once before their first POST/PATCH/DELETE."""
    return CsrfToken(csrf_token=set_csrf_cookie(response))


@router.get("/session", response_model=SessionState)
def current_session(request: Request, db: DbSession) -> SessionState:
    """The signed-in user or null. Always 200: the SPA probes this on every page load, and a 401 for
    guests would print an error in every visitor's browser console. Protected routes still answer 401."""
    token = request.cookies.get(SESSION_COOKIE)
    resolved = resolve_session(db, token) if token else None
    return SessionState(user=to_user_out(db, resolved[1]) if resolved else None)


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, request: Request, response: Response, db: DbSession) -> UserOut:
    """Create a consumer account and sign it in. Entity and admin roles are never self-assigned.

    A taken email answers 409, which tells the caller the address is registered. Without email verification
    there is no way to hide that and still tell a real user why signup failed, so signups are rate-limited
    per IP instead (doc/SECURITY.md)."""
    check_signup_allowed(request)
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role=UserRole.CONSUMER,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(409, "email_taken", "An account with this email already exists.") from exc
    _start_session(db, response, user)
    db.commit()
    return to_user_out(db, user)


@router.post("/login", response_model=UserOut)
def login(body: LoginRequest, request: Request, response: Response, db: DbSession) -> UserOut:
    check_login_allowed(request, body.email)
    user = db.scalar(select(User).where(User.email == body.email))
    if user is None:
        burn_verify_time(body.password)
        record_login_failure(body.email)
        raise ApiError(401, "invalid_credentials", "Email or password is incorrect.")
    # Same answer for a wrong password and a disabled account, so login can't probe account state.
    if not verify_password(user.password_hash, body.password) or user.status != UserStatus.ACTIVE:
        record_login_failure(body.email)
        raise ApiError(401, "invalid_credentials", "Email or password is incorrect.")
    record_login_success(body.email)
    # Signing in again on this browser replaces its previous session instead of leaving it valid.
    previous = request.cookies.get(SESSION_COOKIE)
    if previous:
        revoke_session(db, previous)
    _start_session(db, response, user)
    db.commit()
    return to_user_out(db, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: DbSession) -> None:
    """Revoke the session server-side; safe to call when already signed out."""
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        revoke_session(db, token)
        db.commit()
    clear_session_cookie(response)


@me_router.get("", response_model=UserOut)
def read_me(auth: CurrentAuth, db: DbSession) -> UserOut:
    """Available even while a temporary password is pending, so the UI can route to the change form."""
    return to_user_out(db, auth.user)


@me_router.patch("", response_model=UserOut)
def update_me(body: ProfileUpdate, user: CurrentUser, db: DbSession) -> UserOut:
    if body.full_name != user.full_name:
        record_audit(db, user, "user.profile_updated", "user", user.id, {"changes": {"full_name": [user.full_name, body.full_name]}})
        user.full_name = body.full_name
        db.commit()
    return to_user_out(db, user)


@me_router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(body: PasswordChange, auth: CurrentAuth, response: Response, db: DbSession) -> None:
    """Change the password, clear any temporary-password flag and end every session, this one included.
    This browser gets a brand-new session, so a token captured before the change is useless afterwards."""
    check_password_attempt_allowed(auth.user.id)
    if not verify_password(auth.user.password_hash, body.current_password):
        record_password_failure(auth.user.id)
        raise ApiError(400, "invalid_current_password", "Current password is incorrect.")
    if body.new_password == body.current_password:
        raise ApiError(400, "password_unchanged", "Choose a password different from the current one.")
    was_temporary = auth.user.must_change_password
    auth.user.password_hash = hash_password(body.new_password)
    auth.user.must_change_password = False
    revoke_all_sessions(db, auth.user.id)
    _start_session(db, response, auth.user)
    record_audit(db, auth.user, "user.password_changed", "user", auth.user.id, {"was_temporary": was_temporary})
    db.commit()
