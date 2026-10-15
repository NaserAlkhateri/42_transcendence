"""Partner API keys (NA-05).

A key looks like `sjl_<prefix>_<secret>`. The 8-character prefix is stored in clear to find the key and to show
it in the admin UI; the 256-bit secret is stored only as a SHA-256 hash. A slow password hash isn't needed for
a random 256-bit secret, and a fast one keeps every API call cheap."""

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, Request, Response
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ApiError
from app.db.session import get_db
from app.models import ApiKey
from app.services.rate_limit import partner_limiter

KEY_PREFIX = "sjl"
SCOPE_VEHICLES_READ = "vehicles:read"
SCOPE_WATCHES_MANAGE = "watches:manage"
DEFAULT_SCOPES = [SCOPE_VEHICLES_READ, SCOPE_WATCHES_MANAGE]
LAST_USED_RESOLUTION = timedelta(minutes=1)  # avoid a write on every call

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, description="Partner key issued by a Sijil platform admin")


@dataclass(frozen=True)
class GeneratedKey:
    full_key: str  # shown to the admin once
    prefix: str
    secret_hash: str


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def generate_key() -> GeneratedKey:
    prefix = secrets.token_hex(4)
    secret = secrets.token_urlsafe(32)
    return GeneratedKey(full_key=f"{KEY_PREFIX}_{prefix}_{secret}", prefix=prefix, secret_hash=hash_secret(secret))


def parse_key(raw: str) -> tuple[str, str] | None:
    """(prefix, secret), or None if `raw` is not shaped like a Sijil key."""
    parts = raw.strip().split("_", 2)
    if len(parts) != 3 or parts[0] != KEY_PREFIX or len(parts[1]) != 8 or not parts[2]:
        return None
    return parts[1], parts[2]


def _invalid(request: Request, code: str, message: str) -> ApiError:
    """401 for a missing, unknown or revoked key. Failures also count against the caller's IP, so guessing
    keys is throttled like any other burst."""
    client = request.client.host if request.client else "unknown"
    settings = get_settings()
    result = partner_limiter.hit(f"ip:{client}", settings.partner_rate_limit, settings.partner_rate_window_seconds)
    if not result.allowed:
        return ApiError(429, "rate_limited", "Too many requests. Slow down and retry later.", result.headers())
    return ApiError(401, code, message, {"WWW-Authenticate": "ApiKey"})


def authenticate_partner(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    raw_key: Annotated[str | None, Depends(api_key_header)],
) -> ApiKey:
    """Resolve the X-API-Key header to an active key, apply its rate limit and add the limit headers."""
    if not raw_key:
        raise _invalid(request, "missing_api_key", "Send your partner key in the X-API-Key header.")
    parsed = parse_key(raw_key)
    key = db.scalar(select(ApiKey).where(ApiKey.key_prefix == parsed[0])) if parsed else None
    if key is None or parsed is None or not hmac.compare_digest(key.key_hash, hash_secret(parsed[1])):
        raise _invalid(request, "invalid_api_key", "This API key is not valid.")
    if key.revoked_at is not None:
        raise _invalid(request, "invalid_api_key", "This API key has been revoked.")

    settings = get_settings()
    result = partner_limiter.hit(f"key:{key.id}", settings.partner_rate_limit, settings.partner_rate_window_seconds)
    if not result.allowed:
        raise ApiError(429, "rate_limited", "Rate limit reached for this key. Retry after the window resets.", result.headers())
    response.headers.update(result.headers())

    now = datetime.now(UTC)
    if key.last_used_at is None or now - key.last_used_at > LAST_USED_RESOLUTION:
        key.last_used_at = now
        db.commit()
    return key


def require_scope(key: ApiKey, scope: str) -> None:
    if scope not in key.scopes:
        raise ApiError(403, "insufficient_scope", f"This key does not have the '{scope}' scope.")


PartnerKey = Annotated[ApiKey, Depends(authenticate_partner)]
