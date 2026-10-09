from __future__ import annotations

import hashlib
import mimetypes
from typing import Any, Callable
from pathlib import Path

import markdown
from django.conf import settings

from ki_knowledge.app_config import AppConfig as Config
from ki_knowledge.django_site.domain_paths import (
    default_semantic_domain,
    domain_markdown_dir,
    domain_mix_dir,
    domain_ontology_dir,
    infer_domain_from_path,
    invalidate_domain_summary_cache,
)
from ki_knowledge.integrations.pdf_ingest import extract_text_from_pdf as pdf_extract_text
from ki_knowledge.integrations.mixed_ingest import (
    IMAGE_KIND,
    MARKDOWN_KIND,
    MIX_KINDS,
    ONTOLOGY_KIND,
    PDF_KIND,
    TABLE_KIND,
    TEI_KIND,
    MixedIngestError,
    classify_file,
    discover_mixed_files,
    image_to_markdown,
    table_to_markdown,
    tesseract_binary,
)
from ki_knowledge.integrations.pdf_paths import pdf_relative_source_path, pdf_source_id
from ki_knowledge.knowledge.ontology_ingest import fetch_ontology_url, import_ontology_to_store
from ki_knowledge.ui.knowledge_api_client import discover_markdown_files
from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.integrations.tei_ingest import parse_tei
from ki_knowledge.knowledge.models import KnowledgeArtifact, KnowledgeBlockRecord, KnowledgeSource

IMAGE_PROCESSING_OCR = "ocr"
IMAGE_PROCESSING_ASSET = "asset"
IMAGE_PROCESSING_OPTIONS = (IMAGE_PROCESSING_OCR, IMAGE_PROCESSING_ASSET)


def store() -> KnowledgeStore:
    return KnowledgeStore(settings.KNOWLEDGE_STORE_TARGET)


def data_dir(domain: str | None = None) -> Path:
    return domain_markdown_dir(domain)


def _infer_domain_from_path(path: Path | str | None) -> str | None:
    return infer_domain_from_path(path)


def discover_pdf_files(root: Path) -> list[Path]:
    if not root.exists():
        return []

    found: list[Path] = []
    seen: set[str] = set()

    def walk(current: Path) -> None:
        try:
            resolved_current = current.resolve(strict=False)
        except OSError:
            resolved_current = current
        key = str(resolved_current)
        if key in seen:
            return
        seen.add(key)

        if current.is_file():
            if current.suffix.lower() == ".pdf":
                found.append(current)
            return

        if not current.is_dir():
            return

        try:
            children = sorted(current.iterdir(), key=lambda item: item.name)
        except OSError:
            return

        for child in children:
            walk(child)

    walk(root)
    return sorted({path.resolve(strict=False) for path in found}, key=lambda item: str(item))


def workspace_markdown_files(query: str = "", domain: str | None = None) -> list[dict[str, str]]:
    root = data_dir(domain)
    files = discover_markdown_files(root)
    normalized_query = query.strip().lower()
    if normalized_query:
        files = [
            path
            for path in files
            if normalized_query in path.name.lower() or normalized_query in path.as_posix().lower()
        ]
    return [{"name": path.relative_to(root).as_posix(), "path": str(path)} for path in files]


def discover_ontology_files(root: Path) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []
    suffixes = {".owl", ".rdf", ".ttl", ".n3", ".jsonld"}
    return sorted(path for path in root.glob("**/*") if path.is_file() and path.suffix.lower() in suffixes)


def workspace_ontology_files(query: str = "", domain: str | None = None) -> list[dict[str, str]]:
    root = domain_ontology_dir(domain)
    files = discover_ontology_files(root)
    normalized_query = query.strip().lower()
    if normalized_query:
        files = [
            path
            for path in files
            if normalized_query in path.name.lower() or normalized_query in path.as_posix().lower()
        ]
    return [{"name": path.relative_to(root).as_posix(), "path": str(path)} for path in files]


def render_markdown_html(content: str) -> str:
    return markdown.markdown(
        content,
        extensions=["fenced_code", "tables", "sane_lists", "toc"],
        output_format="html5",
    )


