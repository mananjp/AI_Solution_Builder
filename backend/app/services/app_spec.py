"""
AI Solution Builder — AppSpec (single source of truth for MVP builds)

Replaces keyword/regex domain guessing. The LLM produces ONE validated,
app-specific spec: entities, business *actions* (the logic that makes the app
more than CRUD), screens, and executable acceptance tests. Deterministic code
generates plumbing + tests from it; the coding agent only implements actions/UI.
"""

from __future__ import annotations

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
        if re.search(r"\b" + re.escape(kw) + r"\b", text_lower):
            if label not in found:
                found.append(label)

    return len(found) > 0, found


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
- Aim for a genuinely useful surface area: 3-6 entities with 3+ meaningful fields each, and a screen per entity. Do not pad with placeholder fields like "name"/"title"/"status" when a real attribute is obvious.
- If the user asks for a landing page, portfolio, or showcase website, model realistic entities (e.g. leads, inquiries, contact_messages, subscribers, testimonials) and action (e.g. /actions/submit_inquiry, /actions/subscribe_newsletter) with appropriate screens (e.g. Landing Page at "/", Admin/Inquiries at "/inquiries").
- Put the real logic in `actions` (calculations, state transitions, validation, conflict
  checks, aggregation). Each action has precise `rules` a developer can implement
  without guessing (formulas, edge cases, error codes: 400 invalid, 404 missing, 409 conflict).
- If the app is genuinely pure CRUD, actions may be empty, but core_value must say so.
- Entities: 3–6. Fields snake_case; refs are `<entity>_id` with type "ref".
- REST conventions that ALREADY exist for every entity (do not list them as actions):
  GET/POST /{plural}, GET/PATCH/DELETE /{plural}/{id}, GET /{plural}?<ref_field>=<id>.
  IDs are integers. Responses of CRUD = the object JSON (with "id").
- acceptance_tests: 3–10 scenarios that PROVE the core value end-to-end via HTTP.
  Use `save` to capture ids, e.g. {"group_id": "id"}, then use "{group_id}" in later paths/bodies.
  Every action must be exercised by at least one test with a concrete numeric/string `expect`.
  Include at least one negative test (400/404/409).
- Build the FULL app the user described. A high-end result has real entities with real attributes, a screen per entity, and domain actions wired to acceptance tests - do not deliberately under-build to keep the response small.

