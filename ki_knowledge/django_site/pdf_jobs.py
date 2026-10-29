"""PDF queue access, worker startup and report snapshots."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import subprocess
import sys
import uuid

from django.conf import settings
from ki_knowledge.services.domain_paths import data_layout

from .data_display import display_data_path
from .domain_registry import default_semantic_domain


def pdf_batch_db_path(domain: str | None = None) -> str:
    """Get the PDF batch job database path.

    The job queue is global, not per domain; ``domain`` is accepted for
    backwards compatibility only.
    """
    return str(data_layout().pdf_jobs_db_path())


def get_pdf_batch_processor():
    """Get or create PDF batch processor."""
    from ki_knowledge.integrations.pdf_batch import PDFBatchProcessor
    db_path = pdf_batch_db_path()
    return PDFBatchProcessor(db_path)


def start_pdf_worker(domain: str) -> dict[str, Any]:
    """Launch one detached, tracked PDF worker for a domain from the GUI."""
    processor = get_pdf_batch_processor()
    pending = processor.list_jobs(domain=domain, status="pending")
    if not pending:
        return {"started": False, "reason": "empty", "worker": processor.get_worker_run()}

    log_dir = Path(pdf_batch_db_path()).parent
    log_dir.mkdir(parents=True, exist_ok=True)
    token_hint = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    log_path = log_dir / f"pdf-worker-{token_hint}-{uuid.uuid4().hex[:8]}.log"
    reservation = processor.reserve_worker(domain, str(log_path))
    if not reservation["started"]:
        return {"started": False, "reason": "active", "worker": reservation}

    command = [
        sys.executable,
        str(Path(settings.BASE_DIR) / "manage.py"),
        "process_pdf_jobs",
        "--domain",
        domain,
        "--worker-token",
        reservation["token"],
    ]
    try:
        with log_path.open("ab") as output:
            child = subprocess.Popen(
                command,
                cwd=str(settings.BASE_DIR),
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                close_fds=True,
                start_new_session=True,
            )
    except OSError as exc:
        processor.fail_worker_start(reservation["token"], str(exc))
        return {"started": False, "reason": "launch-failed", "error": str(exc), "worker": processor.get_worker_run()}

    processor.worker_started(reservation["token"], child.pid)
    return {
        "started": True,
        "worker": processor.get_worker_run(),
        "pending_at_start": len(pending),
        "log_path": str(log_path),
    }


def pdf_import_jobs(domain: str | None = None, status: str | None = None, limit: int = 100) -> list[dict]:
    """Get PDF import jobs for a domain."""
    processor = get_pdf_batch_processor()
    jobs = processor.list_jobs(domain=domain or default_semantic_domain(), status=status)
    jobs = jobs[:limit]
    
    return [
        {
            "job_id": j.job_id,
            "pdf_path": j.pdf_path,
            "display_pdf_path": display_data_path(j.pdf_path),
            "domain": j.domain,
            "status": j.status,
            "pages_total": j.pages_total,
            "pages_processed": j.pages_processed,
            "progress_percent": (j.pages_processed / j.pages_total * 100) if j.pages_total > 0 else 0,
            "error_message": j.error_message,
            "created_at": j.created_at,
            "started_at": j.started_at,
            "heartbeat_at": j.heartbeat_at,
            "completed_at": j.completed_at,
            "attempt_count": j.attempt_count,
            "source_id": j.source_id,
            "artifact_id": j.artifact_id,
            "content_preview": _compact_job_preview(j.content_preview),
            "display_content_preview": _compact_job_preview(j.content_preview, limit=80),
        }
        for j in jobs
    ]


def _compact_job_preview(value: str | None, *, limit: int = 200) -> str:
    text = (value or "").replace("\r", " ").replace("\n", " ").strip()
    if not text:
        return ""
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _parse_iso_datetime(value: str | None) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _minutes_since(value: str | None) -> int | None:
    parsed = _parse_iso_datetime(value)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)
    return max(0, int(delta.total_seconds() // 60))


def pdf_import_report(domain: str | None = None, *, limit: int = 12) -> dict[str, Any]:
    """Build a report snapshot for the PDF import queue."""
    resolved_domain = domain or default_semantic_domain()
    jobs = pdf_import_jobs(domain=resolved_domain, limit=2000)
    counts = {
        "total": len(jobs),
        "pending": sum(1 for job in jobs if job["status"] == "pending"),
        "processing": sum(1 for job in jobs if job["status"] == "processing"),
        "done": sum(1 for job in jobs if job["status"] == "done"),
        "failed": sum(1 for job in jobs if job["status"] == "failed"),
    }
    processing_jobs = [
        {
            **job,
            "display_pdf_path": display_data_path(job["pdf_path"]),
            "age_minutes": _minutes_since(job.get("heartbeat_at") or job.get("started_at") or job.get("created_at")),
        }
        for job in jobs
        if job["status"] == "processing"
    ]
    pending_jobs = [
        {
            **job,
            "display_pdf_path": display_data_path(job["pdf_path"]),
            "age_minutes": _minutes_since(job.get("created_at")),
        }
        for job in jobs
        if job["status"] == "pending"
    ]
    failed_jobs = [
        {
            **job,
            "display_pdf_path": display_data_path(job["pdf_path"]),
            "age_minutes": _minutes_since(job.get("completed_at") or job.get("created_at")),
        }
        for job in jobs
        if job["status"] == "failed"
    ]
    return {
        "domain": resolved_domain,
        "counts": counts,
        "processing_jobs": processing_jobs,
        "pending_jobs": pending_jobs[:limit],
        "failed_jobs": failed_jobs[:limit],
        "recent_done": [
            {**job, "display_pdf_path": display_data_path(job["pdf_path"])}
            for job in jobs
            if job["status"] == "done"
        ][:limit],
        "stale_processing": [
            job
            for job in processing_jobs
            if job.get("age_minutes") is not None and job["age_minutes"] >= 60
        ],
    }


def get_pdf_job_stats(domain: str | None = None) -> dict[str, int]:
    """Get PDF import job statistics for a domain."""
    jobs = pdf_import_jobs(domain=domain, limit=1000)
    return {
        "total": len(jobs),
        "pending": sum(1 for j in jobs if j["status"] == "pending"),
        "processing": sum(1 for j in jobs if j["status"] == "processing"),
        "done": sum(1 for j in jobs if j["status"] == "done"),
        "failed": sum(1 for j in jobs if j["status"] == "failed"),
    }


def create_pdf_import_job(pdf_path: str, domain: str | None = None, *, force: bool = False) -> str:
    """Create a new PDF import job."""
    processor = get_pdf_batch_processor()
    return processor.create_job(pdf_path, domain=domain or default_semantic_domain(), force=force)


def delete_pdf_import_jobs(job_ids: list[str], domain: str | None = None) -> dict[str, int]:
    """Delete old PDF import jobs for a domain."""
    processor = get_pdf_batch_processor()
    return processor.delete_jobs(job_ids, domain=domain or default_semantic_domain())


def process_pdf_import_job(job_id: str) -> dict:
    """Process a PDF import job immediately."""
    processor = get_pdf_batch_processor()
    return processor.process_job(job_id)
