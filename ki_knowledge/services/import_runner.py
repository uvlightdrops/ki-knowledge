"""Runner for the document-import step, decoupled from the Django view.

Mirrors ki_knowledge.services.pipeline_runner: the view only creates a job
record and delegates the actual "mark these documents as imported" work to
`run_import_job`, so the same function can later be called from a management
command or a real async worker without changing the job-record contract.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from django.utils import timezone

from ki_knowledge.integrations.document_import_jobs import DocumentImportJobStore


def get_job_store() -> DocumentImportJobStore:
    db_path = Path.home() / ".ki-knowledge" / "pipeline_jobs.db"
    return DocumentImportJobStore(db_path)


def enqueue_import(project_id: int, document_ids: list[int]) -> str:
    """Create a new import job for an explicit document selection."""
    store = get_job_store()
    return store.create_job(project_id=project_id, document_ids=document_ids)


def run_import_job(job_id: str) -> dict[str, Any]:
    """Execute a previously enqueued import job: mark selected documents as imported."""
    from ki_knowledge.django_site.infosite_models import SourceDocument

    store = get_job_store()
    job = store.get_job(job_id)
    if job is None:
        raise ValueError(f"Unknown job_id: {job_id}")

    store.mark_started(job_id)
    try:
        imported_count = 0
        for doc_id in job.document_ids:
            try:
                doc = SourceDocument.objects.get(id=doc_id, project_id=job.project_id)
            except SourceDocument.DoesNotExist:
                continue
            if doc.import_status != "imported":
                doc.import_status = "imported"
                doc.imported = True
                doc.imported_at = timezone.now()
                doc.save()
                imported_count += 1

        store.mark_done(job_id, documents_imported=imported_count)
        return {
            "job_id": job_id,
            "documents_requested": job.documents_requested,
            "documents_imported": imported_count,
        }
    except Exception as exc:  # noqa: BLE001 - persist any failure onto the job record
        store.mark_failed(job_id, str(exc))
        raise


def enqueue_and_run_import(project_id: int, document_ids: list[int]) -> dict[str, Any]:
    """Convenience helper: create + run an import job synchronously today,
    while keeping the job-record contract stable for a future async worker.
    """
    job_id = enqueue_import(project_id, document_ids)
    result = run_import_job(job_id)
    return result
