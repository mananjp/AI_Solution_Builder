"""
Ask the AI Solution Builder to build an employee management system covering all aspects of it.
No pre-filled state, no pre-seeded modules — the AI builder autonomously analyzes the prompt,
infers the domain, designs the architecture, tokens, entities, screens, and full-stack code.
"""

import asyncio
import json
import shutil
import sys
from pathlib import Path
from uuid import uuid4

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.build_orchestrator import BuildContext, run_build_pipeline


async def main():
    solution_id = uuid4()
    build_dir = Path(".data/mvp_builds/employee_management_build").resolve()
    if build_dir.exists():
        shutil.rmtree(build_dir, ignore_errors=True)
    build_dir.mkdir(parents=True, exist_ok=True)

    async def on_progress(phase: str, step: int, pct: int, msg: str):
        print(f"[{pct:3d}%] [{phase.upper()}] {msg}", flush=True)

    user_prompt = "build an employee management system covering all aspects of it"

    ctx = BuildContext(
        solution_id=solution_id,
        build_number=1,
        workspace_dir=build_dir,
        target_dir=str(build_dir),
        ai_state={},  # Completely empty: zero predetermined modules or descriptions
        user_prompt=user_prompt,
        progress_cb=on_progress,
        allow_offline=False,
    )

    print("\n=======================================================", flush=True)
    print("PROMPT TO AI BUILDER: ", user_prompt, flush=True)
    print("AI STATE PASSED:      ", ctx.ai_state, flush=True)
    print("=======================================================\n", flush=True)

    res = await run_build_pipeline(ctx)

    print("\n--- AI BUILDER COMPLETED ---", flush=True)
    print("Files created:", res.get("file_count"), flush=True)
    print("Quality status:", res.get("quality"), flush=True)

    spec_file = build_dir / "spec.json"
    if spec_file.exists():
        spec = json.loads(spec_file.read_text(encoding="utf-8"))
        print(f"\n[AI Derived] App Name: {spec.get('app_name')}", flush=True)
        print(f"[AI Derived] One-Liner: {spec.get('one_liner')}", flush=True)
        print(f"[AI Derived] Core Value: {spec.get('core_value')}", flush=True)
        print(f"[AI Derived] Kind & Stage: {spec.get('app_kind')} ({spec.get('lifecycle_stage')})", flush=True)
        print("[AI Derived] Entities:", [e.get("name") for e in spec.get("entities", [])], flush=True)
        for e in spec.get("entities", []):
            field_names = [f.get("name") for f in e.get("fields", [])]
            print(f"   -> {e.get('name')}: {field_names}", flush=True)
        print("[AI Derived] Screens:", [s.get("route") for s in spec.get("screens", [])], flush=True)
        print("[AI Derived] Actions:", [a.get("name") for a in spec.get("actions", [])], flush=True)


if __name__ == "__main__":
    asyncio.run(main())
