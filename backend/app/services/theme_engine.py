"""
AI Solution Builder — Domain theme engine.

The template ships stock shadcn blue (`--primary: 221.2 83.2% 53.3%`) and
nothing ever varied it, so every generated app looked like the same SaaS
console regardless of industry. This module replaces that with a real palette
system:

  classify_vertical   keyword-scored vertical detection (no LLM call)
  INDUSTRY_PALETTES   ~18 curated vertical token sets
  fallback_theme      deterministic hash-based hue rotation for unknowns
  render_globals_css  the token block that replaces the stock one
  apply_theme         patch globals.css / layout.tsx / tailwind.config.ts

An LLM-proposed palette wins when it passes WCAG validation; the industry
table is what catches everything else. See docs/adr/0005.
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.services.app_spec import (
    BODY_CONTRAST_MIN,
    LARGE_CONTRAST_MIN,
    AppSpec,
    ColourModel,
    ThemeSpec,
    contrast_ratio,
)

logger = logging.getLogger(__name__)


def _c(h: float, s: float, l: float) -> ColourModel:
    return ColourModel(h=h, s=s, l=l)


# ── Industry palettes ────────────────────────────────────────────────────
#
# Every entry is a complete token set: a primary that carries the industry's
# usual association, a near-white background so body text clears 4.5:1
# trivially, a warm/cool muted for secondary surfaces, and a type pairing.
# Primary hues are deliberately spread around the wheel — the acceptance
# criterion is that no two verticals share one, because a shared hue is exactly
# the "every app looks identical" symptom this replaces.

INDUSTRY_PALETTES: dict[str, dict[str, Any]] = {
    "bakery": {
        "keywords": ("bakery", "baker", "bread", "pastry", "pastries", "cupcake", "croissant"),
        "primary": _c(28, 62, 42),
        "accent": _c(12, 68, 52),
        "background": _c(36, 44, 97),
        "foreground": _c(28, 32, 14),
        "muted": _c(34, 30, 90),
        "radius": "0.75rem",
        "font_sans": "Fraunces",
        "font_display": "Fraunces",
        "mood": "artisan",
    },
    "ice_cream": {
        "keywords": ("ice cream", "icecream", "gelato", "frozen", "sorbet", "froyo", "scoop"),
        "primary": _c(340, 70, 48),
        "accent": _c(26, 88, 56),
        "background": _c(20, 60, 98),
        "foreground": _c(330, 30, 15),
        "muted": _c(345, 40, 92),
        "radius": "1.5rem",
        "font_sans": "Quicksand",
        "font_display": "Fredoka",
        "mood": "playful",
    },
    "coffee": {
        "keywords": ("coffee", "cafe", "café", "espresso", "roastery", "brew", "barista"),
        "primary": _c(20, 55, 34),
        "accent": _c(38, 62, 50),
        "background": _c(30, 30, 97),
        "foreground": _c(24, 25, 12),
        "muted": _c(26, 20, 90),
        "radius": "0.5rem",
        "font_sans": "Inter",
        "font_display": "Playfair Display",
        "mood": "warm",
    },
    "restaurant": {
        "keywords": ("restaurant", "diner", "eatery", "bistro", "menu", "chef", "kitchen"),
        "primary": _c(6, 62, 44),
        "accent": _c(38, 68, 52),
        "background": _c(32, 30, 97),
        "foreground": _c(14, 25, 14),
        "muted": _c(20, 22, 90),
        "radius": "0.5rem",
        "font_sans": "Lato",
        "font_display": "Merriweather",
        "mood": "welcoming",
    },
    "fitness": {
        "keywords": ("fitness", "gym", "workout", "exercise", "training", "crossfit", "yoga"),
        "primary": _c(152, 68, 32),
        "accent": _c(200, 78, 44),
        "background": _c(160, 20, 97),
        "foreground": _c(160, 30, 11),
        "muted": _c(155, 20, 90),
        "radius": "0.375rem",
        "font_sans": "Inter",
        "font_display": "Archivo Black",
        "mood": "energetic",
    },
    "fintech": {
        "keywords": ("fintech", "banking", "bank", "investment", "trading", "wallet", "loan"),
        "primary": _c(232, 62, 52),
        "accent": _c(268, 58, 56),
        "background": _c(220, 30, 98),
        "foreground": _c(226, 40, 11),
        "muted": _c(228, 24, 92),
        "radius": "0.5rem",
        "font_sans": "Inter",
        "font_display": "Sora",
        "mood": "trustworthy",
    },
    "healthcare": {
        "keywords": (
            "healthcare",
            "clinic",
            "medical",
            "patient",
            "doctor",
            "hospital",
            "dental",
            "pharmacy",
        ),
        "primary": _c(186, 68, 34),
        "accent": _c(160, 52, 40),
        "background": _c(190, 30, 98),
        "foreground": _c(196, 32, 13),
        "muted": _c(188, 24, 92),
        "radius": "0.5rem",
        "font_sans": "Source Sans 3",
        "font_display": "Source Sans 3",
        "mood": "calm",
    },
    "gaming": {
        "keywords": ("game", "gaming", "gamer", "esports", "tournament", "arcade", "quest"),
        "primary": _c(266, 78, 55),
        "accent": _c(190, 92, 45),
        "background": _c(258, 30, 97),
        "foreground": _c(260, 40, 12),
        "muted": _c(262, 26, 90),
        "radius": "0.75rem",
        "font_sans": "Inter",
        "font_display": "Orbitron",
        "mood": "electric",
    },
    "pets": {
        "keywords": ("pet", "pets", "dog", "cat", "puppy", "kitten", "veterinary", "grooming"),
        "primary": _c(96, 52, 36),
        "accent": _c(34, 78, 52),
        "background": _c(80, 34, 97),
        "foreground": _c(90, 25, 14),
        "muted": _c(84, 24, 90),
        "radius": "1rem",
        "font_sans": "Nunito",
        "font_display": "Baloo 2",
        "mood": "friendly",
    },
    "travel": {
        "keywords": ("travel", "tour", "tourism", "trip", "booking", "itinerary", "vacation"),
        "primary": _c(196, 76, 38),
        "accent": _c(28, 84, 54),
        "background": _c(200, 34, 98),
        "foreground": _c(200, 38, 12),
        "muted": _c(198, 26, 92),
        "radius": "0.5rem",
        "font_sans": "Inter",
        "font_display": "Poppins",
        "mood": "expansive",
    },
    "beauty": {
        "keywords": ("beauty", "salon", "cosmetic", "skincare", "makeup", "spa", "nails"),
        "primary": _c(322, 52, 46),
        "accent": _c(20, 68, 56),
        "background": _c(330, 40, 98),
        "foreground": _c(320, 26, 14),
        "muted": _c(326, 30, 92),
        "radius": "1.25rem",
        "font_sans": "Jost",
        "font_display": "Cormorant Garamond",
        "mood": "refined",
    },
    "realestate": {
        "keywords": ("real estate", "property", "rental", "listing", "housing", "landlord", "broker"),
        "primary": _c(214, 44, 38),
        "accent": _c(160, 42, 36),
        "background": _c(210, 24, 98),
        "foreground": _c(212, 24, 13),
        "muted": _c(212, 18, 92),
        "radius": "0.25rem",
        "font_sans": "Inter",
        "font_display": "Libre Baskerville",
        "mood": "solid",
    },
    "education": {
        "keywords": ("education", "school", "course", "learning", "student", "tutor", "academy"),
        "primary": _c(246, 58, 52),
        "accent": _c(168, 62, 38),
        "background": _c(240, 34, 98),
        "foreground": _c(244, 34, 13),
        "muted": _c(244, 26, 92),
        "radius": "0.75rem",
        "font_sans": "Inter",
        "font_display": "Nunito Sans",
        "mood": "encouraging",
    },
    "legal": {
        "keywords": ("legal", "law", "lawyer", "attorney", "contract", "compliance", "counsel"),
        "primary": _c(200, 34, 30),
        "accent": _c(38, 42, 38),
        "background": _c(210, 18, 98),
        "foreground": _c(214, 22, 11),
        "muted": _c(212, 14, 92),
        "radius": "0.25rem",
        "font_sans": "Source Serif 4",
        "font_display": "Source Serif 4",
        "mood": "authoritative",
    },
    "fashion": {
        "keywords": ("fashion", "clothing", "apparel", "boutique", "garment", "wear", "shoe"),
        "primary": _c(354, 56, 42),
        "accent": _c(38, 42, 40),
        "background": _c(350, 26, 98),
        "foreground": _c(350, 22, 13),
        "muted": _c(352, 20, 92),
        "radius": "0.125rem",
        "font_sans": "Inter",
        "font_display": "Bodoni Moda",
        "mood": "editorial",
    },
    "agriculture": {
        "keywords": ("farm", "agriculture", "crop", "harvest", "livestock", "garden", "orchard"),
        "primary": _c(112, 42, 30),
        "accent": _c(38, 56, 48),
        "background": _c(100, 26, 97),
        "foreground": _c(110, 28, 12),
        "muted": _c(106, 20, 90),
        "radius": "0.5rem",
        "font_sans": "Work Sans",
        "font_display": "Bitter",
        "mood": "grounded",
    },
    "logistics": {
        "keywords": ("logistics", "delivery", "shipping", "fleet", "warehouse", "courier", "supply"),
        "primary": _c(226, 68, 44),
        "accent": _c(32, 72, 48),
        "background": _c(210, 22, 97),
        "foreground": _c(212, 28, 12),
        "muted": _c(211, 16, 92),
        "radius": "0.25rem",
        "font_sans": "Inter",
        "font_display": "Barlow Condensed",
        "mood": "operational",
    },
    "nonprofit": {
        "keywords": ("nonprofit", "charity", "ngo", "donation", "volunteer", "fundraising", "npo"),
        "primary": _c(168, 62, 32),
        "accent": _c(24, 74, 52),
        "background": _c(160, 30, 98),
        "foreground": _c(166, 32, 12),
        "muted": _c(164, 22, 92),
        "radius": "1rem",
        "font_sans": "Inter",
        "font_display": "Figtree",
        "mood": "hopeful",
    },
    "automotive": {
        "keywords": ("auto", "automotive", "car", "vehicle", "garage", "mechanic", "fleet service"),
        "primary": _c(4, 72, 44),
        "accent": _c(210, 30, 34),
        "background": _c(210, 14, 97),
        "foreground": _c(210, 18, 12),
        "muted": _c(210, 12, 92),
        "radius": "0.25rem",
        "font_sans": "Inter",
        "font_display": "Oswald",
        "mood": "mechanical",
    },
}

_DEFAULT_VERTICAL = "generic"


def _vertical_keywords() -> list[tuple[str, tuple[str, ...]]]:
    return [(name, tuple(pal["keywords"])) for name, pal in INDUSTRY_PALETTES.items()]


def classify_vertical(spec: AppSpec | None = None, text: str = "") -> str:
    """Score the spec's language against each vertical's keyword list.

    Deliberately keyword-based: an extra LLM call here would be both slow and
    unnecessary, since the vertical only selects a starting palette that the
    model's own proposal then overrides.
    """
    if spec is not None:
        text = " ".join(
            [
                text,
                spec.app_name,
                spec.one_liner,
                spec.core_value,
                *(e.name for e in spec.entities),
                *(e.description for e in spec.entities),
                *spec.assumptions,
            ]
        )
    lowered = text.lower()
    if not lowered.strip():
        return _DEFAULT_VERTICAL

    best_name, best_score = _DEFAULT_VERTICAL, 0
    for name, keywords in _vertical_keywords():
        score = sum(1 for k in keywords if k in lowered)
        if score > best_score:
            best_name, best_score = name, score
    return best_name


def _theme_from_palette(
    palette: dict[str, Any], *, rationale: str, mood: str = ""
) -> ThemeSpec:
    return ThemeSpec(
        primary=palette["primary"],
        background=palette["background"],
        foreground=palette["foreground"],
        accent=palette.get("accent"),
        muted=palette.get("muted"),
        radius=str(palette.get("radius", "0.5rem")),
        font_sans=str(palette.get("font_sans", "Inter")),
        font_display=str(palette.get("font_display", "Inter")),
        mood=str(mood or palette.get("mood", "")),
        rationale=rationale,
    )


def theme_from_vertical(vertical: str) -> ThemeSpec:
    """The curated palette for a named vertical (generic-neutral if unknown)."""
    palette = INDUSTRY_PALETTES.get(vertical)
    if palette is None:
        return fallback_theme(vertical)
    try:
        return _theme_from_palette(
            palette,
            rationale=(
                f"Palette from the curated '{vertical}' vertical. Unknown verticals fall "
                "back to a deterministic hash-rotated palette instead of stock shadcn blue."
            ),
        )
    except ValidationError as exc:
        # A hand-edited palette can drift out of the contrast envelope. Repairing
        # it here is better than failing a build over a design token.
        logger.warning("Palette '%s' failed validation (%s); darkening primary", vertical, exc)
        background = palette["background"]
        primary = _darken_until_contrasts(palette["primary"], background, LARGE_CONTRAST_MIN)
        repaired = dict(palette, primary=primary)
        return _theme_from_palette(
            repaired,
            rationale=f"Curated '{vertical}' palette with its primary darkened to clear WCAG AA.",
        )


def fallback_theme(seed: str, *, app_name: str = "") -> ThemeSpec:
    """Deterministic hue rotation for verticals with no curated palette.

    Two properties matter: the same seed always yields the same palette (so a
    rebuild does not restyle a live app), and different seeds land far enough
    apart on the wheel that two apps do not read as the same product.
    """
    digest = hashlib.sha256((seed or app_name or "default").encode("utf-8")).digest()
    hue = int.from_bytes(digest[:2], "big") % 360
    # Saturation/lightness are jittered too, but far less, so every rotation
    # still clears the contrast thresholds below.
    sat = 52 + (digest[2] % 24)
    light = 38 + (digest[3] % 10)
    bg_hue = (hue + (8 if digest[4] % 2 else -8)) % 360
    fg_hue = (hue + 200) % 360

    background = _c(bg_hue, 30, 97)
    foreground = _c(fg_hue, 26, 12)
    primary = _darken_until_contrasts(_c(hue, sat, light), background, LARGE_CONTRAST_MIN)

    return ThemeSpec(
        primary=primary,
        accent=_complementary(primary),
        background=background,
        foreground=foreground,
        muted=_c(bg_hue, 24, 90),
        radius="0.5rem",
        font_sans="Inter",
        font_display="Inter",
        mood="distinctive",
        rationale=(
            "Deterministic hash-rotated palette — this vertical has no curated entry, "
            "so the hue is derived from a stable hash of the app seed rather than "
            "defaulting to the template's stock blue."
        ),
    )


def theme_for_spec(text: str, spec: AppSpec | None = None, *, app_name: str = "") -> ThemeSpec:
    """Pick the theme for a spec: vertical palette, else hash-rotated fallback."""
    vertical = classify_vertical(spec, text)
    if vertical in INDUSTRY_PALETTES:
        return theme_from_vertical(vertical)
    return fallback_theme(app_name or (spec.app_name if spec else "") or vertical, app_name=app_name)


def ensure_theme(theme: ThemeSpec | None, *, seed: str) -> ThemeSpec:
    """Return a contrast-valid theme, substituting a fallback when validation fails."""
    if theme is not None:
        return theme
    return fallback_theme(seed)


def contrast_report(theme: ThemeSpec) -> dict[str, float]:
    return {
        "body": round(contrast_ratio(theme.foreground, theme.background), 2),
        "primary": round(contrast_ratio(theme.primary, theme.background), 2),
        "body_min": BODY_CONTRAST_MIN,
        "large_min": LARGE_CONTRAST_MIN,
    }


def _readable(primary: ColourModel, lightness: float) -> ColourModel:
    """Force a lightness while holding hue/saturation — used for on-primary text."""
    return ColourModel(h=primary.h, s=primary.s, l=lightness)


def _darken_until_contrasts(
    colour: ColourModel, background: ColourModel, minimum: float, floor: float = 18.0
) -> ColourModel:
    """Step lightness down in fixed increments until `colour` clears `minimum`.

    Hues differ wildly in perceived brightness — a 48%-lightness yellow reads
    far lighter than the same lightness in navy — so a single lightness range
    cannot guarantee the contrast threshold across every hue on the wheel. The
    step size is fixed (not relative) so the result stays deterministic for a
    given seed.
    """
    lightness = colour.l
    while lightness > floor and contrast_ratio(colour, background) < minimum:
        lightness -= 2.0
    return ColourModel(h=colour.h, s=colour.s, l=max(floor, lightness))


def _complementary(primary: ColourModel) -> ColourModel:
    """Rotated hue at comparable weight — the accent when a palette omits one."""
    return ColourModel(
        h=(primary.h + 180) % 360,
        s=min(90.0, primary.s * 0.85),
        l=max(35.0, min(65.0, primary.l)),
    )


def render_globals_css(theme: ThemeSpec) -> str:
    """The ``:root`` token block that replaces the stock shadcn one.

    Emitting derived chart/gradient/shadow tokens alongside the core four means
    the generated dashboard's Recharts series and the hero gradient both read
    from the same palette instead of hardcoding their own hexes.
    """
    primary = theme.primary
    background = theme.background
    foreground = theme.foreground
    accent = theme.accent or _complementary(primary)
    muted = theme.muted or ColourModel(h=background.h, s=22, l=92)
    ring = theme.ring or primary

    # On-primary text is white or near-black, whichever actually contrasts.
    on_primary = _c(0, 0, 98)
    if contrast_ratio(on_primary, primary) < BODY_CONTRAST_MIN:
        on_primary = _c(primary.h, 24, 10)

    # Series colours walk the wheel in golden-angle steps so adjacent series
    # stay separable without any of them colliding with the primary.
    series: list[ColourModel] = []
    base = primary.h
    for i in range(5):
        hue = (base + i * 137.508) % 360
        series.append(
            ColourModel(
                h=hue,
                s=min(88.0, max(45.0, primary.s)),
                l=min(62.0, max(38.0, primary.l)),
            )
        )

    tokens: list[tuple[str, ColourModel]] = [
        ("primary", primary),
        ("primary-foreground", on_primary),
        ("secondary", muted),
        ("secondary-foreground", foreground),
        ("muted", muted),
        ("muted-foreground", _readable(muted, 38)),
        ("accent", accent),
        ("accent-foreground", _readable(accent, 96 if accent.l > 50 else 98)),
        ("background", background),
        ("foreground", foreground),
        ("card", ColourModel(h=background.h, s=16, l=99)),
        ("card-foreground", foreground),
        ("popover", ColourModel(h=background.h, s=16, l=99)),
        ("popover-foreground", foreground),
        ("ring", ring),
    ]
    for idx, colour in enumerate(series, start=1):
        tokens.append((f"chart-{idx}", colour))

    lines = [
        ":root {",
        "  /* Domain theme — generated by ai-solution-builder. Do not hand-edit;",
        "     re-run codegen or edit theme in spec.json instead. */",
    ]
    for name, colour in tokens:
        lines.append(f"  --{name}: {colour.css()};")
    lines += [
        f"  --radius: {theme.radius};",
        f"  --font-sans: {theme.font_sans}, ui-sans-serif, system-ui, sans-serif;",
        f"  --font-display: {theme.font_display}, ui-serif, Georgia, serif;",
        f"  --gradient-hero: linear-gradient(135deg, {primary.css()} 0%, {accent.css()} 100%);",
        "  --shadow-color: " f"{primary.css()};",
        "  --chart-1: " f"{series[0].css()};",
        "}",
    ]
    return "\n".join(lines)


_TOKEN_BLOCK_RE = re.compile(r":root\s*\{.*?\n\}", re.S)


def patch_globals_css(css: str, theme: ThemeSpec) -> str:
    """Replace the first ``:root`` token block, or prepend one if absent."""
    block = render_globals_css(theme)
    if _TOKEN_BLOCK_RE.search(css):
        return _TOKEN_BLOCK_RE.sub(lambda _m: block, css, count=1)
    return block + "\n\n" + css


def _patch_font_vars(text: str, theme: ThemeSpec) -> str:
    """Point the CSS custom properties the layout reads at the theme fonts."""
    return re.sub(
        r"(--font-sans:\s*)[^;]+;",
        lambda m: f"{m.group(1)}{theme.font_sans}, ui-sans-serif, system-ui, sans-serif;",
        text,
    )


def _patch_tailwind_font(text: str, theme: ThemeSpec) -> str:
    """Rewrite the `fontFamily.sans`/`fontFamily.display` entries."""
    text = re.sub(
        r"(fontFamily\s*:\s*\{[^}]*?sans\s*:\s*)\[[^\]]*\]",
        lambda m: f'{m.group(1)}["{theme.font_sans}", "ui-sans-serif", "system-ui"]',
        text,
        count=1,
    )
    if "display" in text:
        text = re.sub(
            r"(fontFamily\s*:\s*\{[^}]*?display\s*:\s*)\[[^\]]*\]",
            lambda m: f'{m.group(1)}["{theme.font_display}", "ui-serif", "Georgia"]',
            text,
            count=1,
        )
    return text


_THEME_TS = """// Domain theme — generated by ai-solution-builder from spec.json.
// Import from here instead of hardcoding colours so light/dark mode both work.
export const theme = {theme};

