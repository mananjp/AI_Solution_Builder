"""
AI Solution Builder — Document Parser

Universal input ingestion: parses PDF, DOCX, CSV/Excel, plain text,
website URLs, and OpenAPI (YAML/JSON) specs into normalized text for
the AI pipeline.
"""

import io
import ipaddress
import logging
import socket

logger = logging.getLogger(__name__)

_MAX_URL_BYTES = 5 * 1024 * 1024
_REDIRECT_CODES = {301, 302, 303, 307, 308}
_BLOCKED_IP_ATTRS = (
    "is_private",
    "is_loopback",
    "is_link_local",
    "is_reserved",
    "is_multicast",
    "is_unspecified",
)


def extract_readable_html(html: str) -> str:
    """Strip scripts/styles/form elements from an HTML document and return text."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)


async def parse_url(url: str) -> str:
    """Fetch a website URL and extract readable page text.

    Only http(s) URLs resolving to public IPs are fetched (SSRF guard).
    Raises ValueError when the URL cannot be fetched or parsed so callers
    (e.g. the upload API) can surface a meaningful HTTP error.
    """
    import httpx

    def _public_host_or_raise(target: str) -> None:
        parsed = httpx.URL(target)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Only http/https URLs are allowed: {url}")
        host = parsed.host
        if not host:
            raise ValueError(f"Invalid URL: {url}")
        try:
            infos = socket.getaddrinfo(host, None)
        except socket.gaierror as e:
            raise ValueError(f"Could not resolve host: {host}") from e
        for _af, _socktype, _proto, _canon, sockaddr in infos:
            ip = ipaddress.ip_address(sockaddr[0])
            if any(getattr(ip, attr) for attr in _BLOCKED_IP_ATTRS):
                raise ValueError(f"Refusing to fetch non-public address: {ip}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            target = url
            content: bytes | None = None
            content_type = ""
            for _ in range(5):  # redirect loop, re-validating each hop
                _public_host_or_raise(target)
                async with client.stream(
                    "GET",
                    target,
                    headers={"User-Agent": "AISolutionBuilder/1.0 (+document ingestion)"},
                ) as resp:
                    if resp.status_code in _REDIRECT_CODES and resp.headers.get("location"):
                        target = str(httpx.URL(target).join(resp.headers["location"]))
                        continue
                    resp.raise_for_status()
                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in resp.aiter_bytes():
                        total += len(chunk)
                        if total > _MAX_URL_BYTES:
                            raise ValueError(f"Response exceeds {_MAX_URL_BYTES} bytes")
                        chunks.append(chunk)
                    content = b"".join(chunks)
                    content_type = resp.headers.get("content-type", "").lower()
                break
            else:
                raise ValueError(f"Too many redirects fetching {url}")
            assert content is not None

            if "html" in content_type or "xml" in content_type:
                text = extract_readable_html(content.decode("utf-8", errors="replace"))
            else:
                text = content.decode("utf-8", errors="replace").strip()

        if not text:
            return f"No readable content extracted from {url}"
        return text
    except httpx.HTTPError as e:
        raise ValueError(f"Failed to fetch {url}: {e}") from e


async def parse_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF file using PyMuPDF."""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text_parts = []
        for page_num, page in enumerate(doc, 1):
            text = page.get_text()
            if text.strip():
                text_parts.append(f"--- Page {page_num} ---\n{text}")
        doc.close()
        return "\n\n".join(text_parts)
    except Exception as e:
        logger.error(f"PDF parsing failed: {e}")
        return f"[PDF parsing error: {e}]"


async def parse_docx(file_bytes: bytes) -> str:
    """Extract text from a DOCX file."""
    try:
        from docx import Document

        doc = Document(io.BytesIO(file_bytes))
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        return "\n\n".join(paragraphs)
    except Exception as e:
        logger.error(f"DOCX parsing failed: {e}")
        return f"[DOCX parsing error: {e}]"


async def parse_pptx(file_bytes: bytes) -> str:
    """Extract text from slides and speaker notes of a PPT/PPTX presentation."""
    try:
        from pptx import Presentation

        prs = Presentation(io.BytesIO(file_bytes))
        slide_texts: list[str] = []
        for idx, slide in enumerate(prs.slides, 1):
            parts: list[str] = [f"--- Slide {idx} ---"]
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for paragraph in shape.text_frame.paragraphs:
                        text = paragraph.text.strip()
                        if text:
                            parts.append(text)
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                notes = slide.notes_slide.notes_text_frame.text.strip()
                if notes:
                    parts.append(f"[Speaker Notes]: {notes}")
            if len(parts) > 1:
                slide_texts.append("\n".join(parts))
        if not slide_texts:
            return "[Presentation contains no extractable text]"
        return "\n\n".join(slide_texts)
    except Exception as e:
        logger.error(f"PPTX parsing failed: {e}")
        return f"[Presentation parsing error: {e}]"


