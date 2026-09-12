"""
AI Solution Builder — File Upload API Route

Handles file uploads for document ingestion.
Parses uploaded files and returns extracted content.
"""

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.security import get_current_user
from app.ingestion.parser import parse_document, parse_url
from app.models.user import User
from app.schemas import UrlParseRequest

router = APIRouter(prefix="/upload", tags=["Upload"])


@router.post("/url")
async def upload_url(
    payload: UrlParseRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Fetch and parse a website URL into readable text for the AI pipeline."""
    try:
        extracted_text = await parse_url(payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "url": payload.url,
        "extracted_text": extracted_text,
        "character_count": len(extracted_text),
    }


@router.post("/document")
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Upload and parse a document (PDF, DOCX, CSV, Excel, or text).

    Returns the extracted text content for use in the AI chat pipeline.
    """
    # Validate file size (max 10MB)
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")

    # Validate file type
    allowed_extensions = {
        ".pdf",
        ".docx",
        ".csv",
        ".xlsx",
        ".xls",
        ".txt",
        ".md",
        ".json",
        ".yaml",
        ".yml",
    }
    filename = file.filename or "unknown.txt"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(sorted(allowed_extensions))}",
        )

    # Parse the document
    extracted_text = await parse_document(contents, filename)

    return {
        "filename": filename,
        "size_bytes": len(contents),
        "extracted_text": extracted_text,
        "character_count": len(extracted_text),
    }
