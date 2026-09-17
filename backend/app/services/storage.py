"""
AI Solution Builder — Pluggable Storage Backend

Provides LocalStorage (disk, dev-only) and CloudinaryStorage (Cloudinary raw
file storage) behind a common interface.  In production the factory hard-
requires ``STORAGE_BACKEND=cloudinary`` with complete credentials — it never
silently falls back to disk because MVP artifacts must live only in
Cloudinary.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


# ── Interface ────────────────────────────────────────────────────────────────


class StorageBackend(ABC):
    """Common interface for object storage backends."""

    @abstractmethod
    async def upload_bytes(self, data: bytes, key: str) -> str:
        """Upload an in-memory blob to the storage backend.

        Returns the storage key on success.
        """

    @abstractmethod
    async def download_raw(self, key: str) -> bytes:
        """Download a stored object's raw bytes for server-side processing."""

    @abstractmethod
    async def get_download_url(self, key: str, expires_in: int = 3600) -> str | None:
        """Return a download URL for the given key.

        Returns ``None`` when the caller should fall through to a local
        ``FileResponse`` (i.e. for ``LocalStorage``).
        """

    @abstractmethod
    async def delete_file(self, key: str) -> None:
        """Delete the object identified by *key* (best-effort)."""


# ── Local Disk ───────────────────────────────────────────────────────────────


class LocalStorage(StorageBackend):
    """Dev-only wrapper around the local disk."""

    async def upload_bytes(self, data: bytes, key: str) -> str:
        path = Path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    async def download_raw(self, key: str) -> bytes:
        path = Path(key)
        if not path.exists():
            raise FileNotFoundError(f"No local object at {key}")
        return path.read_bytes()

    async def get_download_url(self, key: str, expires_in: int = 3600) -> str | None:
        # Returning None signals the caller to serve the file directly.
        return None

    async def delete_file(self, key: str) -> None:
        # Local cleanup is handled by ``mvp_builder.cleanup_build``.
        pass


# ── Cloudinary (Raw File Storage) ────────────────────────────────────────────


class CloudinaryStorage(StorageBackend):
    """Raw file storage backend targeting Cloudinary.

    Uses the official ``cloudinary`` Python SDK for non-media assets
    (ZIP builds, documents). Network calls are executed via
    ``asyncio.to_thread`` to prevent blocking the async event loop.
    """

    def __init__(
        self,
        cloud_name: str,
        api_key: str,
        api_secret: str,
    ) -> None:
        self._cloud_name = (cloud_name or "").strip().strip("'\"").strip()
        self._api_key = (api_key or "").strip().strip("'\"").strip()
        self._api_secret = (api_secret or "").strip().strip("'\"").strip()
        try:
            import cloudinary

            cloudinary.config(
                cloud_name=self._cloud_name,
                api_key=self._api_key,
                api_secret=self._api_secret,
                secure=True,
            )
        except Exception as exc:
            logger.warning("Could not initialize cloudinary.config: %s", exc)

    async def upload_bytes(self, data: bytes, key: str) -> str:
        import io

        import cloudinary.uploader

        result = await asyncio.to_thread(
            cloudinary.uploader.upload,
            io.BytesIO(data),
            public_id=key,
            resource_type="raw",
            overwrite=True,
            cloud_name=self._cloud_name,
            api_key=self._api_key,
            api_secret=self._api_secret,
        )
        logger.info("Uploaded %s -> cloudinary://%s", key.split("/")[-1], key)
        return str(result.get("public_id", key))

    async def download_raw(self, key: str) -> bytes:
        import cloudinary.api
        import httpx

        def _public_url() -> str:
            resource = cloudinary.api.resource(
                key,
                resource_type="raw",
                cloud_name=self._cloud_name,
                api_key=self._api_key,
                api_secret=self._api_secret,
            )
            return str(resource.get("secure_url") or resource.get("url") or "")

        url = await asyncio.to_thread(_public_url)
        if not url:
            raise FileNotFoundError(f"Cloudinary object not found: {key}")
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content

    async def get_download_url(self, key: str, expires_in: int = 3600) -> str | None:
        import time

        import cloudinary.utils

        expires_at = int(time.time()) + expires_in
        url = cloudinary.utils.private_download_url(
            public_id=key,
            format="",
            resource_type="raw",
            type="upload",
            expires_at=expires_at,
            cloud_name=self._cloud_name,
            api_key=self._api_key,
            api_secret=self._api_secret,
        )
        return str(url) if url else None

    async def delete_file(self, key: str) -> None:
        import cloudinary.uploader

        await asyncio.to_thread(
            cloudinary.uploader.destroy,
            key,
            resource_type="raw",
            cloud_name=self._cloud_name,
            api_key=self._api_key,
            api_secret=self._api_secret,
        )
        logger.info("Deleted cloudinary://%s", key)


# ── Factory ──────────────────────────────────────────────────────────────────


def get_storage() -> StorageBackend:
    """Resolve the configured storage backend.

    ``STORAGE_BACKEND=cloudinary`` requires all three credentials — otherwise
    a ``RuntimeError`` is raised instead of silently falling back to disk.
    Local disk remains available for development only.
    """
    backend = settings.STORAGE_BACKEND.lower()

    if backend == "cloudinary":
        missing = [
            name
            for name, value in [
                ("CLOUDINARY_CLOUD_NAME", settings.CLOUDINARY_CLOUD_NAME),
                ("CLOUDINARY_API_KEY", settings.CLOUDINARY_API_KEY),
                ("CLOUDINARY_API_SECRET", settings.CLOUDINARY_API_SECRET),
            ]
            if not value
        ]
        if missing:
            raise RuntimeError(
                "STORAGE_BACKEND=cloudinary is configured but the following "
                f"credentials are missing: {', '.join(missing)}"
            )

        return CloudinaryStorage(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
        )

    return LocalStorage()
