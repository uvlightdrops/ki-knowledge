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
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


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


class DocumentImportJobStore:
    """SQLite-backed store for document import jobs."""

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
                CREATE TABLE IF NOT EXISTS document_import_jobs (
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
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_document_import_jobs_project "
                "ON document_import_jobs(project_id)"
            )
            conn.commit()

    def create_job(self, project_id: int, document_ids: list[int]) -> str:
        now = datetime.now(timezone.utc).isoformat()
        job_id = f"dimp_{uuid.uuid4().hex[:16]}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO document_import_jobs (
                    job_id, project_id, document_ids_json, status,
                    documents_requested, created_at
                ) VALUES (?, ?, ?, 'pending', ?, ?)
                """,
                (job_id, project_id, json.dumps(document_ids), len(document_ids), now),
            )
            conn.commit()
        return job_id

    def mark_started(self, job_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE document_import_jobs SET status = 'processing', started_at = ? WHERE job_id = ?",
                (now, job_id),
            )
            conn.commit()

    def mark_done(self, job_id: str, documents_imported: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE document_import_jobs
                SET status = 'done', documents_imported = ?, completed_at = ?
                WHERE job_id = ?
                """,
                (documents_imported, now, job_id),
            )
            conn.commit()

    def mark_failed(self, job_id: str, error_message: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE document_import_jobs SET status = 'failed', error_message = ?, completed_at = ? "
                "WHERE job_id = ?",
                (error_message, now, job_id),
            )
            conn.commit()

    def get_job(self, job_id: str) -> Optional[DocumentImportJob]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM document_import_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        return self._row_to_job(row) if row else None

    def list_jobs(self, project_id: Optional[int] = None, limit: int = 200) -> list[DocumentImportJob]:
        query = "SELECT * FROM document_import_jobs"
        params: list[Any] = []
        if project_id is not None:
            query += " WHERE project_id = ?"
            params.append(project_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_job(row) for row in rows]

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> DocumentImportJob:
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
