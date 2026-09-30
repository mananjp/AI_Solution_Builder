"""Show what a user actually receives for a typical prompt."""

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(BACKEND))

from app.services.app_spec import fallback_app_spec  # noqa: E402

PROMPTS = [
    "Build me a gym membership management system with members, trainers, classes and subscriptions",
    "I need an inventory management system for a warehouse with products, suppliers and stock movements",
    "Create a clinic appointment booking system with patients, doctors and appointments",
]

for prompt in PROMPTS:
    spec = fallback_app_spec({}, prompt)
    print("=" * 70)
    print("PROMPT:", prompt)
    print("app_name:", spec.app_name)
    print("entities:", [(e.name, e.plural, [f.name for f in e.fields]) for e in spec.entities])
    print("screens:", [(s.name, s.route, s.uses_entities) for s in spec.screens])
    print("actions:", [a.name for a in spec.actions])
    print("one_liner:", spec.one_liner)
    print("core_value:", spec.core_value)
