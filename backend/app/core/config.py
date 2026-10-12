from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration from environment variables (or a local, untracked .env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    seed_demo_password: str | None = None
    session_ttl_hours: int = 168  # 7 days; sessions are revoked on logout and password change
    cookie_secure: bool = True  # only set False for plain-http local debugging; Caddy serves HTTPS


@lru_cache
def get_settings() -> Settings:
    return Settings()
