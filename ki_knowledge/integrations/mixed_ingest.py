"""Turn mixed source files (tables, images, ...) into markdown for the knowledge store.

The ``mix`` source folder of a domain may hold any file format. Each file is
classified by its extension:

* ``pdf`` / ``markdown`` / ``ontology`` are handled by the existing importers,
* ``table`` (CSV, TSV, ODS, XLSX) is converted to markdown here,
* ``image`` (PNG, JPEG, ...) is OCR'd with the ``tesseract`` CLI here,
* everything else is ``unsupported`` and only reported.

Tables become one ``## <sheet>`` section per sheet and one list item per row
(``- Header: value; Header: value``), so each row ends up as its own
knowledge block.
"""

from __future__ import annotations

import csv
import io
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

PDF_KIND = "pdf"
MARKDOWN_KIND = "markdown"
ONTOLOGY_KIND = "ontology"
TABLE_KIND = "table"
IMAGE_KIND = "image"
UNSUPPORTED_KIND = "unsupported"

_KIND_BY_SUFFIX = {
    ".pdf": PDF_KIND,
    ".md": MARKDOWN_KIND,
    ".markdown": MARKDOWN_KIND,
    ".owl": ONTOLOGY_KIND,
    ".rdf": ONTOLOGY_KIND,
    ".ttl": ONTOLOGY_KIND,
    ".n3": ONTOLOGY_KIND,
    ".jsonld": ONTOLOGY_KIND,
    ".csv": TABLE_KIND,
    ".tsv": TABLE_KIND,
    ".ods": TABLE_KIND,
    ".xlsx": TABLE_KIND,
    ".png": IMAGE_KIND,
    ".jpg": IMAGE_KIND,
    ".jpeg": IMAGE_KIND,
    ".tif": IMAGE_KIND,
    ".tiff": IMAGE_KIND,
    ".bmp": IMAGE_KIND,
    ".gif": IMAGE_KIND,
    ".webp": IMAGE_KIND,
}
MIX_KINDS = (PDF_KIND, MARKDOWN_KIND, ONTOLOGY_KIND, TABLE_KIND, IMAGE_KIND, UNSUPPORTED_KIND)

# Guards against the huge "repeated" empty cells/rows ODS files use for padding.
_MAX_REPEAT = 1024
_OCR_TIMEOUT_SECONDS = 180
_OCR_LANGUAGES_ENV = "KNOWLEDGE_OCR_LANGUAGES"
_OCR_PREFERRED_LANGUAGES = ("deu", "eng")


class MixedIngestError(RuntimeError):
    """A mixed file could not be converted."""


class OcrUnavailableError(MixedIngestError):
    """No OCR engine is installed."""


def classify_file(path: str | Path) -> str:
    return _KIND_BY_SUFFIX.get(Path(path).suffix.lower(), UNSUPPORTED_KIND)


def discover_mixed_files(root: str | Path) -> dict[str, list[Path]]:
    """All files below ``root`` grouped by kind; follows symlinks, skips hidden files and loops."""
    grouped: dict[str, list[Path]] = {kind: [] for kind in MIX_KINDS}
    root = Path(root)
    if not root.exists():
        return grouped
    seen_dirs: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(root, followlinks=True):
        real = os.path.realpath(dirpath)
        if real in seen_dirs:
            dirnames[:] = []
            continue
        seen_dirs.add(real)
        dirnames[:] = sorted(name for name in dirnames if not name.startswith("."))
        for name in sorted(filenames):
            if name.startswith(".") or name.startswith("~$"):
                continue
            path = Path(dirpath) / name
            if path.is_file():
                grouped[classify_file(path)].append(path)
    return grouped


# --- tables -----------------------------------------------------------------------


@dataclass
class Sheet:
    name: str
    rows: list[list[str]]


def _trim(rows: Iterable[list[str]]) -> list[list[str]]:
    """Strip whitespace, trailing empty cells, and empty rows."""
    result = []
    for row in rows:
        cells = [" ".join(str(cell or "").split()) for cell in row]
        while cells and not cells[-1]:
            cells.pop()
        if cells:
            result.append(cells)
    return result


def read_csv_sheets(path: Path) -> list[Sheet]:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    sample = text[:8192]
    if path.suffix.lower() == ".tsv":
        dialect: type[csv.Dialect] | csv.Dialect = csv.excel_tab
    else:
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
    rows = list(csv.reader(io.StringIO(text), dialect))
    return [Sheet(path.stem, _trim(rows))]


def _repeat(value: str | None, empty: bool) -> int:
    count = int(value or 1)
    return 1 if empty and count > _MAX_REPEAT else min(count, _MAX_REPEAT)


def read_ods_sheets(path: Path) -> list[Sheet]:
    try:
        from odf import opendocument, teletype
        from odf.table import CoveredTableCell, Table, TableCell, TableRow
    except ImportError as exc:
        raise MixedIngestError("reading .ods needs odfpy (pip install odfpy)") from exc
    try:
        document = opendocument.load(str(path))
    except Exception as exc:  # odfpy raises zipfile/XML/KeyError variants
        raise MixedIngestError(f"not a valid ODS file: {exc}") from exc
    cell_types = {TableCell().qname, CoveredTableCell().qname}
    sheets = []
    for table in document.spreadsheet.getElementsByType(Table):
        rows: list[list[str]] = []
        for row in table.getElementsByType(TableRow):
            cells: list[str] = []
            for cell in row.childNodes:
                if getattr(cell, "qname", None) not in cell_types:
                    continue
                value = " ".join(teletype.extractText(cell).split()) if cell.childNodes else ""
                cells.extend([value] * _repeat(cell.getAttribute("numbercolumnsrepeated"), not value))
            empty_row = not any(cells)
            rows.extend([list(cells) for _ in range(_repeat(row.getAttribute("numberrowsrepeated"), empty_row))])
        sheets.append(Sheet(table.getAttribute("name") or f"Sheet {len(sheets) + 1}", _trim(rows)))
    return sheets


