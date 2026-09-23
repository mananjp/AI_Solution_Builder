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

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        if not _SNAKE.match(v) or v in RESERVED:
            raise ValueError(f"field name '{v}' must be snake_case and not reserved")
        return v

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

    @field_validator("name", "plural")
    @classmethod
    def _snake(cls, v: str) -> str:
        if not _SNAKE.match(v) or v in RESERVED:
            raise ValueError(f"'{v}' must be snake_case")
        return v


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

    @field_validator("path")
    @classmethod
    def _path(cls, v: str) -> str:
        if not v.startswith("/actions/"):
            raise ValueError("action path must start with /actions/")
        return v


class Screen(BaseModel):
    name: str
    route: str  # Next.js route, "/" allowed
    purpose: str
    uses_entities: list[str] = Field(default_factory=list)
    uses_actions: list[str] = Field(default_factory=list)
    key_interactions: list[str] = Field(min_length=1)


class TestStep(BaseModel):
    method: Literal["GET", "POST", "PATCH", "DELETE"]
    path: str  # may contain {var} saved by earlier steps
    body: dict[str, Any] | None = None
    expect_status: int = 200
    expect: dict[str, Any] = Field(default_factory=dict)  # subset match; dotted keys allowed
    save: dict[str, str] = Field(default_factory=dict)  # var -> dotted key in response


class AcceptanceTest(BaseModel):
    name: str
    description: str
    steps: list[TestStep] = Field(min_length=1, max_length=15)

    @field_validator("name")
    @classmethod
    def _n(cls, v: str) -> str:
        return re.sub(r"[^a-z0-9_]+", "_", v.lower()).strip("_")[:60] or "scenario"


class AppSpec(BaseModel):
    app_name: str
    one_liner: str
    core_value: str = Field(description="What the app DOES that plain CRUD would not")
    assumptions: list[str] = Field(default_factory=list)
    entities: list[Entity] = Field(min_length=1, max_length=6)
    actions: list[Action] = Field(default_factory=list, max_length=8)
    screens: list[Screen] = Field(min_length=1, max_length=6)
    acceptance_tests: list[AcceptanceTest] = Field(min_length=3, max_length=10)

    @model_validator(mode="after")
    def _cross_refs(self) -> AppSpec:
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
            errors.append(f"actions without acceptance tests: {sorted(missing)}")
        if errors:
            raise ValueError("; ".join(errors))
        return self


# ── LLM generation ──────────────────────────────────────────────────────

SPEC_SYSTEM = """You design SMALL but REAL working apps. Output ONLY JSON matching the schema.

Hard rules:
- Model the user's ACTUAL app. Do not default to a generic 'items/status' CRUD app.
- Put the real logic in `actions` (calculations, state transitions, validation, conflict
  checks, aggregation). Each action has precise `rules` a developer can implement
  without guessing (formulas, edge cases, error codes: 400 invalid, 404 missing, 409 conflict).
- If the app is genuinely pure CRUD, actions may be empty, but core_value must say so.
- Entities: 1–6. Fields snake_case; refs are `<entity>_id` with type "ref".
- REST conventions that ALREADY exist for every entity (do not list them as actions):
  GET/POST /{plural}, GET/PATCH/DELETE /{plural}/{id}, GET /{plural}?<ref_field>=<id>.
  IDs are integers. Responses of CRUD = the object JSON (with "id").
- acceptance_tests: 3–10 scenarios that PROVE the core value end-to-end via HTTP.
  Use `save` to capture ids, e.g. {"group_id": "id"}, then use "{group_id}" in later paths/bodies.
  Every action must be exercised by at least one test with a concrete numeric/string `expect`.
  Include at least one negative test (400/404/409).
- Keep it small: this is an MVP a single agent writes in one pass.
"""


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


def _context_from_state(ai_state: dict[str, Any], user_prompt: str) -> str:
    def content(key: str) -> Any:
        v = ai_state.get(key)
        return v.get("content") if isinstance(v, dict) else None

    parts = [
        f"USER REQUEST:\n{user_prompt or ai_state.get('user_message', '')}",
        f"BUSINESS: {ai_state.get('business_description', '')}",
        f"INDUSTRY: {ai_state.get('industry', '')}",
        f"CONFIRMED MODULES: {ai_state.get('confirmed_modules') or ai_state.get('identified_solutions') or []}",
    ]
    for key in ("er_diagram", "api_spec", "lld"):
        c = content(key)
        if c:
            parts.append(
                f"{key.upper()} (reference, simplify if too big):\n{json.dumps(c, default=str)[:3000]}"
            )
    return "\n\n".join(parts)


async def generate_app_spec(
    ai_state: dict[str, Any], user_prompt: str = "", *, max_attempts: int = 3
) -> AppSpec:
    """LLM → AppSpec with validation-error feedback loop. Raises SpecError (no fake fallback)."""
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    from app.core.llm import get_llm, has_llm_credentials

    if not has_llm_credentials():
        raise SpecError("No LLM credentials configured; cannot design an app spec.")

    llm = get_llm(temperature=0.2, max_tokens=6000)
    messages: list[Any] = [
        SystemMessage(content=SPEC_SYSTEM + "\nJSON schema:\n" + _spec_schema_hint()),
        HumanMessage(content=_context_from_state(ai_state, user_prompt)),
    ]
    last_err = ""
    for attempt in range(1, max_attempts + 1):
        resp = await llm.ainvoke(messages)
        raw = str(getattr(resp, "content", resp))
        try:
            spec = AppSpec.model_validate(_extract_json(raw))
            logger.info("AppSpec valid on attempt %d: %s", attempt, spec.app_name)
            return spec
        except (ValidationError, ValueError, json.JSONDecodeError) as err:
            last_err = str(err)[:2500]
            logger.warning("AppSpec attempt %d invalid: %s", attempt, last_err[:300])
            messages += [
                AIMessage(content=raw[:8000]),
                HumanMessage(
                    content=f"Invalid spec. Fix ALL errors and return full JSON only:\n{last_err}"
                ),
            ]
    raise SpecError(f"Could not produce a valid app spec: {last_err}")
