"""
Run custom build pipeline for Architect Studio Portfolio with 2 showcased projects and AI images.
"""

import asyncio
import shutil
from pathlib import Path
from uuid import uuid4

from app.services.build_orchestrator import BuildContext, run_build_pipeline


async def main():
    solution_id = uuid4()
    build_dir = Path(".data/mvp_builds/architect_portfolio_build").resolve()
    if build_dir.exists():
        shutil.rmtree(build_dir, ignore_errors=True)
    build_dir.mkdir(parents=True, exist_ok=True)

    # Pre-populate public/images with the 2 generated architectural images
    img_dir = build_dir / "frontend" / "public" / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    brain_dir = Path(
        r"C:\Users\ASUS\.gemini\antigravity-ide\brain\f5a2576d-a164-4b71-89b6-84254dc5e44c"
    )
    img1 = brain_dir / "villa_caelum_1791396846178.jpg"
    img2 = brain_dir / "timber_pavilion_1791396882978.jpg"

    if img1.exists():
        shutil.copy2(img1, img_dir / "villa_caelum.jpg")
        print(f"Copied {img1.name} -> villa_caelum.jpg ({img1.stat().st_size} bytes)")
    if img2.exists():
        shutil.copy2(img2, img_dir / "timber_pavilion.jpg")
        print(f"Copied {img2.name} -> timber_pavilion.jpg ({img2.stat().st_size} bytes)")

    async def on_progress(phase: str, step: int, pct: int, msg: str):
        print(f"[{pct:3d}%] [{phase.upper()}] {msg}")

    user_prompt = "build a simple landing page for an architect showcasing his 2 projects"
    ctx = BuildContext(
        solution_id=solution_id,
        build_number=1,
        workspace_dir=build_dir,
        target_dir=str(build_dir),
        ai_state={
            "solution_title": "Apex Architecture Atelier",
            "business_description": "Award-winning architectural studio specializing in minimalist modern residences and sustainable mass-timber structures.",
        },
        user_prompt=user_prompt,
        progress_cb=on_progress,
        allow_offline=False,
    )

    print("\n--- Starting Custom Builder Pipeline ---")
    res = await run_build_pipeline(ctx)
    print("\n--- Build Pipeline Completed Successfully ---")
    print("Files created:", res.get("file_count"))
    print("Quality summary:", res.get("quality"))

    page_file = build_dir / "frontend" / "src" / "app" / "page.tsx"
    if page_file.exists():
        content = page_file.read_text(encoding="utf-8")
        print("\n=== FRONTEND LANDING PAGE (page.tsx preview) ===")
        print(f"Total lines: {len(content.splitlines())}")
        has_projects = (
            "villa_caelum" in content or "timber_pavilion" in content or "Villa Caelum" in content
        )
        print(f"Contains architectural project references: {has_projects}")


if __name__ == "__main__":
    asyncio.run(main())
