"""Shared SQLite job-store scaffolding for ki-knowledge's job-tracked pipelines.

Three independent modules — PDFBatchProcessor (pdf_batch.py),
KnowledgeExtractionJobStore (knowledge_pipeline_jobs.py), and
DocumentImportJobStore (document_import_jobs.py) — each hand-rolled their own
near-identical SQLite boilerplate: connection handling, table creation with
column migrations, status transitions (pending -> processing -> done/failed),
and row-to-dataclass conversion. This module extracts that boilerplate into
one reusable base class so new job-tracked pipelines (and the three existing
ones) don't have to re-implement it.

Design notes:
- Each job kind keeps its own table (not a shared polymorphic table), because
  the domain-specific columns (pages_total/pages_processed for PDF,
  files_processed/blocks_stored for knowledge extraction,
  documents_requested/documents_imported for document import) are genuinely
  different and don't benefit from being force-fit into one generic schema.
- `create_job`/`mark_done` stay per-subclass, since idempotency semantics and
  completion payloads differ (see each store's docstring for its own
  idempotency contract).
- `mark_started`, `mark_failed`, `get_job`, `list_jobs`, and schema/column
  migration are generic and live here.
"""

from __future__ import annotations

import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, TypeVar

JobT = TypeVar("JobT")


class SqliteJobStoreBase(ABC):
    """Common SQLite CRUD scaffolding for a single job-history table.

    Subclasses must set `table_name` and implement `_create_table_sql()`,
    `_row_to_job()`, and may override `_extra_columns()` for additive,
    migration-safe column evolution (mirrors the pattern originally used by
    PDFBatchProcessor._init_db for legacy on-disk databases missing newer
    columns).
    """

    table_name: str = ""

    def __init__(self, db_path: str | Path):
        if not self.table_name:
            raise NotImplementedError("Subclasses must set table_name")
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # -- connection & schema -------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @abstractmethod
    def _create_table_sql(self) -> str:
        """Return the full `CREATE TABLE IF NOT EXISTS ...` statement."""

    def _index_sql(self) -> list[str]:
        """Optional list of `CREATE INDEX IF NOT EXISTS ...` statements."""
        return []

    def _extra_columns(self) -> dict[str, str]:
        """Columns to add via `ALTER TABLE` if missing (name -> SQL type).

        Lets a store evolve its schema over time without breaking existing
        on-disk databases created by an older version of the code.
        """
        return {}

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(self._create_table_sql())
            existing_columns = {
                row[1] for row in conn.execute(f"PRAGMA table_info({self.table_name})").fetchall()
            }
            for column_name, column_sql in self._extra_columns().items():
                if column_name not in existing_columns:
                    conn.execute(f"ALTER TABLE {self.table_name} ADD COLUMN {column_name} {column_sql}")
            for index_sql in self._index_sql():
                conn.execute(index_sql)
            conn.commit()

    # -- generic status transitions -----------------------------------------

    def mark_started(self, job_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                f"UPDATE {self.table_name} SET status = 'processing', started_at = ? WHERE job_id = ?",
                (now, job_id),
            )
            conn.commit()

    def mark_failed(self, job_id: str, error_message: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                f"UPDATE {self.table_name} SET status = 'failed', error_message = ?, completed_at = ? "
                "WHERE job_id = ?",
                (error_message, now, job_id),
            )
            conn.commit()

    def _update_fields(self, job_id: str, fields: dict[str, Any]) -> None:
        """Generic partial-update helper (mirrors the old
        PDFBatchProcessor.update_result_metadata pattern), usable by
        subclasses for domain-specific `mark_done`/metadata updates.
        """
        if not fields:
            return
        set_clause = ", ".join(f"{col} = ?" for col in fields)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE {self.table_name} SET {set_clause} WHERE job_id = ?",
                [*fields.values(), job_id],
            )
            conn.commit()

    # -- generic reads --------------------------------------------------------

    @abstractmethod
    def _row_to_job(self, row: sqlite3.Row) -> JobT:
        """Convert a raw SQLite row into the store's job dataclass."""

    def get_job(self, job_id: str) -> Optional[JobT]:
        with self._connect() as conn:
            row = conn.execute(f"SELECT * FROM {self.table_name} WHERE job_id = ?", (job_id,)).fetchone()
        return self._row_to_job(row) if row else None

    def _list_jobs(self, filters: dict[str, Any], limit: int = 200, order_by: str = "created_at DESC") -> list[JobT]:
        """Generic equality-filtered listing helper for subclasses."""
        query = f"SELECT * FROM {self.table_name}"
        params: list[Any] = []
        clauses = []
        for column, value in filters.items():
            if value is None:
                continue
            clauses.append(f"{column} = ?")
            params.append(value)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += f" ORDER BY {order_by} LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_job(row) for row in rows]
