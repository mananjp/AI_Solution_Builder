"""
AI Solution Builder — AppSpec (single source of truth for MVP builds)

Replaces keyword/regex domain guessing. The LLM produces ONE validated,
app-specific spec: entities, business *actions* (the logic that makes the app
more than CRUD), screens, and executable acceptance tests. Deterministic code
generates plumbing + tests from it; the coding agent only implements actions/UI.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

logger = logging.getLogger(__name__)

_SNAKE = re.compile(r"^[a-z][a-z0-9_]{0,40}$")
FieldType = Literal["string", "text", "int", "float", "bool", "date", "datetime", "enum", "ref"]
RESERVED = {"id", "created_at", "updated_at", "metadata", "type", "class", "def", "from", "import"}


class SpecError(ValueError):
    """Spec failed validation after all repair attempts."""


class SpecField(BaseModel):
    name: str
    type: FieldType
    required: bool = True
    enum_values: list[str] = Field(default_factory=list)
    ref: str | None = None  # target entity name when type == "ref"
    default: Any = None
    description: str = ""

    @field_validator("name", mode="before")
    @classmethod
    def _name(cls, v: Any) -> str:
        clean = re.sub(r"[^a-zA-Z0-9_]+", "_", str(v)).strip("_").lower()
        if clean in RESERVED:
            clean = f"{clean}_val"
        return clean or "field"

    @model_validator(mode="after")
    def _consistency(self) -> SpecField:
        if self.type == "enum" and len(self.enum_values) < 2:
            raise ValueError(f"enum field '{self.name}' needs >=2 enum_values")
        if self.type == "ref" and not self.ref:
            raise ValueError(f"ref field '{self.name}' needs 'ref'")
        if self.type == "ref" and not self.name.endswith("_id"):
            raise ValueError(f"ref field '{self.name}' must end with _id")
        return self


class Entity(BaseModel):
    name: str  # singular snake_case, e.g. "expense"
    plural: str  # URL segment, e.g. "expenses"
    description: str = ""
    fields: list[SpecField] = Field(min_length=1, max_length=15)

    @field_validator("name", "plural", mode="before")
    @classmethod
    def _snake(cls, v: Any) -> str:
        clean = re.sub(r"[^a-zA-Z0-9_]+", "_", str(v)).strip("_").lower()
        if clean in RESERVED:
            clean = f"{clean}_rec"
        return clean or "entity"


class Action(BaseModel):
    """Business operation beyond CRUD, e.g. settle_balances, book_slot, checkout."""

    name: str
    method: Literal["GET", "POST"] = "POST"
    path: str  # must start with /actions/
    summary: str
    input_fields: list[SpecField] = Field(default_factory=list)
    rules: list[str] = Field(
        min_length=1, description="Precise business rules / formulas / validations"
    )
    output_example: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name", mode="before")
    @classmethod
    def _name(cls, v: Any) -> str:
        clean = re.sub(r"[^a-zA-Z0-9_]+", "_", str(v)).strip("_").lower()
        if clean and clean[0].isdigit():
            clean = f"act_{clean}"
        return clean or "action"

    @field_validator("path", mode="before")
    @classmethod
    def _path(cls, v: Any) -> str:
        s = str(v).strip()
        cleaned = re.sub(r"\s+", "_", s)
        if not cleaned.startswith("/actions/"):
            cleaned = "/actions/" + cleaned.lstrip("/")
        return cleaned


class Screen(BaseModel):
    name: str
    route: str  # Next.js route, "/" allowed
    purpose: str
    uses_entities: list[str] = Field(default_factory=list)
    uses_actions: list[str] = Field(default_factory=list)
    key_interactions: list[str] = Field(min_length=1)

    @field_validator("uses_actions", mode="before")
    @classmethod
    def _actions(cls, v: Any) -> list[str]:
        if not isinstance(v, list):
            return []
        return [re.sub(r"[^a-zA-Z0-9_]+", "_", str(a)).strip("_").lower() for a in v]

    @field_validator("uses_entities", mode="before")
    @classmethod
    def _entities(cls, v: Any) -> list[str]:
        if not isinstance(v, list):
            return []
        return [re.sub(r"[^a-zA-Z0-9_]+", "_", str(e)).strip("_").lower() for e in v]


class TestStep(BaseModel):
    method: Literal["GET", "POST", "PATCH", "DELETE"]
    path: str  # may contain {var} saved by earlier steps
    body: dict[str, Any] | None = None
    expect_status: int = 200
    expect: dict[str, Any] = Field(default_factory=dict)  # subset match; dotted keys allowed
    save: dict[str, str] = Field(default_factory=dict)  # var -> dotted key in response

    @field_validator("path", mode="before")
    @classmethod
    def _path(cls, v: Any) -> str:
        return re.sub(r"\s+", "_", str(v).strip())


class AcceptanceTest(BaseModel):
    name: str
    description: str
    steps: list[TestStep] = Field(min_length=1, max_length=15)

    @field_validator("name", mode="before")
    @classmethod
    def _n(cls, v: Any) -> str:
        return re.sub(r"[^a-z0-9_]+", "_", str(v).lower()).strip("_")[:60] or "scenario"


ML_KEYWORDS: dict[str, str] = {
    "pytorch": "PyTorch",
    "torch": "PyTorch",
    "torchvision": "PyTorch",
    "tensorflow": "TensorFlow",
    "keras": "Keras",
    "jax": "JAX",
    "scikit-learn": "scikit-learn",
    "sklearn": "scikit-learn",
    "xgboost": "XGBoost",
    "lightgbm": "LightGBM",
    "catboost": "CatBoost",
    "huggingface": "HuggingFace",
    "transformers": "Transformers",
    "opencv": "OpenCV",
    "cv2": "OpenCV",
    "spacy": "spaCy",
    "nltk": "NLTK",
    "yolo": "YOLO",
    "machine learning": "Machine Learning",
    "deep learning": "Deep Learning",
    "neural network": "Neural Network",
    "model training": "Model Training",
    "train model": "Model Training",
    "object detection": "Object Detection",
    "image classification": "Image Classification",
    "sentiment model": "Sentiment Model",
    "recommendation engine": "Recommendation Engine",
    "vector embeddings": "Vector Embeddings",
    "random forest": "Random Forest",
    "clustering": "Clustering",
    "anomaly detection": "Anomaly Detection",
    "pandas": "Pandas",
    "scipy": "SciPy",
}


def detect_ml_requirements(data: Any) -> tuple[bool, list[str]]:
    """Scan text, dictionary, or spec for machine learning and data science requirements."""
    if isinstance(data, dict):
        text = " ".join(str(v) for v in data.values())
    elif isinstance(data, str):
        text = data
    elif hasattr(data, "model_dump"):
        text = json.dumps(data.model_dump())
    else:
        text = str(data)

    text_lower = text.lower()
    found: list[str] = []
    for kw, label in ML_KEYWORDS.items():
        if re.search(r"\b" + re.escape(kw) + r"\b", text_lower) and label not in found:
            found.append(label)

    return len(found) > 0, found


# ── AppSpec v2: growth curve, theming, seeding ───────────────────────────
#
# v1 forced a single shape on every build ("3-6 entities, a screen per
# entity"), which made a one-page landing site and an operating dashboard the
# same app. v2 adds two orthogonal axes instead:
#
#   app_kind        what it is    (landing / catalog / dashboard / …)
#   lifecycle_stage how far it goes (showcase -> transact -> operate)
#
# The invariant is that the *backend is always generated*. A `showcase` build
# still gets its entities, typed CRUD, seed data and acceptance tests — the
# landing page simply reads them. Adding a cart later is purely additive, so
# the growth path never requires a re-scaffold. See docs/adr/0003.

AppKind = Literal[
    "landing",
    "catalog",
    "dashboard",
    "booking",
    "marketplace",
    "tool",
    "portfolio",
    "social",
    "internal",
]

LifecycleStage = Literal["showcase", "transact", "operate"]

DataLayer = Literal["api", "static"]

# Weakest → strongest. A spec claiming a stronger stage than its kind can
# support is a contradiction, not a stretch goal, so it is a hard error.
STAGE_ORDER: dict[str, int] = {"showcase": 0, "transact": 1, "operate": 2}

# Kinds whose entire value proposition is visual. Used by the quality gate to
# decide whether "no images anywhere" is a finding or a non-issue.
VISUAL_APP_KINDS: frozenset[str] = frozenset(
    {"landing", "catalog", "portfolio", "marketplace"}
)


class ColourModel(BaseModel):
    """An HSL colour, matching the Tailwind token form ``H S% L%``.

    Stored as HSL rather than hex because that is exactly the shape the
    generated ``globals.css`` tokens already use (``--primary: 221.2 83.2%
    53.3%``), so theming is a token rewrite and not a colour-space conversion.
    """

    h: float = Field(ge=0, le=360, description="Hue 0-360")
    s: float = Field(ge=0, le=100, description="Saturation percent")
    l: float = Field(ge=0, le=100, description="Lightness percent")

    @model_validator(mode="after")
    def _normalise(self) -> ColourModel:
        # Hue wraps; saturation/lightness clamp. An out-of-range palette that
        # silently becomes black-on-black is worse than a hard validation error.
        object.__setattr__(self, "h", self.h % 360)
        object.__setattr__(self, "s", min(100.0, max(0.0, self.s)))
        object.__setattr__(self, "l", min(100.0, max(0.0, self.l)))
        return self

    def css(self) -> str:
        """Render as a Tailwind HSL token body (``217.2 91.2% 59.8%``)."""
        return f"{self.h:.1f} {self.s:.1f}% {self.l:.1f}%"

    def hex(self) -> str:
        r, g, b = self._rgb255()
        return f"#{r:02x}{g:02x}{b:02x}"

    def _rgb255(self) -> tuple[int, int, int]:
        h = self.h / 360.0
        s = self.s / 100.0
        lightness = self.l / 100.0
        c = (1 - abs(2 * lightness - 1)) * s
        x = c * (1 - abs(((h * 6) % 2) - 1))
        m = lightness - c / 2
        sector = int(h * 6) % 6
        r, g, b = (
            (c, x, 0.0),
            (x, c, 0.0),
            (0.0, c, x),
            (0.0, x, c),
            (x, 0.0, c),
            (c, 0.0, x),
        )[sector]
        return (
            round((r + m) * 255),
            round((g + m) * 255),
            round((b + m) * 255),
        )

    def luminance(self) -> float:
        """WCAG relative luminance."""
        channels = []
        for raw in self._rgb255():
            channel = raw / 255
            channels.append(
                channel / 12.92
                if channel <= 0.03928
                else ((channel + 0.055) / 1.055) ** 2.4
            )
        r, g, b = channels
        return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: ColourModel, b: ColourModel) -> float:
    """WCAG 2.1 contrast ratio between two colours (1.0 … 21.0)."""
    la, lb = a.luminance(), b.luminance()
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


# WCAG 2.1 AA. Body text is the strict threshold; large text and UI borders
# (which is what a `primary` token mostly paints) get the relaxed one.
BODY_CONTRAST_MIN = 4.5
LARGE_CONTRAST_MIN = 3.0


class ThemeSpec(BaseModel):
    """Domain-derived design tokens.

    The v1 palette was a hardcoded shadcn blue that every generated app
    inherited verbatim. This is the colour system that replaces it, and it is
    contrast-checked at validation time so a bad proposal can never ship.
    """

    primary: ColourModel
    background: ColourModel
    foreground: ColourModel
    accent: ColourModel | None = None
    muted: ColourModel | None = None
    ring: ColourModel | None = None
    radius: str = "0.5rem"
    font_sans: str = "Inter"
    font_display: str = "Inter"
    mood: str = Field(default="", description="One-word feel, e.g. 'artisan', 'clinical'")
    rationale: str = Field(default="", description="Why these tokens suit this domain")

    @model_validator(mode="after")
    def _contrast(self) -> ThemeSpec:
        body = contrast_ratio(self.foreground, self.background)
        if body < BODY_CONTRAST_MIN:
            raise ValueError(
                f"theme body contrast {body:.2f}:1 is below WCAG AA {BODY_CONTRAST_MIN}:1 "
                f"(foreground {self.foreground.hex()} on background {self.background.hex()})"
            )
        large = contrast_ratio(self.primary, self.background)
        if large < LARGE_CONTRAST_MIN:
            raise ValueError(
                f"theme primary contrast {large:.2f}:1 is below WCAG AA "
                f"{LARGE_CONTRAST_MIN}:1 for large text and UI borders "
                f"(primary {self.primary.hex()} on background {self.background.hex()})"
            )
        return self

    def tokens(self) -> dict[str, ColourModel]:
        """The full token map, with sensible derivations for the optional roles."""
        out: dict[str, ColourModel] = {
            "primary": self.primary,
            "background": self.background,
            "foreground": self.foreground,
        }
        if self.accent is not None:
            out["accent"] = self.accent
        if self.muted is not None:
            out["muted"] = self.muted
        if self.ring is not None:
            out["ring"] = self.ring
        return out


class AnalyticsModule(BaseModel):
    """Opt-in business analytics.

    Defaults to *off*. v1 shipped the analytics router unconditionally, so an
    ice-cream landing page with three items got a revenue dashboard off the
    back of a `quantity` column. See docs/adr/0004.
    """

    enabled: bool = False
    entity: str | None = Field(
        default=None, description="Entity to aggregate; must exist and carry the metric"
    )
    primary_metric_field: str | None = Field(
        default=None, description="Numeric field to sum; must be int/float on `entity`"
    )
    views: list[Literal["kpi", "trend", "breakdown"]] = Field(default_factory=lambda: ["kpi"])
    rationale: str = Field(default="", description="Why analytics is (not) warranted here")


class SeedRecord(BaseModel):
    """Concrete starting data the generated app ships with.

    This is where "three items and their prices" lands — the prompt's open
    questions resolved into verbatim values rather than invented placeholders.
    """

    entity: str = Field(description="Entity name this record belongs to")
    values: dict[str, Any] = Field(default_factory=dict)
    label: str = Field(default="", description="Short human label, e.g. 'Vanilla scoop'")


class AppSpec(BaseModel):
    app_name: str
    one_liner: str
    core_value: str = Field(description="What the app DOES that plain CRUD would not")
    assumptions: list[str] = Field(default_factory=list)
    entities: list[Entity] = Field(min_length=1, max_length=6)
    actions: list[Action] = Field(default_factory=list, max_length=8)
    screens: list[Screen] = Field(min_length=1, max_length=6)
    acceptance_tests: list[AcceptanceTest] = Field(min_length=3, max_length=10)
    architecture: Literal["next_fullstack", "unified_container"] = "next_fullstack"
    has_ml_model: bool = False
    ml_frameworks: list[str] = Field(default_factory=list)

    # ── v2 growth curve ──
    app_kind: AppKind = Field(
        default="internal",
        description="What the app IS — drives page shape and which surface `/` gets",
    )
    lifecycle_stage: LifecycleStage = Field(
        default="operate",
        description="How far it goes: showcase (browse) → transact (buy/book) → operate (admin)",
    )
    # Defaults to "api" precisely so v1 → v2 stays additive: a showcase build
    # already has the real backend that the later transact stage reuses.
    data_layer: DataLayer = "api"

    # ── v2 theming / modules / data ──
    theme: ThemeSpec | None = None
    analytics: AnalyticsModule = Field(default_factory=AnalyticsModule)
    seed_data: list[SeedRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def _growth_curve(self) -> AppSpec:
        names = {e.name for e in self.entities}
        errors: list[str] = []

        # A landing page with an operating console is a contradiction: there is
        # no admin surface to build against a one-page app.
        if self.app_kind == "landing" and STAGE_ORDER[self.lifecycle_stage] > STAGE_ORDER["transact"]:
            errors.append(
                f"app_kind 'landing' cannot use lifecycle_stage '{self.lifecycle_stage}' "
                "(max 'transact')"
            )

        for record in self.seed_data:
            if record.entity not in names:
                errors.append(f"seed_data references unknown entity '{record.entity}'")

        for record in self.seed_data:
            entity = next((e for e in self.entities if e.name == record.entity), None)
            if entity is None:
                continue
            field_names = {f.name for f in entity.fields}
            unknown = set(record.values) - field_names
            if unknown:
                errors.append(
                    f"seed_data for '{record.entity}' sets unknown field(s): "
                    + ", ".join(sorted(unknown))
                )

        if self.analytics.enabled and self.analytics.entity and self.analytics.entity not in names:
            errors.append(
                f"analytics.entity '{self.analytics.entity}' is not a spec entity"
            )

        if errors:
            raise ValueError("; ".join(errors))
        return self

    @model_validator(mode="after")
    def _cross_refs(self) -> AppSpec:
        if not self.has_ml_model and not self.ml_frameworks:
            has_ml, frameworks = detect_ml_requirements(self)
            if has_ml:
                self.has_ml_model = True
                self.ml_frameworks = frameworks
                self.architecture = "unified_container"
        names = {e.name for e in self.entities}
        plurals = {e.plural for e in self.entities}
        errors: list[str] = []
        if len(names) != len(self.entities) or len(plurals) != len(self.entities):
            errors.append("duplicate entity name/plural")
        for e in self.entities:
            for f in e.fields:
                if f.type == "ref" and f.ref not in names:
                    errors.append(f"{e.name}.{f.name} refs unknown entity '{f.ref}'")
        action_patterns = {
            a.path: re.compile("^" + re.sub(r"\\\{\w+\\\}", "[^/]+", re.escape(a.path)) + "$")
            for a in self.actions
        }
        action_paths = set(action_patterns)
        action_names = {a.name for a in self.actions}
        for s in self.screens:
            for a in s.uses_actions:
                if a not in action_names:
                    errors.append(f"screen '{s.name}' uses unknown action '{a}'")
        valid_prefixes = tuple(f"/{p}" for p in plurals) + ("/actions/",)
        exercised_actions = set()
        for t in self.acceptance_tests:
            for st in t.steps:
                base = st.path.split("?")[0]
                if not base.startswith(valid_prefixes):
                    errors.append(f"test '{t.name}' hits unknown path '{st.path}'")
                for ap, rx in action_patterns.items():
                    if rx.match(base):
                        exercised_actions.add(ap)
        missing = action_paths - exercised_actions
        if missing:
            # Auto-supplement missing action acceptance tests so validation never fails
            for act in self.actions:
                if act.path in missing:
                    self.acceptance_tests.append(
                        AcceptanceTest(
                            name=f"test_{act.name}",
                            description=f"Exercises action {act.name}",
                            steps=[
                                TestStep(
                                    method=act.method,
                                    path=act.path,
                                    body={f.name: "test" for f in act.input_fields}
                                    if act.method == "POST"
                                    else None,
                                    expect_status=200,
                                )
                            ],
                        )
                    )
        if errors:
            raise ValueError("; ".join(errors))
        return self


# ── LLM generation ──────────────────────────────────────────────────────

SPEC_SYSTEM = """You design rich, production-grade working apps. Output ONLY JSON matching the schema.

