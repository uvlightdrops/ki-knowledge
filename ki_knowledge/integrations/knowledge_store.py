"""SQLite-backed store for generic knowledge sources, blocks, relations, and artifacts."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Optional

from ki_knowledge.integrations.markdown_blocks import KnowledgeBlock, MarkdownBlockParser
from ki_knowledge.knowledge.adapters import MarkdownKnowledgeAdapter
from ki_knowledge.knowledge.models import (
    KnowledgeArtifact,
    KnowledgeBlockRecord,
    KnowledgeSource,
)


class KnowledgeStore:
    """Persistent store for shared knowledge-core entities."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_blocks (
                    id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    block_type TEXT NOT NULL,
                    parent_id TEXT,
                    heading_path TEXT NOT NULL,
                    content TEXT NOT NULL,
                    order_index INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_relations (
                    id TEXT PRIMARY KEY,
                    source_block_id TEXT NOT NULL,
                    target_block_id TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    weight REAL NOT NULL DEFAULT 1.0,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_embeddings (
                    block_id TEXT PRIMARY KEY,
                    model TEXT NOT NULL,
                    vector_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_sources (
                    source_id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    location TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    artifact_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    source_block_ids_json TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_knowledge_blocks_source ON knowledge_blocks(source_path)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_knowledge_blocks_type ON knowledge_blocks(block_type)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_knowledge_relations_source ON knowledge_relations(source_block_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_knowledge_sources_type ON knowledge_sources(source_type)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_knowledge_artifacts_type ON knowledge_artifacts(artifact_type)"
            )

    def import_markdown_file(
        self,
        markdown_path: str | Path,
        source_name: Optional[str] = None,
        parser: Optional[MarkdownBlockParser] = None,
        allowed_block_types: Optional[list[str]] = None,
        source_id: Optional[str] = None,
        source_type: Optional[str] = None,
    ) -> list[KnowledgeBlock]:
        path = Path(markdown_path)
        text = path.read_text(encoding="utf-8")
        return self.import_markdown_text(
            text,
            source_path=str(path.resolve()),
            source_name=source_name or path.name,
            parser=parser,
            allowed_block_types=allowed_block_types,
            source_id=source_id,
            source_type=source_type,
        )

    def import_markdown_text(
        self,
        text: str,
        source_path: str,
        source_name: Optional[str] = None,
        parser: Optional[MarkdownBlockParser] = None,
        allowed_block_types: Optional[list[str]] = None,
        source_id: Optional[str] = None,
        source_type: Optional[str] = None,
    ) -> list[KnowledgeBlock]:
        parser = parser or MarkdownBlockParser()
        blocks = parser.parse_markdown(text, source_path=source_path)
        if allowed_block_types:
            allowed = {block_type.strip() for block_type in allowed_block_types if block_type.strip()}
            if allowed and "heading" not in allowed:
                allowed.add("heading")
            blocks = [block for block in blocks if block.block_type in allowed]

        source = KnowledgeSource(
            source_id=source_id or f"markdown:{source_path}",
            source_type=source_type or "markdown",
            title=source_name or Path(source_path).name,
            location=source_path,
            metadata={"source_name": source_name or Path(source_path).name},
        )
        self.upsert_source(source)

        for block in blocks:
            block.metadata["source_name"] = source_name or Path(source_path).name

        for record in MarkdownKnowledgeAdapter.to_records(blocks, source):
            self.upsert_record(record)

        return blocks

    def upsert_source(self, source: KnowledgeSource) -> None:
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO knowledge_sources (
                    source_id, source_type, title, location, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    source_type = excluded.source_type,
                    title = excluded.title,
                    location = excluded.location,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    source.source_id,
                    source.source_type,
                    source.title,
                    source.location,
                    json.dumps(source.metadata, ensure_ascii=False),
                    now,
                    now,
                ),
            )

    def get_source(self, source_id: str) -> Optional[KnowledgeSource]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM knowledge_sources WHERE source_id = ?",
                (source_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_source(row)

    def list_sources(self, source_type: Optional[str] = None) -> list[KnowledgeSource]:
        query = "SELECT * FROM knowledge_sources"
        params: list = []
        if source_type:
            query += " WHERE source_type = ?"
            params.append(source_type)
        query += " ORDER BY updated_at DESC, source_id"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_source(row) for row in rows]

    def upsert_record(self, record: KnowledgeBlockRecord) -> None:
        source = self.get_source(record.source_id)
        if source is None:
            raise ValueError(f"Knowledge source '{record.source_id}' must exist before inserting records.")

        metadata = dict(record.metadata)
        metadata.update(
            {
                "source_id": record.source_id,
                "title": record.title,
                "tags": record.tags,
            }
        )
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO knowledge_blocks (
                    id, source_type, source_path, block_type, parent_id, heading_path, content, order_index,
                    metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    source_type = excluded.source_type,
                    source_path = excluded.source_path,
                    block_type = excluded.block_type,
                    parent_id = excluded.parent_id,
                    heading_path = excluded.heading_path,
                    content = excluded.content,
                    order_index = excluded.order_index,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    record.block_id,
                    source.source_type,
                    source.location,
                    record.block_type,
                    record.parent_block_id,
                    record.path,
                    record.content,
                    record.order_index,
                    json.dumps(metadata, ensure_ascii=False),
                    now,
                    now,
                ),
            )

    def get_record(self, block_id: str) -> Optional[KnowledgeBlockRecord]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM knowledge_blocks WHERE id = ?",
                (block_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def list_records(
        self,
        source_id: Optional[str] = None,
        block_type: Optional[str] = None,
        limit: int | None = None,
    ) -> list[KnowledgeBlockRecord]:
        query = "SELECT * FROM knowledge_blocks"
        params: list = []
        clauses: list[str] = []
        if source_id is not None:
            clauses.append("json_extract(metadata_json, '$.source_id') = ?")
            params.append(source_id)
        if block_type is not None:
            clauses.append("block_type = ?")
            params.append(block_type)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY order_index, created_at"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_record(row) for row in rows]

    def upsert_artifact(self, artifact: KnowledgeArtifact) -> None:
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO knowledge_artifacts (
                    artifact_id, artifact_type, source_id, source_block_ids_json, content,
                    metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(artifact_id) DO UPDATE SET
                    artifact_type = excluded.artifact_type,
                    source_id = excluded.source_id,
                    source_block_ids_json = excluded.source_block_ids_json,
                    content = excluded.content,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    artifact.artifact_id,
                    artifact.artifact_type,
                    artifact.source_id,
                    json.dumps(artifact.source_block_ids, ensure_ascii=False),
                    artifact.content,
                    json.dumps(artifact.metadata, ensure_ascii=False),
                    now,
                    now,
                ),
            )

    def get_artifact(self, artifact_id: str) -> Optional[KnowledgeArtifact]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM knowledge_artifacts WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_artifact(row)

    def list_artifacts(
        self,
        source_id: Optional[str] = None,
        artifact_type: Optional[str] = None,
    ) -> list[KnowledgeArtifact]:
        query = "SELECT * FROM knowledge_artifacts"
        params: list = []
        clauses: list[str] = []
        if source_id is not None:
            clauses.append("source_id = ?")
            params.append(source_id)
        if artifact_type is not None:
            clauses.append("artifact_type = ?")
            params.append(artifact_type)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY updated_at DESC, artifact_id"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_artifact(row) for row in rows]

    def delete_record(self, block_id: str) -> bool:
        with self._connect() as conn:
            conn.execute("DELETE FROM knowledge_embeddings WHERE block_id = ?", (block_id,))
            conn.execute(
                "DELETE FROM knowledge_relations WHERE source_block_id = ? OR target_block_id = ?",
                (block_id, block_id),
            )
            cursor = conn.execute("DELETE FROM knowledge_blocks WHERE id = ?", (block_id,))
        return cursor.rowcount > 0

    def delete_records(self, block_ids: list[str]) -> int:
        unique_ids = [block_id for block_id in dict.fromkeys(str(block_id).strip() for block_id in block_ids) if block_id]
        if not unique_ids:
            return 0
        placeholders = ", ".join("?" for _ in unique_ids)
        with self._connect() as conn:
            conn.execute(f"DELETE FROM knowledge_embeddings WHERE block_id IN ({placeholders})", unique_ids)
            conn.execute(
                f"DELETE FROM knowledge_relations WHERE source_block_id IN ({placeholders}) OR target_block_id IN ({placeholders})",
                unique_ids + unique_ids,
            )
            cursor = conn.execute(f"DELETE FROM knowledge_blocks WHERE id IN ({placeholders})", unique_ids)
        return cursor.rowcount

    def delete_artifact(self, artifact_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM knowledge_artifacts WHERE artifact_id = ?", (artifact_id,))
        return cursor.rowcount > 0

    def delete_artifacts(self, artifact_ids: list[str]) -> int:
        unique_ids = [artifact_id for artifact_id in dict.fromkeys(str(artifact_id).strip() for artifact_id in artifact_ids) if artifact_id]
        if not unique_ids:
            return 0
        placeholders = ", ".join("?" for _ in unique_ids)
        with self._connect() as conn:
            cursor = conn.execute(f"DELETE FROM knowledge_artifacts WHERE artifact_id IN ({placeholders})", unique_ids)
        return cursor.rowcount

    def upsert_block(self, block: KnowledgeBlock) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO knowledge_blocks (
                    id, source_type, source_path, block_type, parent_id, heading_path, content, order_index,
                    metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    source_type = excluded.source_type,
                    source_path = excluded.source_path,
                    block_type = excluded.block_type,
                    parent_id = excluded.parent_id,
                    heading_path = excluded.heading_path,
                    content = excluded.content,
                    order_index = excluded.order_index,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    block.id,
                    block.source_type,
                    block.source_path,
                    block.block_type,
                    block.parent_id,
                    block.heading_path,
                    block.content,
                    block.order_index,
                    json.dumps(block.metadata, ensure_ascii=False),
                    block.created_at,
                    block.updated_at,
                ),
            )

    def get_block(self, block_id: str) -> Optional[KnowledgeBlock]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM knowledge_blocks WHERE id = ?",
                (block_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_block(row)

    def list_blocks(self, limit: int | None = None) -> list[KnowledgeBlock]:
        query = "SELECT * FROM knowledge_blocks ORDER BY order_index, created_at"
        params: list = []
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_block(row) for row in rows]

    def children_of(self, parent_id: str) -> list[KnowledgeBlock]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM knowledge_blocks WHERE parent_id = ? ORDER BY order_index",
                (parent_id,),
            ).fetchall()
        return [self._row_to_block(row) for row in rows]

    def search_blocks(self, query: str, limit: int = 10) -> list[KnowledgeBlock]:
        terms = [token for token in re.split(r"\W+", query.lower()) if token]
        if not terms:
            return []
        clauses = ["LOWER(content) LIKE ?"] * len(terms)
        params = [f"%{term}%" for term in terms]
        sql = f"SELECT * FROM knowledge_blocks WHERE {' OR '.join(clauses)} ORDER BY order_index LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_block(row) for row in rows]

    def add_relation(
        self,
        source_block_id: str,
        target_block_id: str,
        relation: str = "related_to",
        weight: float = 1.0,
        metadata: Optional[dict] = None,
    ) -> str:
        relation_id = f"{source_block_id}:{target_block_id}:{relation}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO knowledge_relations (
                    id, source_block_id, target_block_id, relation, weight, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    weight = excluded.weight,
                    metadata_json = excluded.metadata_json
                """,
                (
                    relation_id,
                    source_block_id,
                    target_block_id,
                    relation,
                    weight,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    self._now(),
                ),
            )
        return relation_id

    def list_relations(self, block_id: Optional[str] = None) -> list[dict]:
        query = "SELECT * FROM knowledge_relations"
        params: list = []
        if block_id is not None:
            query += " WHERE source_block_id = ?"
            params.append(block_id)
        query += " ORDER BY created_at"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        result: list[dict] = []
        for row in rows:
            result.append(
                {
                    "id": row["id"],
                    "source_block_id": row["source_block_id"],
                    "target_block_id": row["target_block_id"],
                    "relation": row["relation"],
                    "weight": float(row["weight"]),
                    "metadata": json.loads(row["metadata_json"]),
                }
            )
        return result

    def list_relations_for_blocks(self, block_ids: list[str]) -> list[dict]:
        if not block_ids:
            return []
        placeholders = ",".join(["?"] * len(block_ids))
        query = f"""
            SELECT *
            FROM knowledge_relations
            WHERE source_block_id IN ({placeholders})
               OR target_block_id IN ({placeholders})
            ORDER BY created_at
        """
        params = [*block_ids, *block_ids]
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            {
                "id": row["id"],
                "source_block_id": row["source_block_id"],
                "target_block_id": row["target_block_id"],
                "relation": row["relation"],
                "weight": float(row["weight"]),
                "metadata": json.loads(row["metadata_json"]),
            }
            for row in rows
        ]

    def add_embedding(self, block_id: str, model: str, vector: list[float]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO knowledge_embeddings (block_id, model, vector_json, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(block_id) DO UPDATE SET
                    model = excluded.model,
                    vector_json = excluded.vector_json,
                    created_at = excluded.created_at
                """,
                (block_id, model, json.dumps(vector), self._now()),
            )

    def get_embedding(self, block_id: str) -> Optional[list[float]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT vector_json FROM knowledge_embeddings WHERE block_id = ?",
                (block_id,),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row["vector_json"])

    def _row_to_source(self, row: sqlite3.Row) -> KnowledgeSource:
        return KnowledgeSource(
            source_id=row["source_id"],
            source_type=row["source_type"],
            title=row["title"],
            location=row["location"],
            metadata=json.loads(row["metadata_json"]),
        )

    def _row_to_record(self, row: sqlite3.Row) -> KnowledgeBlockRecord:
        metadata = json.loads(row["metadata_json"])
        return KnowledgeBlockRecord(
            block_id=row["id"],
            source_id=metadata.get("source_id", ""),
            block_type=row["block_type"],
            title=metadata.get("title", row["heading_path"] or row["block_type"]),
            content=row["content"],
            parent_block_id=row["parent_id"],
            path=row["heading_path"],
            order_index=int(row["order_index"]),
            tags=list(metadata.get("tags", [])),
            metadata={
                key: value
                for key, value in metadata.items()
                if key not in {"source_id", "title", "tags"}
            },
        )

    def _row_to_artifact(self, row: sqlite3.Row) -> KnowledgeArtifact:
        return KnowledgeArtifact(
            artifact_id=row["artifact_id"],
            artifact_type=row["artifact_type"],
            source_id=row["source_id"],
            source_block_ids=json.loads(row["source_block_ids_json"]),
            content=row["content"],
            metadata=json.loads(row["metadata_json"]),
        )

    def _row_to_block(self, row: sqlite3.Row) -> KnowledgeBlock:
        return KnowledgeBlock(
            id=row["id"],
            source_type=row["source_type"],
            source_path=row["source_path"],
            block_type=row["block_type"],
            parent_id=row["parent_id"],
            heading_path=row["heading_path"],
            content=row["content"],
            order_index=int(row["order_index"]),
            metadata=json.loads(row["metadata_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _now(self) -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()
