"""Run an MVP build and show live file creation progress (polling)."""
import asyncio
import os
import uuid
import time
from pathlib import Path

os.environ.setdefault("PYTHONPATH", os.getcwd())

from app.services.mvp_builder import (
    build_mvp_prompt,
    build_workspace_dir,
    create_session,
    list_build_files,
    scaffold_build,
    send_build_prompt,
)


async def watch_dir(build_dir: Path, stop_event: asyncio.Event):
    seen = set()
    while not stop_event.is_set():
        files = list_build_files(build_dir)
        for p in files:
            rp = str(p)
            if rp not in seen:
                print(f"[new file] {rp}")
                seen.add(rp)
        await asyncio.sleep(1)


async def live_build():
    solution_id = uuid.uuid4()
    build_number = 1
    local_dir = build_workspace_dir(solution_id, build_number)
    print("Scaffolding build into:", local_dir)

    # Ensure directory and scaffold
    scaffold_build(
        local_dir,
        app_title="Live Demo App",
        inject_modules=["todos"],
    )

    # Start watcher
    stop_event = asyncio.Event()
    watcher = asyncio.create_task(watch_dir(local_dir, stop_event))

    try:
        # Compose prompt
        ai_state = {
            "solution_title": "Live Demo App",
            "business_description": "A tiny todo app generated for local demo.",
            "confirmed_modules": ["todos"],
        }
        target_dir = f"{solution_id.hex[:12]}/build_{build_number}"
        prompt = build_mvp_prompt(ai_state, target_dir, app_title="Live Demo App")

        print("Creating OpenCode session...")
        session_id = await create_session(f"MVP Live Build - {solution_id}")
        print("Session created:", session_id)

        print("Sending build prompt (streaming created files)...")
        # Send prompt and wait for response; the watcher will print files during this time
        response = await send_build_prompt(session_id, prompt)
        print("Build response received, info:", response.get("info"))

        # Final snapshot
        files = list_build_files(local_dir)
        print("Final file list:")
        for p in files:
            print(" -", p)
        print(f"Total files: {len(files)}")

    finally:
        stop_event.set()
        await watcher


if __name__ == "__main__":
    asyncio.run(live_build())
