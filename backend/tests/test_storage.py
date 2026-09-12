"""Unit tests for the pluggable storage backend (app/services/storage.py).

All Cloudinary calls are mocked via ``unittest.mock`` — no real network or
Cloudinary credentials are needed in CI.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.storage import CloudinaryStorage, LocalStorage, get_storage


# ── LocalStorage ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_local_storage_upload_noop(tmp_path: Path):
    """upload_file is a silent no-op — the file is already on disk."""
    storage = LocalStorage()
    fake_file = tmp_path / "build.zip"
    fake_file.write_bytes(b"PK")

    key = await storage.upload_file(fake_file, "builds/abc/build_1.zip")
    assert key == "builds/abc/build_1.zip"


@pytest.mark.asyncio
async def test_local_storage_download_url_none():
    """get_download_url returns None — caller should serve via FileResponse."""
    storage = LocalStorage()
    url = await storage.get_download_url("builds/abc/build_1.zip")
    assert url is None


@pytest.mark.asyncio
async def test_local_storage_delete_noop():
    """delete_file is a no-op (local cleanup is handled elsewhere)."""
    storage = LocalStorage()
    # Should not raise
    await storage.delete_file("builds/abc/build_1.zip")


# ── CloudinaryStorage ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cloudinary_storage_upload_calls_uploader(tmp_path: Path):
    """upload_file calls cloudinary.uploader.upload with resource_type='raw'."""
    storage = CloudinaryStorage(
        cloud_name="test-cloud",
        api_key="AKID",
        api_secret="SECRET",
    )

    fake_file = tmp_path / "build.zip"
    fake_file.write_bytes(b"PK\x03\x04fake-zip-content")

    mock_upload = MagicMock(return_value={"public_id": "builds/abc/build_1.zip"})
    with patch("cloudinary.uploader.upload", mock_upload):
        key = await storage.upload_file(fake_file, "builds/abc/build_1.zip")

    assert key == "builds/abc/build_1.zip"
    mock_upload.assert_called_once_with(
        str(fake_file),
        public_id="builds/abc/build_1.zip",
        resource_type="raw",
        overwrite=True,
        cloud_name="test-cloud",
        api_key="AKID",
        api_secret="SECRET",
    )


@pytest.mark.asyncio
async def test_cloudinary_storage_download_url():
    """get_download_url calls cloudinary_url with resource_type='raw' and secure=True."""
    storage = CloudinaryStorage(
        cloud_name="test-cloud",
        api_key="AKID",
        api_secret="SECRET",
    )

    expected_url = "https://res.cloudinary.com/test-cloud/raw/upload/builds/abc/build_1.zip"
    mock_url_func = MagicMock(return_value=(expected_url, {}))

    with patch("cloudinary.utils.cloudinary_url", mock_url_func):
        url = await storage.get_download_url("builds/abc/build_1.zip", expires_in=1800)

    assert url == expected_url
    mock_url_func.assert_called_once_with(
        "builds/abc/build_1.zip",
        resource_type="raw",
        secure=True,
        cloud_name="test-cloud",
        api_key="AKID",
        api_secret="SECRET",
    )


@pytest.mark.asyncio
async def test_cloudinary_storage_delete_calls_destroy():
    """delete_file calls cloudinary.uploader.destroy with resource_type='raw'."""
    storage = CloudinaryStorage(
        cloud_name="test-cloud",
        api_key="AKID",
        api_secret="SECRET",
    )

    mock_destroy = MagicMock(return_value={"result": "ok"})
    with patch("cloudinary.uploader.destroy", mock_destroy):
        await storage.delete_file("builds/abc/build_1.zip")

    mock_destroy.assert_called_once_with(
        "builds/abc/build_1.zip",
        resource_type="raw",
        cloud_name="test-cloud",
        api_key="AKID",
        api_secret="SECRET",
    )


# ── get_storage() factory ────────────────────────────────────────────────────


def test_get_storage_returns_local_by_default():
    """Default config (STORAGE_BACKEND=local) returns LocalStorage."""
    with patch("app.services.storage.settings") as mock_settings:
        mock_settings.STORAGE_BACKEND = "local"
        storage = get_storage()
    assert isinstance(storage, LocalStorage)


def test_get_storage_falls_back_on_missing_creds():
    """STORAGE_BACKEND=cloudinary with missing credentials falls back to LocalStorage."""
    with patch("app.services.storage.settings") as mock_settings:
        mock_settings.STORAGE_BACKEND = "cloudinary"
        mock_settings.CLOUDINARY_CLOUD_NAME = "my-cloud"
        mock_settings.CLOUDINARY_API_KEY = ""  # missing
        mock_settings.CLOUDINARY_API_SECRET = ""  # missing
        storage = get_storage()
    assert isinstance(storage, LocalStorage)


def test_get_storage_returns_cloudinary_with_full_config():
    """All Cloudinary vars set returns CloudinaryStorage."""
    with patch("app.services.storage.settings") as mock_settings:
        mock_settings.STORAGE_BACKEND = "cloudinary"
        mock_settings.CLOUDINARY_CLOUD_NAME = "my-cloud"
        mock_settings.CLOUDINARY_API_KEY = "AKID"
        mock_settings.CLOUDINARY_API_SECRET = "SECRET"
        storage = get_storage()
    assert isinstance(storage, CloudinaryStorage)
