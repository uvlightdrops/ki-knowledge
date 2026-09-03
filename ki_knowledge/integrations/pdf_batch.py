"""Batch processing for PDF imports with job tracking.

Shares its generic SQLite connection/schema/status-transition boilerplate
with KnowledgeExtractionJobStore and DocumentImportJobStore via
SqliteJobStoreBase (job_store_base.py). `start_job`/`fail_job`/`complete_job`
are this module's original (pre-unification) method names, kept as thin
wrappers around the shared base so existing callers (views, CLI commands,
tests) don't need to change.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ki_core.config import Config
from ki_knowledge.integrations.job_store_base import SqliteJobStoreBase
from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.integrations.pdf_ingest import extract_text_from_pdf
from ki_knowledge.integrations.pdf_paths import pdf_relative_source_path, pdf_source_id
from ki_knowledge.knowledge.generate import KnowledgeArtifactGenerator


@dataclass
class PDFImportJob:
    """Track PDF import job status."""
    job_id: str
    pdf_path: str
    domain: str
    status: str  # pending, processing, done, failed
    pages_total: int = 0
    pages_processed: int = 0
    error_message: str | None = None
    created_at: str = ""
    started_at: str | None = None
    completed_at: str | None = None
    source_id: str | None = None
    artifact_id: str | None = None
    content_preview: str | None = None
    result_json: str | None = None


class PDFBatchProcessor(SqliteJobStoreBase):
    """Manages PDF import jobs with progress tracking."""

    table_name = "pdf_import_jobs"

    def _create_table_sql(self) -> str:
        return f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                job_id TEXT PRIMARY KEY,
                pdf_path TEXT NOT NULL,
                domain TEXT NOT NULL,
                status TEXT NOT NULL,
                pages_total INTEGER DEFAULT 0,
                pages_processed INTEGER DEFAULT 0,
                error_message TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                source_id TEXT,
                artifact_id TEXT,
                content_preview TEXT,
                result_json TEXT
            )
        """

    def _extra_columns(self) -> dict[str, str]:
        # Additive columns for on-disk databases created before these existed.
        return {
            "source_id": "TEXT",
            "artifact_id": "TEXT",
            "content_preview": "TEXT",
            "result_json": "TEXT",
        }

    def create_job(self, pdf_path: str | Path, domain: str = "default") -> str:
        """Create a new PDF import job. Returns job_id."""
        resolved_path = Path(pdf_path).expanduser()
        pdf_path = str(resolved_path)
        if not resolved_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        normalized_domain = (domain or "default").strip() or "default"
        normalized_path = str(resolved_path.resolve(strict=False))
        stable_hash = hashlib.sha1(f"{normalized_domain}:{normalized_path}".encode("utf-8")).hexdigest()[:16]
        job_id = f"pdf_{stable_hash}"
        now = datetime.now(timezone.utc).isoformat()

        try:
            # Quick scan to get page count
            from pypdf import PdfReader
            with open(resolved_path, "rb") as f:
                reader = PdfReader(f)
                pages_total = len(reader.pages)
        except Exception:
            pages_total = 0

        with self._connect() as conn:
            existing = conn.execute(
                "SELECT job_id FROM pdf_import_jobs WHERE domain = ? AND pdf_path = ? AND status IN ('pending', 'processing') LIMIT 1",
                (normalized_domain, normalized_path),
            ).fetchone()
            if existing:
                return existing["job_id"]

            conn.execute(
                """
                INSERT INTO pdf_import_jobs
                (job_id, pdf_path, domain, status, pages_total, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (job_id, normalized_path, normalized_domain, "pending", pages_total, now),
            )
            conn.commit()

        return job_id

    def list_jobs(self, domain: str | None = None, status: str | None = None) -> list[PDFImportJob]:
        """List all jobs, optionally filtered by domain and/or status."""
        query = "SELECT * FROM pdf_import_jobs WHERE 1=1"
        params = []
        if domain:
            query += " AND domain = ?"
            params.append(domain)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_job(row) for row in rows]

    # -- status transitions (original method names, delegating to the shared base) --

    def start_job(self, job_id: str) -> None:
        """Mark job as processing."""
        self.mark_started(job_id)

    def update_progress(self, job_id: str, pages_processed: int) -> None:
        """Update page processing progress."""
        self._update_fields(job_id, {"pages_processed": pages_processed})

    def complete_job(self, job_id: str) -> None:
        """Mark job as completed."""
        self._update_fields(job_id, {"status": "done", "completed_at": datetime.now(timezone.utc).isoformat()})

    def update_result_metadata(
        self,
        job_id: str,
        *,
        source_id: str | None = None,
        artifact_id: str | None = None,
        content_preview: str | None = None,
        result_json: str | None = None,
    ) -> None:
        """Persist the source/artifact details for a job."""
        fields = {
            "source_id": source_id,
            "artifact_id": artifact_id,
            "content_preview": content_preview,
            "result_json": result_json,
        }
        self._update_fields(job_id, {k: v for k, v in fields.items() if v is not None})

    def fail_job(self, job_id: str, error_message: str) -> None:
        """Mark job as failed."""
        self.mark_failed(job_id, error_message)

    def process_job(
        self,
        job_id: str,
        callback: callable | None = None
    ) -> dict[str, Any]:
        """
        Process a single PDF import job.

        Args:
            job_id: Job ID to process
            callback: Optional function(pages_processed, pages_total) for progress updates

        Returns:
            Dict with results (imported blocks, etc.)
        """
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        self.start_job(job_id)
        pdf_path = Path(job.pdf_path)

        try:
            text = extract_text_from_pdf(pdf_path)
            if not text.strip():
                raise ValueError("PDF contains no extractable text")

            lines = text.split("\n")
            page_markers = [line for line in lines if line.startswith("## Page")]
            pages_processed = len(page_markers)

            self.update_progress(job_id, pages_processed)
            if callback:
                callback(pages_processed, job.pages_total)

            store = self._knowledge_store()
            source_path = str(pdf_path.resolve(strict=False))
            source_name = pdf_relative_source_path(pdf_path, domain=job.domain)
            source_id = pdf_source_id(pdf_path, domain=job.domain)
            blocks = store.import_markdown_text(
                text,
                source_path=source_path,
                source_name=source_name,
                source_id=source_id,
                source_type="pdf",
            )
            if not blocks:
                raise ValueError("PDF produced no knowledge blocks")
            artifact = None
            try:
                artifact = KnowledgeArtifactGenerator(store).generate_summary_note(source_id)
            except ValueError:
                artifact = None

            preview = " ".join(text.split())
            preview = preview[:1800]
            result_payload = {
                "job_id": job_id,
                "status": "done",
                "pages": pages_processed,
                "text_length": len(text),
                "file": str(pdf_path),
                "blocks_imported": len(blocks),
                "source_id": source_id,
                "artifact_id": None if artifact is None else artifact.artifact_id,
                "pipeline": [
                    "extract_text_from_pdf()",
                    "pdf_relative_source_path() + pdf_source_id()",
                    "KnowledgeStore.import_markdown_text(..., source_type='pdf')",
                    "KnowledgeArtifactGenerator.generate_summary_note(source_id)",
                ],
            }
            self.update_result_metadata(
                job_id,
                source_id=source_id,
                artifact_id=None if artifact is None else artifact.artifact_id,
                content_preview=preview,
                result_json=json.dumps(result_payload, ensure_ascii=False),
            )
            self.complete_job(job_id)

            return {
                **result_payload,
                "source_id": source_id,
                "artifact_id": None if artifact is None else artifact.artifact_id,
                "content_preview": preview,
            }
        except Exception as e:
            error_msg = str(e)
            self.fail_job(job_id, error_msg)
            return {
                "job_id": job_id,
                "status": "failed",
                "error": error_msg,
                "file": str(pdf_path),
            }

    def _knowledge_db_path(self) -> Path:
        raw = os.getenv("KNOWLEDGE_DB_PATH", "").strip()
        if raw:
            return Path(raw).expanduser()
        config = Config.from_env()
        if config.knowledge_data_root:
            return Path(config.knowledge_data_root).expanduser() / "knowledge.db"
        data_root = os.getenv("KICLI_DATA_ROOT", "").strip()
        if data_root:
            return Path(data_root).expanduser() / "knowledge.db"
        return Path.home() / "dev_data" / "ki-knowledge" / "knowledge.db"

    def _knowledge_store(self) -> KnowledgeStore:
        return KnowledgeStore(self._knowledge_db_path())

    def cleanup_stale_jobs(self, domain: str | None = None, timeout_seconds: int = 600) -> dict[str, int]:
        """Mark stale processing jobs as failed and delete duplicate pending jobs."""
        now = datetime.now(timezone.utc)
        threshold_seconds = max(0, int(timeout_seconds))
        timed_out = 0
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT job_id, started_at FROM pdf_import_jobs WHERE status = 'processing' AND (? - strftime('%s', started_at)) > ?",
                (now.timestamp(), threshold_seconds),
            ).fetchall()
            for job_id, _ in rows:
                self.fail_job(job_id, f"Timed out after {threshold_seconds}s")
                timed_out += 1

            if domain:
                rows = conn.execute(
                    """
                    SELECT job_id, pdf_path, created_at
                    FROM pdf_import_jobs
                    WHERE domain = ? AND status IN ('pending', 'processing')
                    ORDER BY created_at DESC
                    """,
                    (domain,),
                ).fetchall()
                grouped: dict[str, list[str]] = {}
                for job_id, pdf_path, _ in rows:
                    grouped.setdefault(pdf_path, []).append(job_id)
                for pdf_path, job_ids in grouped.items():
                    keep = job_ids[0]
                    for stale_job_id in job_ids[1:]:
                        conn.execute("DELETE FROM pdf_import_jobs WHERE job_id = ?", (stale_job_id,))
        return {"timed_out": timed_out, "duplicate_pending_removed": 0}

    def process_pending_jobs(self, domain: str | None = None, timeout_seconds: int = 600, callback: callable | None = None) -> dict[str, int]:
        """Process all pending jobs for a domain, recovering stale jobs before processing."""
        cleanup = self.cleanup_stale_jobs(domain=domain, timeout_seconds=timeout_seconds)
        jobs = self.list_jobs(domain=domain, status="pending")
        claimed = 0
        done = 0
        failed = 0
        for job in jobs:
            claimed += 1
            try:
                result = self.process_job(job.job_id, callback=callback)
            except Exception as exc:  # pragma: no cover - defensive path
                self.fail_job(job.job_id, str(exc))
                result = {"status": "failed", "error": str(exc)}
            if result.get("status") == "done":
                done += 1
            else:
                failed += 1
        return {
            "claimed": claimed,
            "done": done,
            "failed": failed,
            "timed_out": cleanup.get("timed_out", 0),
            "total_pending": len(jobs),
        }

    def delete_jobs(self, job_ids: list[str], *, domain: str | None = None) -> dict[str, int]:
        """Delete completed or failed jobs; active jobs are kept."""
        if not job_ids:
            return {"deleted": 0, "skipped_active": 0, "skipped_missing": 0}

        deleted = 0
        skipped_active = 0
        skipped_missing = 0
        normalized_domain = (domain or "").strip() or None

        with self._connect() as conn:
            for job_id in job_ids:
                row = conn.execute("SELECT job_id, domain, status FROM pdf_import_jobs WHERE job_id = ?", (job_id,)).fetchone()
                if row is None:
                    skipped_missing += 1
                    continue
                if normalized_domain is not None and str(row["domain"]) != normalized_domain:
                    skipped_missing += 1
                    continue
                if row["status"] in {"pending", "processing"}:
                    skipped_active += 1
                    continue
                conn.execute("DELETE FROM pdf_import_jobs WHERE job_id = ?", (job_id,))
                deleted += 1
            conn.commit()

        return {
            "deleted": deleted,
            "skipped_active": skipped_active,
            "skipped_missing": skipped_missing,
        }

    def _row_to_job(self, row: sqlite3.Row) -> PDFImportJob:
        """Convert database row to PDFImportJob."""
        return PDFImportJob(
            job_id=row["job_id"],
            pdf_path=row["pdf_path"],
            domain=row["domain"],
            status=row["status"],
            pages_total=row["pages_total"],
            pages_processed=row["pages_processed"],
            error_message=row["error_message"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            source_id=row["source_id"] if "source_id" in row.keys() else None,
            artifact_id=row["artifact_id"] if "artifact_id" in row.keys() else None,
            content_preview=row["content_preview"] if "content_preview" in row.keys() else None,
            result_json=row["result_json"] if "result_json" in row.keys() else None,
        )
