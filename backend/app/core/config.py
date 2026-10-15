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


@lru_cache
def get_settings() -> Settings:
    return Settings()
