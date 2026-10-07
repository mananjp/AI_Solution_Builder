"""
AI Solution Builder — Conversational Build Agent

Turns the build from a one-shot "prompt in, app out" into a conversation:
the agent asks what it genuinely does not know, proposes a plan in plain
English, builds only after the user agrees, and then keeps taking change
requests against the live app.

The agent never answers in free text alone — every turn ends in exactly one
tool call, so the API layer always knows what state to move to:

    ask        -> we need an answer before we can build
    plan       -> here is what I'll build, in plain words; approve or adjust
    build      -> user approved; run the pipeline
    change     -> user wants the built app altered; apply to spec and rebuild
    answer     -> user asked a question; answer it, nothing changes

All user-visible strings pass through plain_language so a non-technical user
can follow the whole thing.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from app.services.plain_language import (
    describe_change,
    describe_data_loss,
    describe_spec,
    dejargon,
    lint_for_jargon,
)

logger = logging.getLogger(__name__)

MAX_QUESTIONS_PER_TURN = 3
MAX_QUESTION_ROUNDS = 3


class Stage(str, Enum):
    GATHERING = "gathering"  # still asking what we need to know
    PLAN_REVIEW = "plan_review"  # plan shown, waiting for approval
    BUILDING = "building"
    READY = "ready"  # app is built and live
    CHANGING = "changing"  # applying a post-build change


@dataclass
class Question:
    id: str
    question: str
    why: str  # plain-language reason this matters
    options: list[dict[str, str]] = field(default_factory=list)
    allow_custom: bool = True
    answer: str | None = None


@dataclass
class ConversationState:
    stage: Stage = Stage.GATHERING
    questions: list[Question] = field(default_factory=list)
    question_rounds: int = 0
    transcript: list[dict[str, str]] = field(default_factory=list)
    spec: dict[str, Any] | None = None
    approved_spec_hash: str | None = None
    build_number: int = 0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["stage"] = self.stage.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ConversationState:
        if not data:
            return cls()
        questions = [Question(**q) for q in data.get("questions", []) if isinstance(q, dict)]
        return cls(
            stage=Stage(data.get("stage", "gathering")),
            questions=questions,
            question_rounds=int(data.get("question_rounds", 0)),
            transcript=list(data.get("transcript", [])),
            spec=data.get("spec"),
            approved_spec_hash=data.get("approved_spec_hash"),
            build_number=int(data.get("build_number", 0)),
        )

    def answered(self) -> list[Question]:
        return [q for q in self.questions if q.answer]

    def pending(self) -> list[Question]:
        return [q for q in self.questions if not q.answer]


# ── Tool schema given to the model ──────────────────────────────────────

TOOLS: list[dict[str, Any]] = [
    {
        "name": "ask",
        "description": (
            "Ask the user up to 3 questions you genuinely cannot answer yourself and that "
            "would change what gets built. Never ask about technology choices, databases, "
            "hosting or frameworks — decide those yourself."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "questions": {
                    "type": "array",
                    "maxItems": MAX_QUESTIONS_PER_TURN,
                    "items": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string"},
                            "why": {
                                "type": "string",
                                "description": "Plain reason this changes the app.",
                            },
                            "options": {
                                "type": "array",
                                "maxItems": 4,
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "label": {"type": "string"},
                                        "description": {"type": "string"},
                                    },
                                    "required": ["label"],
                                },
                            },
                        },
                        "required": ["question", "why"],
                    },
                }
            },
            "required": ["questions"],
        },
    },
    {
        "name": "plan",
        "description": (
            "Propose the complete app design. Call this once you know enough to build "
            "something genuinely useful. The spec must contain real business rules, not CRUD."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "spec": {"type": "object", "description": "A complete AppSpec JSON object."},
                "note": {
                    "type": "string",
                    "description": "One friendly sentence introducing the plan.",
                },
            },
            "required": ["spec"],
        },
    },
    {
        "name": "change",
        "description": (
            "The user asked for something different about an app that already exists. "
            "Return the FULL updated spec with the change applied."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "spec": {"type": "object", "description": "The complete updated AppSpec JSON."},
                "note": {"type": "string", "description": "What you changed, in plain words."},
            },
            "required": ["spec", "note"],
        },
    },
    {
        "name": "answer",
        "description": "The user asked a question. Answer it. Nothing about the app changes.",
        "input_schema": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
    },
]


SYSTEM_PROMPT = """You help someone build a working web app by talking to them. \
Assume they run a business and have never written code.