def tree_lines(node, prefix: str = "") -> list[str]:
    lines: list[str] = []
    for child in node.iter_children():
        lines.append(f"{prefix}{child.name}/")
        lines.extend(tree_lines(child, prefix=prefix + "  "))
    for file_path in node.files:
        lines.append(f"{prefix}{file_path.name}")
    return lines


def import_markdown_file(path: Path, *, source_name: str | None = None, block_types: list[str] | None = None) -> dict[str, Any]:
    from ki_knowledge.django_site.services import store as legacy_store

    store_obj = legacy_store()
    if "/ontology/" in str(path) and path.suffix == ".md":
        invalidate_domain_summary_cache(_infer_domain_from_path(path))
        return {"imported": 0, "source_id": "owl:deprecated-markdown", "note": "Ontology markdown import is deprecated; use OWL format directly"}
    if block_types is None and "/ontology/" in str(path):
        block_types = ["heading", "paragraph"]
    source_id = f"markdown:{path.resolve()}"
    store_obj.import_markdown_file(
        path,
        source_name=source_name,
        allowed_block_types=block_types,
        source_id=source_id,
    )
    invalidate_domain_summary_cache(_infer_domain_from_path(path))
    return {"imported": len(store_obj.list_records(source_id=source_id)), "source_id": source_id}


def import_ontology_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        record_count, source_id = import_ontology_to_store(
            text,
            source_url=str(path),
            title=path.stem.replace("_", " ").title(),
        )
        invalidate_domain_summary_cache(_infer_domain_from_path(path))
        return {"imported": record_count, "source_id": source_id, "type": "ontology"}
    except Exception as exc:
        invalidate_domain_summary_cache(_infer_domain_from_path(path))
        return {"imported": 0, "error": str(exc), "type": "ontology"}


def import_ontology_directory(directory: Path) -> dict[str, Any]:
    if not directory.exists() or not directory.is_dir():
        return {"imported": 0, "error": f"Directory not found: {directory}", "files": 0}

    ontology_suffixes = {".owl", ".rdf", ".ttl", ".n3", ".jsonld"}
    ontology_files = sorted(
        path for path in directory.glob("**/*") if path.is_file() and path.suffix.lower() in ontology_suffixes
    )
    if not ontology_files:
        return {"imported": 0, "files": 0}

    imported = 0
    source_ids: list[str] = []
    for ontology_path in ontology_files:
        result = import_ontology_file(ontology_path)
        imported += int(result.get("imported", 0))
        if "source_id" in result:
            source_ids.append(result["source_id"])
    invalidate_domain_summary_cache(_infer_domain_from_path(directory))
    return {"imported": imported, "source_ids": source_ids, "files": len(ontology_files)}


def import_ontology_url(url: str, *, top_n: int = 50) -> dict[str, Any]:
    text, content_type = fetch_ontology_url(url)
    record_count, source_id = import_ontology_to_store(
        text,
        source_url=url,
        content_type=content_type,
        title=Path(url).stem.replace("_", " ").title() or "Ontology",
        top_n=top_n,
    )
    return {"imported": record_count, "source_id": source_id, "type": "ontology"}


def import_markdown_directory(directory: Path, *, block_types: list[str] | None = None) -> dict[str, Any]:
    store_obj = store()
    files = discover_markdown_files(directory)
    imported = 0
    source_ids: list[str] = []
    for file_path in files:
        result = import_markdown_file(
            file_path,
            source_name=file_path.relative_to(directory).as_posix(),
            block_types=block_types,
        )
        imported += int(result["imported"])
        source_ids.append(result["source_id"])
    invalidate_domain_summary_cache(_infer_domain_from_path(directory))
    return {"imported": imported, "source_ids": source_ids, "files": len(files)}


