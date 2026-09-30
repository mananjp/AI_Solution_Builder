"""Replace the keyword cascade in fallback_app_spec with a lexicon call."""

from pathlib import Path

P = Path("backend/app/services/app_spec.py")
lines = P.read_text(encoding="utf-8").split("\n")

# 1-indexed 499..651 inclusive -> 0-indexed 498..650
start = 498
end = 651  # exclusive slice end (line 651 is last replaced line)

assert lines[start].strip() == "if not entities:", lines[start]
assert lines[end - 1].strip() == "]", repr(lines[end - 1])

replacement = '''    if not entities:
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
        ]'''.split("\n")

out = lines[:start] + replacement + lines[end:]
P.write_text("\n".join(out), encoding="utf-8")
print("replaced; new length", len(out))