HOW YOU TALK
- Plain everyday words. Never say: entity, schema, API, endpoint, CRUD, backend, \
frontend, deploy, boolean, enum, database table, foreign key, framework names.
- Say what the app DOES for them: "it works out who owes what", "it stops two \
people booking the same slot".
- Short sentences. No bullet soup. Never show code, file names or routes.

WHAT TO ASK
- Only ask what genuinely changes the app and that you cannot reasonably decide \
or assume yourself. Maximum 3 questions at a time, and prefer 1-2.
- Good questions are about their business: what they sell, who uses it, what \
should happen when something goes wrong, what the rules are.
- NEVER ask which database, language, hosting, styling or framework to use. \
Decide all of that silently.
- If they already told you something, do not ask again. If they say "you decide" \
or "keep it simple", stop asking and make sensible choices, recording them as assumptions.
- After at most {max_rounds} rounds of questions you must produce a plan.

WHAT YOU BUILD
- The app must actually do its job, not just store records. The `actions` in the \
spec hold the real work: calculations, availability checks, status rules, totals, \
validation. Each action needs precise rules a developer could follow with no guessing.
- Write acceptance tests that prove the real job gets done, with concrete numbers.
- An app that only lists and edits records is a failure unless the user truly asked \
for nothing more.

YOUR REPLY
Always end your turn with exactly one tool call. Never reply with text only.
"""


# ── Model plumbing ──────────────────────────────────────────────────────


def _messages_from_state(state: ConversationState, user_message: str) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for turn in state.transcript[-20:]:
        role = turn.get("role")
        content = str(turn.get("content", ""))
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    context_parts: list[str] = []
    if state.answered():
        answered = "\n".join(f"- {q.question} -> {q.answer}" for q in state.answered())
        context_parts.append(f"Already answered by the user:\n{answered}")
    if state.spec and state.stage in (Stage.READY, Stage.CHANGING, Stage.PLAN_REVIEW):
        context_parts.append(
            "The current app design (JSON) is below. For a change request, return this "
            "same structure with the change applied:\n" + json.dumps(state.spec)[:12000]
        )
    if state.question_rounds >= MAX_QUESTION_ROUNDS:
        context_parts.append(
            "You have used all your question rounds. Do not call `ask` again — produce a plan."
        )

    if context_parts:
        messages.append({"role": "user", "content": "\n\n".join(context_parts)})
    messages.append({"role": "user", "content": user_message})
    return messages


async def _call_model(state: ConversationState, user_message: str) -> tuple[str, dict[str, Any]]:
    """Ask the model for its next move. Returns (tool_name, tool_input)."""
    from app.core.llm import get_llm, has_llm_credentials

    if not has_llm_credentials():
        raise RuntimeError("No AI credentials are configured, so I can't design your app.")

    llm = get_llm(temperature=0.3, max_tokens=8000)
    system = SYSTEM_PROMPT.format(max_rounds=MAX_QUESTION_ROUNDS)
    messages = _messages_from_state(state, user_message)

    bound = llm.bind_tools(TOOLS) if hasattr(llm, "bind_tools") else None
    if bound is not None:
        from langchain_core.messages import HumanMessage, SystemMessage

        payload: list[Any] = [SystemMessage(content=system)]
        for message in messages:
            payload.append(HumanMessage(content=message["content"]))
        response = await bound.ainvoke(payload)
        calls = getattr(response, "tool_calls", None) or []
        if calls:
            call = calls[0]
            return str(call.get("name")), dict(call.get("args") or {})
        # Model replied with prose despite the instruction — treat it as an answer.
        return "answer", {"message": str(getattr(response, "content", "")).strip()}

    # Fallback for providers without tool binding: ask for a JSON envelope.
    from langchain_core.messages import HumanMessage, SystemMessage

    envelope = (
        system
        + "\n\nReturn ONLY JSON: {\"tool\": \"ask|plan|change|answer\", \"input\": {...}}"
        + "\nTool inputs:\n"
        + json.dumps({t["name"]: t["input_schema"] for t in TOOLS})[:4000]
    )
    payload = [SystemMessage(content=envelope)] + [
        HumanMessage(content=m["content"]) for m in messages
    ]
    response = await llm.ainvoke(payload)
    raw = str(getattr(response, "content", response))
    data = _extract_json(raw)
    return str(data.get("tool", "answer")), dict(data.get("input") or {})


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.S)
    if fenced:
        cleaned = fenced.group(1)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < 0:
        return {"tool": "answer", "input": {"message": text}}
    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return {"tool": "answer", "input": {"message": text}}


# ── Guard rails on what the user sees ───────────────────────────────────

# Questions a non-technical user cannot answer and we must never ask.
_FORBIDDEN_QUESTION = re.compile(
    r"\b(database|postgres|sqlite|mysql|framework|react|next\.?js|fastapi|python|typescript"
    r"|host(ing)?|vercel|render|aws|docker|repo(sitory)?|api|rest|graphql|auth(entication)?"
    r"|jwt|oauth|schema|stack|library|deploy)\b",
    re.IGNORECASE,
)


def is_answerable_by_layman(question: str) -> bool:
    """False for questions only a developer could answer."""
    return not _FORBIDDEN_QUESTION.search(question or "")


def clean_user_text(text: str) -> str:
    """Last line of defence before any string reaches the user."""
    cleaned = dejargon(text or "")
    hits = lint_for_jargon(cleaned)
    if hits:
        logger.info(
            "Jargon survived in user-facing copy: %s", [h.term for h in hits][:5]
        )
    return cleaned


def _clean_questions(raw: list[dict[str, Any]]) -> list[Question]:
    questions: list[Question] = []
    for item in raw[:MAX_QUESTIONS_PER_TURN]:
        if not isinstance(item, dict):
            continue
        text = str(item.get("question", "")).strip()
        if not text or not is_answerable_by_layman(text):
            logger.info("Dropped developer-only question: %s", text[:120])
            continue
        options = [
            {
                "label": str(o.get("label", "")).strip(),
                "description": clean_user_text(str(o.get("description", ""))),
            }
            for o in (item.get("options") or [])
            if isinstance(o, dict) and str(o.get("label", "")).strip()
        ]
        questions.append(
            Question(
                id=uuid.uuid4().hex[:8],
                question=clean_user_text(text),
                why=clean_user_text(str(item.get("why", ""))),
                options=options[:4],
            )
        )
    return questions


# ── The turn handler the API calls ──────────────────────────────────────


@dataclass
class TurnResult:
    """What the API layer should do next, plus what to show the user."""

    kind: str  # ask | plan | build | change | answer
    message: str  # plain-language text for the user
    state: ConversationState
    questions: list[Question] = field(default_factory=list)
    spec: Any = None  # AppSpec when kind is plan/change
    plain_plan: str = ""
    changes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "message": self.message,
            "questions": [asdict(q) for q in self.questions],
            "plain_plan": self.plain_plan,
            "changes": self.changes,
            "warnings": self.warnings,
            "stage": self.state.stage.value,
        }


_APPROVALS = {
    "yes", "yep", "yeah", "ok", "okay", "sure", "go", "go ahead", "build", "build it",
    "build it now", "do it", "make it", "proceed", "confirm", "confirmed", "looks good",
    "sounds good", "perfect", "great", "approve", "approved", "start", "lgtm", "fine",
    "haan", "ha", "theek hai", "ho ja", "banao", "kar do",
}


def _is_approval(message: str) -> bool:
    cleaned = re.sub(r"[^a-z\s]", "", (message or "").lower()).strip()
    if not cleaned:
        return False
    if cleaned in _APPROVALS:
        return True
    words = cleaned.split()
    return len(words) <= 4 and any(w in _APPROVALS for w in words)


def record_answers(state: ConversationState, answers: dict[str, str]) -> ConversationState:
    """Attach the user's answers to the questions they belong to."""
    for question in state.questions:
        if question.id in answers and str(answers[question.id]).strip():
            question.answer = str(answers[question.id]).strip()
    return state


