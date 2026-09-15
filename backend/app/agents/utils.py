"""
AI Solution Builder — Agent Utilities

Shared helpers for agent nodes: JSON parsing with truncation recovery.
"""

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def _try_parse_repaired(text: str) -> dict[str, Any] | None:
    """Try to parse a repaired JSON string. Returns dict or None."""
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def parse_llm_json(raw: str) -> dict[str, Any]:
    """Parse LLM JSON response with truncation recovery.

    If the JSON is truncated (common with token limits), attempt to recover
    by closing unclosed braces/brackets and trimming incomplete values.
    Handles XML content inside JSON strings (e.g. BPMN XML).
    """
    content = raw.strip()

    # Strip markdown code fences
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]

    content = content.strip()

    # Try direct parse first
    result = _try_parse_repaired(content)
    if result is not None:
        return result

    # Strategy 1: Close unclosed braces/brackets
    open_braces = content.count("{") - content.count("}")
    open_brackets = content.count("[") - content.count("]")

    if open_braces > 0 or open_brackets > 0:
        # Clean trailing incomplete tokens
        repaired = content.rstrip()
        repaired = re.sub(r',\s*$', '', repaired)
        repaired = re.sub(r':\s*$', '', repaired)
        # Remove trailing unterminated string (unclosed quote without closing quote)
        repaired = re.sub(r':\s*"[^"]*$', '', repaired)
        # Remove trailing partial key
        repaired = re.sub(r',\s*"[^"]*$', '', repaired)

        # Add closing brackets
        for _ in range(open_brackets):
            repaired += "]"
        for _ in range(open_braces):
            repaired += "}"

        result = _try_parse_repaired(repaired)
        if result is not None:
            logger.warning("JSON recovered via bracket repair (%d braces, %d brackets)",
                          open_braces, open_brackets)
            return result

    # Strategy 2: Walk backwards to find last valid closing brace
    stripped = content.rstrip()
    stripped = re.sub(r',\s*$', '', stripped)

    for i in range(len(stripped) - 1, -1, -1):
        if stripped[i] in ('}', ']'):
            candidate = stripped[:i + 1]
            ob = candidate.count("{") - candidate.count("}")
            oj = candidate.count("[") - candidate.count("]")
            # Remove any trailing partial key-value: find last complete value
            candidate = re.sub(r',\s*"[^"]*$', '', candidate)
            candidate = re.sub(r':\s*"[^"]*$', '', candidate)
            candidate = re.sub(r',\s*$', '', candidate)
            for _ in range(oj):
                candidate += "]"
            for _ in range(ob):
                candidate += "}"
            result = _try_parse_repaired(candidate)
            if result is not None:
                logger.warning("JSON recovered via rollback (kept %d/%d chars)", i + 1, len(content))
                return result

    logger.error("JSON truncation recovery failed for content of %d chars", len(raw))
    raise json.JSONDecodeError("Could not parse or recover truncated JSON", raw, 0)