def import_pdf_file(path: Path, *, source_name: str | None = None, domain: str | None = None) -> dict[str, Any]:
    store_obj = store()
    if not path.exists():
        invalidate_domain_summary_cache(domain or _infer_domain_from_path(path))
        return {"imported": 0, "error": f"PDF not found: {path}"}

    try:
        markdown_text = pdf_extract_text(path)
    except Exception as exc:
        invalidate_domain_summary_cache(domain or _infer_domain_from_path(path))
        return {"imported": 0, "error": str(exc), "file": str(path)}

    if not markdown_text.strip():
        invalidate_domain_summary_cache(domain or _infer_domain_from_path(path))
        return {"imported": 0, "error": "PDF contains no extractable text", "file": str(path)}

    store_obj.import_markdown_text(
        markdown_text,
        source_path=str(path.resolve()),
        source_name=source_name or pdf_relative_source_path(path, domain=domain),
        source_id=pdf_source_id(path, domain=domain),
        source_type="pdf",
        replace=True,
    )
    invalidate_domain_summary_cache(domain or _infer_domain_from_path(path))
    source_id = pdf_source_id(path, domain=domain)
    return {"imported": len(store_obj.list_records(source_id=source_id)), "source_id": source_id, "file": str(path)}


def import_pdf_directory(directory: Path, *, domain: str | None = None) -> dict[str, Any]:
    if not directory.exists() or not directory.is_dir():
        invalidate_domain_summary_cache(domain or _infer_domain_from_path(directory))
        return {"imported": 0, "error": f"Directory not found: {directory}"}

    pdf_files = discover_pdf_files(directory)
    imported = 0
    source_ids: list[str] = []

    for pdf_path in pdf_files:
        try:
            relative_name = pdf_path.relative_to(directory).as_posix()
        except ValueError:
            relative_name = pdf_path.name
        result = import_pdf_file(pdf_path, source_name=relative_name, domain=domain)
        imported += int(result.get("imported", 0))
        if "source_id" in result:
            source_ids.append(result["source_id"])

    invalidate_domain_summary_cache(domain or _infer_domain_from_path(directory))
    return {"imported": imported, "source_ids": source_ids, "files": len(pdf_files)}


def _mixed_relative_name(path: Path, domain: str | None) -> str:
    root = domain_mix_dir(domain)
    for candidate in (path, path.resolve(strict=False)):
        for base in (root, root.resolve(strict=False)):
            try:
                return candidate.relative_to(base).as_posix()
            except ValueError:
                continue
    return path.name


def mixed_source_id(path: Path, domain: str | None = None) -> str:
    return f"mix:{_mixed_relative_name(path, domain)}"


def _mixed_source_location(path: Path) -> str:
    """Keep the path below the domain folder (not the symlink target) so domain scoping matches."""
    return str(path.expanduser().absolute())


def _import_converted_file(path: Path, kind: str, markdown_text: str, *, domain: str | None, source_name: str | None) -> dict[str, Any]:
    source_id = mixed_source_id(path, domain)
    store_obj = store()
    store_obj.import_markdown_text(
        markdown_text,
        source_path=_mixed_source_location(path),
        source_name=source_name or _mixed_relative_name(path, domain),
        source_id=source_id,
        source_type=kind,
    )
    return {
        "imported": len(store_obj.list_records(source_id=source_id)),
        "source_id": source_id,
        "file": str(path),
        "kind": kind,
    }


def import_table_file(path: Path, *, domain: str | None = None, source_name: str | None = None) -> dict[str, Any]:
    """Import a CSV/TSV/ODS/XLSX table; each row becomes one knowledge block."""
    resolved_domain = domain or _infer_domain_from_path(path)
    try:
        result = _import_converted_file(path, TABLE_KIND, table_to_markdown(path), domain=resolved_domain, source_name=source_name)
    except (MixedIngestError, OSError, UnicodeError) as exc:
        result = {"imported": 0, "error": str(exc), "file": str(path), "kind": TABLE_KIND}
    invalidate_domain_summary_cache(resolved_domain)
    return result


REFERENCE_STRUCTURE_ARTIFACT = "reference_structure"


