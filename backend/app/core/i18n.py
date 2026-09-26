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

# Mapping of 3-letter ISO 639 codes and common language names to 2-letter canonical codes
LANGUAGE_ALIASES: dict[str, str] = {
    # 3-letter codes
    "guj": "gu",
    "hin": "hi",
    "eng": "en",
    "mar": "mr",
    "ben": "bn",
    "tam": "ta",
    "tel": "te",
    "kan": "kn",
    "mal": "ml",
    "pan": "pa",
    "urd": "ur",
    "ori": "or",
    "asm": "as",
    "spa": "es",
    "fra": "fr",
    "fre": "fr",
    "deu": "de",
    "ger": "de",
    "por": "pt",
    "ita": "it",
    "rus": "ru",
    "jpn": "ja",
    "kor": "ko",
    "zho": "zh",
    "chi": "zh",
    "ara": "ar",
    # Full names
    "gujarati": "gu",
    "hindi": "hi",
    "english": "en",
    "marathi": "mr",
    "bengali": "bn",
    "bangla": "bn",
    "tamil": "ta",
    "telugu": "te",
    "kannada": "kn",
    "malayalam": "ml",
    "punjabi": "pa",
    "urdu": "ur",
    "odia": "or",
    "oriya": "or",
    "assamese": "as",
    "spanish": "es",
    "french": "fr",
    "german": "de",
    "portuguese": "pt",
    "italian": "it",
    "russian": "ru",
    "japanese": "ja",
    "korean": "ko",
    "chinese": "zh",
    "arabic": "ar",
}

# Full language names for prompting LLMs and UI display
LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "gu": "Gujarati (ગુજરાતી)",
    "hi": "Hindi (हिन्दी)",
    "mr": "Marathi (मराठी)",
    "bn": "Bengali (বাংলা)",
    "ta": "Tamil (தமிழ்)",
    "te": "Telugu (తెలుగు)",
    "kn": "Kannada (ಕನ್ನಡ)",
    "ml": "Malayalam (മലയാളം)",
    "pa": "Punjabi (ਪੰਜਾਬੀ)",
    "ur": "Urdu (اردو)",
    "or": "Odia (ଓଡ଼ିଆ)",
    "as": "Assamese (অসমীয়া)",
    "es": "Spanish (Español)",
    "fr": "French (Français)",
    "de": "German (Deutsch)",
    "pt": "Portuguese (Português)",
    "it": "Italian (Italiano)",
    "nl": "Dutch (Nederlands)",
    "ru": "Russian (Русский)",
    "ja": "Japanese (日本語)",
    "ko": "Korean (한국어)",
    "zh": "Chinese (中文)",
    "ar": "Arabic (العربية)",
    "fa": "Persian (فارسی)",
    "he": "Hebrew (עברית)",
    "id": "Indonesian (Bahasa Indonesia)",
    "vi": "Vietnamese (Tiếng Việt)",
    "tr": "Turkish (Türkçe)",
}


def normalize_language_code(code: str, default: str | None = None) -> str:
    """Normalize a BCP47/ISO 639-1/2/3 fragment to our canonical short-code set.

    When ``default`` is ``None`` (or omitted) the app default language is
    returned for empty/unsupported input; pass ``default=""`` to distinguish
    "no language specified" from the app default.
    """
    if not code:
        return default if default is not None else settings.DEFAULT_LANGUAGE

    cleaned = code.strip().lower()
    if cleaned in LANGUAGE_ALIASES:
        return LANGUAGE_ALIASES[cleaned]
    if cleaned in SUPPORTED_LANGUAGES:
        return cleaned

    match = _LANG_RE.match(cleaned)
    if not match:
        return default if default is not None else settings.DEFAULT_LANGUAGE

    primary = match.group(1).lower()
    if primary in LANGUAGE_ALIASES:
        return LANGUAGE_ALIASES[primary]
    if primary == "zh":
        return "zh"
    if primary in SUPPORTED_LANGUAGES:
        return primary
    return default if default is not None else settings.DEFAULT_LANGUAGE


