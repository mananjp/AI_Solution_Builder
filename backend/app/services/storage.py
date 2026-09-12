"""
AI Solution Builder — Pluggable Storage Backend

Provides LocalStorage (disk) and CloudinaryStorage (Cloudinary raw file storage)
behind a common interface.  The factory ``get_storage()`` reads
``settings.STORAGE_BACKEND`` and falls back to local disk when Cloudinary
credentials are missing — mirroring the ``get_llm()`` resilience pattern.
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
    async def upload_file(self, local_path: Path, key: str) -> str:
        """Upload a local file to the storage backend.

        Returns the storage key on success.
        """

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
    """Wraps the existing local-disk behaviour — files are already on disk."""

    async def upload_file(self, local_path: Path, key: str) -> str:
        # Nothing to upload — the file is already on the local filesystem.
        return key

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
    (ZIP builds, documents). Uploads are executed via ``asyncio.to_thread``
    to prevent blocking the async event loop.
    """

    def __init__(
        self,
        cloud_name: str,
        api_key: str,
        api_secret: str,
    ) -> None:
        self._cloud_name = cloud_name
        self._api_key = api_key
        self._api_secret = api_secret

    async def upload_file(self, local_path: Path, key: str) -> str:
        import cloudinary.uploader

        result = await asyncio.to_thread(
            cloudinary.uploader.upload,
            str(local_path),
            public_id=key,
            resource_type="raw",
            overwrite=True,
            cloud_name=self._cloud_name,
            api_key=self._api_key,
            api_secret=self._api_secret,
        )
        logger.info("Uploaded %s -> cloudinary://%s", local_path.name, key)
        return str(result.get("public_id", key))

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
        return url

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

    Falls back to ``LocalStorage`` when ``STORAGE_BACKEND=cloudinary`` but credentials
    are incomplete — same resilience pattern as ``get_llm()``.
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
            logger.warning(
                "STORAGE_BACKEND=cloudinary but missing credentials (%s) "
                "— falling back to local storage",
                ", ".join(missing),
            )
            return LocalStorage()

        return CloudinaryStorage(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
        )

    return LocalStorage()
