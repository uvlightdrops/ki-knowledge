"""Runner for the knowledge extraction pipeline, decoupled from Django views.

This module owns the actual extract-and-store business logic. It is invoked
identically from:
  - Django views (infosite_publish_knowledge_blocks): enqueue + run inline
  - management command run_knowledge_extraction: CLI / cron execution
  - future async worker: same function, no request/response coupling

Views must not perform extraction logic directly; they only create a job
record (idempotent) and delegate execution to `run_extraction_job`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ki_knowledge.integrations.knowledge_pipeline_jobs import KnowledgeExtractionJobStore


def get_job_store() -> KnowledgeExtractionJobStore:
    db_path = Path.home() / ".ki-knowledge" / "pipeline_jobs.db"
    return KnowledgeExtractionJobStore(db_path)


def enqueue_extraction(project) -> str:
    """Create (or reuse) an idempotent extraction job for this project."""
    from ki_knowledge.services.block_storage import InfoSiteBlockStorage

    storage = InfoSiteBlockStorage(project)
    source_id = storage.get_source_id()
    store = get_job_store()
    return store.create_job(project_id=project.id, source_id=source_id)


def run_extraction_job(job_id: str) -> dict[str, Any]:
    """Execute a previously enqueued extraction job.

    Safe to call multiple times: re-running a completed job re-extracts and
    upserts blocks (KnowledgeStore.upsert_record is idempotent by block_id).
    """
    from ki_knowledge.django_site.infosite_models import InfoSiteProject
    from ki_knowledge.services.block_storage import InfoSiteBlockStorage

    store = get_job_store()
    job = store.get_job(job_id)
    if job is None:
        raise ValueError(f"Unknown job_id: {job_id}")

    store.mark_started(job_id)
    try:
        project = InfoSiteProject.objects.get(id=job.project_id)
        storage = InfoSiteBlockStorage(project)
        results = storage.extract_and_store()
        storage.update_document_status()

        store.mark_done(
            job_id,
            files_processed=results.get("files_processed", 0),
            blocks_stored=results.get("blocks_stored", 0),
            result=results,
        )
        return results
    except Exception as exc:  # noqa: BLE001 - persist any failure onto the job record
        store.mark_failed(job_id, str(exc))
        raise


def enqueue_and_run(project) -> dict[str, Any]:
    """Convenience helper for call sites that want synchronous behavior today
    but a decoupled, idempotent, resumable job record for tomorrow (e.g. once
    a real task queue/worker is introduced, only this function's internals
    change -- callers keep working unmodified).
    """
    job_id = enqueue_extraction(project)
    result = run_extraction_job(job_id)
    result["job_id"] = job_id
    return result


def run_pending_jobs(limit: int = 50) -> dict[str, int]:
    """Process all pending extraction jobs. Intended for CLI/cron execution."""
    from ki_knowledge.django_site.infosite_models import InfoSiteProject

    store = get_job_store()
    pending = store.list_pending(limit=limit)
    done = 0
    failed = 0
    for job in pending:
        try:
            run_extraction_job(job.job_id)
            done += 1
        except InfoSiteProject.DoesNotExist:
            store.mark_failed(job.job_id, f"InfoSiteProject {job.project_id} no longer exists")
            failed += 1
        except Exception:
            failed += 1
    return {"claimed": len(pending), "done": done, "failed": failed}
