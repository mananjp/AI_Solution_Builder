"""
AI Solution Builder — Product Image Generation (Gemini)

Generates presentation-grade product visuals (app icon, UI mockup, hero image)
from an :class:`~app.services.app_spec.AppSpec` and hands them back as bytes for
persistence as ``SolutionArtifact`` rows.

Design constraints
------------------
* **Never raises.** Image generation is a presentation nicety bolted onto a build
  that is otherwise complete. Every failure path returns ``None``/``[]`` and logs,
  so a missing key, a quota error or a network blip can never fail a build.
* **No new dependency.** Uses ``httpx`` (already required) against the public
  Gemini REST API rather than adding an unverifiable SDK to the lockfile.
* **Prompts are explicit and structured.** Image models follow long, sectioned
  prompts far more reliably than a single sentence, and they reliably produce
  garbled glyphs unless told not to — so every prompt ends with hard negative
  constraints about text.
"""

from __future__ import annotations

import base64
import binascii
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Public Gemini REST endpoint. The API key travels in the ``x-goog-api-key``
# header rather than a query string so it cannot leak into access logs or
# proxy traces.
_GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Artifact types. ``artifact_type`` is an unconstrained String(100) column, so
# these need no migration.
KIND_APP_ICON = "app_icon"
KIND_UI_MOCKUP = "ui_mockup"
KIND_HERO = "hero_image"

#: Every artifact type that stores image bytes, in display order.
IMAGE_ARTIFACT_TYPES: tuple[str, ...] = (KIND_HERO, KIND_UI_MOCKUP, KIND_APP_ICON)

_EXT_BY_MIME = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
}

# Hard constraints appended to every prompt. Image models love to hallucinate
# illegible text, which reads as broken in a product context, so this is
# non-negotiable and deliberately repetitive.
_NEGATIVE_CONSTRAINTS = """\
RENDERING CONSTRAINTS (strict):
- Do NOT render any text, letters, words, numbers, captions, labels, logos or watermarks anywhere in the image. UI regions, if any, must be abstract shapes only.
- Do NOT render fake or gibberish typography, QR codes or signage.
- No visible brand marks, trademarks or copyrighted characters.
- Photorealistic materials, physically plausible lighting, clean composition, no visual clutter."""


@dataclass(frozen=True)
class ImagePlan:
    """A single image to generate, before the model has been called."""

    kind: str
    title: str
    prompt: str
    aspect_ratio: str


@dataclass(frozen=True)
class GeneratedImage:
    """A successfully generated image, ready to be persisted."""

    kind: str
    title: str
    prompt: str
    aspect_ratio: str
    data: bytes
    mime_type: str
    model: str
    revised_prompt: str | None = field(default=None)


def has_image_credentials() -> bool:
    """True when image generation is both enabled and keyed."""
    return bool(settings.IMAGE_GENERATION_ENABLED and settings.GEMINI_API_KEY.strip())


# ── Prompt construction ───────────────────────────────────────────────────────


def _listify(values: list[Any], limit: int) -> str:
    picked = [str(getattr(v, "name", v)).strip() for v in values[:limit]]
    picked = [p for p in picked if p]
    return ", ".join(picked)


def _subject_block(spec: Any) -> str:
    """Who/what the product is, grounded strictly in the spec."""
    name = str(getattr(spec, "app_name", "") or "the product").strip()
    one_liner = str(getattr(spec, "one_liner", "") or "").strip()
    core_value = str(getattr(spec, "core_value", "") or "").strip()
    lines = [f"Product name: {name}"]
    if one_liner:
        lines.append(f"One-line pitch: {one_liner}")
    if core_value:
        lines.append(f"Core value beyond plain CRUD: {core_value}")
    return "\n".join(lines)


def _domain_block(spec: Any) -> str:
    """The domain vocabulary that should drive the imagery's subject matter."""
    entities = list(getattr(spec, "entities", []) or [])
    screens = list(getattr(spec, "screens", []) or [])
    lines: list[str] = []
    if entities:
        described = [
            f"{e.name} ({e.description})" for e in entities[:4] if getattr(e, "description", "")
        ]
        lines.append(
            "Core domain entities: "
            + (_listify(entities, 4) if not described else "; ".join(described))
        )
    if screens:
        lines.append(f"Key product screens: {_listify(screens, 5)}")
    lines.append(f"Architecture style: {getattr(spec, 'architecture', 'web application')}")
    if getattr(spec, "has_ml_model", False):
        frameworks = _listify(list(getattr(spec, "ml_frameworks", []) or []), 3)
        lines.append(
            "Includes machine learning components"
            + (f" ({frameworks})" if frameworks else "")
            + " — convey analytic/AI character abstractly, never as a robot or brain cliché."
        )
    return "\n".join(lines)


