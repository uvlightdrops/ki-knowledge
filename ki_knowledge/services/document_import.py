"""Synchronous import-status jobs over an explicit document repository."""

from __future__ import annotations

from typing import Protocol, TypedDict

from ki_knowledge.integrations.document_import_jobs import DocumentImportJobStore


class ImportResult(TypedDict):
    job_id: str
    documents_requested: int
    documents_imported: int


class ImportDocuments(Protocol):
    def mark_imported(self, project_id: int, document_ids: list[int]) -> int:
        """Mark selected project documents imported and return the changed count."""
        ...


class DocumentImportService:
    def __init__(self, jobs: DocumentImportJobStore, documents: ImportDocuments):
        self.jobs = jobs
        self.documents = documents

    def enqueue(self, project_id: int, document_ids: list[int]) -> str:
        return self.jobs.create_job(project_id=project_id, document_ids=document_ids)

    def run(self, job_id: str) -> ImportResult:
        job = self.jobs.get_job(job_id)
        if job is None:
            raise ValueError(f"Unknown job_id: {job_id}")
        self.jobs.mark_started(job_id)
        try:
            imported = self.documents.mark_imported(job.project_id, job.document_ids)
            self.jobs.mark_done(job_id, documents_imported=imported)
        except Exception as exc:
            self.jobs.mark_failed(job_id, str(exc))
            raise
        return {
            "job_id": job_id,
            "documents_requested": job.documents_requested,
            "documents_imported": imported,
        }

    def enqueue_and_run(self, project_id: int, document_ids: list[int]) -> ImportResult:
        return self.run(self.enqueue(project_id, document_ids))