async def parse_csv_excel(file_bytes: bytes, filename: str) -> str:
    """Extract schema information from CSV/Excel files."""
    try:
        import pandas as pd

        if filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(file_bytes), nrows=100)
        else:
            df = pd.read_csv(io.BytesIO(file_bytes), nrows=100)

        # Generate schema description
        schema_parts = [
            f"File: {filename}",
            f"Columns ({len(df.columns)}): {', '.join(df.columns.tolist())}",
            f"Row count (sample): {len(df)}",
            "\nColumn types:",
        ]
        for col in df.columns:
            dtype = df[col].dtype
            non_null = df[col].notna().sum()
            sample = df[col].dropna().head(3).tolist()
            schema_parts.append(f"  - {col}: {dtype} ({non_null} non-null) | samples: {sample}")

        # Include first few rows as context
        schema_parts.append(f"\nFirst 5 rows:\n{df.head().to_string()}")

        return "\n".join(schema_parts)
    except Exception as e:
        logger.error(f"CSV/Excel parsing failed: {e}")
        return f"[CSV/Excel parsing error: {e}]"


async def parse_text(file_bytes: bytes) -> str:
    """Parse plain text files."""
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return file_bytes.decode("latin-1")


async def parse_openapi(file_bytes: bytes, filename: str) -> str | None:
    """Parse an OpenAPI/Swagger spec (JSON or YAML) into a compact summary.

    Returns None when the content is not an OpenAPI/Swagger document so the
    caller can fall back to plain-text parsing.
    """
    import json

    try:
        import yaml
    except ImportError:
        yaml = None

    try:
        if filename.lower().endswith(".json"):
            spec = json.loads(file_bytes.decode("utf-8"))
        elif yaml is not None:
            spec = yaml.safe_load(file_bytes.decode("utf-8"))
        else:
            return None
    except Exception:  # noqa: BLE001 - not a spec; let caller fall back to text
        return None

    if not isinstance(spec, dict) or ("openapi" not in spec and "swagger" not in spec):
        return None

    info = spec.get("info") or {}
    title = info.get("title", filename)
    version = info.get("version", "unknown")
    description = info.get("description", "")

    servers = [f"- {s.get('url', '')}" for s in spec.get("servers", []) if isinstance(s, dict)]
    base_path = spec.get("basePath", "") if "swagger" in spec else ""

    tags_raw = spec.get("tags", [])
    tag_names = (
        [str(t["name"]) for t in tags_raw if isinstance(t, dict) and t.get("name")]
        if isinstance(tags_raw, list)
        else []
    )

    paths = spec.get("paths") or {}
    endpoints = []
    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        for method, op in item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                continue
            if isinstance(op, dict):
                endpoints.append(
                    f"- {method.upper()} {path} — {str(op.get('summary', '')).strip() or str(op.get('operationId', '')).strip()}"
                )

    schemas = {k: v for k, v in ((spec.get("components") or {}).get("schemas") or {}).items()}
    if not schemas and "definitions" in spec:
        schemas = dict(spec.get("definitions") or {})

    entity_lines = []
    for name, schema in schemas.items():
        if not isinstance(schema, dict):
            continue
        props = schema.get("properties") or {}
        prop_names = (
            ", ".join(k for k in props) if isinstance(props, dict) else str(schema.get("type", ""))
        )
        entity_lines.append(f"- {name}: {prop_names}")

    parts = [
        f"OpenAPI Specification: {title} (v{version})",
        f"Filename: {filename}",
    ]
    if description:
        parts.append(f"Description: {' '.join(str(description).split())[:600]}")
    if servers:
        parts.append("Servers:\n" + "\n".join(servers))
    if base_path:
        parts.append(f"Base path: {base_path}")
    if tag_names:
        parts.append(f"Tags: {', '.join(tag_names)}")
    if endpoints:
        parts.append("Endpoints:\n" + "\n".join(endpoints))
    if entity_lines:
        parts.append("Schemas (entities):\n" + "\n".join(entity_lines))
    return "\n\n".join(parts)


async def parse_document(file_bytes: bytes, filename: str) -> str:
    """Universal document parser — routes to the correct parser by file extension."""
    filename_lower = filename.lower()

    if filename_lower.endswith(".pdf"):
        return await parse_pdf(file_bytes)
    elif filename_lower.endswith(".docx"):
        return await parse_docx(file_bytes)
    elif filename_lower.endswith((".pptx", ".ppt")):
        return await parse_pptx(file_bytes)
    elif filename_lower.endswith((".csv", ".xlsx", ".xls")):
        return await parse_csv_excel(file_bytes, filename)
    elif filename_lower.endswith((".json", ".yaml", ".yml")):
        openapi_text = await parse_openapi(file_bytes, filename)
        return openapi_text if openapi_text is not None else await parse_text(file_bytes)
    elif filename_lower.endswith((".txt", ".md")):
        return await parse_text(file_bytes)
    else:
        return await parse_text(file_bytes)
