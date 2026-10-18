"""Throttling for sign-in, sign-up and password checks (NA-06).

Buckets are keyed by client IP and, for failed logins, by the submitted email, so guessing one account's
password is slowed down even from many addresses. The answer is the same 429 whether or not the email
exists, so the lock itself reveals nothing about accounts."""

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import ApiError
from app.services.rate_limit import RateLimitResult, auth_limiter

SIGNUP_WINDOW_SECONDS = 3600


def client_ip(request: Request) -> str:
    """The caller's address. Behind Caddy this is only the real client if uvicorn runs with --proxy-headers."""
    return request.client.host if request.client else "unknown"


def _too_many(result: RateLimitResult) -> ApiError:
    return ApiError(429, "rate_limited", "Too many attempts. Wait a few minutes and try again.", result.headers())


def check_login_allowed(request: Request, email: str) -> None:
    """Count this attempt against the IP, and refuse if the IP or the email is over its limit."""
    settings = get_settings()
    by_ip = auth_limiter.hit(f"login-ip:{client_ip(request)}", settings.login_attempts_per_ip, settings.login_window_seconds)
    if not by_ip.allowed:
        raise _too_many(by_ip)
    by_email = auth_limiter.peek(f"login-email:{email}", settings.login_failures_per_email, settings.login_window_seconds)
    if not by_email.allowed:
        raise _too_many(by_email)


def record_login_failure(email: str) -> None:
    settings = get_settings()
    auth_limiter.hit(f"login-email:{email}", settings.login_failures_per_email, settings.login_window_seconds)


def record_login_success(email: str) -> None:
    auth_limiter.clear(f"login-email:{email}")


def check_signup_allowed(request: Request) -> None:
    result = auth_limiter.hit(f"signup-ip:{client_ip(request)}", get_settings().signups_per_ip, SIGNUP_WINDOW_SECONDS)
    if not result.allowed:
        raise _too_many(result)


def check_password_attempt_allowed(user_id: object) -> None:
    settings = get_settings()
    result = auth_limiter.peek(f"password:{user_id}", settings.password_failures_per_user, settings.login_window_seconds)
    if not result.allowed:
        raise _too_many(result)


def record_password_failure(user_id: object) -> None:
    settings = get_settings()
    auth_limiter.hit(f"password:{user_id}", settings.password_failures_per_user, settings.login_window_seconds)
