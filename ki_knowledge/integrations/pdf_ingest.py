"""PDF ingest for knowledge store."""

import re
import statistics
from pathlib import Path
from typing import Any

from pypdf import PdfReader

# A line clearly shorter than the page's typical line ends a paragraph (or is a heading).
SHORT_LINE_RATIO = 0.75
# Lines repeated on more than this share of pages are running heads/footers.
REPEATED_RATIO = 0.3
REPEATED_MIN_PAGES = 10
_HYPHENATED = re.compile(r"[A-Za-zÄÖÜäöüß]-$")
_MARKDOWN_START = re.compile(r"^(#{1,6}\s|```)")


def _join_lines(lines: list[str]) -> str:
    text = lines[0]
    for line in lines[1:]:
        if _HYPHENATED.search(text) and line[:1].islower():
            text = text[:-1] + line
        else:
            text = f"{text} {line}"
    return text


def reflow_page_text(text: str) -> list[str]:
    """Rebuild paragraphs from the line-wise text of a PDF page.

    pypdf keeps the printed line breaks.  A paragraph (or heading) ends at an
    empty line or at a line clearly shorter than the typical line width that
    does not end with a hyphen or comma; hyphenated words are rejoined.
    """
    lines = [line.strip() for line in text.splitlines()]
    widths = [len(line) for line in lines if len(line) > 20]
    width = statistics.median(widths) if widths else 60
    paragraphs: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if not line:
            if current:
                paragraphs.append(current)
                current = []
            continue
        current.append(line)
        if len(line) < SHORT_LINE_RATIO * width and not line.endswith(("-", ",")):
            paragraphs.append(current)
            current = []
    if current:
        paragraphs.append(current)
    result = []
    for lines_of_paragraph in paragraphs:
        paragraph = _join_lines(lines_of_paragraph)
        # Keep PDF text from being read as markdown structure.
        result.append(f"\\{paragraph}" if _MARKDOWN_START.match(paragraph) else paragraph)
    return result


def extract_text_from_pdf(pdf_path: Path, *, paragraphs: bool = True) -> str:
    """Extract the text of a PDF as markdown with one ``## Page N`` section per page.

    With ``paragraphs`` (default) the printed lines are reflowed into
    paragraphs, so every paragraph becomes its own knowledge block.  Without
    it the page text is passed through unchanged (one block per page).
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    text_parts = []
    with open(pdf_path, "rb") as f:
        reader = PdfReader(f)
        pages = []
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if text.strip():
                pages.append((page_num, text))
    if paragraphs:
        pages = [(page_num, "\n\n".join(reflow_page_text(text))) for page_num, text in _drop_repeated_lines(pages)]
    for page_num, body in pages:
        if body.strip():
            text_parts.append(f"## Page {page_num}\n\n{body}")
    
    return "\n\n".join(text_parts)


def _line_key(line: str) -> str:
    return re.sub(r"[\d\s]+", "#", line.strip().lower())


def _drop_repeated_lines(pages: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Remove running heads/footers and page numbers: lines that recur (digits ignored) on many pages."""
    if len(pages) < REPEATED_MIN_PAGES:
        return pages
    counts: dict[str, int] = {}
    for _page, text in pages:
        for key in {_line_key(line) for line in text.splitlines() if line.strip()}:
            counts[key] = counts.get(key, 0) + 1
    limit = REPEATED_RATIO * len(pages)
    return [
        (page, "\n".join(line for line in text.splitlines() if not line.strip() or counts[_line_key(line)] <= limit))
        for page, text in pages
    ]


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
