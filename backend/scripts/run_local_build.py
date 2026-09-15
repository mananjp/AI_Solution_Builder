"""Run a single MVP build locally using the existing OpenCode sidecar.

Usage (from backend/):
    set PYTHONPATH=%cd%
    set OPENCODE_SERVER_URL=http://127.0.0.1:4096
    .\.venv\Scripts\python.exe scripts\run_local_build.py

The script copies the scaffold, invokes the sidecar, and prints a summary
of generated files and the local build directory.
"""
import asyncio
import os
import uuid
from pathlib import Path

# Ensure the local package is importable
os.environ.setdefault("PYTHONPATH", os.getcwd())

from app.services.mvp_builder import run_build


async def main():
    solution_id = uuid.uuid4()
    ai_state = {
        "solution_title": "Local Demo App",
        "business_description": "A tiny todo app generated for local demo.",
        "confirmed_modules": ["todos"],
    }

    print("Starting local MVP build (this may take a minute)...")
    try:
        result = await run_build(solution_id, ai_state, build_number=1, title="Local Demo App")
    except Exception as exc:
        print("Build failed:", exc)
        raise

    print("Build finished")
    print("Session:", result.get("session_id"))
    print("Local dir:", result.get("local_dir"))
    print("Files generated:")
    for p in result.get("files", [])[:200]:
        print(" -", p)
    print(f"Total files: {result.get('file_count')}")
    print("You can zip or inspect the directory above.")


if __name__ == "__main__":
    asyncio.run(main())
