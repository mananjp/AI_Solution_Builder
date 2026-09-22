"""
AI Solution Builder — Multilingual Pipeline (Section 10)

Three-stage localization: language detection on inbound prompts/documents,
translation of generated replies into the caller's language, and a consistent
X-Content-Language response header used by the frontend to render i18n labels.

Best-effort and fail-open: missing libs, empty text, or an unavailable
translation provider falls back to the source text / default language.
"""

import logging
import re

from app.core.config import settings

logger = logging.getLogger(__name__)

# BCP 47-style codes normalized lowercase; zh-cn/zh-tw collapse to zh
SUPPORTED_LANGUAGES = {
    # Core & Western
    "en",
    "es",
    "fr",
    "de",
    "pt",
    "it",
    "nl",
    "ru",
    # Indic Languages
    "hi",
    "gu",
    "mr",
    "bn",
    "ta",
    "te",
    "kn",
    "ml",
    "pa",
    "ur",
    "or",
    "as",
    # Asian & Middle Eastern
    "ja",
    "ko",
    "zh",
    "ar",
    "fa",
    "he",
    "id",
    "vi",
    "tr",
}

RTL_LANGUAGES = {"ar", "ur", "fa", "he"}


def is_rtl(code: str) -> bool:
    """Return True if the language uses a right-to-left script."""
    raw = (code or "").strip().lower().split("-")[0].split("_")[0]
    if raw in RTL_LANGUAGES:
        return True
    norm = normalize_language_code(code, default="en")
    return norm in RTL_LANGUAGES


_LANG_RE = re.compile(r"^([a-z]{2,3})(?:[-_]([a-z0-9]{2,8}))?(?:;q=[0-9.]+)?$", re.IGNORECASE)


def normalize_language_code(code: str, default: str | None = None) -> str:
    """Normalize a BCP47/header fragment to our short-code set.

    When ``default`` is ``None`` (or omitted) the app default language is
    returned for empty/unsupported input; pass ``default=""`` to distinguish
    "no language specified" from the app default.
    """
    if not code:
        return default if default is not None else settings.DEFAULT_LANGUAGE

    match = _LANG_RE.match(code.strip())
    if not match:
        return default if default is not None else settings.DEFAULT_LANGUAGE

    primary = match.group(1).lower()
    if primary == "zh":
        return "zh"
    if primary in SUPPORTED_LANGUAGES:
        return primary
    return default if default is not None else settings.DEFAULT_LANGUAGE


def detect_language(text: str, default: str = "") -> str:
    """Detect the dominant language of text using langdetect (best-effort)."""
    fallback = default or settings.DEFAULT_LANGUAGE
    if not text or not text.strip():
        return fallback
    try:
        from langdetect import detect

        return normalize_language_code(detect(text), fallback)
    except Exception as err:  # LangDetectException on ambiguous/short input
        logger.debug("Language detection failed for %d chars: %s", len(text), err)
        return fallback


def pick_best_language(
    accept_language: str, x_content_language: str, source_text: str, default: str = ""
) -> str:
    """Reconcile the caller's preferred language with the request content.

    Explicit X-Content-Language wins over Accept-Language; if neither is a
    supported code, fall back to detecting the dominant language of the
    source text (which may be a user-supplied document/reply).
    """
    explicit = normalize_language_code(x_content_language, "")
    if explicit:
        return explicit

    hinted = normalize_language_code(accept_language, "")
    detected = detect_language(source_text, "")
    return hinted or detected or default or settings.DEFAULT_LANGUAGE


async def translate_text(text: str, target_lang: str) -> str:
    """Translate generated content into the target language (fail-open).

    Returns the original text when translation is disabled, the target is
    English/default, content is empty, or no live LLM credentials exist.
    """
    if not settings.TRANSLATION_ENABLED:
        return text
    if not text or not text.strip():
        return text
    if target_lang in ("", settings.DEFAULT_LANGUAGE):
        return text

    if settings.LLM_PROVIDER.lower() == "mock":
        return text

    from app.core.llm import get_llm, has_llm_credentials

    # Deterministic offline provider cannot translate meaningfully.
    if not has_llm_credentials():
        return text

    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = get_llm(temperature=0, max_tokens=4000)
        prompt = SystemMessage(
            content=(
                "You are a professional translator. Translate the text between the markers "
                f"into {target_lang}. Preserve technical terms, field names, and code "
                "unchanged. Output only the translation, no commentary, no quotes."
            )
        )
        result = await llm.ainvoke([prompt, HumanMessage(content=text)])
        translated = str(getattr(result, "content", "")).strip()
        if translated:
            return translated
    except Exception as err:
        logger.warning("Translation to %s failed: %s", target_lang, err)

    return text
