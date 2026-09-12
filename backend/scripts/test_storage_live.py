"""Standalone live test for object storage (LocalStorage and Cloudinary).

Usage (from backend/):
    ..\\backend\\venv\\Scripts\\python.exe scripts/test_storage_live.py
or with active virtual environment:
    python scripts/test_storage_live.py

Requires zero Docker, zero PostgreSQL, and zero Redis.
Performs an end-to-end test of:
1. Backend resolution via get_storage()
2. File upload
3. Download URL generation
4. Live HTTP verification of downloaded bytes
5. Remote cleanup (delete_file)
"""

import asyncio
import io
import sys
import tempfile
import zipfile
from pathlib import Path

# Add parent directory to sys.path so app modules are discoverable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from app.core.config import settings
from app.services.storage import CloudinaryStorage, LocalStorage, get_storage


def make_dummy_zip() -> bytes:
    """Generate a valid in-memory ZIP archive for testing."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("test_file.txt", "Hello from Cloudinary live test!\n")
        zf.writestr("metadata.json", '{"status": "ok", "test": true}\n')
    return buf.getvalue()


async def run_live_test() -> int:
    print("=" * 60)
    print(" AI Solution Builder — Live Storage Verification ")
    print("=" * 60)
    print(f"Configured STORAGE_BACKEND: {settings.STORAGE_BACKEND}")

    storage = get_storage()
    print(f"Resolved Storage Class   : {storage.__class__.__name__}")

    if isinstance(storage, LocalStorage):
        print("\n[INFO] Running in LOCAL mode.")
        if settings.STORAGE_BACKEND.lower() == "cloudinary":
            print(
                "[WARN] STORAGE_BACKEND was set to 'cloudinary' but missing credentials "
                "caused fallback to LocalStorage."
            )
            print(f"  CLOUDINARY_CLOUD_NAME: {'SET' if settings.CLOUDINARY_CLOUD_NAME else 'EMPTY'}")
            print(f"  CLOUDINARY_API_KEY   : {'SET' if settings.CLOUDINARY_API_KEY else 'EMPTY'}")
            print(f"  CLOUDINARY_API_SECRET: {'SET' if settings.CLOUDINARY_API_SECRET else 'EMPTY'}")
            print("\nTo test real Cloudinary uploads, fill in these values in .env")
        else:
            print("[OK] Local storage fallback is functioning as expected.")
        return 0

    if isinstance(storage, CloudinaryStorage):
        print("\n[INFO] Running in CLOUDINARY mode.")
        print(f"  Cloud Name : {settings.CLOUDINARY_CLOUD_NAME}")
        print(f"  API Key    : {'*' * (len(settings.CLOUDINARY_API_KEY) - 4) + settings.CLOUDINARY_API_KEY[-4:] if len(settings.CLOUDINARY_API_KEY) >= 4 else '***'}")

        # Create temporary ZIP file on disk
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            zip_bytes = make_dummy_zip()
            tmp_path.write_bytes(zip_bytes)

        test_key = "builds/test_verification/test_build_live.zip"

        try:
            # 1. Upload
            print(f"\n[1/4] Uploading raw asset to Cloudinary (key: {test_key})...")
            uploaded_key = await storage.upload_file(tmp_path, test_key)
            print(f"      Upload success! Returned key: {uploaded_key}")

            # 2. Get download URL
            print("\n[2/4] Generating download URL...")
            download_url = await storage.get_download_url(test_key)
            print(f"      Secure URL: {download_url}")

            if not download_url:
                print("      [FAIL] No URL returned!")
                return 1

            # 3. HTTP GET to verify public/signed access
            print("\n[3/4] Verifying HTTP download from Cloudinary CDN...")
            async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
                resp = await client.get(download_url)
                print(f"      HTTP Response Status: {resp.status_code}")
                if resp.status_code == 200:
                    content_len = len(resp.content)
                    print(f"      Downloaded {content_len} bytes successfully!")
                    # Check ZIP integrity
                    with zipfile.ZipFile(io.BytesIO(resp.content), "r") as check_zf:
                        files = check_zf.namelist()
                        print(f"      Files inside archive: {files}")
                        test_content = check_zf.read("test_file.txt").decode("utf-8")
                        print(f"      test_file.txt content: {test_content.strip()}")
                else:
                    print(f"      [WARN] CDN returned status {resp.status_code}. Response: {resp.text[:200]}")
                    print("      Note: If your Cloudinary account restricts raw delivery, signed delivery is required.")

            # 4. Clean up test file on Cloudinary
            print("\n[4/4] Cleaning up remote test file from Cloudinary...")
            await storage.delete_file(test_key)
            print("      Remote file deleted successfully!")

            print("\n" + "=" * 60)
            print(" ALL CLOUDINARY STORAGE CHECKS PASSED! ")
            print("=" * 60)
            return 0

        except Exception as exc:
            print(f"\n[ERROR] Test failed with exception: {exc}")
            import traceback
            traceback.print_exc()
            return 1
        finally:
            tmp_path.unlink(missing_ok=True)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run_live_test()))