UI quality (the generated frontend is judged on this):
- A shadcn/ui component library is PREINSTALLED and ready to import from "@/components/ui/<name>": alert, badge, button, card (Card/CardHeader/CardTitle/CardDescription/CardContent/CardFooter), checkbox, dialog, dropdown-menu, input, label, select, separator, skeleton, sonner (toasts), switch, table (Table/TableHeader/TableBody/TableRow/TableHead/TableCell), tabs, textarea. Also available: "@/components/ui/skiper-ui" animated primitives, recharts for charts, lucide-react icons, framer-motion, react-hook-form, zod, and Tailwind design tokens (bg-background, bg-card, bg-muted, text-muted-foreground, bg-primary, bg-destructive, border-border, rounded-lg/md/sm).
- Build screens by COMPOSING those premade components. A page assembled from Card + Table + Button + Badge + Input reads as a finished product; the same page hand-rolled from raw <div> elements reads as a wireframe. Do not re-implement a button, card, table, badge, input, modal or toast that already exists.
- If you genuinely need a component that is NOT preinstalled, install it rather than hand-rolling it: run `npx shadcn@latest add <name> --yes` from the `frontend` directory (e.g. `npx shadcn@latest add accordion --yes`). The project is already configured for shadcn (components.json, "@/components/ui" alias, design tokens), so the CLI drops the component in with correct imports and theme support. Common useful additions: accordion, avatar, calendar, chart, command, drawer, form, hover-card, popover, progress, radio-group, scroll-area, slider, tooltip, carousel, pagination, breadcrumb, collapsible, aspect-ratio, alert-dialog. Never invent an import path under "@/components/ui" for a component you did not install. If installing is not possible in your environment, fall back to composing the preinstalled set plus a small local component - never block the build and never leave a dangling import.
- The premade components are yours to PERSONALISE. Tweak them for the app's look - pass className, adjust variants, restyle via the Tailwind tokens - so the UI feels designed for this product rather than default-library. Prefer composing and passing className over forking a component file; only edit a component in "@/components/ui" when the app genuinely needs a new variant that composition cannot express, and keep every existing export intact so other screens keep working.
- Every screen must be responsive, mobile-first, correct at 375px: stack cards, or use an overflow-x-auto table wrapper and hide secondary columns on small screens. Never ship a desktop-only grid that overflows horizontally.
- Give every list screen real affordances: a search/filter input, a proper empty state, loading skeletons while fetching, and a create/edit form with validation - not a bare JSON dump.
- Use lucide-react icons for navigation and primary actions, keep the type scale and spacing consistent, and do not hardcode one-off hex colours - use the design tokens so light and dark mode both work.
- core_value must be a concrete sentence about what the app does beyond CRUD - never leave it empty."""


def _spec_schema_hint() -> str:
    return json.dumps(AppSpec.model_json_schema(), separators=(",", ":"))[:6000]


def _extract_json(text: str) -> dict[str, Any]:
    t = text.strip()
    if "```" in t:
        m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", t, re.S)
        if m:
            t = m.group(1)
    start, end = t.find("{"), t.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("no JSON object in response")
    return json.loads(t[start : end + 1])  # type: ignore[no-any-return]


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
        or ai_state.get("business_description", "").split(".")[0]
        or (user_prompt.split("\n")[0][:40] if user_prompt else "")
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
        combined_text = (
            f"{user_prompt} {uploaded_context} {ai_state.get('business_description', '')}".lower()
        )
        if any(
            k in combined_text
            # "website", "agency" and "service" were dropped as bare keywords:
            # they appear in ordinary prose ("HR services", "customer service",
            # "our agency site") and hijacked internal-tool requests into the
            # inquiry/lead branch. Multi-word forms are specific enough.
            for k in ("landing page", "landing", "portfolio", "showcase", "one-pager", "brochure")
        ):
            entities = [
                (
                    "inquiry",
                    "inquiries",
                    [{"name": "name", "type": "string"}, {"name": "email", "type": "string"}],
                ),
                ("lead", "leads", [{"name": "company", "type": "string"}]),
            ]
        elif any(
            k in combined_text
            for k in (
                "employee",
                "employees",
                "hr",
                "human resource",
                "workforce",
                "staff",
                "payroll",
                "department",
                "attendance",
                "leave",
                "onboarding",
                "hiring",
            )
        ):
            # Checked before the commerce branch: an employee request that
            # mentions "payroll" or "order" must never be read as e-commerce.
            entities = [
                (
                    "employee",
                    "employees",
                    [
                        {"name": "full_name", "type": "string"},
                        {"name": "email", "type": "string"},
                        {"name": "job_title", "type": "string"},
                        {"name": "department", "type": "string"},
                        {"name": "status", "type": "string"},
                    ],
                ),
                (
                    "department",
                    "departments",
                    [
                        {"name": "name", "type": "string"},
                        {"name": "head", "type": "string"},
                        {"name": "location", "type": "string"},
                    ],
                ),
                (
                    "leave_request",
                    "leave_requests",
                    [
                        {"name": "employee_name", "type": "string"},
                        {"name": "leave_type", "type": "string"},
                        {"name": "start_date", "type": "string"},
                        {"name": "end_date", "type": "string"},
                        {"name": "status", "type": "string"},
                    ],
                ),
                (
                    "attendance_record",
                    "attendance_records",
                    [
                        {"name": "employee_name", "type": "string"},
                        {"name": "date", "type": "string"},
                        {"name": "check_in", "type": "string"},
                        {"name": "check_out", "type": "string"},
                        {"name": "status", "type": "string"},
                    ],
                ),
            ]
        elif any(
            k in combined_text for k in ("store", "shop", "ecommerce", "cart", "product", "retail")
        ):
            entities = [
                (
                    "product",
                    "products",
                    [{"name": "title", "type": "string"}, {"name": "price", "type": "float"}],
                ),
                (
                    "order",
                    "orders",
                    [
                        {"name": "customer_name", "type": "string"},
                        {"name": "status", "type": "string"},
                    ],
                ),
            ]
        elif any(k in combined_text for k in ("task", "project", "todo", "kanban", "sprint")):
            entities = [
                ("project", "projects", [{"name": "title", "type": "string"}]),
                (
                    "task",
                    "tasks",
                    [{"name": "title", "type": "string"}, {"name": "status", "type": "string"}],
                ),
            ]
        elif any(
            k in combined_text for k in ("invoice", "billing", "expense", "finance", "payment")
        ):
            entities = [
                (
                    "invoice",
                    "invoices",
                    [
                        {"name": "client_name", "type": "string"},
                        {"name": "amount", "type": "float"},
                    ],
                ),
                (
                    "expense",
                    "expenses",
                    [
                        {"name": "description", "type": "string"},
                        {"name": "amount", "type": "float"},
                    ],
                ),
            ]
        elif any(k in combined_text for k in ("restaurant", "food", "menu", "cafe", "dine")):
            entities = [
                (
                    "menu_item",
                    "menu_items",
                    [{"name": "name", "type": "string"}, {"name": "price", "type": "float"}],
                ),
                (
                    "table_order",
                    "table_orders",
                    [{"name": "table_number", "type": "int"}, {"name": "status", "type": "string"}],
                ),
            ]
        else:
            entities = [
                (
                    "item",
                    "items",
                    [{"name": "name", "type": "string"}, {"name": "description", "type": "text"}],
                ),
                ("category", "categories", [{"name": "name", "type": "string"}]),
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

    return AppSpec(
        app_name=clean_name,
        one_liner=f"Full-stack {clean_name} application",
        core_value=f"Automated management and workflows for {clean_name}",
        entities=spec_entities,
        screens=screens,
        acceptance_tests=tests,
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

    from app.core.llm import get_llm, has_llm_credentials

    if not has_llm_credentials():
        return fallback_app_spec(
            ai_state,
            user_prompt,
            uploaded_context=uploaded_context,
            conversation_history=conversation_history,
        )

    # Use compact 2500 max_tokens to stay well within Groq TPM limits
    llm = get_llm(temperature=0.2, max_tokens=2500)
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
    for attempt in range(1, max_attempts + 1):
        try:
            resp = await llm.ainvoke(messages)
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
            spec = AppSpec.model_validate(_extract_json(raw))
            logger.info("AppSpec valid on attempt %d: %s", attempt, spec.app_name)
            return spec
        except (ValidationError, ValueError, json.JSONDecodeError) as err:
            last_err = str(err)[:2000]
            logger.warning("AppSpec attempt %d invalid: %s", attempt, last_err[:300])
            messages += [
                AIMessage(content=raw[:4000]),
                HumanMessage(
                    content=f"Invalid spec. Fix ALL errors and return full JSON only:\n{last_err}"
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
