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
from app.auth.sessions import create_session, revoke_other_sessions, revoke_session
from app.core.errors import ApiError
from app.db.session import get_db
from app.models import User, UserRole, UserStatus
from app.schemas.auth import CsrfToken, LoginRequest, PasswordChange, ProfileUpdate, SignupRequest, UserOut
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


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, response: Response, db: DbSession) -> UserOut:
    """Create a consumer account and sign it in. Entity and admin roles are never self-assigned."""
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
def login(body: LoginRequest, response: Response, db: DbSession) -> UserOut:
    user = db.scalar(select(User).where(User.email == body.email))
    if user is None:
        burn_verify_time(body.password)
        raise ApiError(401, "invalid_credentials", "Email or password is incorrect.")
    # Same answer for a wrong password and a disabled account, so login can't probe account state.
    if not verify_password(user.password_hash, body.password) or user.status != UserStatus.ACTIVE:
        raise ApiError(401, "invalid_credentials", "Email or password is incorrect.")
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
    user.full_name = body.full_name
    db.commit()
    return to_user_out(db, user)


@me_router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(body: PasswordChange, auth: CurrentAuth, db: DbSession) -> None:
    """Change the password, clear any temporary-password flag and sign out every other device."""
    if not verify_password(auth.user.password_hash, body.current_password):
        raise ApiError(400, "invalid_current_password", "Current password is incorrect.")
    if body.new_password == body.current_password:
        raise ApiError(400, "password_unchanged", "Choose a password different from the current one.")
    auth.user.password_hash = hash_password(body.new_password)
    auth.user.must_change_password = False
    revoke_other_sessions(db, auth.user.id, keep_session_id=auth.session.id)
    db.commit()
