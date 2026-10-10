"""Unit tests for the pluggable storage backend (app/services/storage.py).

All Cloudinary calls are mocked via ``unittest.mock`` — no real network or
Cloudinary credentials are needed in CI.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.storage import CloudinaryStorage, LocalStorage, S3Storage, get_storage

# ── LocalStorage ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_local_storage_upload_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """upload_bytes writes the blob to the keyed path."""
    monkeypatch.setattr("app.services.storage.settings.ARTIFACT_DIR", str(tmp_path))
    storage = LocalStorage()
    key = "builds/abc/build_1.zip"
    await storage.upload_bytes(b"PK", key)
    assert (tmp_path / "builds" / "abc" / "build_1.zip").read_bytes() == b"PK"


@pytest.mark.asyncio
async def test_local_storage_download_raw(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """download_raw reads the blob back from disk."""
    monkeypatch.setattr("app.services.storage.settings.ARTIFACT_DIR", str(tmp_path))
    storage = LocalStorage()
    key = "blob.bin"
    (tmp_path / "blob.bin").write_bytes(b"payload")
    assert await storage.download_raw(key) == b"payload"


@pytest.mark.asyncio
async def test_local_storage_download_url_none():
    """get_download_url returns None — caller should serve via FileResponse."""
    storage = LocalStorage()
    url = await storage.get_download_url("builds/abc/build_1.zip")
    assert url is None


@pytest.mark.asyncio
async def test_local_storage_delete_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """delete_file removes only the requested object under the artifact root."""
    monkeypatch.setattr("app.services.storage.settings.ARTIFACT_DIR", str(tmp_path))
    storage = LocalStorage()
    await storage.upload_bytes(b"PK", "builds/abc/build_1.zip")
    await storage.delete_file("builds/abc/build_1.zip")
    assert not (tmp_path / "builds/abc/build_1.zip").exists()


@pytest.mark.asyncio
async def test_local_storage_rejects_path_escape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.services.storage.settings.ARTIFACT_DIR", str(tmp_path))
    with pytest.raises(ValueError, match="relative path"):
        await LocalStorage().upload_bytes(b"PK", "/tmp/outside.zip")
    with pytest.raises(ValueError, match="relative path"):
        await LocalStorage().upload_bytes(b"PK", "../outside.zip")


# ── CloudinaryStorage ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cloudinary_storage_upload_bytes_calls_uploader():
    """upload_bytes calls cloudinary.uploader.upload with resource_type='raw'."""
    storage = CloudinaryStorage(
        cloud_name="test-cloud",
        api_key="AKID",
        api_secret="SECRET",
    )

    mock_upload = MagicMock(return_value={"public_id": "builds/abc/build_1.zip"})
    with patch("cloudinary.uploader.upload", mock_upload):
        key = await storage.upload_bytes(b"PK\x03\x04fake-zip-content", "builds/abc/build_1.zip")

    assert key == "builds/abc/build_1.zip"
    assert mock_upload.call_count == 1
    args, kwargs = mock_upload.call_args
    assert isinstance(args[0], __import__("io").BytesIO)
    assert args[0].read() == b"PK\x03\x04fake-zip-content"
    assert kwargs["public_id"] == "builds/abc/build_1.zip"
    assert kwargs["resource_type"] == "raw"
    assert kwargs["overwrite"] is True
    assert kwargs["cloud_name"] == "test-cloud"
    assert kwargs["api_key"] == "AKID"
    assert kwargs["api_secret"] == "SECRET"


@pytest.mark.asyncio
async def test_cloudinary_storage_download_raw():
    """download_raw fetches and returns the object bytes."""
    storage = CloudinaryStorage(
        cloud_name="test-cloud",
        api_key="AKID",
        api_secret="SECRET",
    )

    mock_resource = MagicMock(return_value={"secure_url": "https://cdn.example/build.zip"})
    mock_resp = MagicMock(status_code=200, content=b"zip-bytes")

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("cloudinary.api.resource", mock_resource),
        patch("httpx.AsyncClient", return_value=mock_client) as mock_client_cls,
    ):
        data = await storage.download_raw("builds/abc/build_1.zip")

    mock_client_cls.assert_called_once_with(timeout=60.0)
    assert data == b"zip-bytes"
    mock_resource.assert_called_once_with(
        "builds/abc/build_1.zip",
        resource_type="raw",
        cloud_name="test-cloud",
        api_key="AKID",
        api_secret="SECRET",
    )


@pytest.mark.asyncio
async def test_cloudinary_storage_download_url():
    """get_download_url calls private_download_url with an actual expiration."""
    storage = CloudinaryStorage(
        cloud_name="test-cloud",
        api_key="AKID",
        api_secret="SECRET",
    )

    expected_url = "https://api.cloudinary.com/v1_1/test-cloud/raw/upload/builds/abc/build_1.zip?expires_at=1000001800&signature=abc123"
    mock_private_dl = MagicMock(return_value=expected_url)

    with (
        patch("cloudinary.utils.private_download_url", mock_private_dl),
        patch("time.time", return_value=1000000000.0),
    ):
        url = await storage.get_download_url("builds/abc/build_1.zip", expires_in=1800)

    assert url == expected_url
    mock_private_dl.assert_called_once_with(
        public_id="builds/abc/build_1.zip",
        format="",
        resource_type="raw",
        type="upload",
        expires_at=1000001800,
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


@pytest.mark.asyncio
async def test_s3_storage_uses_path_style_and_presigned_urls():
    class FakeBody:
        def __init__(self) -> None:
            self.closed = False

        def read(self) -> bytes:
            return b"zip-bytes"

        def close(self) -> None:
            self.closed = True

    class FakeClient:
        def __init__(self) -> None:
            self.body = FakeBody()
            self.put_calls: list[dict] = []
            self.delete_calls: list[dict] = []

        def put_object(self, **kwargs) -> None:
            self.put_calls.append(kwargs)

        def get_object(self, **kwargs) -> dict:
            assert kwargs == {"Bucket": "artifacts", "Key": "builds/abc/build_1.zip"}
            return {"Body": self.body}

        def generate_presigned_url(self, *args, **kwargs) -> str:
            assert args == ("get_object",)
            assert kwargs == {
                "Params": {"Bucket": "artifacts", "Key": "builds/abc/build_1.zip"},
                "ExpiresIn": 3600,
            }
            return "https://storage.example/presigned"

        def delete_object(self, **kwargs) -> None:
            self.delete_calls.append(kwargs)

    client = FakeClient()

    with patch("boto3.client", return_value=client) as create_client:
        storage = S3Storage(
            endpoint_url="https://storage.example",
            bucket="artifacts",
            region="ap-southeast-1",
            access_key_id="access",
            secret_access_key="secret",
        )
        assert (
            await storage.upload_bytes(b"PK", "builds/abc/build_1.zip") == "builds/abc/build_1.zip"
        )
        assert await storage.download_raw("builds/abc/build_1.zip") == b"zip-bytes"
        assert (
            await storage.get_download_url("builds/abc/build_1.zip")
            == "https://storage.example/presigned"
        )
        await storage.delete_file("builds/abc/build_1.zip")

    create_client.assert_called_once()
    assert create_client.call_args.kwargs["endpoint_url"] == "https://storage.example"
    assert create_client.call_args.kwargs["config"].s3["addressing_style"] == "path"
    assert client.put_calls == [
        {
            "Bucket": "artifacts",
            "Key": "builds/abc/build_1.zip",
            "Body": b"PK",
            "ContentType": "application/zip",
        }
    ]
    assert client.delete_calls == [{"Bucket": "artifacts", "Key": "builds/abc/build_1.zip"}]
    assert client.body.closed


@pytest.mark.asyncio
async def test_s3_storage_rejects_path_escape():
    with patch("boto3.client"):
        storage = S3Storage("https://storage.example", "artifacts", "region", "access", "secret")
    with pytest.raises(ValueError, match="relative path"):
        await storage.upload_bytes(b"PK", "../outside.zip")


def test_get_storage_returns_local_by_default():
    """Default config (STORAGE_BACKEND=local) returns LocalStorage."""
    with patch("app.services.storage.settings") as mock_settings:
        mock_settings.STORAGE_BACKEND = "local"
        storage = get_storage()
    assert isinstance(storage, LocalStorage)


def test_get_storage_raises_on_missing_creds():
    """STORAGE_BACKEND=cloudinary with missing credentials raises RuntimeError.

    The old silent fallback to LocalStorage is intentionally removed so MVP
    artifacts can never leak onto a Render service disk in production.
    """
    with (
        patch("app.services.storage.settings") as mock_settings,
        pytest.raises(RuntimeError),
    ):
        mock_settings.STORAGE_BACKEND = "cloudinary"
        mock_settings.CLOUDINARY_CLOUD_NAME = "my-cloud"
        mock_settings.CLOUDINARY_API_KEY = ""  # missing
        mock_settings.CLOUDINARY_API_SECRET = ""  # missing
        get_storage()


def test_get_storage_returns_cloudinary_with_full_config():
    """All Cloudinary vars set returns CloudinaryStorage."""
    with patch("app.services.storage.settings") as mock_settings:
        mock_settings.STORAGE_BACKEND = "cloudinary"
        mock_settings.CLOUDINARY_CLOUD_NAME = "my-cloud"
        mock_settings.CLOUDINARY_API_KEY = "AKID"
        mock_settings.CLOUDINARY_API_SECRET = "SECRET"
        storage = get_storage()
    assert isinstance(storage, CloudinaryStorage)