async def handle_turn(
    state: ConversationState,
    user_message: str,
    *,
    ai_state: dict[str, Any] | None = None,
    answers: dict[str, str] | None = None,
) -> TurnResult:
    """Advance the conversation by one user turn.

    The caller persists `result.state`, shows `result.message`, and when
    `result.kind == "build"` runs the build pipeline with `result.spec`.
    """
    from app.services.app_spec import AppSpec

    if answers:
        record_answers(state, answers)
    if user_message:
        state.transcript.append({"role": "user", "content": user_message})

    # Approving a plan needs no model call — go straight to building.
    if state.stage == Stage.PLAN_REVIEW and _is_approval(user_message) and state.spec:
        spec = AppSpec.model_validate(state.spec)
        state.stage = Stage.BUILDING
        message = "Great — I'm building it now. This takes a few minutes."
        state.transcript.append({"role": "assistant", "content": message})
        return TurnResult(
            kind="build", message=message, state=state, spec=spec,
            plain_plan=describe_spec(spec),
        )

    tool, payload = await _call_model(state, user_message)

    if tool == "ask":
        questions = _clean_questions(list(payload.get("questions") or []))
        if not questions:
            # Every question was unusable; push the model to plan instead.
            state.question_rounds = MAX_QUESTION_ROUNDS
            return await handle_turn(
                state,
                "Please stop asking and show me the plan, making sensible choices yourself.",
                ai_state=ai_state,
            )
        state.questions.extend(questions)
        state.question_rounds += 1
        state.stage = Stage.GATHERING
        lead = (
            "Before I build this, a couple of things would really change the result:"
            if len(questions) > 1
            else "One thing would really change the result:"
        )
        state.transcript.append({"role": "assistant", "content": lead})
        return TurnResult(kind="ask", message=lead, state=state, questions=questions)

    if tool in ("plan", "change"):
        try:
            spec = AppSpec.model_validate(payload.get("spec") or {})
        except Exception as exc:
            logger.warning("Model returned an invalid spec: %s", exc)
            retry = (
                "That design didn't hold together. Fix these problems and send the whole "
                f"design again: {exc}"
            )
            tool, payload = await _call_model(state, retry)
            spec = AppSpec.model_validate(payload.get("spec") or {})

        old_spec = None
        if state.spec:
            try:
                old_spec = AppSpec.model_validate(state.spec)
            except Exception:
                old_spec = None

        plain_plan = describe_spec(spec)
        note = clean_user_text(str(payload.get("note", "")))

        if tool == "change" and old_spec is not None:
            changes = describe_change(old_spec, spec)
            warnings = describe_data_loss(old_spec, spec)
            state.spec = spec.model_dump()
            state.stage = Stage.BUILDING
            message = note or "Here's what I'm changing:"
            state.transcript.append({"role": "assistant", "content": message})
            return TurnResult(
                kind="change", message=message, state=state, spec=spec,
                plain_plan=plain_plan, changes=changes, warnings=warnings,
            )

        state.spec = spec.model_dump()
        state.stage = Stage.PLAN_REVIEW
        message = note or "Here's what I'm going to build for you."
        state.transcript.append({"role": "assistant", "content": message})
        return TurnResult(
            kind="plan", message=message, state=state, spec=spec, plain_plan=plain_plan,
        )

    message = clean_user_text(str(payload.get("message", "")))
    state.transcript.append({"role": "assistant", "content": message})
    return TurnResult(kind="answer", message=message, state=state)