def _icon_plan(spec: Any) -> ImagePlan:
    return ImagePlan(
        kind=KIND_APP_ICON,
        title=f"{getattr(spec, 'app_name', 'App')} — App Icon",
        aspect_ratio="1:1",
        prompt="\n".join(
            [
                "TASK: Design a single, memorable app-store icon.",
                "",
                _subject_block(spec),
                "",
                "CONCEPT:",
                "- Distil the product above into one abstract geometric symbol that suggests its"
                " domain at a glance. One strong idea only — not a collage.",
                "- Prefer a simple, bold silhouette that stays legible at 32x32 pixels.",
                "- No device mockups, no rounded-square app tile, no drop shadows behind the tile.",
                "",
                "STYLE & ART DIRECTION:",
                "- Flat, modern vector illustration with subtle depth (soft gradient, no skeuomorphism).",
                "- Confident 2-3 colour palette drawn from the product's domain, high contrast against"
                " a plain neutral background.",
                "- Precise geometry, even stroke weights, generous negative space, perfectly centred.",
                "",
                "COMPOSITION:",
                "- Single centred subject, square crop, symmetrical or clearly balanced.",
                "- Generous margin around the subject so it survives circular and rounded masks.",
                "",
                "LIGHTING & COLOR:",
                "- Flat even lighting, no cast shadows, no reflections. Saturated but not neon.",
                "",
                _NEGATIVE_CONSTRAINTS,
            ]
        ),
    )


def _mockup_plan(spec: Any) -> ImagePlan:
    return ImagePlan(
        kind=KIND_UI_MOCKUP,
        title=f"{getattr(spec, 'app_name', 'App')} — Primary Screen Mockup",
        aspect_ratio="16:9",
        prompt="\n".join(
            [
                "TASK: Produce a photorealistic product-UI mockup of this application's main screen.",
                "",
                _subject_block(spec),
                "",
                _domain_block(spec),
                "",
                "SCENE:",
                "- A {app} web dashboard viewed straight-on, floating in a softly lit neutral studio",
                " environment with a subtle gradient backdrop.",
                "- Show the signature screen for this product: a left navigation rail, a top bar, and"
                " a main content area built from abstract cards, tiles, list rows and simple charts.",
                "- Every UI element is a blank shape — rounded rectangles, bars, dots and placeholder"
                " blocks. Imply the layout and data density, never the wording.",
                "",
                "STYLE & ART DIRECTION:",
                "- Modern SaaS product design language: generous whitespace, 8px grid, soft shadows,",
                "  subtle 1px borders, one confident accent colour against near-monochrome neutrals.",
                "- Crisp, legible at full width; realistic depth and material response.",
                "",
                "COMPOSITION:",
                "- Landscape 16:9, screen centred and filling ~80% of the frame.",
                "- Straight-on orthographic view — no perspective skew, no tilted device.",
                "- Balanced negative space around the screen.",
                "",
                "LIGHTING & COLOR:",
                "- Soft diffused key light from upper left, gentle ambient fill, no harsh specular hits.",
                "- Neutral grey-white environment so the accent colour reads clearly.",
                "",
                _NEGATIVE_CONSTRAINTS,
            ]
        ),
    )


def _hero_plan(spec: Any) -> ImagePlan:
    return ImagePlan(
        kind=KIND_HERO,
        title=f"{getattr(spec, 'app_name', 'App')} — Hero Visual",
        aspect_ratio="16:9",
        prompt="\n".join(
            [
                "TASK: Create an editorial marketing hero image for this product's landing page.",
                "",
                _subject_block(spec),
                "",
                _domain_block(spec),
                "",
                "CONCEPT:",
                "- A metaphorical, editorial-quality scene that captures the product's domain and the"
                " value it delivers. Abstract and premium rather than literal or stocky.",
                "- Express the core value above as a visual idea (flow, orchestration, insight,"
                " control, collaboration) using shape, light and depth.",
                "",
                "STYLE & ART DIRECTION:",
                "- Cinematic 3D render or high-end abstract digital art; sophisticated, restrained,",
                "  contemporary. Think premium SaaS launch visual, not clip art.",
                "- Cohesive duotone-leaning palette with one luminous accent.",
                "- Realistic material response, volumetric depth, gentle film-like grain.",
                "",
                "COMPOSITION:",
                "- Landscape 16:9 with deliberate negative space on the left third, suitable for",
                "  overlaying a headline.",
                "- Clear single focal point, layered foreground/midground/background for depth.",
                "",
                "LIGHTING & COLOR:",
                "- Dramatic directional light with soft coloured rim light, deep but readable shadows.",
                "- Cinematic contrast; avoid muddy midtones.",
                "",
                _NEGATIVE_CONSTRAINTS,
            ]
        ),
    )


