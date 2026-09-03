"""Job tracking store for knowledge extraction/publishing pipelines.

This mirrors the existing PDFBatchProcessor pattern (ki_knowledge.integrations.pdf_batch):
a durable, idempotent SQLite job table that decouples pipeline execution from the
request/response cycle of Django views. Views only create/read job records; the
actual extraction+storage work is executed by a separate runner function that can
be invoked from a view, a management command, or a cron job identically.

The generic connection/schema/status-transition boilerplate lives in
SqliteJobStoreBase (job_store_base.py), shared with DocumentImportJobStore.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from ki_knowledge.integrations.job_store_base import SqliteJobStoreBase


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


class KnowledgeExtractionJobStore(SqliteJobStoreBase):
    """SQLite-backed store for knowledge extraction jobs."""

    table_name = "knowledge_extraction_jobs"

    def _create_table_sql(self) -> str:
        return f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
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

    def _index_sql(self) -> list[str]:
        return [
            f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_project ON {self.table_name}(project_id)"
        ]

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
                f"SELECT job_id FROM {self.table_name} "
                "WHERE project_id = ? AND status IN ('pending', 'processing') LIMIT 1",
                (project_id,),
            ).fetchone()
            if existing:
                return existing["job_id"]

            conn.execute(
                f"""
                INSERT INTO {self.table_name} (
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

    def mark_done(self, job_id: str, files_processed: int, blocks_stored: int, result: dict[str, Any]) -> None:
        self._update_fields(
            job_id,
            {
                "status": "done",
                "files_processed": files_processed,
                "blocks_stored": blocks_stored,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "result_json": json.dumps(result, ensure_ascii=False, default=str),
            },
        )

    def list_jobs(
        self, project_id: Optional[int] = None, status: Optional[str] = None, limit: int = 200
    ) -> list[KnowledgeExtractionJob]:
        return self._list_jobs({"project_id": project_id, "status": status}, limit=limit)

    def list_pending(self, limit: int = 50) -> list[KnowledgeExtractionJob]:
        return self.list_jobs(status="pending", limit=limit)

    def _row_to_job(self, row: sqlite3.Row) -> KnowledgeExtractionJob:
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
