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
    # The API accepts only Auth0-issued RS256 access tokens. The local
    # HS256 secret and password hashing are gone: credentials, MFA, social
    # login, breached-password detection and session revocation all belong to
    # Auth0, and a compromise of the database no longer yields passwords.
    # Domain only, never a URL, with any scheme or trailing path stripped.
    AUTH0_DOMAIN: str = ""
    # API identifier from the Auth0 dashboard. Tokens without this audience are
    # rejected, which is what stops an ID token minted for another app of the
    # same tenant from being replayed against this API.
    AUTH0_AUDIENCE: str = ""
    # Namespaced custom claim carrying the SUTRA role. Created by the
    # Post-Login Action in deploy/auth0/post-login-action.js.
    AUTH0_ROLE_CLAIM: str = "https://sutra.app/roles"
    # Comma-separated emails promoted to "admin" on first login. The first
    # login also wins the "owner" role for any new organisation, so an empty
    # value here is safe.
    AUTH0_ADMIN_EMAILS: str = ""
    # Clock skew tolerance when validating exp/nbf, in seconds.
    AUTH0_LEEWAY_SECONDS: int = 30
    # How long a fetched JWKS is cached before it is re-fetched, in seconds.
    # Also bounds exposure if Auth0 rotates a signing key.
    AUTH0_JWKS_CACHE_SECONDS: int = 600
    # Set false only to keep the API bootable in tests/CI without a tenant.
    # In production this is forced on by enforce_production_secrets.
    AUTH0_ENABLED: bool = True

    # Dev-only escape hatch so the UI can be exercised without a working Auth0
    # tenant. Grants a synthetic local user (real DB rows, real org/workspace) to
    # requests that carry no bearer token. `enforce_production_secrets` makes
    # booting with this on in production a hard error, so it cannot leak.
    DEV_AUTH_BYPASS: bool = False
    DEV_AUTH_BYPASS_EMAIL: str = "dev@sutra.local"

    # ── Secret encryption at rest ──────────────────────────
    # Encrypts user-supplied deploy tokens (GitHub PAT, Render and Vercel keys)
    # before they are written to the users.settings JSON. It is a separate value
    # from anything Auth0 knows: rotating Auth0 credentials must never make
    # stored deploy secrets unreadable, and vice versa.
    SECRET_ENCRYPTION_KEY: str = ""
    # Deprecated. Only read, never written: lets an existing database decrypt
    # values encrypted before the move to SECRET_ENCRYPTION_KEY. Safe to leave
    # unset on a fresh deployment, and safe to delete once every stored secret
    # has been re-saved.
    JWT_SECRET_KEY: str = ""

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
    OPENCODE_AGENT: str = "mvp-builder"
    MVP_BUILD_TIMEOUT: int = 600  # seconds
    MVP_BUILD_DIR: str = ".data/mvp_builds"
    MVP_TEMPLATE_DIR: str = "opencode/templates/mvp"
    MVP_BUILD_CREDIT_COST: int = 30
    MVP_VERIFY_NPM: bool = False  # Skip npm install/build in memory-constrained environments
    MVP_VERIFY_INSTALL_TIMEOUT: int = 180  # seconds for npm install in checkpoint
    MVP_VERIFY_BUILD_TIMEOUT: int = 120  # seconds for npm run build in checkpoint
    MVP_MAX_REPAIR_TURNS: int = 4
    MVP_TEST_TIMEOUT_S: int = 180
    MVP_QUALITY_GATE: bool = False  # Enforce strict zero-placeholder and visual quality gate

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
        """Fail at boot rather than 401 every request.

        The previous HS256 check was a single secret. Auth0 is three values,
        and a missing one produces a confusing runtime failure: the app boots,
        the login button works, and every API call returns 401. Validating in
        the constructor turns that into an immediate, actionable startup error.
        """
        if self.APP_ENV == "production":
            if self.DEV_AUTH_BYPASS:
                raise ValueError(
                    "DEV_AUTH_BYPASS must be false when APP_ENV='production'. "
                    "It authenticates requests that carry no token, which would make "
                    "the entire API public."
                )
            if not self.AUTH0_ENABLED:
                raise ValueError(
                    "AUTH0_ENABLED must be true when APP_ENV='production'. "
                    "Unauthenticated access to the API is not supported."
                )
            if not self.auth0_domain:
                raise ValueError(
                    "AUTH0_DOMAIN must be set when APP_ENV='production'. "
                    "Expected the bare tenant domain, e.g. 'your-tenant.us.auth0.com'."
                )
            if not self.AUTH0_AUDIENCE:
                raise ValueError(
                    "AUTH0_AUDIENCE must be set when APP_ENV='production'. "
                    "Use the API identifier from the Auth0 dashboard, not the client ID."
                )
            if not self.SECRET_ENCRYPTION_KEY:
                raise ValueError(
                    "SECRET_ENCRYPTION_KEY must be set when APP_ENV='production'. "
                    "Deploy credentials are encrypted with it; without it they cannot "
                    "be stored. Generate one with: openssl rand -base64 48"
                )
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
