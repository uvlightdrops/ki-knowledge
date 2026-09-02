"""Generic graph layer for knowledge blocks."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Optional, Iterable

from ki_knowledge.integrations.knowledge_store import KnowledgeStore


@dataclass
class KnowledgeNeighbor:
    """A direct graph neighbor for a block."""

    neighbor_id: str
    neighbor_type: str
    relation: str
    weight: float


@dataclass
class KnowledgeGraphNode:
    """Serializable graph node for visualization payloads."""

    node_id: str
    label: str
    node_type: str
    path: str
    metadata: dict


@dataclass
class KnowledgeGraphEdge:
    """Serializable graph edge for visualization payloads."""

    source: str
    target: str
    predicate: str
    weight: float
    metadata: dict


class KnowledgeGraph:
    """Build and query a lightweight knowledge graph over knowledge blocks."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_graph_nodes (
                    node_id TEXT PRIMARY KEY,
                    node_type TEXT NOT NULL,
                    label TEXT NOT NULL,
                    props_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_graph_edges (
                    src_id TEXT NOT NULL,
                    dst_id TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    weight REAL NOT NULL DEFAULT 1.0,
                    props_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (src_id, dst_id, relation)
                )
                """
            )

    def rebuild_from_store(self, store: KnowledgeStore) -> dict[str, int]:
        with self._connect() as conn:
            conn.execute("DELETE FROM knowledge_graph_edges")
            conn.execute("DELETE FROM knowledge_graph_nodes")

            for block in store.list_blocks():
                self._upsert_node(conn, block.id, "block", block.content[:120])
                self._upsert_edge(conn, block.id, block.parent_id, "parent_of", 1.0) if block.parent_id else None

            for relation in store.list_relations():
                self._upsert_edge(
                    conn,
                    relation["source_block_id"],
                    relation["target_block_id"],
                    relation["relation"],
                    relation["weight"],
                )

            node_count = conn.execute("SELECT COUNT(*) AS c FROM knowledge_graph_nodes").fetchone()["c"]
            edge_count = conn.execute("SELECT COUNT(*) AS c FROM knowledge_graph_edges").fetchone()["c"]

        return {"nodes": int(node_count), "edges": int(edge_count)}

    def neighbors(
        self,
        block_id: str,
        relation_filter: Optional[Iterable[str]] = None,
        limit: int = 25,
    ) -> list[KnowledgeNeighbor]:
        params: list = [block_id]
        where_relation = ""
        if relation_filter:
            rels = list(relation_filter)
            if rels:
                placeholders = ",".join(["?"] * len(rels))
                where_relation = f" AND relation IN ({placeholders})"
                params.extend(rels)
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT dst_id, relation, weight
                FROM knowledge_graph_edges
                WHERE src_id = ? {where_relation}
                ORDER BY weight DESC, dst_id ASC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()

        return [
            KnowledgeNeighbor(
                neighbor_id=row["dst_id"],
                neighbor_type="block",
                relation=row["relation"],
                weight=float(row["weight"]),
            )
            for row in rows
        ]

    def related_block_ids(
        self,
        block_ids: list[str],
        relations: Iterable[str] = ("related_to",),
        limit_per_seed: int = 5,
    ) -> list[str]:
        seen = set(block_ids)
        result: list[str] = []
        rels = list(relations)
        placeholders = ",".join(["?"] * len(rels))

        with self._connect() as conn:
            for block_id in block_ids:
                rows = conn.execute(
                    f"""
                    SELECT dst_id
                    FROM knowledge_graph_edges
                    WHERE src_id = ?
                      AND relation IN ({placeholders})
                    ORDER BY weight DESC
                    LIMIT ?
                    """,
                    (block_id, *rels, limit_per_seed),
                ).fetchall()
                for row in rows:
                    target_id = row["dst_id"]
                    if target_id not in seen:
                        seen.add(target_id)
                        result.append(target_id)
        return result

    def source_graph_payload(self, store: KnowledgeStore, source_id: str, limit: int = 400) -> dict:
        """Build a source-scoped graph payload for visualization."""
        records = store.list_records(source_id=source_id, limit=limit)
        nodes = [
            KnowledgeGraphNode(
                node_id=record.block_id,
                label=record.title or record.path or record.block_type,
                node_type=record.block_type,
                path=record.path,
                metadata=record.metadata,
            )
            for record in records
        ]
        node_ids = {node.node_id for node in nodes}

        edges: list[KnowledgeGraphEdge] = []
        for record in records:
            if record.parent_block_id and record.parent_block_id in node_ids:
                edges.append(
                    KnowledgeGraphEdge(
                        source=record.block_id,
                        target=record.parent_block_id,
                        predicate="parent_of",
                        weight=1.0,
                        metadata={},
                    )
                )

        seen_edge_ids = {(edge.source, edge.target, edge.predicate) for edge in edges}
        for relation in store.list_relations_for_blocks(list(node_ids)):
            if relation["source_block_id"] in node_ids and relation["target_block_id"] in node_ids:
                key = (relation["source_block_id"], relation["target_block_id"], relation["relation"])
                if key in seen_edge_ids:
                    continue
                seen_edge_ids.add(key)
                edges.append(
                    KnowledgeGraphEdge(
                        source=relation["source_block_id"],
                        target=relation["target_block_id"],
                        predicate=relation["relation"],
                        weight=relation["weight"],
                        metadata=relation["metadata"],
                    )
                )

        return {
            "source_id": source_id,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": [
                {
                    "node_id": node.node_id,
                    "label": node.label,
                    "node_type": node.node_type,
                    "path": node.path,
                    "metadata": node.metadata,
                }
                for node in nodes
            ],
            "edges": [
                {
                    "source": edge.source,
                    "target": edge.target,
                    "predicate": edge.predicate,
                    "weight": edge.weight,
                    "metadata": edge.metadata,
                }
                for edge in edges
            ],
        }

    def _upsert_node(self, conn: sqlite3.Connection, node_id: str, node_type: str, label: str) -> None:
        conn.execute(
            """
            INSERT INTO knowledge_graph_nodes (node_id, node_type, label, props_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(node_id) DO UPDATE SET
                node_type = excluded.node_type,
                label = excluded.label,
                props_json = excluded.props_json
            """,
            (node_id, node_type, label, json.dumps({}, ensure_ascii=False)),
        )

    def _upsert_edge(
        self,
        conn: sqlite3.Connection,
        src_id: str,
        dst_id: Optional[str],
        relation: str,
        weight: float,
    ) -> None:
        if not dst_id:
            return
        conn.execute(
            """
            INSERT INTO knowledge_graph_edges (src_id, dst_id, relation, weight, props_json)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(src_id, dst_id, relation) DO UPDATE SET
                weight = excluded.weight,
                props_json = excluded.props_json
            """,
            (src_id, dst_id, relation, weight, json.dumps({}, ensure_ascii=False)),
        )