def import_tei_file(path: Path, *, domain: str | None = None, source_name: str | None = None) -> dict[str, Any]:
    """Import a TEI edition as page text and keep its markup outline as reference structure.

    Headings are imported as plain paragraphs so structure detection still has
    to find them; the TEI ``div``/``head`` outline is stored separately as a
    ``reference_structure`` artifact for evaluation.
    """
    resolved_domain = domain or _infer_domain_from_path(path)
    try:
        document = parse_tei(path)
        result = _import_converted_file(path, TEI_KIND, document.to_markdown(), domain=resolved_domain, source_name=source_name)
    except (ValueError, OSError, UnicodeError) as exc:
        invalidate_domain_summary_cache(resolved_domain)
        return {"imported": 0, "error": str(exc), "file": str(path), "kind": TEI_KIND}

    source_id = result["source_id"]
    store_obj = store()
    source = store_obj.get_source(source_id)
    if source is not None:
        source.title = source_name or document.title or source.title
        source.metadata = {
            **source.metadata,
            "domain": resolved_domain,
            "relative_path": _mixed_relative_name(path, resolved_domain),
            "title": document.title,
            "author": document.author,
            "year": document.year,
            "licence": document.licence,
            "pages_total": len(document.pages),
            "reference_sections": len(document.sections),
        }
        store_obj.upsert_source(source)
    store_obj.upsert_artifact(
        KnowledgeArtifact(
            artifact_id=hashlib.sha256(f"{source_id}:{REFERENCE_STRUCTURE_ARTIFACT}".encode("utf-8")).hexdigest()[:24],
            artifact_type=REFERENCE_STRUCTURE_ARTIFACT,
            source_id=source_id,
            source_block_ids=[],
            content=document.outline_markdown(),
            metadata={
                "origin": "tei",
                "licence": document.licence,
                "pages_total": len(document.pages),
                "sections": [section.to_dict() for section in document.sections],
            },
        )
    )
    invalidate_domain_summary_cache(resolved_domain)
    return {**result, "reference_sections": len(document.sections), "pages": len(document.pages)}


def import_image_file(
    path: Path,
    *,
    domain: str | None = None,
    source_name: str | None = None,
    image_processing: str = IMAGE_PROCESSING_OCR,
) -> dict[str, Any]:
    """Always store the image as an object; optionally add OCR-derived text."""
    resolved_domain = domain or _infer_domain_from_path(path)
    if image_processing not in IMAGE_PROCESSING_OPTIONS:
        return {"imported": 0, "error": f"unknown image processing mode: {image_processing}", "file": str(path)}

    source_id = mixed_source_id(path, resolved_domain)
    relative_path = _mixed_relative_name(path, resolved_domain)
    store_obj = store()
    source = KnowledgeSource(
        source_id=source_id,
        source_type=IMAGE_KIND,
        title=source_name or relative_path,
        location=_mixed_source_location(path),
        metadata={
            "domain": resolved_domain,
            "relative_path": relative_path,
            "folder": str(Path(relative_path).parent) if Path(relative_path).parent != Path(".") else "",
            "image_processing": image_processing,
        },
    )
    store_obj.upsert_source(source)
    store_obj.delete_records_by_type(source_id, {"heading", "paragraph", "list_item", "code_block"})
    image_record = KnowledgeBlockRecord(
        block_id=hashlib.sha256(f"{source_id}:image".encode("utf-8")).hexdigest()[:24],
        source_id=source_id,
        block_type=IMAGE_KIND,
        object_type="image",
        title=Path(source_name or relative_path).name,
        content="",
        path=str(Path(relative_path).parent) if Path(relative_path).parent != Path(".") else "",
        order_index=0,
        metadata={
            "record_schema_version": 1,
            "source_format": path.suffix.lower().lstrip("."),
            "relative_path": relative_path,
            "media_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            "provenance": {"extractor": "native_asset", "source_format": path.suffix.lower().lstrip(".")},
        },
    )
    store_obj.upsert_record(image_record)
    imported = 1
    warnings = []
    try:
        if image_processing == IMAGE_PROCESSING_OCR:
            blocks = store_obj.import_markdown_text(
                image_to_markdown(path),
                source_path=_mixed_source_location(path),
                source_name=source_name or relative_path,
                source_id=source_id,
                source_type=IMAGE_KIND,
            )
            imported += len([block for block in blocks if block.block_type != "heading"])
            store_obj.upsert_source(source)
    except (MixedIngestError, OSError) as exc:
        warnings.append(str(exc))
    invalidate_domain_summary_cache(resolved_domain)
    return {
        "imported": imported,
        "source_id": source_id,
        "file": str(path),
        "kind": IMAGE_KIND,
        "warnings": warnings,
        "image_processing": image_processing,
    }


