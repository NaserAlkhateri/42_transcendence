from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration from environment variables (or a local, untracked .env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    seed_demo_password: str | None = None
    seed_partner_api_key: str | None = None  # optional demo partner key, format sjl_<8 hex>_<secret>
    session_ttl_hours: int = 168  # 7 days; sessions are revoked on logout and password change
    cookie_secure: bool = True  # only set False for plain-http local debugging; Caddy serves HTTPS
    partner_rate_limit: int = 60  # partner API requests per key per window (NA-05)
    partner_rate_window_seconds: int = 60
    partner_max_watches: int = 500  # VINs one partner key may watch
    # Authentication throttling (NA-06). Behind Caddy, run uvicorn with --proxy-headers so limits see the real client IP.
    login_attempts_per_ip: int = 30  # per login_window_seconds, successful or not
    login_failures_per_email: int = 10  # wrong passwords for one email before it is locked for the window
    login_window_seconds: int = 900
    signups_per_ip: int = 10  # per hour
    password_failures_per_user: int = 10  # wrong current passwords on /me/password, per login_window_seconds
    max_request_bytes: int = 1_000_000  # JSON API bodies; file uploads (BU-03) need their own, larger limit


@lru_cache
def get_settings() -> Settings:
    return Settings()
