"""Read-only inventory of every PDF below the configured data root.

The scan never imports, OCRs, or writes anything. Titles come from PDF
metadata when present; otherwise the file name is used and explicitly labeled
as a fallback. Scanned books usually have no metadata title, so their true
title can only be verified later (OCR / manual review).
"""

from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.errors import DependencyError, FileNotDecryptedError, PdfReadError, PdfStreamError

from ki_knowledge.data_layout import PDF, SOURCE_TYPES, DataLayout

TITLE_SOURCE_METADATA = "metadata"
TITLE_SOURCE_FILENAME = "filename"

_PLACEHOLDER_TITLES = {"", "-", "untitled", "unbenannt", "unknown", "title", "none", "null"}
_FIRST_PAGE_HINT_MAX_CHARS = 160

# Known failure modes of malformed/unsupported PDFs. Anything else is a bug and propagates.
_PDF_READ_ERRORS: tuple[type[BaseException], ...] = (
    PdfReadError,
    PdfStreamError,
    FileNotDecryptedError,
    DependencyError,
    OSError,
    ValueError,
    TypeError,
    NotImplementedError,
)


@dataclass
class PdfInventoryEntry:
    path: str
    relative_path: str
    root_label: str
    title: str
    title_source: str
    metadata_title: str = ""
    author: str = ""
    page_count: int | None = None
    size_bytes: int | None = None
    encrypted: bool = False
    via_symlink: bool = False
    first_page_text: str = ""
    warnings: list[str] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PdfInventory:
    roots: list[dict[str, Any]] = field(default_factory=list)
    entries: list[PdfInventoryEntry] = field(default_factory=list)
    scan_errors: list[dict[str, str]] = field(default_factory=list)
    duplicates: list[dict[str, str]] = field(default_factory=list)
    skipped_cycles: list[str] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, int]:
        return {
            "total": len(self.entries),
            "metadata_titles": sum(1 for e in self.entries if e.title_source == TITLE_SOURCE_METADATA),
            "filename_fallbacks": sum(1 for e in self.entries if e.title_source == TITLE_SOURCE_FILENAME),
            "file_errors": sum(1 for e in self.entries if e.error),
            "scan_errors": len(self.scan_errors),
            "duplicates": len(self.duplicates),
            "skipped_cycles": len(self.skipped_cycles),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "roots": list(self.roots),
            "summary": self.summary,
            "entries": [entry.to_dict() for entry in self.entries],
            "scan_errors": list(self.scan_errors),
            "duplicates": list(self.duplicates),
            "skipped_cycles": list(self.skipped_cycles),
        }


def configured_inventory_roots(layout: DataLayout | None = None) -> list[tuple[str, Path]]:
    """Return ``(label, path)`` scan roots from configuration only.

    The data root always comes first; a configured PDF type-root override
    (``KNOWLEDGE_PDF_ROOT``) is added when it lives outside the data root.
    """
    resolved_layout = layout or DataLayout.from_config()
    roots: list[tuple[str, Path]] = [("data root", resolved_layout.root)]
    override = resolved_layout.type_root_overrides.get(PDF)
    if override is not None and not _is_within(_safe_resolve(override), _safe_resolve(resolved_layout.root)):
        roots.append(("PDF root override", override))
    return roots


def domain_inventory_roots(domain: str, layout: DataLayout | None = None) -> list[tuple[str, Path]]:
    """Scan only this domain's source and output directories, including overrides."""
    resolved_layout = layout or DataLayout.from_config()
    roots = []
    for source_type in SOURCE_TYPES:
        name = next(
            (name for name in resolved_layout.source_domain_names(source_type)
             if name.casefold() == domain.casefold()),
            domain,
        )
        path = resolved_layout.source_dir(source_type, name)
        if path.exists() or path.is_symlink():
            roots.append((f"{source_type}/{name}", path))
    output = resolved_layout.output_dir(domain)
    if output.exists() or output.is_symlink():
        roots.append((f"output/{domain}", output))
    return roots


def scan_configured_pdf_inventory(*, domain: str, include_first_page_text: bool = False) -> PdfInventory:
    return scan_pdf_inventory(domain_inventory_roots(domain), include_first_page_text=include_first_page_text)


def scan_pdf_inventory(
    roots: list[tuple[str, Path]],
    *,
    include_first_page_text: bool = False,
) -> PdfInventory:
    inventory = PdfInventory()
    seen_files: dict[str, str] = {}
    for label, root in roots:
        root = Path(root)
        status = _root_status(root)
        inventory.roots.append({"label": label, "path": str(root), "status": status})
        if status != "ok":
            continue
        for display_path, error in _walk_pdfs(root, inventory):
            relative = display_path.relative_to(root).as_posix()
            if error:
                inventory.entries.append(_error_entry(display_path, relative, label, error))
                continue
            physical = str(_safe_resolve(display_path))
            if physical in seen_files:
                inventory.duplicates.append({"relative_path": relative, "same_as": seen_files[physical]})
                continue
            seen_files[physical] = relative
            inventory.entries.append(
                read_pdf_entry(display_path, relative, label, include_first_page_text=include_first_page_text)
            )
    inventory.entries.sort(key=lambda e: (e.title.casefold(), e.title, e.relative_path))
    return inventory