Hard rules:
- Model the user's ACTUAL domain. Never default to a generic 'items/status' CRUD or todo app, and never substitute a different industry's entities (an employee/HR request must not become products/orders).

Growth curve — decide these FIRST, they shape everything else:
- `app_kind` (what the app IS): landing | catalog | dashboard | booking | marketplace | tool | portfolio | social | internal
- `lifecycle_stage` (how far it goes):
    * "showcase" — browse only. Names, photos, prices, categories. No cart, no checkout, no admin.
    * "transact" — the user commits. Cart + order, booking + slot, checkout + payment.
    * "operate" — the business runs on it. Admin, staff views, reporting.
  The backend is ALWAYS generated: a "showcase" build still gets real entities, typed CRUD,
  seed data and acceptance tests — the landing page simply reads them. Adding a cart later is
  purely additive, so scope the FIRST version honestly rather than padding it. A one-page
  ice-cream vendor is app_kind="landing", lifecycle_stage="showcase", exactly ONE entity, and
  3 seed_data records. "landing" may not use lifecycle_stage="operate".
- `analytics.enabled` is FALSE by default. Turn it on ONLY for a real business with something
  to measure, and then you MUST name a real numeric metric on a real entity
  (`analytics.entity` + `analytics.primary_metric_field`). Never enable it just because some
  column happens to be numeric.
