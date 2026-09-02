"""Knowledge graph layer for cached Jira issues."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Iterable, Optional

from ki_knowledge.integrations.jira_cache import JiraIssueCache, CachedIssue


@dataclass
class GraphNeighbor:
    """Neighbor in issue-centric graph traversal."""

    neighbor_id: str
    neighbor_type: str
    relation: str
    weight: float


class JiraKnowledgeGraph:
    """Build and query a lightweight knowledge graph in SQLite."""

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
                CREATE TABLE IF NOT EXISTS graph_nodes (
                    node_id TEXT PRIMARY KEY,
                    node_type TEXT NOT NULL,
                    label TEXT NOT NULL,
                    props_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS graph_edges (
                    src_id TEXT NOT NULL,
                    dst_id TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    weight REAL NOT NULL DEFAULT 1.0,
                    props_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (src_id, dst_id, relation)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_graph_edges_src ON graph_edges(src_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_graph_edges_dst ON graph_edges(dst_id)"
            )

    def rebuild_from_cache(self, cache: JiraIssueCache, issue_limit: int = 5000) -> dict[str, int]:
        """Rebuild graph from cached issues."""
        issues = cache.list_issues(limit=issue_limit)
        with self._connect() as conn:
            conn.execute("DELETE FROM graph_edges")
            conn.execute("DELETE FROM graph_nodes")

            for issue in issues:
                self._insert_issue_node(conn, issue)
                self._connect_issue_metadata(conn, issue)

            self._connect_related_issues_by_label(conn, issues)

            node_count = conn.execute("SELECT COUNT(*) AS c FROM graph_nodes").fetchone()["c"]
            edge_count = conn.execute("SELECT COUNT(*) AS c FROM graph_edges").fetchone()["c"]

        return {"nodes": int(node_count), "edges": int(edge_count)}

    def related_issue_keys(
        self,
        issue_keys: list[str],
        relations: Iterable[str] = ("related_label",),
        limit_per_seed: int = 5,
    ) -> list[str]:
        """Return issue keys reachable from seed keys via given relation types."""
        seen = set(issue_keys)
        result: list[str] = []
        rels = list(relations)
        placeholders = ",".join(["?"] * len(rels))

        with self._connect() as conn:
            for key in issue_keys:
                rows = conn.execute(
                    f"""
                    SELECT ge.dst_id, ge.weight
                    FROM graph_edges ge
                    JOIN graph_nodes gn ON ge.dst_id = gn.node_id
                    WHERE ge.src_id = ?
                      AND ge.relation IN ({placeholders})
                      AND gn.node_type = 'issue'
                    ORDER BY ge.weight DESC
                    LIMIT ?
                    """,
                    (f"issue:{key}", *rels, limit_per_seed),
                ).fetchall()
                for row in rows:
                    neighbor_key = row["dst_id"].removeprefix("issue:")
                    if neighbor_key not in seen:
                        seen.add(neighbor_key)
                        result.append(neighbor_key)
        return result

    def issue_neighbors(
        self,
        issue_key: str,
        relation_filter: Optional[Iterable[str]] = None,
        limit: int = 25,
    ) -> list[GraphNeighbor]:
        """Return direct neighbors for an issue node."""
        source_node = f"issue:{issue_key}"
        params: list = [source_node]
        where_relation = ""
        if relation_filter:
            rels = list(relation_filter)
            if rels:
                placeholders = ",".join(["?"] * len(rels))
                where_relation = f" AND ge.relation IN ({placeholders})"
                params.extend(rels)
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT gn.node_id, gn.node_type, ge.relation, ge.weight
                FROM graph_edges ge
                JOIN graph_nodes gn ON ge.dst_id = gn.node_id
                WHERE ge.src_id = ? {where_relation}
                ORDER BY ge.weight DESC, gn.node_id ASC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()

        return [
            GraphNeighbor(
                neighbor_id=row["node_id"],
                neighbor_type=row["node_type"],
                relation=row["relation"],
                weight=float(row["weight"]),
            )
            for row in rows
        ]

    def export_cypher(self, limit_nodes: int = 200, limit_edges: int = 600) -> str:
        """Export a Cypher snippet for learning and external graph tools."""
        with self._connect() as conn:
            nodes = conn.execute(
                """
                SELECT node_id, node_type, label
                FROM graph_nodes
                ORDER BY node_id
                LIMIT ?
                """,
                (limit_nodes,),
            ).fetchall()
            edges = conn.execute(
                """
                SELECT src_id, dst_id, relation, weight
                FROM graph_edges
                ORDER BY relation, src_id, dst_id
                LIMIT ?
                """,
                (limit_edges,),
            ).fetchall()

        lines = ["// Cypher export generated by JiraKnowledgeGraph"]
        for node in nodes:
            var_name = self._cypher_var(node["node_id"])
            label = node["node_type"].capitalize()
            safe_id = node["node_id"].replace("'", "\\'")
            safe_label = node["label"].replace("'", "\\'")
            lines.append(
                f"MERGE ({var_name}:{label} {{id: '{safe_id}'}}) SET {var_name}.name = '{safe_label}';"
            )
        for edge in edges:
            src_var = self._cypher_var(edge["src_id"])
            dst_var = self._cypher_var(edge["dst_id"])
            rel = edge["relation"].upper().replace("-", "_")
            lines.append(
                f"MATCH ({src_var} {{id: '{edge['src_id']}'}}), ({dst_var} {{id: '{edge['dst_id']}'}}) "
                f"MERGE ({src_var})-[:{rel} {{weight: {float(edge['weight'])}}}]->({dst_var});"
            )
        return "\n".join(lines)

    def _insert_issue_node(self, conn: sqlite3.Connection, issue: CachedIssue) -> None:
        issue_id = f"issue:{issue.key}"
        props = {
            "status": issue.status,
            "issue_type": issue.issue_type,
            "assignee": issue.assignee,
            "created_at": issue.created_at,
            "updated_at": issue.updated_at,
            "event_day": issue.event_day,
        }
        conn.execute(
            """
            INSERT OR REPLACE INTO graph_nodes (node_id, node_type, label, props_json)
            VALUES (?, ?, ?, ?)
            """,
            (issue_id, "issue", issue.summary, json.dumps(props, ensure_ascii=False)),
        )

    def _connect_issue_metadata(self, conn: sqlite3.Connection, issue: CachedIssue) -> None:
        issue_id = f"issue:{issue.key}"

        if issue.assignee:
            assignee_id = f"assignee:{issue.assignee.lower()}"
            self._upsert_node(conn, assignee_id, "assignee", issue.assignee)
            self._upsert_edge(conn, issue_id, assignee_id, "assigned_to", 1.0)

        status_id = f"status:{issue.status.lower()}"
        self._upsert_node(conn, status_id, "status", issue.status)
        self._upsert_edge(conn, issue_id, status_id, "has_status", 1.0)

        type_id = f"type:{issue.issue_type.lower()}"
        self._upsert_node(conn, type_id, "type", issue.issue_type)
        self._upsert_edge(conn, issue_id, type_id, "has_type", 1.0)

        if issue.event_day:
            day_id = f"day:{issue.event_day}"
            self._upsert_node(conn, day_id, "day", issue.event_day)
            self._upsert_edge(conn, issue_id, day_id, "updated_on", 1.0)

        for label in issue.labels:
            label_id = f"label:{label.lower()}"
            self._upsert_node(conn, label_id, "label", label)
            self._upsert_edge(conn, issue_id, label_id, "has_label", 1.0)

    def _connect_related_issues_by_label(
        self,
        conn: sqlite3.Connection,
        issues: list[CachedIssue],
    ) -> None:
        label_to_issues: dict[str, list[str]] = {}
        for issue in issues:
            issue_id = f"issue:{issue.key}"
            for label in issue.labels:
                norm = label.lower().strip()
                if not norm:
                    continue
                label_to_issues.setdefault(norm, []).append(issue_id)

        pair_weights: dict[tuple[str, str], float] = {}
        for _, issue_ids in label_to_issues.items():
            unique_ids = sorted(set(issue_ids))
            for i, left in enumerate(unique_ids):
                for right in unique_ids[i + 1:]:
                    pair = (left, right)
                    pair_weights[pair] = pair_weights.get(pair, 0.0) + 1.0

        for (left, right), weight in pair_weights.items():
            self._upsert_edge(conn, left, right, "related_label", weight)
            self._upsert_edge(conn, right, left, "related_label", weight)

    def _upsert_node(
        self,
        conn: sqlite3.Connection,
        node_id: str,
        node_type: str,
        label: str,
    ) -> None:
        conn.execute(
            """
            INSERT OR REPLACE INTO graph_nodes (node_id, node_type, label, props_json)
            VALUES (?, ?, ?, ?)
            """,
            (node_id, node_type, label, "{}"),
        )

    def _upsert_edge(
        self,
        conn: sqlite3.Connection,
        src_id: str,
        dst_id: str,
        relation: str,
        weight: float,
    ) -> None:
        conn.execute(
            """
            INSERT OR REPLACE INTO graph_edges (src_id, dst_id, relation, weight, props_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (src_id, dst_id, relation, weight, "{}"),
        )

    def _cypher_var(self, node_id: str) -> str:
        sanitized = "".join(ch if ch.isalnum() else "_" for ch in node_id)
        return f"n_{sanitized}"