def detect_indic_script(text: str) -> str:
    """Deterministic script identification for Indic languages via Unicode ranges.

    Returns the canonical language code (e.g. 'gu', 'hi', 'bn', 'ta', 'te', 'mr')
    or empty string if no Indic script is detected.
    """
    if not text:
        return ""

    counts: dict[str, int] = {
        "gu": 0,  # 0x0A80 - 0x0AFF Gujarati
        "dev": 0,  # 0x0900 - 0x097F Devanagari (Hindi / Marathi)
        "bn": 0,  # 0x0980 - 0x09FF Bengali / Assamese
        "pa": 0,  # 0x0A00 - 0x0A7F Gurmukhi (Punjabi)
        "or": 0,  # 0x0B00 - 0x0B7F Odia
        "ta": 0,  # 0x0B80 - 0x0BFF Tamil
        "te": 0,  # 0x0C00 - 0x0C7F Telugu
        "kn": 0,  # 0x0C80 - 0x0CFF Kannada
        "ml": 0,  # 0x0D00 - 0x0D7F Malayalam
        "ur": 0,  # 0x0600 - 0x06FF / 0x0750 - 0x077F Arabic/Urdu
    }

    marathi_markers = 0
    assamese_markers = 0

    for ch in text:
        cp = ord(ch)
        if 0x0A80 <= cp <= 0x0AFF:
            counts["gu"] += 1
        elif 0x0900 <= cp <= 0x097F:
            counts["dev"] += 1
            if cp == 0x0933:  # ळ (Marathi LLA)
                marathi_markers += 1
        elif 0x0980 <= cp <= 0x09FF:
            counts["bn"] += 1
            if cp in (0x09F0, 0x09F1):  # Assamese Ra / Wa
                assamese_markers += 1
        elif 0x0A00 <= cp <= 0x0A7F:
            counts["pa"] += 1
        elif 0x0B00 <= cp <= 0x0B7F:
            counts["or"] += 1
        elif 0x0B80 <= cp <= 0x0BFF:
            counts["ta"] += 1
        elif 0x0C00 <= cp <= 0x0C7F:
            counts["te"] += 1
        elif 0x0C80 <= cp <= 0x0CFF:
            counts["kn"] += 1
        elif 0x0D00 <= cp <= 0x0D7F:
            counts["ml"] += 1
        elif 0x0600 <= cp <= 0x06FF or 0x0750 <= cp <= 0x077F:
            counts["ur"] += 1

    # Find the dominant script with at least 2 characters (or 1 for very short words)
    best_script, count = max(counts.items(), key=lambda item: item[1])
    if count == 0:
        return ""

    if best_script == "dev":
        # Disambiguate Hindi vs Marathi
        if marathi_markers > 0:
            return "mr"
        # Check common Marathi words
        lower_t = text.lower()
        if any(w in lower_t for w in ("आहे", "नाही", "करा", "माझे", "तुमचे", "पाहिजे", "झाले")):
            return "mr"
        return "hi"

    if best_script == "bn":
        if assamese_markers > 0:
            return "as"
        return "bn"

    return best_script


def detect_language(text: str, default: str = "") -> str:
    """Detect the dominant language of text using deterministic Unicode script first, then langdetect."""
    fallback = default or settings.DEFAULT_LANGUAGE
    if not text or not text.strip():
        return fallback

    # 1. Deterministic Indic & non-Latin script check (instant, zero failure rate)
    indic = detect_indic_script(text)
    if indic:
        return normalize_language_code(indic, fallback)

    # 2. Statistical detection for Latin/other scripts via langdetect
    try:
        from langdetect import detect

        detected = detect(text)
        return normalize_language_code(detected, fallback)
    except Exception as err:
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

    # If the user typed in a distinct native script (e.g. Gujarati or Devanagari),
    # prioritize that over a generic browser Accept-Language header (e.g. en-US).
    script_detected = detect_indic_script(source_text)
    if script_detected:
        return script_detected

    hinted = normalize_language_code(accept_language, "")
    detected = detect_language(source_text, "")
    return hinted or detected or default or settings.DEFAULT_LANGUAGE


async def translate_text(text: str, target_lang: str) -> str:
    """Translate generated content into the target language (fail-open).

    Returns the original text when translation is disabled, the target is
    English/default, content is empty, or no live LLM credentials exist.
    """
    target = normalize_language_code(target_lang, "")
    if not settings.TRANSLATION_ENABLED:
        return text
    if not text or not text.strip():
        return text
    if target in ("", settings.DEFAULT_LANGUAGE):
        return text

    if settings.LLM_PROVIDER.lower() == "mock":
        return text

    from app.core.llm import get_llm, has_llm_credentials

    # Deterministic offline provider cannot translate meaningfully.
    if not has_llm_credentials():
        return text

    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        target_name = LANGUAGE_NAMES.get(target, target)
        llm = get_llm(temperature=0, max_tokens=4000)
        prompt = SystemMessage(
            content=(
                f"You are a professional software translator. Translate the text into {target_name}. "
                "Preserve all markdown formatting, technical terms, code blocks, JSON structures, "
                "variable names, table names, API paths, and punctuation unchanged. "
                "Output only the direct translation with no meta-commentary, notes, or quotes."
            )
        )
        result = await llm.ainvoke([prompt, HumanMessage(content=text)])
        translated = str(getattr(result, "content", "")).strip()
        if translated:
            return translated
    except Exception as err:
        logger.warning("Translation to %s failed: %s", target, err)

    return text