- `seed_data` is where the user's concrete content goes — the actual item names, the actual
  prices. If the user named specific things, use those verbatim; never invent placeholders
  like "Item 1" or "Product A".

Entities and surface area:
- As many entities as the stage genuinely needs (1 for a landing page, up to 6 for an
  operating app), with real attributes each. Do not pad with placeholder fields like
  "name"/"title"/"status" when a real attribute is obvious.
- If the user asks for a landing page, portfolio, or showcase website, model realistic
  entities (e.g. leads, inquiries, contact_messages, subscribers, testimonials) and actions
  (e.g. /actions/submit_inquiry, /actions/subscribe_newsletter) with appropriate screens
  (e.g. Landing Page at "/", Admin/Inquiries at "/inquiries").
- Put the real logic in `actions` (calculations, state transitions, validation, conflict
  checks, aggregation). Each action has precise `rules` a developer can implement
  without guessing (formulas, edge cases, error codes: 400 invalid, 404 missing, 409 conflict).
- If the app is genuinely pure CRUD, actions may be empty, but core_value must say so.
- Entities: 1-6, sized to the lifecycle stage. Fields snake_case; refs are `<entity>_id` with type "ref".
- REST conventions that ALREADY exist for every entity (do not list them as actions):
  GET/POST /{plural}, GET/PATCH/DELETE /{plural}/{id}, GET /{plural}?<ref_field>=<id>.
  IDs are integers. Responses of CRUD = the object JSON (with "id").
- acceptance_tests: 3-10 scenarios that PROVE the core value end-to-end via HTTP.
  Use `save` to capture ids, e.g. {"group_id": "id"}, then use "{group_id}" in later paths/bodies.
  Every action must be exercised by at least one test with a concrete numeric/string `expect`.
  Include at least one negative test (400/404/409).
- Build the FULL app the user described, at the stage you declared. A high-end result has real
  entities with real attributes, a screen per entity, and domain actions wired to acceptance tests.

Theme (`theme`) — required, and it is what stops every app looking identical:
- Propose a `theme` in HSL: `primary`, `background`, `foreground` (and optionally `accent`,
  `muted`, `ring`) as objects {"h": 0-360, "s": 0-100, "l": 0-100}.
- These tokens REPLACE the template's stock blue in globals.css, so pick colours that actually
  suit the industry. Ice cream is warm cream/coral, not SaaS blue; a clinic is calm teal; a
  fintech is deep indigo. Two apps in different industries must not share a primary hue.
- Constraints are enforced and your spec is REJECTED if you break them: foreground on background
  must reach 4.5:1 contrast (body text) and primary on background at least 3:1 (large text and
  borders). Aim comfortably above: light neutral backgrounds (l 94-99) with dark foregrounds
  (l 8-20) and a saturated primary (s 55-90, l 35-50) all pass easily.
- Also set `radius` (e.g. "0.25rem" for clinical precision, "1rem" for friendly), `font_sans`,
  `font_display`, a one-word `mood`, and a `rationale` sentence.