_PLAN_BUILDERS = {
    KIND_HERO: _hero_plan,
    KIND_UI_MOCKUP: _mockup_plan,
    KIND_APP_ICON: _icon_plan,
}


def plan_images(spec: Any, limit: int | None = None) -> list[ImagePlan]:
    """Build the ordered list of images to generate for *spec*.

    Ordering runs hero -> UI mockup -> app icon so that if the caller has to stop
    early (count limit, partial failure) the most valuable asset survives.
    """
    count = settings.MVP_IMAGE_COUNT if limit is None else max(0, int(limit))
    plans: list[ImagePlan] = []
    for kind in IMAGE_ARTIFACT_TYPES:
        if len(plans) >= count:
            break
        builder = _PLAN_BUILDERS.get(kind)
        if builder is None:  # pragma: no cover - guarded by IMAGE_ARTIFACT_TYPES
            continue
        try:
            plans.append(builder(spec))
        except Exception as exc:  # noqa: BLE001 - a bad spec must not break the build
            logger.warning("Could not build image plan for %s (%s); skipping", kind, exc)
    return plans


# ── Gemini call ───────────────────────────────────────────────────────────────


def _extract_image(payload: dict[str, Any]) -> tuple[bytes, str] | None:
    """Pull the first inline image out of a Gemini ``generateContent`` response.

    Returns ``(data, mime_type)`` or ``None``. Both ``inlineData`` (current REST
    casing) and ``inline_data`` (SDK-style) are accepted so a casing change on
    Google's side degrades to a skip rather than a crash.
    """
    for candidate in payload.get("candidates") or []:
        content = (candidate or {}).get("content") or {}
        for part in content.get("parts") or []:
            if not isinstance(part, dict):
                continue
            inline = part.get("inlineData") or part.get("inline_data")
            if not isinstance(inline, dict):
                continue
            raw = inline.get("data")
            if not raw:
                continue
            mime = str(inline.get("mimeType") or inline.get("mime_type") or "image/png")
            if not mime.startswith("image/"):
                continue
            try:
                return base64.b64decode(raw, validate=False), mime
            except (binascii.Error, ValueError) as exc:
                logger.warning("Gemini returned undecodable image data (%s)", exc)
                return None
    return None


def _extract_text(payload: dict[str, Any]) -> str | None:
    """Best-effort prose the model returned alongside the image."""
    chunks: list[str] = []
    for candidate in payload.get("candidates") or []:
        content = (candidate or {}).get("content") or {}
        for part in content.get("parts") or []:
            if isinstance(part, dict) and part.get("text"):
                chunks.append(str(part["text"]))
    joined = "\n".join(chunks).strip()
    return joined or None


async def _call_gemini(plan: ImagePlan) -> GeneratedImage | None:
    """Call Gemini once. Returns ``None`` on any failure — never raises."""
    model = settings.GEMINI_IMAGE_MODEL
    url = _GEMINI_ENDPOINT.format(model=model)
    body: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": plan.prompt}]}],
        "generationConfig": {
            # Ask for image-only output; asking for text as well makes the model
            # spend capacity rendering captions we do not want.
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": plan.aspect_ratio},
        },
    }
    headers = {
        "x-goog-api-key": settings.GEMINI_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=float(settings.MVP_IMAGE_TIMEOUT)) as client:
            resp = await client.post(url, json=body, headers=headers)
    except Exception as exc:  # noqa: BLE001 - network/DNS/TLS/timeout all fail-open
        logger.warning("Gemini image request for %s failed (%s)", plan.kind, exc)
        return None

    if resp.status_code >= 400:
        # Log the status and a truncated body for diagnosis, never the key.
        logger.warning(
            "Gemini image request for %s returned HTTP %s: %s",
            plan.kind,
            resp.status_code,
            resp.text[:300],
        )
        return None

    try:
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini returned non-JSON for %s (%s)", plan.kind, exc)
        return None

    if payload.get("promptFeedback", {}).get("blockReason"):
        logger.info("Gemini blocked the %s prompt: %s", plan.kind, payload["promptFeedback"])
        return None

    found = _extract_image(payload)
    if found is None:
        logger.info("Gemini returned no image bytes for %s", plan.kind)
        return None

    data, mime_type = found
    if not data:
        logger.info("Gemini returned an empty image for %s", plan.kind)
        return None

    return GeneratedImage(
        kind=plan.kind,
        title=plan.title,
        prompt=plan.prompt,
        aspect_ratio=plan.aspect_ratio,
        data=data,
        mime_type=mime_type,
        model=model,
        revised_prompt=_extract_text(payload),
    )


