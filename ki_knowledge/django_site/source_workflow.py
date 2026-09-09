from __future__ import annotations

from typing import Any
from pathlib import Path

import markdown
from django.conf import settings

from ki_knowledge.app_config import AppConfig as Config
from ki_knowledge.django_site.domain_paths import (
    default_semantic_domain,
    domain_markdown_dir,
    domain_ontology_dir,
    domain_pdf_dir,
    invalidate_domain_summary_cache,
    normalize_semantic_domain,
)
from ki_knowledge.integrations.pdf_ingest import extract_text_from_pdf as pdf_extract_text
from ki_knowledge.integrations.pdf_paths import pdf_relative_source_path, pdf_source_id
from ki_knowledge.knowledge.ontology_ingest import fetch_ontology_url, import_ontology_to_store
from ki_knowledge.ui.knowledge_api_client import discover_markdown_files
from ki_knowledge.integrations.knowledge_store import KnowledgeStore


def store() -> KnowledgeStore:
    return KnowledgeStore(settings.KNOWLEDGE_DB_PATH)


def data_dir(domain: str | None = None) -> Path:
    return domain_markdown_dir(domain)


def _infer_domain_from_path(path: Path | str | None) -> str | None:
    raw = str(path or "").strip()
    if not raw:
        return None
    candidate = Path(raw).expanduser()
    root_candidates = [
        domain_markdown_dir(),
        domain_ontology_dir(),
        domain_pdf_dir(),
    ]
    for root in root_candidates:
        try:
            relative = candidate.resolve().relative_to(root.resolve())
        except (OSError, RuntimeError, ValueError):
            continue
        if relative.parts:
            return normalize_semantic_domain(relative.parts[0])
    return None


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
    blocks = store_obj.import_markdown_file(path, source_name=source_name, allowed_block_types=block_types)
    invalidate_domain_summary_cache(_infer_domain_from_path(path))
    return {"imported": len(blocks), "source_id": f"markdown:{path.resolve()}"}


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

    blocks = store_obj.import_markdown_text(
        markdown_text,
        source_path=str(path.resolve()),
        source_name=source_name or pdf_relative_source_path(path, domain=domain),
        source_id=pdf_source_id(path, domain=domain),
        source_type="pdf",
    )
    invalidate_domain_summary_cache(domain or _infer_domain_from_path(path))
    return {"imported": len(blocks), "source_id": pdf_source_id(path, domain=domain), "file": str(path)}


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
]
