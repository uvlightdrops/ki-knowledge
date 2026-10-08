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
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ki_knowledge.app_config import AppConfig as Config
from ki_knowledge.config_runtime import knowledge_db_path, knowledge_store_target
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
    attempt_count: int = 0
    claim_token: str | None = None
    heartbeat_at: str | None = None


class PDFBatchProcessor(SqliteJobStoreBase):
    """Manages PDF import jobs with progress tracking."""

    table_name = "pdf_import_jobs"

    def _init_db(self) -> None:
        super()._init_db()
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pdf_worker_runs (
                    token TEXT PRIMARY KEY,
                    domain TEXT NOT NULL,
                    status TEXT NOT NULL,
                    pid INTEGER,
                    log_path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    heartbeat_at TEXT NOT NULL,
                    finished_at TEXT,
                    error_message TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pdf_worker_runs_status_heartbeat "
                "ON pdf_worker_runs(status, heartbeat_at)"
            )
            conn.commit()

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
                result_json TEXT,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                claim_token TEXT,
                heartbeat_at TEXT
            )
        """

    def _extra_columns(self) -> dict[str, str]:
        # Additive columns for on-disk databases created before these existed.
        return {
            "source_id": "TEXT",
            "artifact_id": "TEXT",
            "content_preview": "TEXT",
            "result_json": "TEXT",
            "attempt_count": "INTEGER NOT NULL DEFAULT 0",
            "claim_token": "TEXT",
            "heartbeat_at": "TEXT",
        }

    def _index_sql(self) -> list[str]:
        return [
            "CREATE INDEX IF NOT EXISTS idx_pdf_jobs_domain_status_created "
            "ON pdf_import_jobs(domain, status, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_pdf_jobs_domain_path_status "
            "ON pdf_import_jobs(domain, pdf_path, status)",
        ]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 30000")
        return conn

    def reserve_worker(self, domain: str, log_path: str, *, stale_after_seconds: int = 45) -> dict[str, Any]:
        """Reserve the single GUI-started worker or report the already active one."""
        now_dt = datetime.now(timezone.utc)
        now = now_dt.isoformat()
        cutoff = datetime.fromtimestamp(
            now_dt.timestamp() - max(10, stale_after_seconds),
            tz=timezone.utc,
        ).isoformat()
        token = uuid.uuid4().hex
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                UPDATE pdf_worker_runs
                SET status = 'failed', finished_at = ?, error_message = 'Worker heartbeat expired'
                WHERE status IN ('starting', 'running') AND heartbeat_at < ?
                """,
                (now, cutoff),
            )
            active = conn.execute(
                "SELECT * FROM pdf_worker_runs WHERE status IN ('starting', 'running') "
                "ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            if active is not None:
                conn.commit()
                return {**dict(active), "started": False}
            conn.execute(
                """
                INSERT INTO pdf_worker_runs
                    (token, domain, status, log_path, created_at, heartbeat_at)
                VALUES (?, ?, 'starting', ?, ?, ?)
                """,
                (token, domain, log_path, now, now),
            )
            row = conn.execute("SELECT * FROM pdf_worker_runs WHERE token = ?", (token,)).fetchone()
            conn.commit()
        return {**dict(row), "started": True}

    def worker_started(self, token: str, pid: int) -> bool:
        """Record the child PID without reviving a completed/expired run."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE pdf_worker_runs SET status = 'running', pid = ?, heartbeat_at = ?
                WHERE token = ? AND (
                    status = 'starting' OR (status = 'running' AND pid = ?)
                )
                """,
                (pid, now, token, pid),
            )
            conn.commit()
        return cursor.rowcount == 1

    def worker_heartbeat(self, token: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE pdf_worker_runs SET heartbeat_at = ?
                WHERE token = ? AND status IN ('starting', 'running')
                """,
                (now, token),
            )
            conn.commit()
        return cursor.rowcount == 1

    def finish_worker(self, token: str, *, error_message: str = "") -> bool:
        now = datetime.now(timezone.utc).isoformat()
        status = "failed" if error_message else "done"
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE pdf_worker_runs
                SET status = ?, finished_at = ?, heartbeat_at = ?, error_message = ?
                WHERE token = ? AND status IN ('starting', 'running')
                """,
                (status, now, now, error_message or None, token),
            )
            conn.commit()
        return cursor.rowcount == 1

    def get_worker_run(self, *, stale_after_seconds: int = 45) -> dict[str, Any] | None:
        """Return the latest GUI worker and mark an expired heartbeat as failed."""
        cutoff = datetime.fromtimestamp(
            datetime.now(timezone.utc).timestamp() - max(10, stale_after_seconds),
            tz=timezone.utc,
        ).isoformat()
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE pdf_worker_runs
                SET status = 'failed', finished_at = ?, error_message = 'Worker heartbeat expired'
                WHERE status IN ('starting', 'running') AND heartbeat_at < ?
                """,
                (now, cutoff),
            )
            row = conn.execute(
                "SELECT * FROM pdf_worker_runs ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            conn.commit()
        return dict(row) if row is not None else None

    def fail_worker_start(self, token: str, error_message: str) -> bool:
        return self.finish_worker(token, error_message=error_message)

    def create_job(self, pdf_path: str | Path, domain: str = "default", *, force: bool = False) -> str:
        """Idempotently enqueue a PDF; active jobs are reused and failed jobs requeued."""
        resolved_path = Path(pdf_path).expanduser()
        if not resolved_path.is_file():
            raise FileNotFoundError(f"PDF file not found: {resolved_path}")
        if resolved_path.suffix.lower() != ".pdf":
            raise ValueError(f"Not a PDF file: {resolved_path}")

        normalized_domain = (domain or "default").strip() or "default"
        normalized_path = str(resolved_path.resolve(strict=False))
        stable_hash = hashlib.sha1(f"{normalized_domain}:{normalized_path}".encode("utf-8")).hexdigest()[:16]
        job_id = f"pdf_{stable_hash}"

        try:
            from pypdf import PdfReader
            with open(resolved_path, "rb") as f:
                reader = PdfReader(f)
                pages_total = len(reader.pages)
        except Exception:
            pages_total = 0

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT job_id, status FROM pdf_import_jobs WHERE domain = ? AND pdf_path = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (normalized_domain, normalized_path),
            ).fetchone()
            if existing:
                if existing["status"] == "failed" or (force and existing["status"] == "done"):
                    conn.execute(
                        """
                        UPDATE pdf_import_jobs
                        SET status = 'pending', pages_total = ?, pages_processed = 0,
                            error_message = NULL, created_at = ?, started_at = NULL,
                            completed_at = NULL, claim_token = NULL, heartbeat_at = NULL,
                            source_id = NULL, artifact_id = NULL, content_preview = NULL, result_json = NULL
                        WHERE job_id = ? AND status = ?
                        """,
                        (pages_total, datetime.now(timezone.utc).isoformat(), existing["job_id"], existing["status"]),
                    )
                conn.commit()
                return str(existing["job_id"])

            conn.execute(
                """
                INSERT INTO pdf_import_jobs
                (job_id, pdf_path, domain, status, pages_total, created_at)
                VALUES (?, ?, ?, 'pending', ?, ?)
                """,
                (job_id, normalized_path, normalized_domain, pages_total, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

        return job_id

    def requeue_job(self, job_id: str, *, domain: str | None = None, include_done: bool = False) -> bool:
        """Explicitly requeue a terminal job while preserving its stable job ID and attempt history."""
        terminal_statuses = ("failed", "done") if include_done else ("failed",)
        placeholders = ", ".join("?" for _ in terminal_statuses)
        clauses = [f"status IN ({placeholders})", "job_id = ?"]
        params: list[Any] = [*terminal_statuses, job_id]
        if domain is not None:
            clauses.append("domain = ?")
            params.append(domain)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute(
                f"""
                UPDATE pdf_import_jobs
                SET status = 'pending', pages_processed = 0, error_message = NULL,
                    started_at = NULL, completed_at = NULL, claim_token = NULL, heartbeat_at = NULL,
                    source_id = NULL, artifact_id = NULL, content_preview = NULL, result_json = NULL,
                    created_at = ?
                WHERE {' AND '.join(clauses)}
                """,
                [datetime.now(timezone.utc).isoformat(), *params],
            )
            conn.commit()
        return cursor.rowcount == 1

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

    def claim_job(self, job_id: str | None = None, *, domain: str | None = None) -> PDFImportJob | None:
        """Atomically claim the oldest pending job, or a specific pending job."""
        token = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            clauses = ["status = 'pending'"]
            params: list[Any] = []
            if job_id is not None:
                clauses.append("job_id = ?")
                params.append(job_id)
            if domain is not None:
                clauses.append("domain = ?")
                params.append(domain)
            row = conn.execute(
                "SELECT * FROM pdf_import_jobs WHERE " + " AND ".join(clauses) + " ORDER BY created_at, job_id LIMIT 1",
                params,
            ).fetchone()
            if row is None:
                conn.commit()
                return None
            updated = conn.execute(
                """
                UPDATE pdf_import_jobs
                SET status = 'processing', started_at = ?, heartbeat_at = ?,
                    claim_token = ?, attempt_count = attempt_count + 1,
                    pages_processed = 0, error_message = NULL, completed_at = NULL
                WHERE job_id = ? AND status = 'pending'
                """,
                (now, now, token, row["job_id"]),
            ).rowcount
            if updated != 1:
                conn.rollback()
                return None
            claimed = conn.execute("SELECT * FROM pdf_import_jobs WHERE job_id = ?", (row["job_id"],)).fetchone()
            conn.commit()
        return self._row_to_job(claimed)

    def start_job(self, job_id: str) -> str | None:
        """Compatibility wrapper returning the claim token for the claimed job."""
        claimed = self.claim_job(job_id)
        return claimed.claim_token if claimed is not None else None

    def mark_started(self, job_id: str) -> str | None:
        """Compatibility alias that still claims atomically instead of updating blindly."""
        return self.start_job(job_id)

    def mark_failed(self, job_id: str, error_message: str) -> None:
        raise RuntimeError("PDF jobs must be failed with fail_job(job_id, error_message, claim_token)")

    def _heartbeat_job(self, job_id: str, claim_token: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE pdf_import_jobs SET heartbeat_at = ? "
                "WHERE job_id = ? AND status = 'processing' AND claim_token = ?",
                (now, job_id, claim_token),
            )
            conn.commit()
        return cursor.rowcount == 1

    def update_progress(self, job_id: str, pages_processed: int, claim_token: str) -> bool:
        """Update progress for the worker that currently owns this job."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE pdf_import_jobs SET pages_processed = ?, heartbeat_at = ? "
                "WHERE job_id = ? AND status = 'processing' AND claim_token = ?",
                (pages_processed, now, job_id, claim_token),
            )
            conn.commit()
        return cursor.rowcount == 1

    def complete_job(self, job_id: str, claim_token: str) -> bool:
        """Complete a job only for its current owner."""
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE pdf_import_jobs SET status = 'done', completed_at = ?, "
                "claim_token = NULL, heartbeat_at = NULL "
                "WHERE job_id = ? AND status = 'processing' AND claim_token = ?",
                (datetime.now(timezone.utc).isoformat(), job_id, claim_token),
            )
            conn.commit()
        return cursor.rowcount == 1

    def update_result_metadata(
        self,
        job_id: str,
        *,
        source_id: str | None = None,
        artifact_id: str | None = None,
        content_preview: str | None = None,
        result_json: str | None = None,
        claim_token: str,
    ) -> None:
        """Persist the source/artifact details for a job."""
        fields = {
            "source_id": source_id,
            "artifact_id": artifact_id,
            "content_preview": content_preview,
            "result_json": result_json,
        }
        values = {k: v for k, v in fields.items() if v is not None}
        assignments = ", ".join(f"{key} = ?" for key in values)
        with self._connect() as conn:
            cursor = conn.execute(
                f"UPDATE pdf_import_jobs SET {assignments}, heartbeat_at = ? "
                "WHERE job_id = ? AND status = 'processing' AND claim_token = ?",
                [*values.values(), datetime.now(timezone.utc).isoformat(), job_id, claim_token],
            )
            conn.commit()
        if cursor.rowcount != 1:
            raise RuntimeError(f"PDF job lease lost before saving result: {job_id}")

    def fail_job(self, job_id: str, error_message: str, claim_token: str) -> bool:
        """Fail a job, optionally only if the caller still owns its lease."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE pdf_import_jobs SET status = 'failed', error_message = ?, completed_at = ?, "
                "claim_token = NULL, heartbeat_at = NULL "
                "WHERE job_id = ? AND status = 'processing' AND claim_token = ?",
                (error_message, now, job_id, claim_token),
            )
            conn.commit()
        return cursor.rowcount == 1

    def process_job(
        self,
        job_id: str,
        callback: callable | None = None,
        *,
        timeout_seconds: int = 3600,
    ) -> dict[str, Any]:
        """Claim and process one pending job; concurrent workers cannot both run it."""
        claimed = self.claim_job(job_id)
        if claimed is None:
            current = self.get_job(job_id)
            if current is None:
                raise ValueError(f"Job not found: {job_id}")
            return {
                "job_id": job_id,
                "status": current.status,
                "claimed": False,
                "error": "Job is not pending; another worker may own it.",
            }

        claim_token = claimed.claim_token
        if not claim_token:
            raise RuntimeError(f"Claimed PDF job has no lease token: {job_id}")

        return self._process_with_heartbeat(claimed, claim_token, callback, timeout_seconds)

    def _process_with_heartbeat(
        self,
        job: PDFImportJob,
        claim_token: str,
        callback: callable | None,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        stop_heartbeat = threading.Event()

        def heartbeat() -> None:
            interval = max(1.0, min(30.0, max(timeout_seconds, 1) / 3))
            while not stop_heartbeat.wait(interval):
                if not self._heartbeat_job(job.job_id, claim_token):
                    return

        heartbeat_thread = threading.Thread(target=heartbeat, name=f"pdf-heartbeat-{job.job_id}", daemon=True)
        heartbeat_thread.start()
        try:
            return self._process_claimed_job(job, claim_token, callback)
        finally:
            stop_heartbeat.set()
            heartbeat_thread.join(timeout=2)

    def _process_claimed_job(
        self,
        job: PDFImportJob,
        claim_token: str,
        callback: callable | None,
    ) -> dict[str, Any]:
        job_id = job.job_id
        pdf_path = Path(job.pdf_path)

        try:
            text = extract_text_from_pdf(pdf_path)
            if not text.strip():
                raise ValueError("PDF contains no extractable text")

            lines = text.split("\n")
            page_markers = [line for line in lines if line.startswith("## Page")]
            pages_processed = len(page_markers)

            if not self.update_progress(job_id, pages_processed, claim_token):
                return {"job_id": job_id, "status": "lease_lost", "file": str(pdf_path)}
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
                claim_token=claim_token,
            )
            if not self.complete_job(job_id, claim_token):
                return {"job_id": job_id, "status": "lease_lost", "file": str(pdf_path)}

            return {
                **result_payload,
                "source_id": source_id,
                "artifact_id": None if artifact is None else artifact.artifact_id,
                "content_preview": preview,
            }
        except Exception as exc:
            error_msg = str(exc)
            if not self.fail_job(job_id, error_msg, claim_token):
                return {"job_id": job_id, "status": "lease_lost", "file": str(pdf_path)}
            return {
                "job_id": job_id,
                "status": "failed",
                "error": error_msg,
                "file": str(pdf_path),
            }

    def _knowledge_db_path(self) -> Path:
        return knowledge_db_path(Config.from_env())

    def _knowledge_store(self) -> KnowledgeStore:
        return KnowledgeStore(knowledge_store_target(Config.from_env()))

    def cleanup_stale_jobs(self, domain: str | None = None, timeout_seconds: int = 3600) -> dict[str, int]:
        """Fail expired leases and safely suppress duplicate pending jobs.

        Processing jobs are never removed or superseded. If a duplicate group
        has a live processing job it is preserved; otherwise the oldest pending
        job is retained. Superseded pending rows are retained as failed for audit.
        """
        threshold = max(1, int(timeout_seconds))
        cutoff = datetime.fromtimestamp(
            datetime.now(timezone.utc).timestamp() - threshold,
            tz=timezone.utc,
        ).isoformat()
        now = datetime.now(timezone.utc).isoformat()
        clauses = ["status = 'processing'", "COALESCE(heartbeat_at, started_at, created_at) < ?"]
        params: list[Any] = [cutoff]
        if domain is not None:
            clauses.append("domain = ?")
            params.append(domain)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                "SELECT job_id FROM pdf_import_jobs WHERE " + " AND ".join(clauses),
                params,
            ).fetchall()
            job_ids = [row["job_id"] for row in rows]
            for job_id in job_ids:
                conn.execute(
                    """
                    UPDATE pdf_import_jobs
                    SET status = 'failed', error_message = ?, completed_at = ?,
                        claim_token = NULL, heartbeat_at = NULL
                    WHERE job_id = ? AND status = 'processing'
                    """,
                    (f"Worker lease expired after {threshold}s without heartbeat", now, job_id),
                )
            duplicate_clauses = ["status IN ('pending', 'processing')"]
            duplicate_params: list[Any] = []
            if domain is not None:
                duplicate_clauses.append("domain = ?")
                duplicate_params.append(domain)
            active = conn.execute(
                "SELECT job_id, domain, pdf_path, status, created_at FROM pdf_import_jobs WHERE "
                + " AND ".join(duplicate_clauses)
                + " ORDER BY domain, pdf_path, CASE status WHEN 'processing' THEN 0 ELSE 1 END, created_at DESC, job_id",
                duplicate_params,
            ).fetchall()
            grouped: dict[tuple[str, str], list[sqlite3.Row]] = {}
            for row in active:
                grouped.setdefault((row["domain"], row["pdf_path"]), []).append(row)
            duplicates = 0
            for rows in grouped.values():
                if len(rows) < 2:
                    continue
                retained = next((row for row in rows if row["status"] == "processing"), rows[0])
                for row in rows:
                    if row["job_id"] == retained["job_id"] or row["status"] == "processing":
                        continue
                    changed = conn.execute(
                        """
                        UPDATE pdf_import_jobs
                        SET status = 'failed', error_message = ?, completed_at = ?
                        WHERE job_id = ? AND status = 'pending'
                        """,
                        (f"Duplicate pending job superseded by {retained['job_id']}", now, row["job_id"]),
                    ).rowcount
                    duplicates += changed
            conn.commit()
        return {
            "timed_out": len(job_ids),
            "duplicate_pending_removed": duplicates,
            "duplicates_suppressed": duplicates,
        }

    def retry_failed_jobs(
        self,
        domain: str | None = None,
        job_ids: list[str] | None = None,
    ) -> dict[str, int]:
        """Atomically return selected failed jobs to pending without changing their IDs."""
        clauses = ["status = 'failed'"]
        params: list[Any] = []
        if domain is not None:
            clauses.append("domain = ?")
            params.append(domain)
        if job_ids is not None:
            ids = list(dict.fromkeys(item.strip() for item in job_ids if item.strip()))
            if not ids:
                return {"retried": 0}
            placeholders = ", ".join("?" for _ in ids)
            clauses.append(f"job_id IN ({placeholders})")
            params.extend(ids)
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                "SELECT job_id FROM pdf_import_jobs WHERE " + " AND ".join(clauses),
                params,
            ).fetchall()
            selected_ids = [row["job_id"] for row in rows]
            for selected_id in selected_ids:
                conn.execute(
                    """
                    UPDATE pdf_import_jobs
                    SET status = 'pending', pages_processed = 0, error_message = NULL,
                        started_at = NULL, completed_at = NULL, claim_token = NULL, heartbeat_at = NULL,
                        source_id = NULL, artifact_id = NULL, content_preview = NULL, result_json = NULL,
                        created_at = ?
                    WHERE job_id = ? AND status = 'failed'
                    """,
                    (now, selected_id),
                )
            conn.commit()
        return {"retried": len(selected_ids)}

    def process_pending_jobs(
        self,
        domain: str | None = None,
        timeout_seconds: int = 3600,
        callback: callable | None = None,
        max_jobs: int | None = None,
    ) -> dict[str, int]:
        """Recover expired leases and process jobs this worker atomically claims."""
        cleanup = self.cleanup_stale_jobs(domain=domain, timeout_seconds=timeout_seconds)
        claimed = 0
        done = 0
        failed = 0
        limit = None if max_jobs is None else max(0, int(max_jobs))
        while limit is None or claimed < limit:
            job = self.claim_job(domain=domain)
            if job is None:
                break
            claimed += 1
            token = job.claim_token
            if not token:
                raise RuntimeError(f"Claimed PDF job has no lease token: {job.job_id}")
            result = self._process_with_heartbeat(job, token, callback, timeout_seconds)
            if result.get("status") == "done":
                done += 1
            elif result.get("status") == "failed":
                failed += 1
        return {
            "claimed": claimed,
            "done": done,
            "failed": failed,
            "timed_out": cleanup.get("timed_out", 0),
            "total_pending": claimed,
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
            conn.execute("BEGIN IMMEDIATE")
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
            attempt_count=int(row["attempt_count"] or 0) if "attempt_count" in row.keys() else 0,
            claim_token=row["claim_token"] if "claim_token" in row.keys() else None,
            heartbeat_at=row["heartbeat_at"] if "heartbeat_at" in row.keys() else None,
        )