UI quality (the generated frontend is judged on this):
- A shadcn/ui component library is PREINSTALLED and ready to import from "@/components/ui/<name>": alert, badge, button, card (Card/CardHeader/CardTitle/CardDescription/CardContent/CardFooter), checkbox, dialog, dropdown-menu, input, label, select, separator, skeleton, sonner (toasts), switch, table (Table/TableHeader/TableBody/TableRow/TableHead/TableCell), tabs, textarea. Also available: lucide-react icons, framer-motion, react-hook-form, zod, and Tailwind design tokens (bg-background, bg-card, bg-muted, text-muted-foreground, bg-primary, bg-destructive, border-border, rounded-lg/md/sm). `recharts` is only installed when `analytics.enabled` is true.
- Build screens by COMPOSING those premade components. A page assembled from Card + Table + Button + Badge + Input reads as a finished product; the same page hand-rolled from raw <div> elements reads as a wireframe. Do not re-implement a button, card, table, badge, input, modal or toast that already exists.
- If you genuinely need a component that is NOT preinstalled, install it rather than hand-rolling it: run `npx shadcn@latest add <name> --yes` from the `frontend` directory (e.g. `npx shadcn@latest add accordion --yes`). The project is already configured for shadcn (components.json, "@/components/ui" alias, design tokens), so the CLI drops the component in with correct imports and theme support. Common useful additions: accordion, avatar, calendar, chart, command, drawer, form, hover-card, popover, progress, radio-group, scroll-area, slider, tooltip, carousel, pagination, breadcrumb, collapsible, aspect-ratio, alert-dialog. Never invent an import path under "@/components/ui" for a component you did not install. If installing is not possible in your environment, fall back to composing the preinstalled set plus a small local component - never block the build and never leave a dangling import.
- The premade components are yours to PERSONALISE. Tweak them for the app's look - pass className, adjust variants, restyle via the Tailwind tokens - so the UI feels designed for this product rather than default-library. Prefer composing and passing className over forking a component file; only edit a component in "@/components/ui" when the app genuinely needs a new variant that composition cannot express, and keep every existing export intact so other screens keep working.
- Every screen must be responsive, mobile-first, correct at 375px: stack cards, or use an overflow-x-auto table wrapper and hide secondary columns on small screens. Never ship a desktop-only grid that overflows horizontally.
- Give every list screen real affordances: a search/filter input, a proper empty state, loading skeletons while fetching, and a create/edit form with validation - not a bare JSON dump.
- Reference images that already exist at `/assets/...` (real photo files land there before you write code). NEVER hotlink an external image URL.
- Use lucide-react icons for navigation and primary actions, keep the type scale and spacing consistent, and do not hardcode one-off hex colours - use the design tokens so light and dark mode both work.
- core_value must be a concrete sentence about what the app does beyond CRUD - never leave it empty."""


def _spec_schema_hint() -> str:
    # A compact hand-written shape instead of a JSON Schema dump. The dump was
    # ~1500 prompt tokens of mostly-optional metadata, and under Groq's 8000
    # TPM ceiling that left too little budget for the completion — responses came
    # back `finish_reason: length` with truncated JSON, and when they did parse
    # the model omitted the buried required scalars (`app_name`, `one_liner`).
    # Listing only what must be present makes the contract explicit and cheap.
    return (
        'Required shape:\n'
        '{"app_name": str, "one_liner": str, "core_value": str, '
        '"entities": [{"name": str, "plural": str, "description": str, '
        '"fields": [{"name": str, "type": "string|text|int|float|bool|date|datetime|enum|ref", '
        '"required": true, "description": str, "ref": str?}]}], '
        '"screens": [{"name": str, "route": str, "purpose": str, '
        '"uses_entities": [str], "uses_actions": [str], "key_interactions": [str]}], '
        '"actions": [{"name": str, "method": "GET|POST", "path": "/actions/<name>", '
        '"summary": str, "input_fields": [<field>], "rules": [str], '
        '"output_example": {}}], '
        '"acceptance_tests": [{"name": str, "description": str, '
        '"steps": [{"method": "GET|POST|PATCH|DELETE", "path": str, "body": {}, '
        '"expect_status": 200, "expect": {}, "save": {}}]}]}\n'
        "Required scalars: app_name, one_liner, core_value.\n"
        "Bounded: 1-6 entities, 1-6 screens, 3-10 acceptance_tests, 0-8 actions.\n"
        "Entity field types may only be: string, text, int, float, bool, date, "
        "datetime, enum, ref.\n"
        "An `enum` field MUST include >=2 `enum_values`; a `ref` field MUST include "
        "`ref` set to a valid entity name and a name ending in `_id`."
    )


def _extract_json(text: str) -> dict[str, Any]:
    t = text.strip()
    if "```" in t:
        m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", t, re.S)
        if m:
            t = m.group(1)
    start, end = t.find("{"), t.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("no JSON object in response")
    return _repair_spec_dict(_loads_lenient(t[start : end + 1]))  # type: ignore[no-any-return]


def _loads_lenient(raw: str) -> dict[str, Any]:
    """Parse JSON, salvaging output truncated by ``finish_reason: length``.

    The spec call budgets 5000 tokens, and a reasoning model spends ~900 of them
    before writing a byte, so the model still runs out mid-object. That produced
    `Unterminated string` on every attempt and silently degraded the build to the
    deterministic stub. Dropping back to the last complete value and closing the
    open containers recovers a usable — if shorter — spec from what did arrive.
    """
    try:
        return json.loads(raw)  # type: ignore[no-any-return]
    except (json.JSONDecodeError, ValueError):
        pass

    # Trim to the last character that can end a value.
    cut = len(raw)
    while cut > 1 and raw[cut - 1] not in '}],"0123456789truefalsnl':
        cut -= 1
    fragment = raw[:cut]

    # Re-close what the truncation left open: strings first, then containers,
    # tracked in order so the result is well-formed.
    open_stack: list[str] = []
    in_string = False
    escaped = False
    for ch in fragment:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "{[":
            open_stack.append("}" if ch == "{" else "]")
        elif ch in "}]" and open_stack:
            open_stack.pop()

    repaired = fragment
    if in_string:
        repaired += '"'
    repaired += "".join(reversed(open_stack))

    try:
        return json.loads(repaired)  # type: ignore[no-any-return]
    except (json.JSONDecodeError, ValueError):
        pass

    # Last resort: walk backwards until the containers balance, dropping the
    # half-written value that truncation left behind.
    for i in range(len(fragment) - 1, max(len(fragment) - 600, 0), -1):
        candidate = fragment[: i + 1].rstrip().rstrip(",")
        stack: list[str] = []
        instr = esc = False
        for ch in candidate:
            if instr:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    instr = False
                continue
            if ch == '"':
                instr = True
            elif ch in "{[":
                stack.append("}" if ch == "{" else "]")
            elif ch in "}]" and stack:
                stack.pop()
        if instr:
            candidate += '"'
        candidate += "".join(reversed(stack))
        try:
            return json.loads(candidate)  # type: ignore[no-any-return]
        except (json.JSONDecodeError, ValueError):
            continue
    raise ValueError("unparseable JSON even after truncation repair")


def _ensure_required_collections(data: dict[str, Any]) -> None:
    """Guarantee the required collections exist before validation.

    Two failures showed up on an out-of-the-box prompt ("rooftop beekeeping apiary"):
    the model omitted ``acceptance_tests`` entirely, and it proposed theme colours
    (honey-yellow ``#d4a411``) that fail the WCAG AA contrast rule. Both are
    mechanical, so repair them here rather than spending a whole LLM repair turn —
    on a rate-limited tier that turn is what broke the build.
    """
    entities = data.get("entities")
    if not isinstance(entities, list) or not [
        e for e in entities if isinstance(e, dict) and e.get("name")
    ]:
        data["entities"] = [
            {
                "name": "record",
                "plural": "records",
                "description": "Primary record",
                "fields": [
                    {"name": "title", "type": "string", "required": True},
                    {"name": "details", "type": "text", "required": True},
                ],
            }
        ]
        entities = data["entities"]

    valid_entities = [e for e in entities if isinstance(e, dict) and e.get("name")]
    first = valid_entities[0] if valid_entities else {"name": "record", "plural": "records"}

    if not data.get("screens"):
        data["screens"] = [
            {
                "name": "dashboard",
                "route": "/",
                "purpose": "Overview",
                "uses_entities": [first.get("name")],
                "key_interactions": ["summary", "navigate"],
            },
            *[
                {
                    "name": f"{e.get('name')}_mgmt",
                    "route": f"/{e.get('plural') or str(e.get('name')) + 's'}",
                    "purpose": f"Manage {e.get('plural')}",
                    "uses_entities": [e.get("name")],
                    "key_interactions": ["create", "list", "view"],
                }
                for e in valid_entities[:6]
            ],
        ]

    if not data.get("acceptance_tests"):
        # The schema requires at least three; reuse the create/list/get shape the
        # deterministic fallback already uses for the first entity.
        name = str(first.get("name") or "record")
        plural = str(first.get("plural") or f"{name}s")
        body = {
            f.get("name"): "sample" if str(f.get("type")) == "string" else 1
            for f in (first.get("fields") or [])[:3]
            if isinstance(f, dict)
        }
        data["acceptance_tests"] = [
            {
                "name": f"create_{name}",
                "description": f"Creating a {name} returns HTTP 201",
                "steps": [
                    {
                        "method": "POST",
                        "path": f"/{plural}",
                        "body": body,
                        "expect_status": 201,
                        "expect": body,
                        "save": {"id": "id"},
                    }
                ],
            },
            {
                "name": f"list_{plural}",
                "description": f"Listing {plural} returns HTTP 200",
                "steps": [
                    {"method": "GET", "path": f"/{plural}", "expect_status": 200}
                ],
            },
            {
                "name": f"get_{name}",
                "description": f"A single {name} can be created and retrieved",
                "steps": [
                    {
                        "method": "POST",
                        "path": f"/{plural}",
                        "body": body,
                        "expect_status": 201,
                        "save": {"id": "id"},
                    },
                    {
                        "method": "GET",
                        "path": f"/{plural}/{{id}}",
                        "expect_status": 200,
                    },
                ],
            },
        ]

    # The model picks thematically apt colours (honey yellow for a beekeeping app)
    # without checking contrast. An unusable theme must not discard a good spec:
    # drop it and let the caller apply a deterministic, contrast-safe palette.
    theme = data.get("theme")
    if theme and theme != "":
        try:
            ThemeSpec.model_validate(theme)
        except Exception:
            data.pop("theme", None)


def _repair_spec_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Coerce near-miss model output into a validatable spec, in memory.

    Repairs the failures that recur on every generation, each of which would
    otherwise cost a whole LLM repair turn — and on a rate-limited tier that turn
    is exactly what blew the token budget and degraded the build to stubs:
    an `enum` field with no ``enum_values``, a `ref` field with no target, a
    `ref` name not ending in ``_id``, a theme whose colours fail the WCAG AA
    contrast check, and missing required collections.
    """
    _ensure_required_collections(data)
    _resolve_test_variables(data)

    entity_names = {
        str(e.get("name", "")).lower()
        for e in data.get("entities", [])
        if isinstance(e, dict) and e.get("name")
    }
    for entity in data.get("entities", []):
        if not isinstance(entity, dict):
            continue
        for field in entity.get("fields", []):
            if not isinstance(field, dict):
                continue
            ftype = str(field.get("type", "")).lower()
            if ftype == "enum" and len(field.get("enum_values") or []) < 2:
                # No values supplied: degrade to a plain string rather than
                # reject the whole spec over one field.
                field["type"] = "string"
                field.pop("enum_values", None)
            elif ftype == "ref":
                ref = str(field.get("ref") or "").lower()
                if ref not in entity_names:
                    field.pop("ref", None)
                    field["type"] = "string"
                elif not str(field.get("name", "")).endswith("_id"):
                    field["name"] = f"{field['name']}_id"

    for action in data.get("actions", []):
        if not isinstance(action, dict):
            continue
        # `path` is derivable from the name (it must start with /actions/).
        if not action.get("path"):
            slug = re.sub(r"[^a-z0-9]+", "_", str(action.get("name", "action")).lower()).strip("_")
            action["path"] = f"/actions/{slug or 'action'}"
        if not action.get("summary"):
            action["summary"] = str(action.get("description") or "Custom business action")
        action.pop("description", None)
        if not action.get("rules"):
            action["rules"] = ["Implement the described behaviour generally."]

    for test in data.get("acceptance_tests", []):
        if not isinstance(test, dict):
            continue
        # One smoke step is enough to satisfy the schema; richer steps are better
        # but their absence should not discard an otherwise good spec.
        if not test.get("steps"):
            plural = str(
                (data.get("entities") or [{}])[0].get("plural") or "items"
            )
            test["steps"] = [
                {
                    "method": "GET",
                    "path": f"/{plural}",
                    "expect_status": 200,
                }
            ]
    _resolve_test_variables(data)
    return data


def _resolve_test_variables(data: dict[str, Any]) -> None:
    """Make every ``{var}`` in an acceptance test resolvable by an earlier step.

    The model writes step bodies like ``{"hive_id": "{hive_id}"}`` without the
    prerequisite step that created the hive and saved ``hive_id``. The placeholder
    then posts as a literal string, the FK lookup 404s, and the acceptance test
    fails for a reason that has nothing to do with the business logic it was
    meant to exercise.
    """
    entities = {
        str(e.get("name")).lower(): e
        for e in data.get("entities", [])
        if isinstance(e, dict) and e.get("name")
    }
    if not entities:
        return

    for test in data.get("acceptance_tests", []):
        if not isinstance(test, dict):
            continue
        steps = test.get("steps")
        if not isinstance(steps, list) or not steps:
            continue

        saved: set[str] = set()
        wanted: list[str] = []
        seen_wanted: set[str] = set()
        for step in steps:
            if not isinstance(step, dict):
                continue
            for var in (step.get("save") or {}).values():
                saved.add(var)

        def _collect(payload: Any) -> None:
            if isinstance(payload, dict):
                for value in payload.values():
                    _collect(value)
            elif isinstance(payload, list):
                for value in payload:
                    _collect(value)
            elif isinstance(payload, str):
                m = re.fullmatch(r"[{<](\w+)[}>]", payload.strip())
                if m and m.group(1) not in saved and m.group(1) not in seen_wanted:
                    seen_wanted.add(m.group(1))
                    wanted.append(m.group(1))

        for step in steps:
            if isinstance(step, dict):
                _collect(step.get("body"))
                _collect(step.get("path"))

        if not wanted:
            continue

        # Synthesize the prerequisite creations, in order, so the ids exist before
        # the original steps run.
        prefixes: list[dict[str, Any]] = []
        for var in wanted:
            stem = var
            ent = entities.get(stem)
            if ent is None:
                # `hive_id` -> `hive`
                stripped = re.sub(r"_id$", "", var)
                ent = entities.get(stripped)
            if ent is None:
                continue
            plural = str(ent.get("plural") or f"{stem}s")
            body = {}
            for f in (ent.get("fields") or [])[:4]:
                if not isinstance(f, dict) or not f.get("name"):
                    continue
                body[str(f["name"])] = _sample_field_value(f)
            if not body:
                body = {"name": "seed"}
            prefixes.append(
                {
                    "method": "POST",
                    "path": f"/{plural}",
                    "body": body,
                    "expect_status": 201,
                    "save": {var: "id"},
                }
            )
        if prefixes:
            test["steps"] = prefixes + [s for s in steps if isinstance(s, dict)]


def _sample_field_value(field: dict[str, Any]) -> Any:
    """A type-correct sample value for a generated spec field."""
    ftype = str(field.get("type") or "string").lower()
    name = str(field.get("name") or "").lower()
    if "email" in name:
        return "seed@example.com"
    if "date" in name or "time" in name or "at" in name:
        return "2024-09-01T10:00:00Z"
    return _SAMPLE_VALUES.get(ftype, "seed")


_SAMPLE_VALUES: dict[str, Any] = {
    "string": "seed",
    "text": "seed",
    "int": 1,
    "integer": 1,
    "float": 1.0,
    "bool": True,
    "boolean": True,
    "date": "2024-09-01",
    "datetime": "2024-09-01T10:00:00Z",
    "enum": "active",
    "ref": 1,
}


def _context_from_state(
    ai_state: dict[str, Any],
    user_prompt: str,
    uploaded_context: str = "",
    conversation_history: list[dict[str, Any]] | None = None,
) -> str:
    def content(key: str) -> Any:
        v = ai_state.get(key)
        return v.get("content") if isinstance(v, dict) else None

    parts = [
        f"USER REQUEST:\n{user_prompt or ai_state.get('user_message', '')}",
        f"BUSINESS: {ai_state.get('business_description', '')}",
        f"INDUSTRY: {ai_state.get('industry', '')}",
        f"CONFIRMED MODULES: {ai_state.get('confirmed_modules') or ai_state.get('identified_solutions') or []}",
    ]

    # Include uploaded document context (PDFs, ERDs, images, PPTs)
    if uploaded_context:
        parts.append(
            f"UPLOADED DOCUMENT CONTEXT (user-provided reference material):\n"
            f"{uploaded_context[:2500]}"
        )

    # Include conversation history for multi-turn context
    if conversation_history:
        user_msgs = [
            m.get("content", "")
            for m in conversation_history
            if m.get("role") == "user" and m.get("content")
        ]
        if user_msgs:
            # Include last 3 user messages for context
            history_text = "\n---\n".join(user_msgs[-3:])
            parts.append(
                f"CONVERSATION HISTORY (previous user messages for context):\n{history_text[:1500]}"
            )

    for key in ("er_diagram", "api_spec", "lld"):
        c = content(key)
        if c:
            parts.append(
                f"{key.upper()} (reference, simplify if too big):\n{json.dumps(c, default=str)[:1200]}"
            )
    return "\n\n".join(parts)


_IRREGULAR_PLURALS: dict[str, str] = {
    "person": "people",
    "child": "children",
    "man": "men",
    "woman": "women",
    "foot": "feet",
    "tooth": "teeth",
    "mouse": "mice",
    "goose": "geese",
    # Sibilant stems that double the final consonant instead of taking "es".
    # These are lexical exceptions, not a rule - "bus"/"gas"/"lens" take "es".
    "quiz": "quizzes",
}

# Suffixes that already end in a sibilant sound, so a singular noun needs "es"
# rather than a bare "s" (dish -> dishes, box -> boxes).
_ESCH_SUFFIXES: tuple[str, ...] = ("s", "x", "z", "ch", "sh")

# A trailing "s" here is part of the singular stem, not a plural marker, so
# these still need "es" (address -> addresses, campus -> campuses).
_SINGULAR_S_ENDINGS: tuple[str, ...] = ("ss", "us", "is")

# Richness budgets for the deterministic fallback. The previous caps (4
# entities / 5 fields / 3 modules) truncated real ER diagrams down to a
# two-entity toy, which is what made generated apps look thin even when the
# upstream template and diagram were rich.
#
# _MAX_FALLBACK_ENTITIES is coupled to the Screen limit: the fallback emits one
# screen per entity plus a dashboard, and AppSpec allows at most 6 screens, so
# this must stay at 5 or validation fails.
_MAX_FALLBACK_ENTITIES = 5
_MAX_FALLBACK_FIELDS = 10
_MAX_FALLBACK_MODULES = 5


def pluralize(name: str) -> str:
    """Return the plural form of an entity *name*.

    Entity names arrive from ER diagrams and templates in both singular and
    plural form. The previous inline rule appended "es" to anything already
    ending in "s", which turned the plural "products" into "productses" and
    "orders" into "orderses" - those became module names, routes and table
    names, so the whole app was mislabelled. A name that is already plural is
    now returned unchanged.
    """
    word = name.strip().lower()
    if not word:
        return name
    if word in _IRREGULAR_PLURALS:
        return _IRREGULAR_PLURALS[word]
    if word.endswith(_SINGULAR_S_ENDINGS):
        return f"{word}es"
    if word.endswith(_ESCH_SUFFIXES):
        return word if word.endswith("s") else f"{word}es"
    if word.endswith("y") and len(word) > 1 and word[-2] not in "aeiou":
        return f"{word[:-1]}ies"
    if word.endswith("s"):
        return word
    return f"{word}s"


def _prompt_title(prompt: str) -> str:
    """Derive a clean product name from a chat-style request.

    Slicing the first 40 characters produced names like
    "Create a clinic appointment booking syst" — the request verb and a word cut
    in half. This strips the request frame and trailing artefact nouns instead.
    """
    from app.services.domain_lexicon import _title_from_prompt

    return _title_from_prompt(prompt)


# Keyword evidence for the growth curve. This only feeds the *offline* fallback
# path — the LLM is told to declare `app_kind`/`lifecycle_stage` explicitly. Its
# job is to keep a no-LLM build from defaulting to a six-entity dashboard when
# the user plainly asked for a single page.
_KIND_HINTS: tuple[tuple[AppKind, tuple[str, ...]], ...] = (
    ("landing", ("landing page", "one page", "single page", "homepage", "brochure")),
    ("portfolio", ("portfolio", "resume", "cv site")),
    ("marketplace", ("marketplace", "multi-vendor", "multi seller", "two-sided")),
    ("booking", ("book", "booking", "appointment", "reservation", "schedule", "slot")),
    ("catalog", ("catalog", "catalogue", "storefront", "shop", "menu", "products")),
    ("social", ("community", "forum", "feed", "social network")),
    ("dashboard", ("dashboard", "admin panel", "analytics", "reporting", "kpi")),
    ("internal", ("crm", "erp", "inventory", "inventory management", "back office")),
)
_STAGE_HINTS: tuple[tuple[LifecycleStage, tuple[str, ...]], ...] = (
    (
        "operate",
        (
            "dashboard",
            "admin",
            "reporting",
            "analytics",
            "manage staff",
            "back office",
            "kpi",
            "approval",
            "approve",
            "approved",
            "workflow",
            "assign",
            "schedule",
            "tracker",
            "tracking",
            "management system",
            "payroll",
            "attendance",
            "timesheet",
            "leave request",
            "leave tracker",
            "request",
            "review",
            "escalation",
            "audit",
        ),
    ),
    (
        "transact",
        (
            "checkout",
            "cart",
            "payment",
            "order",
            "buy",
            "sell",
            "booking",
            "book a",
            "pay",
            "reservation",
            "appointment",
            "invoice",
        ),
    ),
)


def infer_growth_curve(text: str) -> tuple[AppKind, LifecycleStage]:
    """Keyword-scored ``(app_kind, lifecycle_stage)`` for the offline fallback path."""
    lowered = f" {text.lower()} "

    kind: AppKind = "internal"
    best = 0
    for candidate, keywords in _KIND_HINTS:
        hits = sum(len(k) for k in keywords if k in lowered)
        if hits > best:
            best, kind = hits, candidate

    stage: LifecycleStage = "showcase"
    for candidate, keywords in _STAGE_HINTS:
        if any(k in lowered for k in keywords):
            stage = candidate
            break

    # The landing cap is a validation rule, not a preference.
    if kind == "landing" and STAGE_ORDER[stage] > STAGE_ORDER["transact"]:
        stage = "transact"
    return kind, stage


def resolve_analytics_module(
    module: AnalyticsModule, spec_entities: list[Entity]
) -> AnalyticsModule:
    """Auto-disable analytics that has no real entity + numeric metric behind it.

    Enabling a revenue dashboard off the back of a stray `quantity` column is the
    exact failure this exists to prevent, so an unsupported request is downgraded
    with a recorded reason rather than silently building the wrong thing.
    """
    if not module.enabled:
        return module

    reasons: list[str] = []
    if not module.entity:
        reasons.append("analytics.enabled without naming a target entity")
        return AnalyticsModule(
            enabled=False,
            rationale=(module.rationale + "; " if module.rationale else "")
            + "auto-disabled: " + "; ".join(reasons),
        )

    entity = next((e for e in spec_entities if e.name == module.entity), None)
    if entity is None:
        reasons.append(f"analytics.entity '{module.entity}' is not a spec entity")
    elif not module.primary_metric_field:
        reasons.append(
            f"analytics.enabled on '{entity.name}' without naming a numeric metric"
        )
    else:
        field = next(
            (f for f in entity.fields if f.name == module.primary_metric_field), None
        )
        if field is None:
            reasons.append(
                f"analytics.primary_metric_field '{module.primary_metric_field}' "
                f"does not exist on '{entity.name}'"
            )
        elif field.type not in ("int", "float"):
            reasons.append(
                f"analytics.primary_metric_field '{field.name}' is '{field.type}', "
                "not a number"
            )

    if reasons:
        logger.info("Disabling analytics for '%s': %s", module.entity, "; ".join(reasons))
        return AnalyticsModule(
            enabled=False,
            rationale=(module.rationale + "; " if module.rationale else "")
            + "auto-disabled: " + "; ".join(reasons),
        )
    return module


def fallback_app_spec(
    ai_state: dict[str, Any],
    user_prompt: str = "",
    uploaded_context: str = "",
    conversation_history: list[dict[str, Any]] | None = None,
) -> AppSpec:
    """Deterministically synthesize a valid AppSpec from user requirements and state.

    Ensures that OpenCode receives a well-formed spec with valid schemas, models, and
    acceptance tests even when the external LLM provider hits rate limits or is offline.
    """
    title = (
        ai_state.get("solution_title")
        or _prompt_title(user_prompt or ai_state.get("business_description", ""))
        or "Custom App"
    ).strip()
    clean_name = re.sub(r"[^\w\s]+", " ", title).strip() or "Custom App"

    # Extract entities from er_diagram or confirmed_modules or heuristics
    er = (
        ai_state.get("er_diagram", {}).get("content", {})
        if isinstance(ai_state.get("er_diagram"), dict)
        else {}
    )
    raw_entities = er.get("entities", []) if isinstance(er, dict) else []

    entities: list[tuple[str, str, list[dict[str, Any]]]] = []
    if raw_entities:
        for ent in raw_entities[:_MAX_FALLBACK_ENTITIES]:
            if isinstance(ent, dict) and ent.get("name"):
                ename = re.sub(r"[^a-zA-Z0-9_]+", "_", str(ent["name"]).lower()).strip("_")
                eplural = pluralize(ename)
                fields = []
                for f in ent.get("fields", [])[:_MAX_FALLBACK_FIELDS]:
                    fname = f.get("name", "") if isinstance(f, dict) else str(f)
                    fname = re.sub(r"[^a-zA-Z0-9_]+", "_", fname.lower()).strip("_")
                    if fname and fname not in ("id", "created_at"):
                        fields.append({"name": fname, "type": "string"})
                if not fields:
                    fields = [{"name": "name", "type": "string"}]
                entities.append((ename, eplural, fields))

    if not entities:
        modules = ai_state.get("confirmed_modules") or ai_state.get("identified_solutions", [])
        if modules:
            for m in modules[:_MAX_FALLBACK_MODULES]:
                ename = re.sub(r"[^a-zA-Z0-9_]+", "_", str(m).lower()).strip("_")
                eplural = pluralize(ename)
                entities.append(
                    (
                        ename,
                        eplural,
                        [{"name": "title", "type": "string"}, {"name": "status", "type": "string"}],
                    )
                )

    if not entities:
        from app.services.domain_lexicon import infer_entities as _infer

        combined_text = (
            f"{user_prompt} {uploaded_context} {ai_state.get('business_description', '')}".strip()
        )
        # The lexicon reads the request itself: a curated vertical when one
        # matches, otherwise the nouns the user actually typed. The previous
        # fixed item/category cascade made every offline build look identical
        # apart from its title, which read as "it only renamed my project".
        entities = [
            (name, plural, [{"name": fname, "type": ftype} for fname, ftype in fields])
            for name, plural, fields in _infer(combined_text, limit=_MAX_FALLBACK_ENTITIES)
        ]

    spec_entities: list[Entity] = []
    for ename, eplural, f_list in entities:
        spec_fields = [
            SpecField(name=f["name"], type=f.get("type", "string"), required=True) for f in f_list
        ]
        spec_entities.append(
            Entity(name=ename, plural=eplural, description=f"{ename} entity", fields=spec_fields)
        )

    screens = [
        Screen(
            name="dashboard",
            route="/",
            purpose=f"Overview of {clean_name}",
            uses_entities=[e.name for e in spec_entities],
            key_interactions=["view summary", "navigate records"],
        ),
        *[
            Screen(
                name=f"{e.name}_mgmt",
                route=f"/{e.plural}",
                purpose=f"Manage {e.plural}",
                uses_entities=[e.name],
                key_interactions=["create record", "list records", "view details"],
            )
            for e in spec_entities
        ],
    ]

    first_e = spec_entities[0]
    sample_body = {
        f.name: (10.0 if f.type == "float" else 1 if f.type == "int" else "Sample Value")
        for f in first_e.fields
    }

    tests = [
        AcceptanceTest(
            name=f"create_{first_e.name}",
            description=f"A new {first_e.name} can be created via POST",
            steps=[
                TestStep(
                    method="POST",
                    path=f"/{first_e.plural}",
                    body=sample_body,
                    expect_status=201,
                    expect=sample_body,
                    save={"id": "id"},
                )
            ],
        ),
        AcceptanceTest(
            name=f"list_{first_e.plural}",
            description=f"Listing {first_e.plural} returns HTTP 200",
            steps=[
                TestStep(
                    method="GET",
                    path=f"/{first_e.plural}",
                    expect_status=200,
                )
            ],
        ),
        AcceptanceTest(
            name=f"get_{first_e.name}",
            description=f"A single {first_e.name} can be created and retrieved by ID",
            steps=[
                TestStep(
                    method="POST",
                    path=f"/{first_e.plural}",
                    body=sample_body,
                    expect_status=201,
                    save={"id": "id"},
                ),
                TestStep(
                    method="GET",
                    path=f"/{first_e.plural}/{{id}}",
                    expect_status=200,
                ),
            ],
        ),
    ]

    # ── v2: growth curve, theme, seed data ──
    growth_text = " ".join(
        str(x) for x in (user_prompt, ai_state.get("business_description", "")) if x
    )
    app_kind, lifecycle_stage = infer_growth_curve(growth_text)

    # The workflow the user asked for, if any. Without this a "manager approval
    # workflow" prompt built a read-only app.
    spec_actions = _derive_fallback_actions(user_prompt, spec_entities)

    # Imported lazily: theme_engine builds on the AppSpec types defined above,
    # so a module-level import here would be circular.
    from app.services.theme_engine import theme_for_spec

    return AppSpec(
        app_name=clean_name,
        one_liner=f"Full-stack {clean_name} application",
        core_value=f"Automated management and workflows for {clean_name}",
        entities=spec_entities,
        screens=screens,
        actions=spec_actions,
        acceptance_tests=tests,
        app_kind=app_kind,
        lifecycle_stage=lifecycle_stage,
        # No user-supplied content is available offline, so leave seed_data
        # empty rather than fabricate placeholder rows.
        seed_data=[],
        analytics=resolve_analytics_module(AnalyticsModule(), spec_entities),
        theme=theme_for_spec(growth_text, app_name=clean_name),
    )


# State transitions a request can name, mapped to the action they imply. A build
# that skips these ships a read-only app for a request that was explicitly a
# workflow ("manager approval workflow", "cancel my booking").
_WORKFLOW_HINTS: tuple[tuple[str, str, str], ...] = (
    ("approve", "approve", "approved"),
    ("approval", "approve", "approved"),
    ("reject", "reject", "rejected"),
    ("decline", "reject", "rejected"),
    ("deny", "reject", "rejected"),
    ("cancel", "cancel", "cancelled"),
    ("complete", "complete", "completed"),
    ("fulfil", "fulfil", "fulfilled"),
    ("submit", "submit", "submitted"),
    ("book", "book", "booked"),
    ("books", "book", "booked"),
    ("booking", "book", "booked"),
    ("slot", "book", "booked"),
    ("slots", "book", "booked"),
    ("reserve", "reserve", "reserved"),
    ("reserves", "reserve", "reserved"),
    ("reservation", "reserve", "reserved"),
    ("reservations", "reserve", "reserved"),
    ("checkout", "checkout", "checked_out"),
)


def _derive_fallback_actions(user_prompt: str, entities: list[Entity]) -> list[Action]:
    """Derive business actions from the request text.

    An approval or tracking workflow is a state transition the user explicitly
    asked for. The deterministic fallback used to emit no actions at all, so such
    an app shipped as read-only CRUD that silently dropped the workflow — the build
    "succeeded" while ignoring what was requested.
    """
    lowered = f" {user_prompt.lower()} "
    if not entities:
        return []

    from app.services.domain_lexicon import _keyword_matches

    # The action must act on the record the workflow is *about*, not on a party
    # that merely happens to have a status column. Prefer a request-like entity
    # (request/booking/order/application/ticket), then any status-bearing entity
    # that is not a party (employee/doctor/customer), and only then the last one.
    _REQUESTY = ("request", "booking", "order", "application", "ticket", "appointment", "reservation")
    _PARTYISH = ("employee", "doctor", "customer", "patient", "member", "user", "client", "supplier")
    has_status = [e for e in entities if any(f.name == "status" for f in e.fields)]
    target = next(
        (e for e in has_status if any(k in e.name for k in _REQUESTY)),
        None,
    )
    if target is None:
        target = next(
            (e for e in has_status if not any(p in e.name for p in _PARTYISH)),
            None,
        )
    if target is None:
        target = has_status[-1] if has_status else entities[-1]

    actions: list[Action] = []
    seen: set[str] = set()
    for keyword, verb, resulting in _WORKFLOW_HINTS:
        if not _keyword_matches(keyword, lowered):
            continue
        name = f"{verb}_{target.name}"
        if name in seen:
            continue
        seen.add(name)
        actions.append(
            Action(
                name=name,
                method="POST",
                path=f"/actions/{name}",
                summary=f"{verb.capitalize()} a {target.name} and record the outcome",
                input_fields=[
                    SpecField(
                        name=f"{target.name}_id",
                        type="int",
                        description=f"The {target.name} being {verb}d",
                    )
                ],
                rules=[
                    f"A {target.name} must exist before it can be {verb}d.",
                    f"Set the {target.name} status to '{resulting}'.",
                    "Refuse the transition when the record is already in that state.",
                ],
                output_example={"id": 1, "status": resulting, "updated": True},
            )
        )
        if len(actions) >= 3:
            break
    return actions


def normalize_spec(spec: AppSpec) -> AppSpec:
    """Enforce the v2 invariants that are repairable rather than fatal.

    Three things can be fixed without asking the model again: an unsupported
    analytics target (downgrade with a reason), a missing/invalid theme (fall
    back to the industry palette), and a `landing` kind that over-claims an
    operating stage (clamp it). Everything else stays a validation error so the
    repair loop can see it.
    """
    analytics = resolve_analytics_module(spec.analytics, spec.entities)
    app_kind = spec.app_kind
    stage = spec.lifecycle_stage
    if app_kind == "landing" and STAGE_ORDER[stage] > STAGE_ORDER["transact"]:
        stage = "transact"

    theme = spec.theme
    if theme is None:
        from app.services.theme_engine import theme_for_spec

        text = " ".join(
            [spec.app_name, spec.one_liner, spec.core_value, *spec.assumptions]
        )
        theme = theme_for_spec(text, app_name=spec.app_name)

    if (
        analytics is spec.analytics
        and app_kind == spec.app_kind
        and stage == spec.lifecycle_stage
        and theme is spec.theme
    ):
        return spec
    return spec.model_copy(
        update={
            "analytics": analytics,
            "app_kind": app_kind,
            "lifecycle_stage": stage,
            "theme": theme,
        }
    )


async def generate_app_spec(
    ai_state: dict[str, Any],
    user_prompt: str = "",
    *,
    max_attempts: int = 3,
    uploaded_context: str = "",
    conversation_history: list[dict[str, Any]] | None = None,
) -> AppSpec:
    """LLM → AppSpec with validation-error feedback loop and deterministic fallback on rate limits."""
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    from app.core.config import settings
    from app.core.llm import get_llm, has_llm_credentials

    if not has_llm_credentials():
        return fallback_app_spec(
            ai_state,
            user_prompt,
            uploaded_context=uploaded_context,
            conversation_history=conversation_history,
        )

    # 2500 was silently fatal: this is a *reasoning* model (gpt-oss-120b burns
    # ~900 completion tokens on hidden reasoning), leaving only ~1600 for the
    # spec, so every response returned `finish_reason: length` with truncated
    # JSON and the build silently degraded to the deterministic stub. Budget for
    # that overhead, but keep prompt+completion under Groq's 8000 TPM ceiling
    # (the compact schema hint holds the prompt near ~800 tokens).
    llm = get_llm(temperature=0.2, max_tokens=5000)
    messages: list[Any] = [
        SystemMessage(content=SPEC_SYSTEM + "\nJSON schema:\n" + _spec_schema_hint()),
        HumanMessage(
            content=_context_from_state(
                ai_state,
                user_prompt,
                uploaded_context=uploaded_context,
                conversation_history=conversation_history,
            )
        ),
    ]
    last_err = ""
    # A 12s cap here was shorter than a real model response, so every build fell
    # back to the deterministic stub spec and the app never became what was asked
    # for. Use the same generous budget as a generation pass.
    spec_timeout = max(12.0, float(getattr(settings, "MVP_BUILD_TIMEOUT", 2700)) / 30.0)
    for attempt in range(1, max_attempts + 1):
        try:
            resp = await asyncio.wait_for(llm.ainvoke(messages), timeout=spec_timeout)
        except Exception as exc:
            logger.warning(
                "generate_app_spec LLM error on attempt %d (%s); using smart fallback AppSpec",
                attempt,
                exc,
            )
            return fallback_app_spec(
                ai_state,
                user_prompt,
                uploaded_context=uploaded_context,
                conversation_history=conversation_history,
            )

        raw = str(getattr(resp, "content", resp))
        try:
            spec = normalize_spec(AppSpec.model_validate(_extract_json(raw)))
            logger.info("AppSpec valid on attempt %d: %s", attempt, spec.app_name)
            return spec
        except (ValidationError, ValueError, json.JSONDecodeError) as err:
            last_err = str(err)[:2000]
            logger.warning("AppSpec attempt %d invalid: %s", attempt, last_err[:300])
            # Do NOT re-send `raw` plus the whole history on a retry: on Groq that
            # pushed past the 8000-token-per-minute ceiling and the retry died
            # with 413/429, so the spec fell back to stubs. Only the error text is
            # needed for the model to correct itself.
            messages = [
                SystemMessage(content=SPEC_SYSTEM + "\nJSON schema:\n" + _spec_schema_hint()),
                *messages[1:2],
                HumanMessage(
                    content=(
                        "Your previous answer was not a valid spec. Return the COMPLETE "
                        f"JSON object only, fixing ALL of these errors:\n{last_err}"
                    )
                ),
            ]

    logger.warning(
        "AppSpec validation exhausted %d attempts; using smart fallback AppSpec", max_attempts
    )
    return fallback_app_spec(
        ai_state,
        user_prompt,
        uploaded_context=uploaded_context,
        conversation_history=conversation_history,
    )
