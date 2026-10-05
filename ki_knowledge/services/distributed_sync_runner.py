from __future__ import annotations

from typing import Any

from ki_knowledge.data_layout import DataLayout
from ki_knowledge.integrations.distributed_sync_jobs import DistributedSyncJobStore


def get_job_store() -> DistributedSyncJobStore:
    return DistributedSyncJobStore(DataLayout.from_config().pipeline_jobs_db_path())


def enqueue_sync_job(*, domain: str, job_type: str, payload: dict[str, Any] | None = None) -> str:
    return get_job_store().create_job(domain=domain, job_type=job_type, payload=payload)


def run_sync_job(job_id: str) -> dict[str, Any]:
    from ki_knowledge.django_site.distributed_api import export_sync_snapshot, pull_domains_from_master

    store = get_job_store()
    job = store.get_job(job_id)
    if job is None:
        raise ValueError(f"Unknown job_id: {job_id}")

    store.mark_started(job_id)
    try:
        if job.job_type == "pull":
            result = pull_domains_from_master(domains=[job.domain])
        elif job.job_type == "export":
            result = export_sync_snapshot(domains=[job.domain])
        else:
            raise ValueError(f"unsupported distributed sync job type: {job.job_type}")
        store.mark_done(job_id, result=result)
        return {"job_id": job_id, "job_type": job.job_type, "domain": job.domain, **result}
    except Exception as exc:
        store.mark_failed(job_id, str(exc))
        raise


def enqueue_sync(*, domain: str, job_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    job_id = enqueue_sync_job(domain=domain, job_type=job_type, payload=payload)
    return {"job_id": job_id, "job_type": job_type, "domain": domain, "status": "pending"}


def run_pending_sync_jobs(*, domain: str | None = None, limit: int = 50) -> dict[str, Any]:
    store = get_job_store()
    jobs = store.list_pending_for_domain(domain, limit=limit) if domain else store.list_pending(limit=limit)
    result = {"claimed": len(jobs), "done": 0, "failed": 0}
    for job in jobs:
        try:
            run_sync_job(job.job_id)
            result["done"] += 1
        except Exception:
            result["failed"] += 1
    return result
