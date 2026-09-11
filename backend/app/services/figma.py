"""
AI Solution Builder — Figma Exporter (Section 11)

Translates generated wireframes into a Figma REST-API-shaped file manifest
(frames, sections, and elements). The manifest is CI/CD-consumable: it can be
uploaded to a Figma file via the Figma REST API with an access token, or fed
directly to the frontend canvas editor.
"""

from typing import Any


def _frame_for_screen(screen: dict[str, Any], index: int) -> dict[str, Any]:
    children: list[dict[str, Any]] = []
    for component in screen.get("components", []):
        children.append(
            {
                "type": "FRAME",
                "name": component.get("title", component.get("type", "Element")),
                "boundingBox": {"x": 0, "y": children.__len__() * 96, "width": 1200, "height": 88},
                "fills": [{"color": {"r": 0.16, "g": 0.12, "b": 0.28, "a": 1}}],
                "children": [
                    {
                        "type": "TEXT",
                        "name": "label",
                        "characters": component.get("description", ""),
                    }
                ],
            }
        )

    return {
        "type": "FRAME",
        "name": screen.get("name", f"Screen {index + 1}"),
        "boundingBox": {"x": 0, "y": 0, "width": 1200, "height": 800},
        "backgroundColor": {"r": 1, "g": 1, "b": 1, "a": 1},
        "children": children,
    }


def build_figma_manifest(bundle: dict[str, Any]) -> dict[str, Any]:
    """Build a Figma file manifest from the wireframe artifacts in a bundle."""
    pages: list[dict[str, Any]] = []
    wireframes = bundle.get("wireframes") or [
        {"name": data.get("module", "wireframes"), "screens": data.get("screens", [])}
        for data in [
            art.get("content", {})
            for art in bundle.get("artifacts", [])
            if art["artifact_type"] == "wireframe"
        ]
        if isinstance(data, dict)
    ]

    for idx, page in enumerate(wireframes):
        screens = page.get("screens", [])
        pages.append(
            {
                "type": "CANVAS",
                "name": page.get("name", f"Wireframes {idx + 1}"),
                "children": [
                    _frame_for_screen(screen, screen_idx)
                    for screen_idx, screen in enumerate(screens)
                ],
            }
        )

    return {
        "name": bundle.get("title", "AI Solution Builder Wireframes"),
        "type": "FILE",
        "children": pages or [{"type": "CANVAS", "name": "Wireframes 1", "children": []}],
        "version": bundle.get("status", "complete"),
        "exported_by": "AI Solution Builder",
    }
