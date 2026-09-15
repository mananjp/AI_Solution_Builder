"""
AI Solution Builder — Input Sanitization & Prompt Injection Prevention

Provides comprehensive input validation, content filtering, and prompt
injection detection for all user-facing endpoints.
"""

import re
import hashlib
from typing import Optional


# ── Limits ──────────────────────────────────────────
MAX_MESSAGE_LENGTH = 10_000
MAX_URL_LENGTH = 2_048
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
MAX_FILENAME_LENGTH = 255
MAX_SEARCH_QUERY_LENGTH = 500

# ── Prompt Injection Patterns ───────────────────────
# Common jailbreak and injection attempts
_INJECTION_PATTERNS = [
    # Direct instruction override
    r"(?i)ignore\s+(all\s+)?(previous|prior|above|earlier|preceding)\s+(instructions?|prompts?|rules?|constraints?)",
    r"(?i)disregard\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?)",
    r"(?i)forget\s+(everything|all|your)\s+(you|were|have been)\s+(told|instructed|programmed)",
    r"(?i)override\s+(your|the|all)\s+(safety|instructions?|rules?|constraints?|guidelines?)",
    r"(?i)break\s+(out|free|through)\s+(of|from)\s+(your|the)\s+(instructions?|rules?|constraints?)",
    
    # Role manipulation
    r"(?i)you\s+are\s+now\s+(?:a|an|the)\s+\w+",
    r"(?i)act\s+as\s+(?:a|an|the)\s+\w+",
    r"(?i)pretend\s+(?:you|to)\s+(?:are|be|have)\s+",
    r"(?i)role\s*play\s+(?:as|being)\s+",
    r"(?i)from\s+now\s+on\s+you\s+(?:are|will|should|must)",
    r"(?i)new\s+(instructions?|role|persona|identity)",
    
    # System prompt extraction
    r"(?i)what\s+(?:are|is)\s+your\s+(?:system\s+)?(instructions?|prompts?|rules?|guidelines?)",
    r"(?i)show\s+(?:me\s+)?your\s+(?:system\s+)?(instructions?|prompts?|rules?|code)",
    r"(?i)reveal\s+(?:your\s+)?(system\s+)?(instructions?|prompts?|rules?|programming)",
    r"(?i)print\s+(?:your\s+)?(system\s+)?(instructions?|prompts?|rules?|message)",
    r"(?i)output\s+(?:your\s+)?(system\s+)?(instructions?|prompts?|rules?|template)",
    r"(?i)repeat\s+(?:everything|all|your)\s+(from|in)\s+(?:the\s+)?(?:system|initial)\s+(message|prompt|instruction)",
    
    # Encoded/obfuscated attacks
    r"(?i)base64\s*(?:decode|encode)",
    r"(?i)rot13\s*(?:decode|encode)",
    r"(?i)hex\s*(?:decode|encode)",
    r"(?i)reverse\s*(?:this|text|string|input)",
    
    # Data exfiltration
    r"(?i)(?:send|transmit|upload|exfiltrate|email)\s+(?:all\s+)?(?:the\s+)?(?:data|information|secrets?|keys?|tokens?|passwords?)",
    r"(?i)(?:copy|steal|extract)\s+(?:all\s+)?(?:user\s+)?(?:data|information|records?|secrets?)",
    
    # Multi-language injection
    r"(?i)ignor(?:ar|er|ez)\s+(?:las?\s+)?(?:instrucciones?|antérieures?|vorherigen?)",
    r"(?i)oublie(?:z|s)?\s+(?:tout|alles|alles)",
    
    # Delimiter injection
    r"(?:<\|im_start\|>|<\|im_end\|>|<\|system\|>|<\|user\|>|<\|assistant\|>)",
    r"(?:\#\#\#\s*System|\#\#\#\s*New\s+Instruction)",
    r"(?:---\s*BEGIN\s+(?:SYSTEM|INSTRUCTION|PROMPT)\s*(?:MESSAGE)?\s*---)",
    r"(?:---\s*END\s+(?:SYSTEM|INSTRUCTION|PROMPT)\s*(?:MESSAGE)?\s*---)",
]

_INJECTION_REGEX = [re.compile(p) for p in _INJECTION_PATTERNS]

# ── Harmful Content Patterns ────────────────────────
_HARMFUL_PATTERNS = [
    r"(?i)\b(?:hack|exploit|vulnerability|sql\s*injection|xss|csrf)\b.*\b(?:how\s+to|tutorial|guide|steps?)\b",
    r"(?i)\b(?:bomb|explosive|weapon|poison|drug\s+manufacture)\b.*\b(?:make|build|create|synthesize|how)\b",
    r"(?i)\b(?:child|minor|underage)\b.*\b(?:sexual|porn|nsfw|explicit)\b",
    r"(?i)\b(?:suicide|self[- ]harm)\b.*\b(?:how|method|ways?|steps?)\b",
]

_HARMFUL_REGEX = [re.compile(p) for p in _HARMFUL_PATTERNS]