export const chartColors = {charts};

/** Public URL for a sourced asset, e.g. assets/menu_items/1.jpg */
export function assetUrl(path: string): string {{
  if (!path) return '';
  return path.startsWith('/') ? path : `/assets/${{path}}`;
}}
"""


def _theme_ts_body(theme: ThemeSpec) -> tuple[str, str]:
    serialised = (
        "{\n"
        + ",\n".join(f'  {name}: "{colour.css()}"' for name, colour in theme.tokens().items())
        + ",\n"
        + f'  radius: "{theme.radius}",\n'
        + f'  fontSans: "{theme.font_sans}",\n'
        + f'  fontDisplay: "{theme.font_display}"\n'
        + "}"
    )
    chart_colours: list[ColourModel] = []
    for idx in range(1, 6):
        hue = (theme.primary.h + (idx - 1) * 137.508) % 360
        chart_colours.append(
            ColourModel(
                h=hue,
                s=min(88.0, max(45.0, theme.primary.s)),
                l=min(62.0, max(38.0, theme.primary.l)),
            )
        )
    charts = "[\n  " + ",\n  ".join(f'"hsl({c.css()})"' for c in chart_colours) + ",\n]"
    return serialised, charts


def apply_theme(fe_dir: Path | str, theme: ThemeSpec) -> dict[str, Any]:
    """Patch every place the theme lives in a scaffolded frontend.

    Returns a report of what was actually touched, because a missing file is
    normal (an older scaffold may have no tailwind.config.ts) and must not be
    treated as a failure.
    """
    fe = Path(fe_dir)
    applied: dict[str, Any] = {"globals_css": False, "layout": False, "tailwind": False, "theme_ts": False}

    globals_css = fe / "src" / "app" / "globals.css"
    if globals_css.is_file():
        try:
            patched = patch_globals_css(
                globals_css.read_text(encoding="utf-8"), theme
            )
            globals_css.write_text(patched, encoding="utf-8")
            applied["globals_css"] = True
        except OSError as exc:
            logger.warning("Could not patch %s: %s", globals_css, exc)

    layout = fe / "src" / "app" / "layout.tsx"
    if layout.is_file():
        try:
            src = layout.read_text(encoding="utf-8")
            patched = _patch_font_vars(src, theme)
            if patched != src:
                layout.write_text(patched, encoding="utf-8")
                applied["layout"] = True
        except OSError as exc:
            logger.warning("Could not patch %s: %s", layout, exc)

    tailwind = fe / "tailwind.config.ts"
    if not tailwind.is_file():
        tailwind = fe / "tailwind.config.js"
    if tailwind.is_file():
        try:
            src = tailwind.read_text(encoding="utf-8")
            patched = _patch_tailwind_font(src, theme)
            if patched != src:
                tailwind.write_text(patched, encoding="utf-8")
                applied["tailwind"] = True
        except OSError as exc:
            logger.warning("Could not patch %s: %s", tailwind, exc)

    lib_dir = fe / "src" / "lib"
    try:
        lib_dir.mkdir(parents=True, exist_ok=True)
        serialised, charts = _theme_ts_body(theme)
        (lib_dir / "theme.ts").write_text(
            _THEME_TS.format(theme=serialised, charts=charts), encoding="utf-8"
        )
        applied["theme_ts"] = True
    except OSError as exc:
        logger.warning("Could not write theme.ts: %s", exc)

    logger.info(
        "Applied theme (primary=%s) to %s: %s",
        theme.primary.css(),
        fe,
        {k: v for k, v in applied.items() if v},
    )
    return applied


# The stock shadcn primary this engine exists to replace. The quality gate
# reports `theme_unused` while a build still carries it.
STOCK_SHADCN_PRIMARY = "221.2 83.2% 53.3%"


def has_stock_palette(fe_dir: Path | str) -> bool:
    """True while ``globals.css`` still holds the unvaried template palette."""
    globals_css = Path(fe_dir) / "src" / "app" / "globals.css"
    if not globals_css.is_file():
        return False
    try:
        return STOCK_SHADCN_PRIMARY in globals_css.read_text(encoding="utf-8")
    except OSError:
        return False