async def generate_product_images(
    spec: Any,
    limit: int | None = None,
    on_progress: Any = None,
    total_budget: float | None = None,
) -> list[GeneratedImage]:
    """Generate the planned product visuals for *spec*.

    Images are produced sequentially rather than concurrently: it keeps the
    per-minute quota predictable, produces steadier progress events for the SSE
    stream, and a failure costs one image rather than the whole batch.

    ``total_budget`` caps the *whole* phase in seconds. The cap is checked
    *before* starting each new image rather than enforced with ``wait_for``, so
    images that already finished are still returned and persisted instead of
    being thrown away by a cancellation.

    ``on_progress`` is an optional ``async (done, total, title) -> None`` callback
    used to drive the build progress stream.
    """
    if not has_image_credentials():
        logger.info("Image generation skipped: no Gemini credentials configured")
        return []
    if spec is None:
        logger.info("Image generation skipped: no AppSpec available")
        return []

    plans = plan_images(spec, limit=limit)
    if not plans:
        return []

    budget = settings.MVP_IMAGE_TOTAL_BUDGET if total_budget is None else total_budget
    started = time.monotonic()

    results: list[GeneratedImage] = []
    total = len(plans)
    for index, plan in enumerate(plans, start=1):
        if budget and budget > 0 and (time.monotonic() - started) >= budget:
            logger.info(
                "Image phase budget of %ss exhausted after %d/%d visuals; "
                "continuing with what completed",
                budget,
                len(results),
                total,
            )
            break
        if on_progress is not None:
            try:
                await on_progress(index - 1, total, plan.title)
            except Exception as exc:  # noqa: BLE001 - progress must never abort work
                logger.warning("Image progress callback failed (%s)", exc)
        image = await _call_gemini(plan)
        if image is not None:
            results.append(image)
    if on_progress is not None:
        try:
            await on_progress(total, total, f"{len(results)} of {total} visuals ready")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Image progress callback failed (%s)", exc)

    logger.info(
        "Generated %d/%d product visuals for '%s'",
        len(results),
        total,
        getattr(spec, "app_name", "?"),
    )
    return results


def image_extension(mime_type: str) -> str:
    return _EXT_BY_MIME.get(mime_type, "png")


def image_storage_key(solution_id: Any, kind: str, mime_type: str) -> str:
    """Collision-free storage key for one generated image.

    The random component matters: without it the key would be deterministic
    (``artifacts/<solution>/visuals/<kind>.png``) and a second build would
    overwrite the first build's bytes *while the v1 artifact row still points at
    that key* - so viewing v1 would silently return v2's image.
    """
    token = uuid.uuid4().hex[:12]
    return f"artifacts/{solution_id}/visuals/{kind}_{token}.{image_extension(mime_type)}"


def is_image_artifact(artifact_type: str) -> bool:
    return artifact_type in IMAGE_ARTIFACT_TYPES


def image_content(image: GeneratedImage, storage_key: str) -> dict[str, Any]:
    """The JSONB ``content`` payload stored on the artifact row.

    The bytes live in object storage; this dict carries everything the UI needs
    to render and explain the image without a second round-trip.
    """
    return {
        "image": {
            "storage_key": storage_key,
            "mime_type": image.mime_type,
            "bytes": len(image.data),
            "aspect_ratio": image.aspect_ratio,
        },
        "prompt": image.prompt,
        "revised_prompt": image.revised_prompt,
        "model": image.model,
        "generator": "gemini",
    }


def image_content_text(image: GeneratedImage) -> str:
    """Human-readable rendering of the prompt, shown alongside the image."""
    lines = [
        f"# {image.title}",
        "",
        f"- **Kind:** `{image.kind}`",
        f"- **Model:** `{image.model}`",
        f"- **Aspect ratio:** `{image.aspect_ratio}`",
        f"- **MIME type:** `{image.mime_type}`",
        f"- **Size:** {len(image.data):,} bytes",
        "",
        "## Generation prompt",
        "",
        "```text",
        image.prompt,
        "```",
    ]
    if image.revised_prompt:
        lines += ["", "## Model commentary", "", image.revised_prompt]
    return "\n".join(lines)


__all__ = [
    "GeneratedImage",
    "IMAGE_ARTIFACT_TYPES",
    "ImagePlan",
    "KIND_APP_ICON",
    "KIND_HERO",
    "KIND_UI_MOCKUP",
    "generate_product_images",
    "has_image_credentials",
    "image_content",
    "image_content_text",
    "image_extension",
    "image_storage_key",
    "is_image_artifact",
    "plan_images",
]
