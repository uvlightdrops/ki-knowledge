"""SQLite-backed store for generic knowledge sources, blocks, relations, and artifacts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, Optional

from ki_knowledge.integrations.sql_backend import StoreTarget, connect, ilike_operator, json_text, vector_literal

from ki_knowledge.integrations.markdown_blocks import KnowledgeBlock, MarkdownBlockParser
from ki_knowledge.knowledge.adapters import MarkdownKnowledgeAdapter
from ki_knowledge.knowledge.models import (
    KnowledgeArtifact,
    KnowledgeBlockRecord,
    KnowledgeSource,
)


# SQLite's default compiled limit is SQLITE_MAX_VARIABLE_NUMBER (typically 999,
# sometimes as low as 32766 or as strict as 999 depending on the build). Stay
# well under the lowest common value so large "delete many"/"look up many"
# batches don't hit "too many SQL variables".
_SQLITE_MAX_VARIABLES = 900


def _chunked(items: list, size: int) -> "list[list]":
    """Split items into chunks of at most `size` elements."""
    return [items[i : i + size] for i in range(0, len(items), size)]


def _json_loads(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    return json.loads(value)


class KnowledgeStore:
    """Persistent store for shared knowledge-core entities."""

    def __init__(self, db_path: str | Path | StoreTarget):
        self.target = db_path if isinstance(db_path, StoreTarget) else StoreTarget.parse(db_path, schema="knowledge")
        self.db_path = str(self.target.sqlite_path) if self.target.is_sqlite else self.target.safe_label()
        self._init_schema()

    def _connect(self):
        return connect(self.target)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            metadata_type = "jsonb" if conn.dialect == "postgres" else "TEXT"
            metadata_default = "'{}'::jsonb" if conn.dialect == "postgres" else "'{}'"
            embedding_type = "vector" if conn.dialect == "postgres" else "TEXT"
            if conn.dialect == "postgres":
                conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS knowledge_blocks (
                    id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    block_type TEXT NOT NULL,
                    parent_id TEXT,
                    heading_path TEXT NOT NULL,
                    content TEXT NOT NULL,
                    order_index INTEGER NOT NULL,
                    metadata_json {metadata_type} NOT NULL DEFAULT {metadata_default},
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS knowledge_relations (
                    id TEXT PRIMARY KEY,
                    source_block_id TEXT NOT NULL,
                    target_block_id TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    weight REAL NOT NULL DEFAULT 1.0,
                    metadata_json {metadata_type} NOT NULL DEFAULT {metadata_default},
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS knowledge_embeddings (
                    block_id TEXT PRIMARY KEY,
                    model TEXT NOT NULL,
                    vector_json {embedding_type} NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS knowledge_sources (
                    source_id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    location TEXT NOT NULL,
                    metadata_json {metadata_type} NOT NULL DEFAULT {metadata_default},
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS knowledge_artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    artifact_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    source_block_ids_json {metadata_type} NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json {metadata_type} NOT NULL DEFAULT {metadata_default},
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
            if conn.dialect == "postgres":
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_knowledge_blocks_source_id_json "
                    "ON knowledge_blocks ((metadata_json ->> 'source_id'))"
                )
            else:
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_knowledge_blocks_source_id_json "
                    "ON knowledge_blocks(json_extract(metadata_json, '$.source_id'))"
                )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_store_migrations (
                    name TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )
            migration = "v1_remove_markdown_heading_records"
            applied = conn.execute(
                "SELECT 1 FROM knowledge_store_migrations WHERE name = ?",
                (migration,),
            ).fetchone()
            if applied is None:
                heading_ids = "SELECT id FROM knowledge_blocks WHERE block_type = 'heading'"
                conn.execute(f"DELETE FROM knowledge_embeddings WHERE block_id IN ({heading_ids})")
                conn.execute(
                    f"DELETE FROM knowledge_relations WHERE source_block_id IN ({heading_ids}) "
                    f"OR target_block_id IN ({heading_ids})"
                )
                if conn.dialect == "postgres":
                    conn.execute(
                        f"""
                        DELETE FROM knowledge_artifacts
                        WHERE EXISTS (
                            SELECT 1 FROM jsonb_array_elements_text(source_block_ids_json) AS value
                            WHERE value IN ({heading_ids})
                        )
                        """
                    )
                else:
                    conn.execute(
                        f"""
                        DELETE FROM knowledge_artifacts
                        WHERE EXISTS (
                            SELECT 1 FROM json_each(knowledge_artifacts.source_block_ids_json)
                            WHERE value IN ({heading_ids})
                        )
                        """
                    )
                conn.execute(f"DELETE FROM knowledge_blocks WHERE id IN ({heading_ids})")
                conn.execute(
                    "INSERT INTO knowledge_store_migrations (name, applied_at) VALUES (?, ?)",
                    (migration, self._now()),
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
        self.delete_records_by_type(source.source_id, {"heading"})

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
                "object_type": record.object_type or record.block_type,
            }
        )
        metadata.setdefault("record_schema_version", 1)
        metadata.setdefault("provenance", {"source_format": source.source_type})
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

    def delete_records_by_type(self, source_id: str, block_types: set[str]) -> int:
        """Remove obsolete parser-only records when a source is re-imported."""
        if not block_types:
            return 0
        placeholders = ",".join("?" for _ in block_types)
        with self._connect() as conn:
            source_expr = json_text("metadata_json", "source_id", conn.dialect)
            rows = conn.execute(
                f"""
                SELECT id FROM knowledge_blocks
                WHERE {source_expr} = ?
                  AND block_type IN ({placeholders})
                """,
                [source_id, *sorted(block_types)],
            ).fetchall()
            ids = [row["id"] for row in rows]
            if not ids:
                return 0
            if conn.dialect == "postgres":
                conn.execute(
                    f"""
                    DELETE FROM knowledge_artifacts
                    WHERE EXISTS (
                        SELECT 1 FROM jsonb_array_elements_text(source_block_ids_json) AS value
                        WHERE value IN (
                            SELECT id FROM knowledge_blocks
                            WHERE {source_expr} = ?
                              AND block_type IN ({placeholders})
                        )
                    )
                    """,
                    [source_id, *sorted(block_types)],
                )
            else:
                conn.execute(
                    f"""
                    DELETE FROM knowledge_artifacts
                    WHERE EXISTS (
                        SELECT 1 FROM json_each(knowledge_artifacts.source_block_ids_json)
                        WHERE value IN (
                            SELECT id FROM knowledge_blocks
                            WHERE {source_expr} = ?
                              AND block_type IN ({placeholders})
                        )
                    )
                    """,
                    [source_id, *sorted(block_types)],
                )
            for batch in _chunked(ids, _SQLITE_MAX_VARIABLES // 2):
                placeholders = ",".join("?" for _ in batch)
                conn.execute(f"DELETE FROM knowledge_embeddings WHERE block_id IN ({placeholders})", batch)
                conn.execute(
                    f"DELETE FROM knowledge_relations WHERE source_block_id IN ({placeholders}) "
                    f"OR target_block_id IN ({placeholders})",
                    [*batch, *batch],
                )
                conn.execute(f"DELETE FROM knowledge_blocks WHERE id IN ({placeholders})", batch)
        return len(ids)

    def list_records(
        self,
        source_id: Optional[str] = None,
        block_type: Optional[str] = None,
        limit: int | None = None,
    ) -> list[KnowledgeBlockRecord]:
        with self._connect() as conn:
            query = "SELECT * FROM knowledge_blocks"
            params: list = []
            clauses: list[str] = []
            if source_id is not None:
                clauses.append(f"{json_text('metadata_json', 'source_id', conn.dialect)} = ?")
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
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_record(row) for row in rows]

    def query_records(
        self,
        source_ids: Iterable[str],
        *,
        block_type: Optional[str] = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[list[KnowledgeBlockRecord], int]:
        """Records of the given sources (domain scope) with total count, paged in SQL."""
        ids = sorted({str(item) for item in source_ids if item})
        if not ids:
            return [], 0
        with self._connect() as conn:
            placeholders = ",".join("?" for _ in ids)
            clauses = [f"{json_text('metadata_json', 'source_id', conn.dialect)} IN ({placeholders})"]
            params: list[Any] = list(ids)
            if block_type is not None:
                clauses.append("block_type = ?")
                params.append(block_type)
            where = " AND ".join(clauses)
            total = int(
                conn.execute(f"SELECT COUNT(*) FROM knowledge_blocks WHERE {where}", params).fetchone()[0]
            )
            query = f"SELECT * FROM knowledge_blocks WHERE {where} ORDER BY order_index, created_at, id"
            page_params = list(params)
            if limit is not None:
                query += " LIMIT ? OFFSET ?"
                page_params.extend((limit, max(0, offset)))
            rows = conn.execute(query, page_params).fetchall()
        return [self._row_to_record(row) for row in rows], total

    def browse_records(
        self,
        source_id: str,
        *,
        query_text: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[KnowledgeBlockRecord], int]:
        """Return one source's records and total count for a paged content browser."""
        with self._connect() as conn:
            op = ilike_operator(conn.dialect)
            clauses = [f"{json_text('metadata_json', 'source_id', conn.dialect)} = ?"]
            params: list[Any] = [source_id]
            needle = query_text.strip()
            if needle:
                pattern = f"%{needle}%"
                clauses.append(
                    f"(content {op} ? OR heading_path {op} ? OR {json_text('metadata_json', 'title', conn.dialect)} {op} ?)"
                )
                params.extend((pattern, pattern, pattern))
            where = " AND ".join(clauses)
            total = int(
                conn.execute(f"SELECT COUNT(*) FROM knowledge_blocks WHERE {where}", params).fetchone()[0]
            )
            rows = conn.execute(
                f"SELECT * FROM knowledge_blocks WHERE {where} ORDER BY order_index, created_at, id LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
        return [self._row_to_record(row) for row in rows], total

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
        deleted = 0
        with self._connect() as conn:
            for chunk in _chunked(unique_ids, _SQLITE_MAX_VARIABLES // 2):
                placeholders = ", ".join("?" for _ in chunk)
                conn.execute(f"DELETE FROM knowledge_embeddings WHERE block_id IN ({placeholders})", chunk)
                conn.execute(
                    f"DELETE FROM knowledge_relations WHERE source_block_id IN ({placeholders}) OR target_block_id IN ({placeholders})",
                    chunk + chunk,
                )
                cursor = conn.execute(f"DELETE FROM knowledge_blocks WHERE id IN ({placeholders})", chunk)
                deleted += cursor.rowcount
        return deleted

    def delete_artifact(self, artifact_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM knowledge_artifacts WHERE artifact_id = ?", (artifact_id,))
        return cursor.rowcount > 0

    def delete_artifacts(self, artifact_ids: list[str]) -> int:
        unique_ids = [artifact_id for artifact_id in dict.fromkeys(str(artifact_id).strip() for artifact_id in artifact_ids) if artifact_id]
        if not unique_ids:
            return 0
        deleted = 0
        with self._connect() as conn:
            for chunk in _chunked(unique_ids, _SQLITE_MAX_VARIABLES):
                placeholders = ", ".join("?" for _ in chunk)
                cursor = conn.execute(f"DELETE FROM knowledge_artifacts WHERE artifact_id IN ({placeholders})", chunk)
                deleted += cursor.rowcount
        return deleted

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
                    "metadata": _json_loads(row["metadata_json"]),
                }
            )
        return result

    def list_relations_for_blocks(self, block_ids: list[str]) -> list[dict]:
        if not block_ids:
            return []
        seen_ids: set = set()
        result: list[dict] = []
        with self._connect() as conn:
            for chunk in _chunked(list(block_ids), _SQLITE_MAX_VARIABLES // 2):
                placeholders = ",".join(["?"] * len(chunk))
                query = f"""
                    SELECT *
                    FROM knowledge_relations
                    WHERE source_block_id IN ({placeholders})
                       OR target_block_id IN ({placeholders})
                    ORDER BY created_at
                """
                params = [*chunk, *chunk]
                rows = conn.execute(query, params).fetchall()
                for row in rows:
                    if row["id"] in seen_ids:
                        continue
                    seen_ids.add(row["id"])
                    result.append(
                        {
                            "id": row["id"],
                            "source_block_id": row["source_block_id"],
                            "target_block_id": row["target_block_id"],
                            "relation": row["relation"],
                            "weight": float(row["weight"]),
                            "metadata": _json_loads(row["metadata_json"]),
                            "_created_at": row["created_at"],
                        }
                    )
        result.sort(key=lambda item: item.pop("_created_at"))
        return result

    def add_embedding(self, block_id: str, model: str, vector: list[float]) -> None:
        with self._connect() as conn:
            value = vector_literal(vector) if conn.dialect == "postgres" else json.dumps(vector)
            placeholder = "?::vector" if conn.dialect == "postgres" else "?"
            conn.execute(
                f"""
                INSERT INTO knowledge_embeddings (block_id, model, vector_json, created_at)
                VALUES (?, ?, {placeholder}, ?)
                ON CONFLICT(block_id) DO UPDATE SET
                    model = excluded.model,
                    vector_json = excluded.vector_json,
                    created_at = excluded.created_at
                """,
                (block_id, model, value, self._now()),
            )

    def get_embedding(self, block_id: str) -> Optional[list[float]]:
        with self._connect() as conn:
            vector_expr = "vector_json::text AS vector_json" if conn.dialect == "postgres" else "vector_json"
            row = conn.execute(
                f"SELECT {vector_expr} FROM knowledge_embeddings WHERE block_id = ?",
                (block_id,),
            ).fetchone()
        if row is None:
            return None
        value = row["vector_json"]
        if isinstance(value, list):
            return [float(item) for item in value]
        return [float(item) for item in json.loads(str(value))]

    def source_stats(self) -> dict[str, dict[str, Any]]:
        """Per source id: record and artifact counts plus timestamps (one query per table)."""
        stats: dict[str, dict[str, Any]] = {}

        def entry(source_id: str) -> dict[str, Any]:
            return stats.setdefault(source_id, {"records": 0, "artifacts": 0, "created_at": "", "updated_at": ""})

        with self._connect() as conn:
            for row in conn.execute("SELECT source_id, created_at, updated_at FROM knowledge_sources"):
                item = entry(row["source_id"])
                item["created_at"] = row["created_at"]
                item["updated_at"] = row["updated_at"]
            for row in conn.execute(
                f"SELECT {json_text('metadata_json', 'source_id', conn.dialect)} AS source_id, COUNT(*) AS n "
                f"FROM knowledge_blocks GROUP BY {json_text('metadata_json', 'source_id', conn.dialect)}"
            ):
                if row["source_id"]:
                    entry(row["source_id"])["records"] = int(row["n"])
            for row in conn.execute("SELECT source_id, COUNT(*) AS n FROM knowledge_artifacts GROUP BY source_id"):
                entry(row["source_id"])["artifacts"] = int(row["n"])
        return stats

    def delete_source(self, source_id: str) -> dict[str, int]:
        """Remove a source with its records (incl. embeddings/relations) and artifacts."""
        with self._connect() as conn:
            block_ids = [
                row["id"]
                for row in conn.execute(
                    f"SELECT id FROM knowledge_blocks WHERE {json_text('metadata_json', 'source_id', conn.dialect)} = ?",
                    (source_id,),
                )
            ]
        records = self.delete_records(block_ids)
        with self._connect() as conn:
            artifacts = conn.execute("DELETE FROM knowledge_artifacts WHERE source_id = ?", (source_id,)).rowcount
            sources = conn.execute("DELETE FROM knowledge_sources WHERE source_id = ?", (source_id,)).rowcount
        return {"sources": sources, "records": records, "artifacts": artifacts}

    def _row_to_source(self, row) -> KnowledgeSource:
        return KnowledgeSource(
            source_id=row["source_id"],
            source_type=row["source_type"],
            title=row["title"],
            location=row["location"],
            metadata=_json_loads(row["metadata_json"]),
        )

    def _row_to_record(self, row) -> KnowledgeBlockRecord:
        metadata = _json_loads(row["metadata_json"])
        object_type = metadata.pop("object_type", "")
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
            object_type=object_type,
            metadata={
                key: value
                for key, value in metadata.items()
                if key not in {"source_id", "title", "tags"}
            },
        )

    def _row_to_artifact(self, row) -> KnowledgeArtifact:
        return KnowledgeArtifact(
            artifact_id=row["artifact_id"],
            artifact_type=row["artifact_type"],
            source_id=row["source_id"],
            source_block_ids=_json_loads(row["source_block_ids_json"]),
            content=row["content"],
            metadata=_json_loads(row["metadata_json"]),
        )

    def _row_to_block(self, row) -> KnowledgeBlock:
        return KnowledgeBlock(
            id=row["id"],
            source_type=row["source_type"],
            source_path=row["source_path"],
            block_type=row["block_type"],
            parent_id=row["parent_id"],
            heading_path=row["heading_path"],
            content=row["content"],
            order_index=int(row["order_index"]),
            metadata=_json_loads(row["metadata_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _now(self) -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()
