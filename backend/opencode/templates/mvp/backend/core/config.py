from __future__ import annotations

from functools import lru_cache
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

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
    CORS_ORIGINS: list[str] | str = Field(default=["http://localhost:3000"], alias="CORS_ORIGINS")

    # ── Database ───────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/app_db", alias="DATABASE_URL"
    )

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
        url = _clean_env(v)
        if not url:
            return url
        # SQLite support for local/test runs
        if url.startswith("sqlite://") and not url.startswith("sqlite+aiosqlite://"):
            return "sqlite+aiosqlite://" + url[len("sqlite://") :]
        unsupported = {"channel_binding", "connect_timeout"}
        if url.startswith("postgres://"):
            url = "postgresql+asyncpg://" + url[len("postgres://") :]
        elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://") :]
        if "sslmode=" in url:
            url = url.replace("sslmode=", "ssl=")
        parsed = urlsplit(url)
        if parsed.query:
            filtered = urlencode(
                [(k, val) for k, val in parse_qsl(parsed.query) if k.lower() not in unsupported]
            )
            url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, filtered, parsed.fragment))
        return url

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def split_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            v = _clean_env(v)
            if v.startswith("[") and v.endswith("]"):
                try:
                    import json

                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return [str(x).strip() for x in parsed if str(x).strip()]
                except Exception:
                    pass
            return [o.strip() for o in v.split(",") if o.strip()]
        if isinstance(v, (list, tuple, set)):
            return [str(o).strip() for o in v if str(o).strip()]
        return ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
