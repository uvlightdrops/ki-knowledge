"""Job tracking store for distributed sync operations."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from ki_knowledge.integrations.job_store_base import SqliteJobStoreBase


@dataclass
class DistributedSyncJob:
    job_id: str
    domain: str
    job_type: str
    status: str
    payload_json: str = "{}"
    result_json: str = "{}"
    error_message: Optional[str] = None
    created_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    @property
    def payload(self) -> dict[str, Any]:
        try:
            return json.loads(self.payload_json or "{}")
        except (TypeError, ValueError):
            return {}

    @property
    def result(self) -> dict[str, Any]:
        try:
            return json.loads(self.result_json or "{}")
        except (TypeError, ValueError):
            return {}


class DistributedSyncJobStore(SqliteJobStoreBase):
    table_name = "distributed_sync_jobs"

    def _create_table_sql(self) -> str:
        return f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                job_id TEXT PRIMARY KEY,
                domain TEXT NOT NULL,
                job_type TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{{}}',
                result_json TEXT NOT NULL DEFAULT '{{}}',
                error_message TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT
            )
        """

    def _index_sql(self) -> list[str]:
        return [
            f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_domain ON {self.table_name}(domain)",
            f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_status ON {self.table_name}(status)",
        ]

    def create_job(self, *, domain: str, job_type: str, payload: dict[str, Any] | None = None) -> str:
        now = datetime.now(timezone.utc).isoformat()
        job_id = f"dsync_{uuid.uuid4().hex[:16]}"
        with self._connect() as conn:
            conn.execute(
                f"""
                INSERT INTO {self.table_name} (
                    job_id, domain, job_type, status, payload_json, result_json, created_at
                ) VALUES (?, ?, ?, 'pending', ?, '{{}}', ?)
                """,
                (job_id, domain, job_type, json.dumps(payload or {}, ensure_ascii=False, default=str), now),
            )
            conn.commit()
        return job_id

    def mark_done(self, job_id: str, result: dict[str, Any]) -> None:
        self._update_fields(
            job_id,
            {
                "status": "done",
                "result_json": json.dumps(result, ensure_ascii=False, default=str),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    def list_jobs(self, domain: Optional[str] = None, status: Optional[str] = None, limit: int = 200) -> list[DistributedSyncJob]:
        return self._list_jobs({"domain": domain, "status": status}, limit=limit)

    def list_pending(self, limit: int = 50) -> list[DistributedSyncJob]:
        return self.list_jobs(status="pending", limit=limit)

    def list_pending_for_domain(self, domain: str, limit: int = 50) -> list[DistributedSyncJob]:
        return self._list_jobs({"domain": domain, "status": "pending"}, limit=limit)

    def _row_to_job(self, row: sqlite3.Row) -> DistributedSyncJob:
        return DistributedSyncJob(
            job_id=row["job_id"],
            domain=row["domain"],
            job_type=row["job_type"],
            status=row["status"],
            payload_json=row["payload_json"],
            result_json=row["result_json"],
            error_message=row["error_message"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )
