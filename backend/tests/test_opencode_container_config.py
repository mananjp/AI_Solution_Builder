"""Static regressions for the OpenCode sidecar's runtime configuration."""

from __future__ import annotations

from pathlib import Path


def test_opencode_model_is_resolved_at_container_startup() -> None:
    root = Path(__file__).resolve().parents[1] / "opencode"
    config = (root / "config.json").read_text(encoding="utf-8")
    entrypoint = (root / "entrypoint.sh").read_text(encoding="utf-8")

    assert '"__OPENCODE_MODEL__"' in config
    assert '"__OPENCODE_SMALL_MODEL__"' in config
    assert 'sed -i "s|__OPENCODE_MODEL__|${MODEL}|g"' in entrypoint
    assert 'sed -i "s|__OPENCODE_SMALL_MODEL__|${SMALL_MODEL}|g"' in entrypoint
    assert "contains unsupported characters" in entrypoint
    # Both the primary and the small model are validated before serve starts.
    assert 'for VALUE in "${MODEL}" "${SMALL_MODEL}"; do' in entrypoint


def test_default_models_are_free_tier_and_distinct() -> None:
    """Small calls must not burn the primary (generation) model's quota."""
    config = (Path(__file__).resolve().parents[2] / "backend/app/core/config.py").read_text(
        encoding="utf-8"
    )
    assert 'OPENCODE_MODEL: str = "opencode/step-5-preview-free"' in config
    assert 'OPENCODE_SMALL_MODEL: str = "opencode/nemotron-3.5-lightning-free"' in config


def test_compose_gives_sidecar_overridable_dns_recovery() -> None:
    compose = (Path(__file__).resolve().parents[2] / "docker-compose.yml").read_text(
        encoding="utf-8"
    )
    assert "OPENCODE_DNS_PRIMARY" in compose
    assert "OPENCODE_DNS_SECONDARY" in compose
