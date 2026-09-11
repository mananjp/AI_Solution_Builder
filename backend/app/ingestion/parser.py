"""
AI Solution Builder — Document Parser

Universal input ingestion: parses PDF, DOCX, CSV/Excel, and plain text
into normalized text for the AI pipeline.
"""

import io
import logging

logger = logging.getLogger(__name__)


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


async def parse_document(file_bytes: bytes, filename: str) -> str:
    """Universal document parser — routes to the correct parser by file extension."""
    filename_lower = filename.lower()

    if filename_lower.endswith(".pdf"):
        return await parse_pdf(file_bytes)
    elif filename_lower.endswith(".docx"):
        return await parse_docx(file_bytes)
    elif filename_lower.endswith((".csv", ".xlsx", ".xls")):
        return await parse_csv_excel(file_bytes, filename)
    elif filename_lower.endswith((".txt", ".md", ".json", ".yaml", ".yml")):
        return await parse_text(file_bytes)
    else:
        return await parse_text(file_bytes)