def import_mixed_file(
    path: Path,
    *,
    domain: str | None = None,
    image_processing: str = IMAGE_PROCESSING_OCR,
) -> dict[str, Any]:
    """Import one file of any supported kind (PDFs synchronously)."""
    kind = classify_file(path)
    if kind == TABLE_KIND:
        return import_table_file(path, domain=domain)
    if kind == IMAGE_KIND:
        return import_image_file(path, domain=domain, image_processing=image_processing)
    if kind == TEI_KIND:
        return import_tei_file(path, domain=domain)
    if kind == PDF_KIND:
        return {**import_pdf_file(path, domain=domain), "kind": kind}
    if kind == MARKDOWN_KIND:
        return {**import_markdown_file(path, source_name=_mixed_relative_name(path, domain)), "kind": kind}
    if kind == ONTOLOGY_KIND:
        return {**import_ontology_file(path), "kind": kind}
    return {"imported": 0, "error": f"unsupported file type: {path.suffix or path.name}", "file": str(path), "kind": kind}


def mixed_files_summary(domain: str | None = None) -> dict[str, Any]:
    """Counts per kind in the domain's ``mix`` folder plus OCR availability."""
    root = domain_mix_dir(domain)
    grouped = discover_mixed_files(root)
    return {
        "dir": root,
        "exists": root.exists(),
        "counts": {kind: len(grouped[kind]) for kind in MIX_KINDS},
        "total": sum(len(files) for files in grouped.values()),
        "unsupported_examples": [path.name for path in grouped["unsupported"][:5]],
        "ocr_available": tesseract_binary() is not None,
    }


def import_mixed_directory(
    directory: Path,
    *,
    domain: str | None = None,
    queue_pdf: Callable[[Path], Any] | None = None,
    kinds: tuple[str, ...] = MIX_KINDS,
    image_processing: str = IMAGE_PROCESSING_OCR,
) -> dict[str, Any]:
    """Import every supported file below ``directory``.

    PDFs go to ``queue_pdf`` (e.g. the PDF job queue) when given, otherwise
    they are imported synchronously.     Images are still stored as image objects when OCR is unavailable; the
    optional text extraction warning is returned in ``errors``.
    """
    resolved_domain = domain or _infer_domain_from_path(directory)
    grouped = discover_mixed_files(directory)
    summary: dict[str, Any] = {
        "imported": 0,
        "files": {kind: 0 for kind in MIX_KINDS},
        "queued_pdfs": 0,
        "source_ids": [],
        "errors": [],
        "unsupported": [str(path) for path in grouped["unsupported"]],
    }
    for kind in kinds:
        if kind == "unsupported":
            continue
        for path in grouped[kind]:
            if kind == PDF_KIND and queue_pdf is not None:
                try:
                    queue_pdf(path)
                    summary["queued_pdfs"] += 1
                except (FileNotFoundError, OSError, ValueError) as exc:
                    summary["errors"].append({"file": str(path), "kind": kind, "error": str(exc)})
                continue
            result = import_mixed_file(path, domain=resolved_domain, image_processing=image_processing)
            summary["files"][kind] += 1
            summary["imported"] += int(result.get("imported", 0) or 0)
            if result.get("error"):
                summary["errors"].append({"file": str(path), "kind": kind, "error": result["error"]})
            for warning in result.get("warnings", []):
                summary["errors"].append({"file": str(path), "kind": kind, "error": warning})
            if not result.get("error") and result.get("source_id"):
                summary["source_ids"].append(result["source_id"])
    invalidate_domain_summary_cache(resolved_domain)
    return summary


__all__ = [
    "data_dir",
    "discover_pdf_files",
    "workspace_markdown_files",
    "discover_ontology_files",
    "workspace_ontology_files",
    "render_markdown_html",
    "tree_lines",
    "import_markdown_file",
    "import_ontology_file",
    "import_ontology_directory",
    "import_ontology_url",
    "import_markdown_directory",
    "import_pdf_file",
    "import_pdf_directory",
    "import_table_file",
    "import_image_file",
    "import_mixed_file",
    "import_mixed_directory",
    "mixed_files_summary",
    "mixed_source_id",
]