def read_xlsx_sheets(path: Path) -> list[Sheet]:
    try:
        import openpyxl
    except ImportError as exc:
        raise MixedIngestError("reading .xlsx needs openpyxl (pip install openpyxl)") from exc
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        return [
            Sheet(sheet.title, _trim([["" if value is None else str(value) for value in row] for row in sheet.iter_rows(values_only=True)]))
            for sheet in workbook.worksheets
        ]
    finally:
        workbook.close()


def read_table_sheets(path: str | Path) -> list[Sheet]:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in (".csv", ".tsv"):
        return read_csv_sheets(path)
    if suffix == ".ods":
        return read_ods_sheets(path)
    if suffix == ".xlsx":
        return read_xlsx_sheets(path)
    raise MixedIngestError(f"unsupported table format: {suffix}")


def _md_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("*", "\\*").replace("_", "\\_").replace("#", "\\#")


def _is_number(value: str) -> bool:
    try:
        float(value.replace(",", "."))
    except ValueError:
        return False
    return True


def _has_header(rows: list[list[str]]) -> bool:
    """First row is a header if the table has data below it and the row is not purely numeric."""
    return len(rows) > 1 and any(cell and not _is_number(cell) for cell in rows[0])


def sheets_to_markdown(title: str, sheets: list[Sheet]) -> str:
    """One heading per sheet, one list item per row (``Header: value; ...`` when a header exists)."""
    lines = [f"# {title}", ""]
    for sheet in sheets:
        if not sheet.rows:
            continue
        lines += [f"## {sheet.name}", ""]
        width = max(len(row) for row in sheet.rows)
        if _has_header(sheet.rows):
            header, body = sheet.rows[0], sheet.rows[1:]
            names = [header[i] if i < len(header) and header[i] else f"Spalte {i + 1}" for i in range(width)]
            lines += [f"Spalten: {', '.join(_md_escape(name) for name in names)}", ""]
            for row in body:
                pairs = [f"{_md_escape(names[i])}: {_md_escape(cell)}" for i, cell in enumerate(row) if cell]
                if pairs:
                    lines.append(f"- {'; '.join(pairs)}")
        elif width == 1:
            lines.append("Werte: " + ", ".join(_md_escape(row[0]) for row in sheet.rows))
        else:
            for row in sheet.rows:
                lines.append(f"- {'; '.join(_md_escape(cell) for cell in row)}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def table_to_markdown(path: str | Path) -> str:
    path = Path(path)
    sheets = read_table_sheets(path)
    if not any(sheet.rows for sheet in sheets):
        raise MixedIngestError("table is empty")
    return sheets_to_markdown(path.name, sheets)


# --- images (OCR) -------------------------------------------------------------------


def tesseract_binary() -> str | None:
    return shutil.which("tesseract")


def ocr_languages(binary: str) -> str:
    configured = os.getenv(_OCR_LANGUAGES_ENV, "").strip()
    if configured:
        return configured
    try:
        listing = subprocess.run([binary, "--list-langs"], capture_output=True, text=True, timeout=30, check=False)
        available = set(listing.stdout.split())
    except (OSError, subprocess.SubprocessError):
        available = set()
    chosen = [lang for lang in _OCR_PREFERRED_LANGUAGES if lang in available]
    return "+".join(chosen) or "eng"


def ocr_image_text(path: str | Path) -> str:
    binary = tesseract_binary()
    if binary is None:
        raise OcrUnavailableError(
            "OCR engine missing: sudo apt install tesseract-ocr tesseract-ocr-deu"
        )
    try:
        completed = subprocess.run(
            [binary, str(path), "stdout", "-l", ocr_languages(binary)],
            capture_output=True,
            text=True,
            timeout=_OCR_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise MixedIngestError(f"OCR timed out after {_OCR_TIMEOUT_SECONDS}s") from exc
    if completed.returncode != 0:
        raise MixedIngestError(f"tesseract failed: {completed.stderr.strip()[:300]}")
    return completed.stdout


def image_to_markdown(path: str | Path) -> str:
    """OCR text of an image as markdown paragraphs (blank lines separate blocks)."""
    path = Path(path)
    text = ocr_image_text(path)
    paragraphs = []
    for chunk in text.replace("\f", "\n\n").split("\n\n"):
        joined = " ".join(chunk.split())
        if len(joined) >= 2:
            paragraphs.append(_md_escape(joined))
    if not paragraphs:
        raise MixedIngestError("OCR found no text")
    return "\n\n".join([f"# {path.name}", *paragraphs]) + "\n"


__all__ = [
    "IMAGE_KIND",
    "MARKDOWN_KIND",
    "MIX_KINDS",
    "ONTOLOGY_KIND",
    "PDF_KIND",
    "TABLE_KIND",
    "UNSUPPORTED_KIND",
    "MixedIngestError",
    "OcrUnavailableError",
    "Sheet",
    "classify_file",
    "discover_mixed_files",
    "image_to_markdown",
    "ocr_image_text",
    "read_table_sheets",
    "sheets_to_markdown",
    "table_to_markdown",
    "tesseract_binary",
]
