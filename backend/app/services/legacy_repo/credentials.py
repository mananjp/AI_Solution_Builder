"""
AI Solution Builder — Secure Credential Management & Validation

Detects required credentials (Groq, OpenAI, Anthropic, Gemini), validates format,
performs minimal live API connection tests, provides masked representation (••••••••••••abcd),
and securely persists to target workspace .env without committing or hardcoding secrets.
"""

import logging
import re
from pathlib import Path

import httpx

from app.services.legacy_repo.boundary import assert_safe_boundary

logger = logging.getLogger(__name__)

KEY_PATTERNS = {
    "GROQ_API_KEY": re.compile(r"^gsk_[a-zA-Z0-9]{30,}$"),
    "OPENAI_API_KEY": re.compile(r"^sk-[a-zA-Z0-9_\-]{30,}$"),
    "ANTHROPIC_API_KEY": re.compile(r"^sk-ant-[a-zA-Z0-9_\-]{30,}$"),
    "GEMINI_API_KEY": re.compile(r"^AIza[a-zA-Z0-9_\-]{20,}$"),
}


def mask_secret(secret: str | None) -> str:
    """Return masked representation of a secret, e.g. ••••••••••••abcd."""
    if not secret:
        return "••••"
    secret_str = str(secret).strip()
    if len(secret_str) <= 6:
        return "••••" + secret_str[-2:]
    suffix = secret_str[-4:]
    return "•" * 12 + suffix


class CredentialValidator:
    """Validates and securely provisions API credentials for legacy repo extensions."""

    @classmethod
    def validate_format(cls, key_name: str, value: str) -> tuple[bool, str]:
        """Validate key format using provider-specific heuristics."""
        clean_val = value.strip()
        if not clean_val:
            return False, f"{key_name} cannot be empty"

        pattern = KEY_PATTERNS.get(key_name)
        if pattern:
            if not pattern.match(clean_val):
                return (
                    False,
                    f"Invalid format for {key_name}. Key does not match standard provider pattern.",
                )
            return True, f"Format valid for {key_name}"

        # Generic API key check
        if len(clean_val) < 12:
            return False, f"{key_name} is suspiciously short (expected >= 12 characters)"
        return True, f"Format valid for {key_name}"

    @classmethod
    async def test_connectivity(cls, key_name: str, value: str) -> tuple[bool, str]:
        """Perform a minimal, non-destructive connection test to the provider API."""
        clean_val = value.strip()
        format_ok, msg = cls.validate_format(key_name, clean_val)
        if not format_ok:
            return False, msg

        timeout = 5.0
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                if key_name == "GROQ_API_KEY":
                    resp = await client.get(
                        "https://api.groq.com/openai/v1/models",
                        headers={"Authorization": f"Bearer {clean_val}"},
                    )
                    if resp.status_code == 200:
                        return True, "Groq API connection test succeeded (HTTP 200)"
                    return False, f"Groq API returned HTTP {resp.status_code}: {resp.text[:120]}"

                elif key_name == "OPENAI_API_KEY":
                    resp = await client.get(
                        "https://api.openai.com/v1/models",
                        headers={"Authorization": f"Bearer {clean_val}"},
                    )
                    if resp.status_code == 200:
                        return True, "OpenAI API connection test succeeded (HTTP 200)"
                    return False, f"OpenAI API returned HTTP {resp.status_code}: {resp.text[:120]}"

                elif key_name == "ANTHROPIC_API_KEY":
                    # Anthropic doesn't have a simple GET models without custom version header
                    resp = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": clean_val,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json",
                        },
                        json={
                            "model": "claude-3-haiku-20240307",
                            "max_tokens": 1,
                            "messages": [{"role": "user", "content": "ping"}],
                        },
                    )
                    if resp.status_code in (200, 400):  # 400 with valid key means auth succeeded
                        return True, "Anthropic API key verified"
                    return False, f"Anthropic API returned HTTP {resp.status_code}"

                elif key_name == "GEMINI_API_KEY":
                    resp = await client.get(
                        f"https://generativelanguage.googleapis.com/v1/models?key={clean_val}"
                    )
                    if resp.status_code == 200:
                        return True, "Gemini API connection test succeeded"
                    return False, f"Gemini API returned HTTP {resp.status_code}"

                # Unknown provider, format is valid
                return (
                    True,
                    f"Format verified for {key_name} (live ping not available for this provider)",
                )

        except Exception as exc:
            logger.warning("Connection test failed for %s: %s", key_name, exc)
            return False, f"Connection test failed: {exc}"

    @classmethod
    def apply_to_workspace_env(
        cls,
        workspace_dir: Path,
        credentials: dict[str, str],
        *,
        env_filename: str = ".env",
    ) -> list[str]:
        """Safely write credentials to workspace .env, ensuring .gitignore covers .env and .env.example exists."""
        safe_dir = assert_safe_boundary(workspace_dir, action="write credentials to")
        env_file = safe_dir / env_filename
        env_example = safe_dir / ".env.example"
        gitignore_file = safe_dir / ".gitignore"

        # Read existing .env if present
        existing_lines: list[str] = []
        existing_keys: set[str] = set()
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    k = stripped.split("=", 1)[0].strip()
                    existing_keys.add(k)
                existing_lines.append(line)

        # Merge new credentials
        updated_keys: list[str] = []
        for key, val in credentials.items():
            if not val:
                continue
            updated_keys.append(key)
            new_line = f"{key}={val}"
            # Check if key already in existing_lines
            replaced = False
            for idx, line in enumerate(existing_lines):
                stripped = line.strip()
                if (
                    stripped
                    and not stripped.startswith("#")
                    and "=" in stripped
                    and stripped.split("=", 1)[0].strip() == key
                ):
                    existing_lines[idx] = new_line
                    replaced = True
                    break
            if not replaced:
                existing_lines.append(new_line)

        env_file.write_text("\n".join(existing_lines) + "\n", encoding="utf-8")

        # Update .env.example with placeholders (NEVER with real secret values)
        example_lines: list[str] = []
        existing_example_keys: set[str] = set()
        if env_example.exists():
            for line in env_example.read_text(encoding="utf-8", errors="ignore").splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    existing_example_keys.add(stripped.split("=", 1)[0].strip())
                example_lines.append(line)

        for key in credentials:
            if key not in existing_example_keys:
                example_lines.append(f"{key}=your_{key.lower()}_here")

        env_example.write_text("\n".join(example_lines) + "\n", encoding="utf-8")

        # Ensure .gitignore includes .env
        gi_lines: list[str] = []
        if gitignore_file.exists():
            gi_lines = gitignore_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        gi_set = {line.strip() for line in gi_lines}
        if ".env" not in gi_set:
            gi_lines.append(".env")
            gi_lines.append(".env.local")
            gitignore_file.write_text("\n".join(gi_lines) + "\n", encoding="utf-8")

        return updated_keys