def read_pdf_entry(
    path: Path,
    relative_path: str,
    root_label: str = "data root",
    *,
    include_first_page_text: bool = False,
) -> PdfInventoryEntry:
    entry = PdfInventoryEntry(
        path=str(path),
        relative_path=relative_path,
        root_label=root_label,
        title=filename_title(path),
        title_source=TITLE_SOURCE_FILENAME,
        via_symlink=_path_uses_symlink(path),
    )
    try:
        entry.size_bytes = path.stat().st_size
    except OSError as exc:
        entry.error = f"unreadable: {exc.strerror or exc}"
        return entry

    pypdf_logger = logging.getLogger("pypdf")
    collector = _WarningCollector()
    pypdf_logger.addHandler(collector)
    try:
        _read_into(entry, path, include_first_page_text=include_first_page_text)
    finally:
        pypdf_logger.removeHandler(collector)
    entry.warnings = collector.messages + [w for w in entry.warnings if w not in collector.messages]
    return entry


class _WarningCollector(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage().strip()
        if message and message not in self.messages:
            self.messages.append(message)


def _read_into(entry: PdfInventoryEntry, path: Path, *, include_first_page_text: bool) -> None:
    try:
        with path.open("rb") as handle:
            reader = PdfReader(handle, strict=False)
            if reader.is_encrypted:
                entry.encrypted = True
                try:
                    decrypted = reader.decrypt("")
                except (DependencyError, NotImplementedError) as exc:
                    entry.error = f"encrypted: unsupported encryption ({type(exc).__name__}: {exc})"
                    return
                if not decrypted:
                    entry.error = "encrypted: password required"
                    return
            metadata = reader.metadata
            raw_title = _clean_text(metadata.title if metadata else None)
            entry.metadata_title = raw_title
            entry.author = _clean_text(metadata.author if metadata else None)
            if raw_title and raw_title.casefold() not in _PLACEHOLDER_TITLES:
                entry.title = raw_title
                entry.title_source = TITLE_SOURCE_METADATA
            entry.page_count = len(reader.pages)
            if include_first_page_text and entry.page_count:
                entry.first_page_text = _first_page_line(reader, entry)
    except _PDF_READ_ERRORS as exc:
        entry.error = f"unreadable PDF: {type(exc).__name__}: {exc}"


def filename_title(path: Path) -> str:
    stem = path.stem.replace("_", " ").strip()
    return " ".join(stem.split()) or path.name


def _walk_pdfs(root: Path, inventory: PdfInventory):
    """Yield ``(path, error)`` for PDFs below ``root`` in deterministic order.

    Follows symlinked directories (like ``services.discover_pdf_files``) with a
    cycle guard, but records directory errors and cycles instead of skipping
    them silently.
    """
    visited_dirs: set[str] = set()
    pending: list[tuple[Path, str]] = []

    def visit(directory: Path) -> None:
        key = str(_safe_resolve(directory))
        if key in visited_dirs:
            inventory.skipped_cycles.append(_relative_or_str(directory, root))
            return
        visited_dirs.add(key)
        try:
            children = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as exc:
            inventory.scan_errors.append(
                {"path": _relative_or_str(directory, root), "error": f"directory unreadable: {exc.strerror or exc}"}
            )
            return
        for child in children:
            child_path = Path(child.path)
            try:
                is_dir = child.is_dir(follow_symlinks=True)
                is_file = child.is_file(follow_symlinks=True)
            except OSError as exc:
                if child.name.lower().endswith(".pdf"):
                    pending.append((child_path, f"unreadable: {exc.strerror or exc}"))
                else:
                    inventory.scan_errors.append(
                        {"path": _relative_or_str(child_path, root), "error": f"entry not inspectable: {exc.strerror or exc}"}
                    )
                continue
            if is_dir:
                visit(child_path)
            elif is_file and child.name.lower().endswith(".pdf"):
                pending.append((child_path, ""))
            elif child.is_symlink() and child.name.lower().endswith(".pdf"):
                pending.append((child_path, "broken symlink"))

    visit(root)
    yield from pending


def _root_status(root: Path) -> str:
    if not root.exists():
        return "missing"
    if not root.is_dir():
        return "not a directory"
    if not os.access(root, os.R_OK | os.X_OK):
        return "unreadable"
    return "ok"


def _error_entry(path: Path, relative: str, label: str, error: str) -> PdfInventoryEntry:
    return PdfInventoryEntry(
        path=str(path),
        relative_path=relative,
        root_label=label,
        title=filename_title(path),
        title_source=TITLE_SOURCE_FILENAME,
        via_symlink=path.is_symlink(),
        error=error,
    )


def _first_page_line(reader: PdfReader, entry: PdfInventoryEntry) -> str:
    try:
        text = reader.pages[0].extract_text() or ""
    except _PDF_READ_ERRORS as exc:
        entry.warnings.append(f"page 1 text not extractable: {type(exc).__name__}: {exc}")
        return ""
    for line in text.splitlines():
        cleaned = " ".join(line.split())
        if len(cleaned) >= 3:
            return cleaned[:_FIRST_PAGE_HINT_MAX_CHARS]
    return ""


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\x00", "").split())


def _path_uses_symlink(path: Path) -> bool:
    try:
        return path.resolve(strict=False) != Path(os.path.abspath(path))
    except OSError:
        return False


def _safe_resolve(path: Path) -> Path:
    try:
        return Path(path).resolve(strict=False)
    except OSError:
        return Path(os.path.abspath(path))


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _relative_or_str(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix() or "."
    except ValueError:
        return str(path)
