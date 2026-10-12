from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration from environment variables (or a local, untracked .env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    seed_demo_password: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