class SanitizationResult:
    """Result of input sanitization check."""
    
    def __init__(
        self,
        is_safe: bool = True,
        reason: Optional[str] = None,
        category: Optional[str] = None,
        sanitized_text: Optional[str] = None,
    ):
        self.is_safe = is_safe
        self.reason = reason
        self.category = category
        self.sanitized_text = sanitized_text
    
    def __bool__(self) -> bool:
        return self.is_safe


def sanitize_input(
    text: str,
    max_length: int = MAX_MESSAGE_LENGTH,
    check_injection: bool = True,
    check_harmful: bool = True,
) -> SanitizationResult:
    """
    Validate and sanitize user input text.
    
    Checks for:
    - Empty/whitespace-only input
    - Excessive length
    - Prompt injection attempts
    - Harmful content
    - Control character injection
    
    Returns SanitizationResult with is_safe=True if all checks pass.
    """
    if not text or not text.strip():
        return SanitizationResult(
            is_safe=False,
            reason="Input cannot be empty",
            category="empty_input",
        )
    
    # Trim and check length
    text = text.strip()
    if len(text) > max_length:
        return SanitizationResult(
            is_safe=False,
            reason=f"Input exceeds maximum length of {max_length} characters",
            category="length_violation",
        )
    
    # Check for control characters (except newlines and tabs)
    control_chars = re.findall(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', text)
    if control_chars:
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    
    # Check for prompt injection
    if check_injection:
        for pattern in _INJECTION_REGEX:
            if pattern.search(text):
                return SanitizationResult(
                    is_safe=False,
                    reason="Input contains potentially manipulative content",
                    category="prompt_injection",
                    sanitized_text=text,
                )
    
    # Check for harmful content
    if check_harmful:
        for pattern in _HARMFUL_REGEX:
            if pattern.search(text):
                return SanitizationResult(
                    is_safe=False,
                    reason="Input contains potentially harmful content",
                    category="harmful_content",
                    sanitized_text=text,
                )
    
    # Normalize whitespace (collapse multiple spaces/newlines)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return SanitizationResult(
        is_safe=True,
        sanitized_text=text,
    )


def sanitize_filename(filename: str) -> SanitizationResult:
    """Validate and sanitize a filename."""
    if not filename or not filename.strip():
        return SanitizationResult(
            is_safe=False,
            reason="Filename cannot be empty",
            category="empty_input",
        )
    
    filename = filename.strip()
    
    if len(filename) > MAX_FILENAME_LENGTH:
        return SanitizationResult(
            is_safe=False,
            reason=f"Filename exceeds {MAX_FILENAME_LENGTH} characters",
            category="length_violation",
        )
    
    # Path traversal check
    if '..' in filename or '/' in filename or '\\' in filename:
        return SanitizationResult(
            is_safe=False,
            reason="Filename contains invalid path characters",
            category="path_traversal",
        )
    
    # Only allow safe characters
    if not re.match(r'^[\w\-. ]+$', filename):
        return SanitizationResult(
            is_safe=False,
            reason="Filename contains invalid characters",
            category="invalid_chars",
        )
    
    return SanitizationResult(is_safe=True, sanitized_text=filename)


def sanitize_url(url: str) -> SanitizationResult:
    """Validate and sanitize a URL."""
    if not url or not url.strip():
        return SanitizationResult(
            is_safe=False,
            reason="URL cannot be empty",
            category="empty_input",
        )
    
    url = url.strip()
    
    if len(url) > MAX_URL_LENGTH:
        return SanitizationResult(
            is_safe=False,
            reason=f"URL exceeds {MAX_URL_LENGTH} characters",
            category="length_violation",
        )
    
    # Only allow http/https
    if not re.match(r'^https?://', url, re.IGNORECASE):
        return SanitizationResult(
            is_safe=False,
            reason="Only HTTP and HTTPS URLs are allowed",
            category="invalid_protocol",
        )
    
    # Block internal/private IPs (SSRF prevention)
    private_ip_patterns = [
        r'https?://(?:localhost|127\.\d+\.\d+\.\d+|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)',
        r'https?://\[::1\]',
        r'https?://0\.0\.0\.0',
    ]
    for pattern in private_ip_patterns:
        if re.match(pattern, url, re.IGNORECASE):
            return SanitizationResult(
                is_safe=False,
                reason="URLs pointing to internal/private networks are not allowed",
                category="ssrf_prevention",
            )
    
    return SanitizationResult(is_safe=True, sanitized_text=url)


def content_hash(text: str) -> str:
    """Generate a SHA-256 hash of content for deduplication."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]


def detect_language_hint(text: str) -> str:
    """Quick heuristic language detection (returns ISO 639-1 code)."""
    # Simple character frequency analysis
    if re.search(r'[\u4e00-\u9fff]', text):
        return 'zh'
    if re.search(r'[\u3040-\u309f\u30a0-\u30ff]', text):
        return 'ja'
    if re.search(r'[\uac00-\ud7af]', text):
        return 'ko'
    if re.search(r'[\u0400-\u04ff]', text):
        return 'ru'
    if re.search(r'[\u0600-\u06ff]', text):
        return 'ar'
    if re.search(r'[\u0900-\u097f]', text):
        return 'hi'
    return 'en'
