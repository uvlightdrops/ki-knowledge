"""Copy knowledge and semantic SQLite stores into PostgreSQL schemas.

Dry run by default; SQLite files are opened read-only and never modified.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ki_knowledge.app_config import AppConfig as Config
from ki_knowledge.config_runtime import knowledge_db_path
from ki_knowledge.data_layout import DataLayout
from ki_knowledge.integrations.knowledge_graph import KnowledgeGraph
from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.integrations.semantic_terms import SemanticTermStore
from ki_knowledge.integrations.sql_backend import StoreTarget, connect, normalized_schema, vector_literal

KNOWLEDGE_TABLES = {
    "knowledge_sources": ["source_id", "source_type", "title", "location", "metadata_json", "created_at", "updated_at"],
    "knowledge_blocks": ["id", "source_type", "source_path", "block_type", "parent_id", "heading_path", "content", "order_index", "metadata_json", "created_at", "updated_at"],
    "knowledge_relations": ["id", "source_block_id", "target_block_id", "relation", "weight", "metadata_json", "created_at"],
    "knowledge_embeddings": ["block_id", "model", "vector_json", "created_at"],
    "knowledge_artifacts": ["artifact_id", "artifact_type", "source_id", "source_block_ids_json", "content", "metadata_json", "created_at", "updated_at"],
    "knowledge_graph_nodes": ["node_id", "node_type", "label", "props_json"],
    "knowledge_graph_edges": ["src_id", "dst_id", "relation", "weight", "props_json"],
    "knowledge_store_migrations": ["name", "applied_at"],
}
SEMANTIC_TABLES = {
    "semantic_terms": ["term_id", "canonical_label", "normalized_label", "language", "status", "created_at", "updated_at"],
    "semantic_term_aliases": ["alias_id", "term_id", "alias_label", "normalized_alias", "source", "created_at"],
    "semantic_term_candidates": ["candidate_id", "raw_label", "normalized_label", "score", "issue_count", "sample_issue_keys_json", "source_type", "promoted_term_id", "created_at"],
    "semantic_enrichment_jobs": ["job_id", "term_id", "job_type", "status", "attempts", "next_retry_at", "error_message", "prompt_text", "created_at", "updated_at"],
    "semantic_facts": ["fact_id", "term_id", "fact_type", "content", "confidence", "model_id", "prompt_version", "prompt_hash", "response_hash", "supersedes_fact_id", "created_at"],
    "semantic_relations": ["relation_id", "source_term_id", "target_term_id", "relation_type", "weight", "provenance_fact_id", "created_at"],
    "semantic_record_term_links": ["link_id", "record_id", "term_id", "source", "confidence", "evidence", "job_id", "created_at", "updated_at"],
}
JSON_COLUMNS = {"metadata_json", "source_block_ids_json", "props_json", "sample_issue_keys_json"}


def _ro_conn(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def _counts(path: Path, tables: dict[str, list[str]]) -> dict[str, int]:
    if not path.exists():
        return {table: 0 for table in tables}
    with _ro_conn(path) as conn:
        result = {}
        for table in tables:
            result[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) if _table_exists(conn, table) else 0
        return result


def _validate_json(value: Any, *, table: str, column: str, row_id: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    try:
        json.loads(text or "null")
    except json.JSONDecodeError as exc:
        raise CommandError(f"Invalid JSON in {table}.{column} row {row_id}: {exc}") from exc
    return text


def _target_count(target: StoreTarget, table: str) -> int:
    with connect(target) as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _truncate(target: StoreTarget, tables: list[str]) -> None:
    with connect(target) as conn:
        for table in reversed(tables):
            conn.execute(f"TRUNCATE TABLE {table}") if conn.dialect == "postgres" else conn.execute(f"DELETE FROM {table}")


def _copy_table(src_path: Path, target: StoreTarget, table: str, columns: list[str], *, batch_size: int) -> int:
    if not src_path.exists():
        return 0
    with _ro_conn(src_path) as src:
        if not _table_exists(src, table):
            return 0
        present = {row[1] for row in src.execute(f"PRAGMA table_info({table})")}
        columns = [column for column in columns if column in present]
        order_col = columns[0]
        rows = src.execute(f"SELECT {', '.join(columns)} FROM {table} ORDER BY {order_col}")
        copied = 0
        with connect(target) as dst:
            placeholders = ["?" for _ in columns]
            if table == "knowledge_embeddings" and dst.dialect == "postgres":
                placeholders[columns.index("vector_json")] = "?::vector"
            sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
            batch: list[tuple[Any, ...]] = []
            for row in rows:
                values = []
                row_id = row[order_col]
                for col in columns:
                    value = row[col]
                    if col in JSON_COLUMNS:
                        value = _validate_json(value, table=table, column=col, row_id=row_id)
                    if table == "knowledge_embeddings" and col == "vector_json" and dst.dialect == "postgres":
                        try:
                            value = vector_literal(json.loads(value))
                        except Exception as exc:
                            raise CommandError(f"Invalid vector_json in {table} row {row_id}: {exc}") from exc
                    values.append(value)
                batch.append(tuple(values))
                if len(batch) >= batch_size:
                    dst.executemany(sql, batch)
                    copied += len(batch)
                    batch.clear()
            if batch:
                dst.executemany(sql, batch)
                copied += len(batch)
        return copied


class Command(BaseCommand):
    help = "Copy knowledge.db and semantic term tables into PostgreSQL schemas (dry run by default)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--confirm-services-stopped", action="store_true")
        parser.add_argument("--replace", action="store_true")
        parser.add_argument("--domain", action="append", help="Only migrate this semantic domain (can repeat).")
        parser.add_argument("--knowledge-only", action="store_true", help="Skip the semantic term schemas.")
        parser.add_argument("--batch-size", type=int, default=2000)
        parser.add_argument("--knowledge-schema", default="knowledge", help="Test/staging only: the application always reads schema 'knowledge'.")

    def handle(self, *args, **options):
        base_target = getattr(settings, "KNOWLEDGE_STORE_TARGET", None)
        if not base_target or not base_target.is_postgres:
            raise CommandError("Knowledge store target is not PostgreSQL.")
        dsn = base_target.postgres_dsn or ""
        cfg = Config.from_env()
        layout = DataLayout.from_config(cfg)
        knowledge_path = knowledge_db_path(cfg)
        from ki_knowledge.django_site.knowledge_summary import jira_cache_db_path
        from ki_knowledge.django_site.domain_paths import normalize_semantic_domain

        if not knowledge_path.is_file():
            raise CommandError(f"Knowledge store not found: {knowledge_path}")
        domains = [] if options["knowledge_only"] else sorted(
            {normalize_semantic_domain(d) for d in (options["domain"] or layout.domain_names())}
        )
        # Domains without a cache file have no semantic data; their schema is created lazily on use.
        semantic_paths = [
            (domain, path) for domain in domains
            if (path := Path(jira_cache_db_path(domain)).expanduser()).is_file()
        ]
        if options["domain"] and len(semantic_paths) != len(domains):
            missing = sorted(set(domains) - {domain for domain, _path in semantic_paths})
            raise CommandError(f"No semantic cache file for domain(s): {', '.join(missing)}")

        knowledge_counts = _counts(knowledge_path, KNOWLEDGE_TABLES)
        semantic_counts = [(domain, path, _counts(path, SEMANTIC_TABLES)) for domain, path in semantic_paths]
        self.stdout.write(f"Knowledge source: {knowledge_path}")
        self.stdout.write(f"Knowledge target schema: {options['knowledge_schema']}")
        self.stdout.write(f"Knowledge rows: {sum(knowledge_counts.values())} across {sum(1 for c in knowledge_counts.values() if c)} tables")
        for table, count in sorted(knowledge_counts.items()):
            if count:
                self.stdout.write(f"  {table}: {count}")
        self.stdout.write(f"Semantic domains: {len(semantic_counts)}")
        for domain, path, counts in semantic_counts:
            total = sum(counts.values())
            if total:
                self.stdout.write(f"  {domain}: {total} rows from {path}")
        if not options["apply"]:
            self.stdout.write("Dry run. Re-run with --apply --confirm-services-stopped.")
            return
        if not options["confirm_services_stopped"]:
            raise CommandError("Stop Django and all workers, then pass --confirm-services-stopped.")

        knowledge_target = StoreTarget.postgres(dsn, schema=options["knowledge_schema"])
        KnowledgeStore(knowledge_target)
        KnowledgeGraph(knowledge_target)
        targets = [(knowledge_target, KNOWLEDGE_TABLES, knowledge_path, "knowledge")]
        semantic_targets = []
        for domain, path, _counts_for_domain in semantic_counts:
            schema = normalized_schema("semantic_", domain)
            target = StoreTarget.postgres(dsn, schema=schema)
            SemanticTermStore(target)
            semantic_targets.append((domain, path, target))
            targets.append((target, SEMANTIC_TABLES, path, f"semantic:{domain}"))

        existing = []
        for target, tables, _path, label in targets:
            for table in tables:
                if table == "knowledge_store_migrations":
                    continue  # written by the store's own schema setup, replaced by the source rows
                count = _target_count(target, table)
                if count:
                    existing.append((label, table, count))
        if existing and not options["replace"]:
            raise CommandError("PostgreSQL target already contains rows; use --replace to overwrite managed schemas.")
        for target, tables, _path, _label in targets:
            _truncate(target, list(tables.keys()) if options["replace"] else [t for t in tables if t == "knowledge_store_migrations"])

        copied_summary = []
        for target, tables, path, label in targets:
            for table, columns in tables.items():
                copied = _copy_table(path, target, table, columns, batch_size=options["batch_size"])
                expected = _counts(path, tables).get(table, 0)
                actual = _target_count(target, table)
                if actual != expected:
                    raise CommandError(f"Count mismatch for {label}.{table}: sqlite={expected} postgres={actual}")
                if copied:
                    copied_summary.append((label, table, copied))
        total = sum(count for _label, _table, count in copied_summary)
        self.stdout.write(self.style.SUCCESS(f"Copied {total} rows into PostgreSQL schemas."))
        for label, table, count in copied_summary:
            self.stdout.write(f"  {label}.{table}: {count}")
