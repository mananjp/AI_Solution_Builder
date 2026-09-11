"""Verify the backend environment loads correctly.

Usage (from backend/):
    python scripts/check_env.py

Prints resolved configuration values (secrets redacted) and verifies that
required provider keys are present for the configured LLM_PROVIDER.
"""

import sys

from app.core.config import settings


def redact(value: str) -> str:
    if not value:
        return "(empty)"
    if len(value) < 12:
        return "*" * len(value)
    return value[:4] + "..." + value[-4:]


def main() -> int:
    print(f"APP_NAME                : {settings.APP_NAME}")
    print(f"APP_ENV                 : {settings.APP_ENV}")
    print(f"DATABASE_URL            : {redact(settings.DATABASE_URL)}")
    print(f"REDIS_URL               : {redact(settings.REDIS_URL)}")
    print(f"LLM_PROVIDER            : {settings.LLM_PROVIDER}")
    if settings.LLM_PROVIDER == "groq":
        status = (
            "OK" if settings.GROQ_API_KEY else "MISSING — set GROQ_API_KEY or use LLM_PROVIDER=mock"
        )
        print(f"GROQ_API_KEY            : {redact(settings.GROQ_API_KEY)} ({status})")
    elif settings.LLM_PROVIDER == "openai":
        status = (
            "OK"
            if settings.OPENAI_API_KEY
            else "MISSING — set OPENAI_API_KEY or use LLM_PROVIDER=mock"
        )
        print(f"OPENAI_API_KEY          : {redact(settings.OPENAI_API_KEY)} ({status})")
    print(f"EMBEDDING_MODEL         : {settings.EMBEDDING_MODEL}")
    print(f"RATE_LIMIT_ENABLED      : {settings.RATE_LIMIT_ENABLED}")
    print("OK — configuration loads cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
