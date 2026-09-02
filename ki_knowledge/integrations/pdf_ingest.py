"""PDF ingest for knowledge store."""

from pathlib import Path
from typing import Any

from pypdf import PdfReader


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract all text from a PDF file."""
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    text_parts = []
    with open(pdf_path, "rb") as f:
        reader = PdfReader(f)
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if text.strip():
                text_parts.append(f"## Page {page_num}\n\n{text}")
    
    return "\n\n".join(text_parts)


def import_pdf_file(
    pdf_path: Path,
    *,
    source_name: str | None = None,
    domain: str | None = None,
) -> dict[str, Any]:
    """
    Import a single PDF file as markdown blocks into the knowledge store.
    
    Args:
        pdf_path: Path to the PDF file
        source_name: Custom source name (defaults to PDF filename)
        domain: Knowledge domain (optional)
    
    Returns:
        Dict with import results (imported blocks count, etc.)
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    try:
        markdown_text = extract_text_from_pdf(pdf_path)
    except Exception as e:
        return {
            "imported": 0,
            "error": f"Failed to extract text from PDF: {e}",
            "file": str(pdf_path),
        }
    
    if not markdown_text.strip():
        return {
            "imported": 0,
            "error": "PDF contains no extractable text",
            "file": str(pdf_path),
        }
    
    return {
        "imported": 1,
        "file": str(pdf_path),
        "source_name": source_name or pdf_path.stem,
        "text": markdown_text,
        "domain": domain,
    }
