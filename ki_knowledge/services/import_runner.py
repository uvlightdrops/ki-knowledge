"""Compatibility entry points for synchronous import-status jobs."""

from __future__ import annotations

from ki_knowledge.data_layout import DataLayout
from ki_knowledge.integrations.document_import_jobs import DocumentImportJobStore
from ki_knowledge.services.document_import import DocumentImportService, ImportResult


def get_job_store() -> DocumentImportJobStore:
    return DocumentImportJobStore(DataLayout.from_config().pipeline_jobs_db_path())


def enqueue_import(project_id: int, document_ids: list[int]) -> str:
    """Create a new import job for an explicit document selection."""
    store = get_job_store()
    return store.create_job(project_id=project_id, document_ids=document_ids)


def _service() -> DocumentImportService:
    from ki_knowledge.django_site.document_import import DjangoImportDocuments

    return DocumentImportService(get_job_store(), DjangoImportDocuments())


def run_import_job(job_id: str) -> ImportResult:
    """Run inline; this call returns only after completion or raises on failure."""
    return _service().run(job_id)


def enqueue_and_run_import(project_id: int, document_ids: list[int]) -> ImportResult:
    """Convenience helper: create + run an import job synchronously today,
    while keeping the job-record contract stable for a future async worker.
    """
    job_id = enqueue_import(project_id, document_ids)
    result = run_import_job(job_id)
    return result
