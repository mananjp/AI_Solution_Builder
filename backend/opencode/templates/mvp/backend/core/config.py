from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _clean_env(v: Any) -> Any:
    """Drop inline comments (e.g. `# comment`) from .env values."""
    if isinstance(v, str):
        v = v.split("#")[0].strip()
    return v


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App ────────────────────────────────────────────────────────────
    APP_NAME: str = Field(default="__APP_NAME__", alias="APP_NAME")
    APP_TITLE: str = Field(default="__APP_TITLE__", alias="APP_TITLE")
    APP_ENV: str = Field(default="development", alias="APP_ENV")
    DEBUG: bool = Field(default=True, alias="DEBUG")
    API_PREFIX: str = Field(default="/api/v1", alias="API_PREFIX")
    CORS_ORIGINS: list[str] = Field(default=["http://localhost:3000"], alias="CORS_ORIGINS")

    # ── Database ───────────────────────────────────────────────────────
    DATABASE_URL: str = Field(default="postgresql+asyncpg://postgres:postgres@localhost:5432/app_db", alias="DATABASE_URL")

    # ── Security ───────────────────────────────────────────────────────
    JWT_SECRET: str = Field(default="__JWT_SECRET__", alias="JWT_SECRET")
    JWT_ALGORITHM: str = Field(default="HS256", alias="JWT_ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60 * 24, alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    # ── Runtime ────────────────────────────────────────────────────────
    BACKEND_PORT: int = Field(default=8000, alias="BACKEND_PORT")
    LOG_LEVEL: str = Field(default="info", alias="LOG_LEVEL")

    # ── External integrations (placeholders) ──────────────────────────
    OPENAI_API_KEY: str = Field(default="", alias="OPENAI_API_KEY")
    ANTHROPIC_API_KEY: str = Field(default="", alias="ANTHROPIC_API_KEY")

    @field_validator("DATABASE_URL")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        # Allow `postgresql://` scheme shorthand from Render/other hosts.
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return _clean_env(v)

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def split_origins(cls, v: Any) -> Any:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()