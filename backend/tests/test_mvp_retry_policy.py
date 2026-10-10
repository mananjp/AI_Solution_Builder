"""Regression tests for retriable MVP worker failures."""

from __future__ import annotations

import pytest

from app.api.mvp import _is_retryable_build_error


@pytest.mark.parametrize(
    "message",
    [
        "Could not resolve host: api.groq.com",
        "Resolving timed out after 5000 milliseconds",
        "Temporary failure in name resolution",
    ],
)
def test_dns_provider_failures_are_retried(message: str) -> None:
    assert _is_retryable_build_error(RuntimeError(message))


def test_invalid_provider_configuration_is_not_retried() -> None:
    assert not _is_retryable_build_error(RuntimeError("invalid API key"))
