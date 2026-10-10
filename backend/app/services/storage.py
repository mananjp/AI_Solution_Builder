"""
AI Solution Builder — Pluggable Storage Backend

Provides local disk, Cloudinary raw file storage, and S3-compatible storage
(including Neon Object Storage) behind a common interface. In production the
factory never silently falls back to disk: MVP artifacts must be durable.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


def _validate_object_key(key: str) -> str:
    """Reject keys that could be interpreted as paths outside an object prefix."""
    candidate = Path(key)
    if not key or candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("Artifact key must be a relative path")
    return key


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
    """Dev-only artifact store rooted outside the mutable build workspace."""

    def _path(self, key: str) -> Path:
        candidate = Path(_validate_object_key(key))
        root = Path(settings.ARTIFACT_DIR).resolve()
        path = (root / candidate).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError("Artifact key escapes the configured artifact store") from exc
        return path

    async def upload_bytes(self, data: bytes, key: str) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    async def download_raw(self, key: str) -> bytes:
        path = self._path(key)
        if not path.exists():
            raise FileNotFoundError(f"No local object at {key}")
        return path.read_bytes()

    async def get_download_url(self, key: str, expires_in: int = 3600) -> str | None:
        # Returning None signals the caller to serve the file directly.
        return None

    async def delete_file(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


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


# ── S3-compatible object storage (Neon) ─────────────────────────────────────


class S3Storage(StorageBackend):
    """Durable artifact storage for S3-compatible providers such as Neon.

    Calls use a bounded SDK retry policy and are moved off the event loop. A
    presigned URL keeps downloads out of the API process while retaining a
    short-lived, private object URL.
    """

    def __init__(
        self,
        endpoint_url: str,
        bucket: str,
        region: str,
        access_key_id: str,
        secret_access_key: str,
        force_path_style: bool = True,
    ) -> None:
        import boto3
        from botocore.config import Config

        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=Config(
                signature_version="s3v4",
                connect_timeout=10,
                read_timeout=60,
                retries={"max_attempts": 3, "mode": "standard"},
                s3={"addressing_style": "path" if force_path_style else "virtual"},
            ),
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        """Create the bucket when it is missing, tolerating a concurrent creator.

        Neon and MinIO both require the bucket to exist before ``put_object``;
        doing it here keeps a fresh deployment (and local dev) working without a
        manual console step. An already-existing bucket is not an error.
        """
        from botocore.exceptions import ClientError

        def _create() -> None:
            try:
                self._client.head_bucket(Bucket=self._bucket)
                return
            except ClientError as exc:
                code = str(exc.response.get("Error", {}).get("Code", ""))
                if code not in {"403", "404", "NoSuchBucket", "NotFound"}:
                    raise
            try:
                self._client.create_bucket(Bucket=self._bucket)
                logger.info("Created object-storage bucket: %s", self._bucket)
            except ClientError as exc:
                code = str(exc.response.get("Error", {}).get("Code", ""))
                if code in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
                    return
                logger.warning("Could not create bucket %s: %s", self._bucket, exc)

        try:
            _create()
        except Exception as exc:  # noqa: BLE001 — never block boot on optional bucket setup
            logger.warning("Bucket pre-flight check failed for %s: %s", self._bucket, exc)

    async def upload_bytes(self, data: bytes, key: str) -> str:
        key = _validate_object_key(key)
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType="application/zip",
        )
        logger.info("Uploaded artifact to S3-compatible object storage: %s", key.split("/")[-1])
        return key

    async def download_raw(self, key: str) -> bytes:
        key = _validate_object_key(key)

        def _download() -> bytes:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            body = response["Body"]
            try:
                data: bytes = body.read()
            finally:
                body.close()
            return data

        return await asyncio.to_thread(_download)

    async def get_download_url(self, key: str, expires_in: int = 3600) -> str | None:
        key = _validate_object_key(key)
        return await asyncio.to_thread(
            self._client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    async def delete_file(self, key: str) -> None:
        key = _validate_object_key(key)
        await asyncio.to_thread(self._client.delete_object, Bucket=self._bucket, Key=key)
        logger.info("Deleted artifact from S3-compatible object storage: %s", key)


# ── Factory ──────────────────────────────────────────────────────────────────


def get_storage() -> StorageBackend:
    """Resolve the configured storage backend.

    Remote backends require complete credentials — otherwise a ``RuntimeError``
    is raised instead of silently falling back to disk.
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

    if backend in {"neon_s3", "s3"}:
        missing = [
            name
            for name, value in [
                ("S3_ENDPOINT_URL", settings.S3_ENDPOINT_URL),
                ("S3_BUCKET", settings.S3_BUCKET),
                ("S3_REGION", settings.S3_REGION),
                ("S3_ACCESS_KEY_ID", settings.S3_ACCESS_KEY_ID),
                ("S3_SECRET_ACCESS_KEY", settings.S3_SECRET_ACCESS_KEY),
            ]
            if not value
        ]
        if missing:
            raise RuntimeError(
                "STORAGE_BACKEND=neon_s3 is configured but the following "
                f"values are missing: {', '.join(missing)}"
            )
        return S3Storage(
            endpoint_url=settings.S3_ENDPOINT_URL,
            bucket=settings.S3_BUCKET,
            region=settings.S3_REGION,
            access_key_id=settings.S3_ACCESS_KEY_ID,
            secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            force_path_style=settings.S3_FORCE_PATH_STYLE,
        )

    if backend != "local":
        raise RuntimeError(
            "STORAGE_BACKEND must be one of: local, cloudinary, neon_s3. "
            f"Received {settings.STORAGE_BACKEND!r}."
        )

    return LocalStorage()
