"""Job tracking store for knowledge extraction/publishing pipelines.

This mirrors the existing PDFBatchProcessor pattern (ki_knowledge.integrations.pdf_batch):
a durable, idempotent SQLite job table that decouples pipeline execution from the
request/response cycle of Django views. Views only create/read job records; the
actual extraction+storage work is executed by a separate runner function that can
be invoked from a view, a management command, or a cron job identically.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


@dataclass
class KnowledgeExtractionJob:
    """Track a knowledge-block extraction + publish job for one InfoSite project."""

    job_id: str
    project_id: int
    source_id: str
    status: str  # pending, processing, done, failed
    files_processed: int = 0
    blocks_stored: int = 0
    error_message: Optional[str] = None
    created_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result_json: Optional[str] = None

    @property
    def result(self) -> dict[str, Any]:
        if not self.result_json:
            return {}
        try:
            return json.loads(self.result_json)
        except (TypeError, ValueError):
            return {}


class KnowledgeExtractionJobStore:
    """SQLite-backed store for knowledge extraction jobs."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_extraction_jobs (
                    job_id TEXT PRIMARY KEY,
                    project_id INTEGER NOT NULL,
                    source_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    files_processed INTEGER DEFAULT 0,
                    blocks_stored INTEGER DEFAULT 0,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    result_json TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_knowledge_extraction_jobs_project "
                "ON knowledge_extraction_jobs(project_id)"
            )
            conn.commit()

    @staticmethod
    def make_job_id(project_id: int, source_id: str) -> str:
        seed = f"{project_id}:{source_id}"
        digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]
        return f"kbex_{digest}"

    def create_job(self, project_id: int, source_id: str) -> str:
        """Create a job if none is currently pending/processing for this project (idempotent)."""
        now = datetime.now(timezone.utc).isoformat()
        job_id = self.make_job_id(project_id, source_id)

        with self._connect() as conn:
            existing = conn.execute(
                "SELECT job_id FROM knowledge_extraction_jobs "
                "WHERE project_id = ? AND status IN ('pending', 'processing') LIMIT 1",
                (project_id,),
            ).fetchone()
            if existing:
                return existing["job_id"]

            conn.execute(
                """
                INSERT INTO knowledge_extraction_jobs (
                    job_id, project_id, source_id, status, created_at
                ) VALUES (?, ?, ?, 'pending', ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    status = 'pending',
                    error_message = NULL,
                    started_at = NULL,
                    completed_at = NULL,
                    result_json = NULL,
                    created_at = excluded.created_at
                """,
                (job_id, project_id, source_id, now),
            )
            conn.commit()
        return job_id

    def mark_started(self, job_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE knowledge_extraction_jobs SET status = 'processing', started_at = ? WHERE job_id = ?",
                (now, job_id),
            )
            conn.commit()

    def mark_done(self, job_id: str, files_processed: int, blocks_stored: int, result: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE knowledge_extraction_jobs
                SET status = 'done', files_processed = ?, blocks_stored = ?,
                    completed_at = ?, result_json = ?
                WHERE job_id = ?
                """,
                (files_processed, blocks_stored, now, json.dumps(result, ensure_ascii=False, default=str), job_id),
            )
            conn.commit()

    def mark_failed(self, job_id: str, error_message: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE knowledge_extraction_jobs SET status = 'failed', error_message = ?, completed_at = ? "
                "WHERE job_id = ?",
                (error_message, now, job_id),
            )
            conn.commit()

    def get_job(self, job_id: str) -> Optional[KnowledgeExtractionJob]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM knowledge_extraction_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        return self._row_to_job(row) if row else None

    def list_jobs(
        self, project_id: Optional[int] = None, status: Optional[str] = None, limit: int = 200
    ) -> list[KnowledgeExtractionJob]:
        query = "SELECT * FROM knowledge_extraction_jobs"
        clauses = []
        params: list[Any] = []
        if project_id is not None:
            clauses.append("project_id = ?")
            params.append(project_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_job(row) for row in rows]

    def list_pending(self, limit: int = 50) -> list[KnowledgeExtractionJob]:
        return self.list_jobs(status="pending", limit=limit)

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> KnowledgeExtractionJob:
        return KnowledgeExtractionJob(
            job_id=row["job_id"],
            project_id=row["project_id"],
            source_id=row["source_id"],
            status=row["status"],
            files_processed=row["files_processed"],
            blocks_stored=row["blocks_stored"],
            error_message=row["error_message"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            result_json=row["result_json"],
        )
