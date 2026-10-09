"""Django glue for the book pipeline: collect a domain's documents and read the overview."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from django.conf import settings

from ki_knowledge.integrations.document_pipeline import (
    DocumentInput,
    DocumentStageStore,
    funnel,
    sync_documents,
)
from ki_knowledge.integrations.pdf_paths import pdf_source_id
from ki_knowledge.integrations.sql_backend import connect

from .domain_paths import normalize_semantic_domain


def stage_store() -> DocumentStageStore:
    return DocumentStageStore(settings.KNOWLEDGE_STORE_TARGET)


def _newest_pdf_jobs(domain: str) -> list[dict[str, Any]]:
    from .services import pdf_batch_db_path

    path = Path(pdf_batch_db_path())
    if not path.is_file():
        return []
    try:
        with closing(sqlite3.connect(path.absolute().as_uri() + "?mode=ro", uri=True)) as connection:
            rows = connection.execute(
                "SELECT pdf_path, status, error_message, pages_total, source_id FROM pdf_import_jobs "
                "WHERE domain = ? ORDER BY created_at DESC",
                (domain,),
            ).fetchall()
    except sqlite3.Error:
        return []
    newest: dict[str, dict[str, Any]] = {}
    for pdf_path, status, error, pages_total, source_id in rows:
        key = str(Path(pdf_path).expanduser().resolve(strict=False))
        if key not in newest:
            newest[key] = {
                "path": pdf_path,
                "status": status or "",
                "error": error or "",
                "pages_total": int(pages_total or 0),
                "source_id": source_id or pdf_source_id(pdf_path, domain=domain),
            }
    return list(newest.values())


BOOK_SOURCE_TYPES = frozenset({"pdf", "tei"})


def domain_documents(domain: str) -> list[DocumentInput]:
    """Imported book sources (PDF, TEI) of the domain plus PDFs whose newest import job failed or is open."""
    from .knowledge_summary import _domain_scoped_sources

    jobs = {job["source_id"]: job for job in _newest_pdf_jobs(domain)}
    documents: dict[str, DocumentInput] = {}
    for source in _domain_scoped_sources(domain):
        if source.source_type not in BOOK_SOURCE_TYPES:
            continue
        job = jobs.get(source.source_id, {})
        metadata = getattr(source, "metadata", None) or {}
        extra = {"source_type": source.source_type}
        if metadata.get("reference_sections"):
            extra["reference_sections"] = int(metadata["reference_sections"])
        documents[source.source_id] = DocumentInput(
            source_id=source.source_id,
            title=source.title or Path(str(source.location)).stem,
            path=str(source.location or ""),
            imported=True,
            pages_total=int(job.get("pages_total") or metadata.get("pages_total") or 0),
            job_status=str(job.get("status", "")),
            job_error=str(job.get("error", "")),
            extra=extra,
        )
    for source_id, job in jobs.items():
        if source_id in documents:
            continue
        documents[source_id] = DocumentInput(
            source_id=source_id,
            title=Path(job["path"]).stem,
            path=job["path"],
            imported=False,
            pages_total=job["pages_total"],
            job_status=job["status"],
            job_error=job["error"],
        )
    return list(documents.values())


def linked_record_ids(domain: str) -> set[str]:
    from .services import semantic_target

    target = semantic_target(domain)
    if target.is_sqlite and not Path(str(target.sqlite_path)).is_file():
        return set()
    try:
        with connect(target) as conn:
            return {row[0] for row in conn.execute("SELECT DISTINCT record_id FROM semantic_record_term_links").fetchall()}
    except Exception:  # A domain without semantic store simply has no links yet.
        return set()


def refresh_book_pipeline(domain: str) -> dict[str, int]:
    resolved = normalize_semantic_domain(domain)
    return sync_documents(
        stage_store(),
        settings.KNOWLEDGE_STORE_TARGET,
        resolved,
        domain_documents(resolved),
        linked_record_ids=linked_record_ids(resolved),
    )


def book_pipeline_overview(domain: str) -> dict[str, Any]:
    resolved = normalize_semantic_domain(domain)
    store = stage_store()
    documents = store.documents(resolved)
    return {
        "documents": documents,
        "funnel": funnel(documents),
        "last_updated": store.last_updated(resolved),
    }
