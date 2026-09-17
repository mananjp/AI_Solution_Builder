"""
AI Solution Builder — Application Configuration

Loads all settings from environment variables via pydantic-settings.
Covers database, Redis, JWT auth, pluggable LLM providers, rate limiting,
and storage paths.
"""

from pydantic import model_validator
from pydantic_settings import BaseSettings

# Placeholder values that must never be used as the JWT signing key in production.
_PLACEHOLDER_SECRETS = {
    "",
    "change-me",
    "change-this-to-a-long-random-string-in-production",
}


class Settings(BaseSettings):
    """Central configuration loaded from .env file / environment."""

    # ── App ───────────────────────────────────────
    APP_NAME: str = "AI Solution Builder"
    APP_ENV: str = "development"
    APP_ROLE: str = "app"  # "app" (API + frontend) | "builder" (worker + opencode)
    CORS_ORIGINS: str = "http://localhost:3000"
    LOG_LEVEL: str = "INFO"

    # ── Database ──────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_solution_builder"
    DB_POOL_SIZE: int = 3
    DB_MAX_OVERFLOW: int = 2
    DB_POOL_RECYCLE: int = 300

    # ── Redis ─────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── JWT Auth ──────────────────────────────────
    JWT_SECRET_KEY: str = "change-this-to-a-long-random-string-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # ── AI / LLM Provider ─────────────────────────
    # Premade apps build directly through the OpenCode sidecar; this provider
    # only backs the legacy LangGraph analysis pipeline. "mock" keeps the app
    # functional offline with deterministic output.
    LLM_PROVIDER: str = "mock"  # groq | openai | mock
    GROQ_API_KEY: str = ""
    GROQ_MODEL_NAME: str = "openai/gpt-oss-120b"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL_NAME: str = "gpt-4o-mini"

    # ── Embeddings ────────────────────────────────
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIM: int = 384
    EMBEDDING_CHUNK_SIZE: int = 800

    # ── Rate Limiting ─────────────────────────────
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_AI_REQUESTS: int = 10
    RATE_LIMIT_AI_WINDOW_SECONDS: int = 60

    # ── Storage ───────────────────────────────────
    UPLOAD_DIR: str = ".data/uploads"
    EXPORT_DIR: str = ".data/exports"

    # ── Object Storage (Cloudinary) ───────────────
    STORAGE_BACKEND: str = "local"  # "local" | "cloudinary"
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""

    # Only honor X-Forwarded-For when a trusted reverse proxy sits in front;
    # otherwise clients can forge it to dodge rate limits / audit attribution.
    TRUST_PROXY_HEADERS: bool = False

    # ── Credits ───────────────────────────────────
    GENERATION_CREDIT_COST: int = 20
    REGENERATION_CREDIT_COST: int = 5
    EXPORT_CREDIT_COST: int = 2

    # ── Multilingual / Localization ───────────────
    DEFAULT_LANGUAGE: str = "en"
    TRANSLATION_ENABLED: bool = True

    # ── One-Click Deploy (GitHub) ─────────────────
    GITHUB_TOKEN: str = ""

    # ── Row-Level Security ────────────────────────
    RLS_ENABLED: bool = False

    # ── OpenCode MVP Builder (sidecar) ────────────
    OPENCODE_SERVER_URL: str = "http://127.0.0.1:4096"
    OPENCODE_SERVER_PASSWORD: str = ""
    OPENCODE_MODEL: str = "groq/openai/gpt-oss-120b"
    OPENCODE_AGENT: str = "mvp-builder"
    MVP_BUILD_TIMEOUT: int = 600  # seconds
    MVP_BUILD_DIR: str = ".data/mvp_builds"
    MVP_TEMPLATE_DIR: str = "opencode/templates/mvp"
    MVP_BUILD_CREDIT_COST: int = 30
    MVP_VERIFY_NPM: bool = False  # Skip npm install/build in memory-constrained environments
    MVP_VERIFY_INSTALL_TIMEOUT: int = 180  # seconds for npm install in checkpoint
    MVP_VERIFY_BUILD_TIMEOUT: int = 120  # seconds for npm run build in checkpoint

    # ── Worker Process / Queue ────────────────────
    WORKER_MODE: str = "inline"  # "worker" (separate process) | "inline" (in-process fallback)
    WORKER_POLL_INTERVAL: float = 2.0  # seconds

    # ── Social OAuth & Anonymous Login ────────────
    FRONTEND_URL: str = "http://localhost:3000"
    AUTH_GITHUB_CLIENT_ID: str = ""
    AUTH_GITHUB_CLIENT_SECRET: str = ""
    AUTH_GOOGLE_CLIENT_ID: str = ""
    AUTH_GOOGLE_CLIENT_SECRET: str = ""
    ALLOW_ANONYMOUS_AUTH: bool = True
    ANONYMOUS_CREDITS: int = 50

    @model_validator(mode="after")
    def enforce_production_secrets(self) -> "Settings":
        if self.APP_ENV == "production" and (
            self.JWT_SECRET_KEY in _PLACEHOLDER_SECRETS or len(self.JWT_SECRET_KEY) < 32
        ):
            raise ValueError(
                "JWT_SECRET_KEY must be set to a strong, unique secret "
                f"(>= 32 chars) when APP_ENV='production'. Current value: {self.JWT_SECRET_KEY!r}"
            )
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = (".env", "../.env")
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
