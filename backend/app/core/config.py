"""
AI Solution Builder — Application Configuration

Loads all settings from environment variables via pydantic-settings.
Covers database, Redis, JWT auth, pluggable LLM providers, rate limiting,
and storage paths.
"""

import logging
from typing import Any

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

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
    # Disable connection pooling entirely (NullPool). Every checkout opens a fresh
    # connection and returns it on release, so no connection can outlive the event
    # loop that opened it. Required for the test suite, where one process drives
    # several loops across the run.
    DB_POOL_DISABLE: bool = False

    # ── Redis ─────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Auth0 (identity provider) ─────────────────────────
    # ── Auth Configuration ─────────────────────────
    JWT_SECRET_KEY: str = "sutra-default-jwt-secret-key-change-in-production-2026"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    ALLOW_ANONYMOUS_AUTH: bool = True
    ANONYMOUS_CREDITS: int | None = None  # None = unlimited credits for demo

    AUTH_GITHUB_CLIENT_ID: str = ""
    AUTH_GITHUB_CLIENT_SECRET: str = ""
    AUTH_GOOGLE_CLIENT_ID: str = ""
    AUTH_GOOGLE_CLIENT_SECRET: str = ""

    # Optional Auth0 integration
    AUTH0_DOMAIN: str = ""
    AUTH0_AUDIENCE: str = ""
    AUTH0_ROLE_CLAIM: str = "https://sutra.app/roles"
    AUTH0_ADMIN_EMAILS: str = ""
    AUTH0_LEEWAY_SECONDS: int = 30
    AUTH0_JWKS_CACHE_SECONDS: int = 600
    AUTH0_ENABLED: bool = False

    DEV_AUTH_BYPASS: bool = False
    DEV_AUTH_BYPASS_EMAIL: str = "dev@sutra.local"

    # ── Secret encryption at rest ──────────────────────────
    SECRET_ENCRYPTION_KEY: str = ""

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

    # ── Security / Threat Scanning ────────────────────
    SECURITY_SCAN_ENABLED: bool = True
    SECURITY_SCAN_BLOCK_THRESHOLD: str = "suspicious"  # malicious | suspicious
    SECURITY_SCAN_FAIL_UNAVAILABLE_MODE: str = "allow"  # allow | quarantine | block
    SECURITY_SCAN_SOURCES: str = ""  # glob allowlist, e.g. "upload.*,legacy_repo.*"; "" = all
    SECURITY_CACHE_TTL: int = 604800  # 7 days
    SECURITY_QUARANTINE_DIR: str = ".data/quarantine"

    CLAMAV_ENABLED: bool = False
    CLAMAV_HOST: str = "clamav"
    CLAMAV_PORT: int = 3310
    CLAMAV_TIMEOUT: float = 5.0

    # ── VirusTotal (Layer 2 — OFF by default) ────────
    # NOTE: the free Community API is limited to 4 req/min and 500 req/day and
    # "must not be used in commercial products or services" (VT docs, Getting
    # started). This layer is a local-dev signal only unless a commercial licence
    # is in place. VIRUSTOTAL_ACK_TOS must be explicitly set to acknowledge the
    # usage terms before the layer can be switched on at all.
    VIRUSTOTAL_ENABLED: bool = False
    VIRUSTOTAL_ACK_TOS: bool = False
    VIRUSTOTAL_API_KEY: str = ""
    VIRUSTOTAL_TIMEOUT: float = 15.0
    VIRUSTOTAL_UPLOAD_TIMEOUT: float = 60.0
    VIRUSTOTAL_MAX_UPLOAD_BYTES: int = 33554432  # VT POST /files hard cap: 32 MB
    VIRUSTOTAL_MIN_DETECTIONS: int = 3
    VIRUSTOTAL_CACHE_TTL: int = 604800
    VIRUSTOTAL_RPM: int = 4
    VIRUSTOTAL_DAILY: int = 500
    VIRUSTOTAL_ASYNC: bool = True

    SCAN_URL_INGEST: bool = True
    SCAN_GENERATED_ARTIFACTS: bool = False  # flip on after measuring FPs

    ARCHIVE_MAX_ENTRIES: int = 10000
    ARCHIVE_MAX_UNCOMPRESSED_BYTES: int = 524288000  # 500 MB
    ARCHIVE_MAX_RATIO: int = 100
    ARCHIVE_MAX_NESTED_DEPTH: int = 2

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

    # ── One-Click Deploy (GitHub, Render & Vercel) ──
    GITHUB_TOKEN: str = ""
    RENDER_API_KEY: str = ""
    VERCEL_TOKEN: str = ""
    VERCEL_TEAM_ID: str = ""

    # ── Payment Gateways (Razorpay & Stripe) ───────
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    STRIPE_API_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    # Generic HMAC-SHA256 secret used to authenticate /billing/webhook payloads.
    # Fails closed (503) when not configured so unauthenticated callers can't self-credit.
    PAYMENT_WEBHOOK_SECRET: str = ""

    # ── Row-Level Security ────────────────────────
    RLS_ENABLED: bool = False

    # ── OpenCode MVP Builder (sidecar) ────────────
    OPENCODE_SERVER_URL: str = "http://127.0.0.1:4096"
    OPENCODE_SERVER_USERNAME: str = "opencode"
    OPENCODE_SERVER_PASSWORD: str = ""
    # Comma-separated sidecar endpoints (e.g. "http://opencode-1:4096,http://opencode-2:4096").
    # When set, concurrent builds are spread across containers and each session is
    # deterministically pinned to one member of the pool (parallel multi-user builds).
    OPENCODE_POOL_URLS: str = ""
    OPENCODE_ZEN_API_KEY: str = ""  # Optional — only needed for opencode/* Zen models
    OPENCODE_MODEL: str = "opencode/big-pickle"
    OPENCODE_AGENT: str = "build"
    MVP_BUILD_TIMEOUT: int = 600  # seconds
    MVP_BUILD_DIR: str = ".data/mvp_builds"
    MVP_TEMPLATE_DIR: str = "opencode/templates/mvp"
    MVP_BUILD_CREDIT_COST: int = 30
    MVP_VERIFY_NPM: bool = False  # Skip npm install/build in memory-constrained environments
    MVP_VERIFY_INSTALL_TIMEOUT: int = 180  # seconds for npm install in checkpoint
    MVP_VERIFY_BUILD_TIMEOUT: int = 120  # seconds for npm run build in checkpoint
    MVP_MAX_REPAIR_TURNS: int = 4
    MVP_TEST_TIMEOUT_S: int = 180
    MVP_QUALITY_GATE: bool = True  # Enforce strict zero-placeholder and visual quality gate

    # ── Product Image Generation (Gemini) ───────────
    # Optional. When no key is configured the build's "illustrating" phase is
    # skipped entirely and the pipeline continues to verification unchanged, so
    # image generation can never block a build.
    GEMINI_API_KEY: str = ""
    GEMINI_IMAGE_MODEL: str = "gemini-2.5-flash-image"
    IMAGE_GENERATION_ENABLED: bool = True
    MVP_IMAGE_COUNT: int = 3
    MVP_IMAGE_TIMEOUT: int = 120  # seconds per image request
    # Cap on the whole illustration phase. Checked before each new image, so a
    # run that overruns still keeps (and persists) whatever already finished.
    MVP_IMAGE_TOTAL_BUDGET: int = 180

    # ── Worker Process / Queue ────────────────────
    WORKER_MODE: str = "inline"  # "worker" (separate process) | "inline" (in-process fallback)
    WORKER_POLL_INTERVAL: float = 2.0  # seconds
    WORKER_HEARTBEAT_INTERVAL: float = 10.0
    WORKER_HEARTBEAT_STALE_SECONDS: int = 180
    WORKER_RETRY_DELAY_SECONDS: int = 10

    # ── Frontend origin ───────────────────────────
    # Used for CORS and the Auth0 post-login redirect allow-list check.
    FRONTEND_URL: str = "http://localhost:3000"

    @field_validator(
        "CLOUDINARY_CLOUD_NAME",
        "CLOUDINARY_API_KEY",
        "CLOUDINARY_API_SECRET",
        "VIRUSTOTAL_API_KEY",
        mode="before",
    )
    @classmethod
    def clean_pasted_creds(cls, v: Any) -> str:
        if not v:
            return ""
        return str(v).strip().strip("'\"").strip()

    @field_validator("GEMINI_API_KEY", mode="before")
    @classmethod
    def clean_gemini_key(cls, v: Any) -> str:
        """Tolerate copy-pasted keys wrapped in quotes or whitespace."""
        if not v:
            return ""
        return str(v).strip().strip("'\"").strip()

    @model_validator(mode="after")
    def enforce_scanner_config(self) -> "Settings":
        if self.VIRUSTOTAL_ENABLED and not self.VIRUSTOTAL_ACK_TOS:
            raise ValueError(
                "VIRUSTOTAL_ENABLED requires VIRUSTOTAL_ACK_TOS=true to acknowledge "
                "VirusTotal Terms of Service (Community API is non-commercial only)."
            )
        if self.SECURITY_SCAN_BLOCK_THRESHOLD not in ("malicious", "suspicious"):
            raise ValueError(
                f"SECURITY_SCAN_BLOCK_THRESHOLD must be 'malicious' or 'suspicious', "
                f"got {self.SECURITY_SCAN_BLOCK_THRESHOLD!r}"
            )
        if self.SECURITY_SCAN_FAIL_UNAVAILABLE_MODE not in ("allow", "quarantine", "block"):
            raise ValueError(
                f"SECURITY_SCAN_FAIL_UNAVAILABLE_MODE must be 'allow', 'quarantine', or 'block', "
                f"got {self.SECURITY_SCAN_FAIL_UNAVAILABLE_MODE!r}"
            )
        if self.VIRUSTOTAL_ENABLED and self.APP_ENV == "production":
            logger.warning(
                "VIRUSTOTAL_ENABLED=true in production: ensure an enterprise commercial licence "
                "is in place to comply with VirusTotal Terms of Service."
            )
        return self

    @model_validator(mode="after")
    def enforce_production_secrets(self) -> "Settings":
        """Fail at boot rather than 401 every request."""
        if self.APP_ENV == "production":
            if self.JWT_SECRET_KEY in _PLACEHOLDER_SECRETS or len(self.JWT_SECRET_KEY) < 32:
                raise ValueError(
                    "JWT_SECRET_KEY must be set to a strong, unique secret "
                    f"(>= 32 chars) when APP_ENV='production'. Current value: {self.JWT_SECRET_KEY!r}"
                )
            if self.AUTH0_ENABLED:
                if not self.auth0_domain:
                    raise ValueError(
                        "AUTH0_DOMAIN must be set when AUTH0_ENABLED is true. "
                        "Expected the bare tenant domain, e.g. 'your-tenant.us.auth0.com'."
                    )
                if not self.AUTH0_AUDIENCE:
                    raise ValueError("AUTH0_AUDIENCE must be set when AUTH0_ENABLED is true.")
        # Auto-detect real LLM provider if credentials are provided and provider is still default mock
        if self.LLM_PROVIDER == "mock":
            if self.GROQ_API_KEY and self.GROQ_API_KEY.strip():
                self.LLM_PROVIDER = "groq"
            elif self.OPENAI_API_KEY and self.OPENAI_API_KEY.strip():
                self.LLM_PROVIDER = "openai"
        return self

    @property
    def auth0_domain(self) -> str:
        """Normalised bare tenant domain, or "" when unconfigured.

        Tolerates the several shapes this value gets pasted in as: a full URL,
        a trailing slash, a protocol-relative value, or a leading dot. Stripping
        the scheme matters because the issuer claim is compared verbatim, and
        "https://x.auth0.com/" != "x.auth0.com".
        """
        raw = (self.AUTH0_DOMAIN or "").strip().strip('"').strip("'")
        for prefix in ("https://", "http://", "//"):
            if raw.lower().startswith(prefix):
                raw = raw[len(prefix) :]
        return raw.strip("/").strip().lstrip(".")

    @property
    def auth0_issuer(self) -> str:
        """The `iss` claim every valid token must carry."""
        return f"https://{self.auth0_domain}/"

    @property
    def auth0_jwks_url(self) -> str:
        return f"https://{self.auth0_domain}/.well-known/jwks.json"

    @property
    def auth0_admin_emails(self) -> set[str]:
        return {e.strip().lower() for e in self.AUTH0_ADMIN_EMAILS.split(",") if e.strip()}

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = (".env", "../.env")
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
