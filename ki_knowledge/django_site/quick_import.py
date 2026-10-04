"""Format-neutral quick import: one-click import per source folder plus file upload.

Paths are never taken from the client; every folder is resolved from the
active domain on the server.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from ki_knowledge.data_layout import JIRA, MARKDOWN, MIX, ONTOLOGY, PDF
from ki_knowledge.integrations.mixed_ingest import (
    IMAGE_KIND,
    MARKDOWN_KIND,
    ONTOLOGY_KIND,
    PDF_KIND,
    TABLE_KIND,
    classify_file,
)

from .domain_paths import domain_source_dir, invalidate_domain_summary_cache
from .source_workflow import IMAGE_PROCESSING_OCR


@dataclass(frozen=True)
class QuickSource:
    key: str
    source_type: str
    label: str
    icon: str
    formats: str


QUICK_SOURCES: tuple[QuickSource, ...] = (
    QuickSource("md", MARKDOWN, "Markdown", "📝", ".md"),
    QuickSource("pdf", PDF, "PDF", "📄", ".pdf"),
    QuickSource("owl", ONTOLOGY, "Ontologie", "🕸️", ".owl .ttl .rdf"),
    QuickSource("jira", JIRA, "Jira", "🎫", "Jira-CSV"),
    QuickSource("mix", MIX, "Mix", "🧩", "Tabellen, Bilder, gemischt"),
)
QUICK_SOURCE_KEYS = tuple(source.key for source in QUICK_SOURCES)

# Upload target folder per file kind (tables/images only make sense in mix/).
_UPLOAD_TARGET = {
    PDF_KIND: PDF,
    MARKDOWN_KIND: MARKDOWN,
    ONTOLOGY_KIND: ONTOLOGY,
    TABLE_KIND: MIX,
    IMAGE_KIND: MIX,
}
UPLOAD_ACCEPT = ".md,.markdown,.pdf,.owl,.rdf,.ttl,.n3,.jsonld,.csv,.tsv,.ods,.xlsx,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.gif,.webp"
MAX_UPLOAD_FILES = 50


def _imported_group(source: Any) -> str | None:
    source_type = getattr(source, "source_type", "")
    source_id = getattr(source, "source_id", "") or ""
    if source_type in {TABLE_KIND, IMAGE_KIND} or source_id.startswith(("mix:", "pdf:mix/")):
        return "mix"
    return {"markdown": "md", "pdf": "pdf", "owl": "owl"}.get(source_type)


def quick_import_rows(domain: str, state: dict[str, Any], sources: Iterable[Any]) -> list[dict[str, Any]]:
    """Per source folder: file count, imported count, and whether an import makes sense."""
    from .services import display_data_path

    imported: dict[str, int] = {}
    for source in sources:
        group = _imported_group(source)
        if group:
            imported[group] = imported.get(group, 0) + 1
    files = {
        "md": int(state.get("markdown_files", 0) or 0),
        "pdf": int(state.get("pdf_files", 0) or 0),
        "owl": int(state.get("ontology_files", 0) or 0),
        "jira": int(state.get("jira_csv_files", 0) or 0),
        "mix": int(state.get("mix_files", 0) or 0),
    }
    imported["jira"] = int(state.get("issues", 0) or 0)
    rows = []
    for source in QUICK_SOURCES:
        directory = domain_source_dir(source.source_type, domain)
        count = files[source.key]
        rows.append(
            {
                "key": source.key,
                "label": source.label,
                "icon": source.icon,
                "formats": source.formats,
                "dir": display_data_path(directory),
                "folder": f"{source.key}/",
                "linked": directory.is_symlink(),
                "files": count,
                "imported": imported.get(source.key, 0),
                "imported_unit": "Issues" if source.key == "jira" else "Quellen",
                "can_import": count > 0,
            }
        )
    return rows


def _queue_pdf(domain: str):
    from .services import create_pdf_import_job

    return lambda path: create_pdf_import_job(str(path), domain=domain)


def run_source_import(
    key: str,
    domain: str,
    image_processing: str = IMAGE_PROCESSING_OCR,
) -> dict[str, Any]:
    """Import one source folder of the domain. Returns ``{"ok", "message", "warnings"}``."""
    from .services import discover_pdf_files, jira_reimport_data
    from .source_workflow import import_markdown_directory, import_mixed_directory, import_ontology_directory

    source = next((item for item in QUICK_SOURCES if item.key == key), None)
    if source is None:
        return {"ok": False, "message": f"Unbekannte Quelle: {key}", "warnings": []}
    directory = domain_source_dir(source.source_type, domain)
    if key != "jira" and not directory.exists():
        return {"ok": False, "message": f"{source.label}: Ordner fehlt noch.", "warnings": []}
    warnings: list[str] = []
    if key == "md":
        result = import_markdown_directory(directory)
        message = f"{result['files']} Dateien, {result['imported']} Blöcke"
    elif key == "pdf":
        queue = _queue_pdf(domain)
        queued = 0
        for path in discover_pdf_files(directory):
            try:
                queue(path)
                queued += 1
            except (FileNotFoundError, OSError, ValueError) as exc:
                warnings.append(f"{path.name}: {exc}")
        message = f"{queued} PDF-Jobs eingereiht"
    elif key == "owl":
        result = import_ontology_directory(directory)
        if result.get("error"):
            return {"ok": False, "message": f"{source.label}: {result['error']}", "warnings": []}
        message = f"{result.get('files', 0)} Dateien, {result.get('imported', 0)} Einträge"
    elif key == "jira":
        try:
            result = jira_reimport_data(domain)
        except (ValueError, OSError) as exc:
            return {"ok": False, "message": f"{source.label}: {exc}", "warnings": []}
        message = f"{result['issues']} Issues"
    else:
        result = import_mixed_directory(
            directory,
            domain=domain,
            queue_pdf=_queue_pdf(domain),
            image_processing=image_processing,
        )
        counts = ", ".join(f"{kind}: {count}" for kind, count in result["files"].items() if count)
        message = f"{result['imported']} Wissensobjekte ({counts or 'keine Dateien'}), {result['queued_pdfs']} PDF-Jobs"
        warnings.extend(f"{Path(error['file']).name}: {error['error']}" for error in result["errors"])
    invalidate_domain_summary_cache(domain)
    return {"ok": True, "message": f"{source.icon} {source.label}: {message}", "warnings": warnings}


def run_all_imports(
    domain: str,
    rows: Iterable[dict[str, Any]],
    image_processing: str = IMAGE_PROCESSING_OCR,
) -> list[dict[str, Any]]:
    return [run_source_import(row["key"], domain, image_processing) for row in rows if row["can_import"]]


def _unique_target(directory: Path, name: str) -> Path:
    target = directory / name
    stem, suffix = Path(name).stem, Path(name).suffix
    counter = 2
    while target.exists():
        target = directory / f"{stem}-{counter}{suffix}"
        counter += 1
    return target


def save_and_import_uploads(
    files: Iterable[Any],
    domain: str,
    image_processing: str = IMAGE_PROCESSING_OCR,
) -> dict[str, Any]:
    """Store uploaded files in the matching source folder of the domain and import them."""
    from .source_workflow import import_mixed_file

    queue = _queue_pdf(domain)
    imported: list[str] = []
    warnings: list[str] = []
    for index, upload in enumerate(files):
        name = Path(str(getattr(upload, "name", "") or "")).name
        if index >= MAX_UPLOAD_FILES:
            warnings.append(f"Mehr als {MAX_UPLOAD_FILES} Dateien – Rest ignoriert.")
            break
        if not name or name.startswith((".", "~$")):
            warnings.append(f"{name or '(ohne Namen)'}: ungültiger Dateiname")
            continue
        kind = classify_file(name)
        target_type = _UPLOAD_TARGET.get(kind)
        if target_type is None:
            warnings.append(f"{name}: Format nicht unterstützt")
            continue
        directory = domain_source_dir(target_type, domain)
        directory.mkdir(parents=True, exist_ok=True)
        target = _unique_target(directory, name)
        with target.open("wb") as handle:
            for chunk in upload.chunks():
                handle.write(chunk)
        try:
            if kind == PDF_KIND:
                queue(target)
                imported.append(f"{target.name} (PDF-Job)")
                continue
            result = import_mixed_file(target, domain=domain, image_processing=image_processing)
        except (OSError, ValueError) as exc:
            warnings.append(f"{target.name}: {exc}")
            continue
        if result.get("error"):
            warnings.append(f"{target.name}: gespeichert, Import fehlgeschlagen – {result['error']}")
        else:
            imported.append(f"{target.name} ({result.get('imported', 0)} Blöcke)")
        warnings.extend(f"{target.name}: {warning}" for warning in result.get("warnings", []))
    invalidate_domain_summary_cache(domain)
    return {"imported": imported, "warnings": warnings}


__all__ = [
    "MAX_UPLOAD_FILES",
    "QUICK_SOURCES",
    "QUICK_SOURCE_KEYS",
    "UPLOAD_ACCEPT",
    "quick_import_rows",
    "run_all_imports",
    "run_source_import",
    "save_and_import_uploads",
]
