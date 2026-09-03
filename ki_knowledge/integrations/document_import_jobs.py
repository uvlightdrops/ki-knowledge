"""Job tracking store for the document-import step ("mark selected as imported").

Mirrors the existing KnowledgeExtractionJobStore/PDFBatchProcessor pattern: a
durable SQLite job table that records *what* was imported, *when*, and with
what result, instead of silently flipping a status flag inside a request/
response cycle. This gives the import step the same auditability and UI
consistency as the knowledge-extraction pipeline (job history, status, error
messages), and leaves room to make the actual import step genuinely
asynchronous later (e.g. checksum/content-hash computation, virus scanning,
format conversion) without changing the job-record contract.

Unlike KnowledgeExtractionJobStore's per-project idempotent job_id, import
jobs are *not* idempotent by design: each "Import-Job starten" click is a
distinct, user-initiated batch operation over an explicit document selection,
so job_id is derived from a random token rather than a stable hash of inputs.

The generic connection/schema/status-transition boilerplate lives in
SqliteJobStoreBase (job_store_base.py), shared with KnowledgeExtractionJobStore.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from ki_knowledge.integrations.job_store_base import SqliteJobStoreBase


@dataclass
class DocumentImportJob:
    """Track a batch "mark documents as imported" operation for one project."""

    job_id: str
    project_id: int
    document_ids_json: str
    status: str  # pending, processing, done, failed
    documents_requested: int = 0
    documents_imported: int = 0
    error_message: Optional[str] = None
    created_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    @property
    def document_ids(self) -> list[int]:
        try:
            return json.loads(self.document_ids_json)
        except (TypeError, ValueError):
            return []


class DocumentImportJobStore(SqliteJobStoreBase):
    """SQLite-backed store for document import jobs."""

    table_name = "document_import_jobs"

    def _create_table_sql(self) -> str:
        return f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                job_id TEXT PRIMARY KEY,
                project_id INTEGER NOT NULL,
                document_ids_json TEXT NOT NULL,
                status TEXT NOT NULL,
                documents_requested INTEGER DEFAULT 0,
                documents_imported INTEGER DEFAULT 0,
                error_message TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT
            )
        """

    def _index_sql(self) -> list[str]:
        return [
            f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_project ON {self.table_name}(project_id)"
        ]

    def create_job(self, project_id: int, document_ids: list[int]) -> str:
        now = datetime.now(timezone.utc).isoformat()
        job_id = f"dimp_{uuid.uuid4().hex[:16]}"
        with self._connect() as conn:
            conn.execute(
                f"""
                INSERT INTO {self.table_name} (
                    job_id, project_id, document_ids_json, status,
                    documents_requested, created_at
                ) VALUES (?, ?, ?, 'pending', ?, ?)
                """,
                (job_id, project_id, json.dumps(document_ids), len(document_ids), now),
            )
            conn.commit()
        return job_id

    def mark_done(self, job_id: str, documents_imported: int) -> None:
        self._update_fields(
            job_id,
            {
                "status": "done",
                "documents_imported": documents_imported,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    def list_jobs(self, project_id: Optional[int] = None, limit: int = 200) -> list[DocumentImportJob]:
        return self._list_jobs({"project_id": project_id}, limit=limit)

    def _row_to_job(self, row: sqlite3.Row) -> DocumentImportJob:
        return DocumentImportJob(
            job_id=row["job_id"],
            project_id=row["project_id"],
            document_ids_json=row["document_ids_json"],
            status=row["status"],
            documents_requested=row["documents_requested"],
            documents_imported=row["documents_imported"],
            error_message=row["error_message"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )
