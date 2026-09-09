from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Any

from django.conf import settings

from ki_knowledge.django_site.domain_paths import (
    _cached_get,
    _cached_set,
    _resolve_domain_file,
    _resolve_existing_domain_dir,
    default_semantic_domain,
    domain_jira_dir,
    domain_markdown_dir,
    domain_ontology_dir,
    domain_pdf_dir,
    invalidate_domain_summary_cache,
    jira_type_root,
    markdown_type_root,
    normalize_semantic_domain,
    ontology_type_root,
    pdf_type_root,
)
from ki_knowledge.integrations.semantic_terms import SemanticTermStore
from ki_knowledge.integrations.knowledge_store import KnowledgeStore


def _domain_summary_cache_key(domain: str | None = None) -> str:
    resolved = normalize_semantic_domain(domain or default_semantic_domain())
    return f"ki-knowledge:domain-summary:{resolved}"


def _domain_source_ids_cache_key(domain: str | None = None) -> str:
    resolved = normalize_semantic_domain(domain or default_semantic_domain())
    return f"ki-knowledge:domain-source-ids:{resolved}"


def domain_storage_root() -> Path:
    raw = os.getenv("KNOWLEDGE_JIRA_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser()
    return jira_type_root()


def domain_db_paths(domain: str | None = None) -> dict[str, Path]:
    resolved = normalize_semantic_domain(domain or default_semantic_domain())
    domain_dir = _resolve_existing_domain_dir(domain_storage_root(), resolved)
    return {
        "domain": domain_dir,
        "cache_db": _resolve_domain_file(domain_dir, "cache.sqlite", "jira_cache.sqlite"),
        "graph_db": _resolve_domain_file(domain_dir, "graph.sqlite", "jira_graph.sqlite"),
        "cypher_path": _resolve_domain_file(domain_dir, "graph.cypher", "jira_graph.cypher"),
    }


def _is_under_dir(path: Path, root: Path) -> bool:
    try:
        path_resolved = path.expanduser().resolve()
    except OSError:
        path_resolved = path.expanduser()
    try:
        root_resolved = root.expanduser().resolve()
    except OSError:
        root_resolved = root.expanduser()
    if path_resolved == root_resolved:
        return True
    return str(path_resolved).startswith(f"{root_resolved}{os.sep}")


def store() -> KnowledgeStore:
    return KnowledgeStore(settings.KNOWLEDGE_DB_PATH)


def _domain_scoped_sources(domain: str | None = None, *, limit: int | None = None) -> list[Any]:
    resolved = normalize_semantic_domain(domain or default_semantic_domain())
    if resolved == "default":
        rows = store().list_sources()[:limit] if limit is not None else store().list_sources()
        return rows

    roots = [
        domain_markdown_dir(resolved),
        domain_jira_dir(resolved),
        domain_ontology_dir(resolved),
        domain_pdf_dir(resolved),
    ]
    clauses: list[str] = []
    params: list[str] = []
    for root in roots:
        root_str = str(root.expanduser())
        clauses.append("(location = ? OR location LIKE ? OR location LIKE ?)")
        params.extend([root_str, f"{root_str}/%", f"{root_str}\\%"])
    if not clauses:
        return []
    sql = "SELECT * FROM knowledge_sources WHERE " + " OR ".join(clauses)
    sql += " ORDER BY updated_at DESC, source_id"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(str(limit))
    with sqlite3.connect(settings.KNOWLEDGE_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
    store_obj = store()
    return [store_obj._row_to_source(row) for row in rows]


def domain_knowledge_summary(domain: str | None = None) -> dict[str, Any]:
    cache_key = _domain_summary_cache_key(domain)
    cached = _cached_get(cache_key)
    if cached is not None:
        return cached

    store_obj = store()
    scoped_sources = _domain_scoped_sources(domain)
    source_ids = [source.source_id for source in scoped_sources]
    source_count = len(source_ids)
    if not source_ids:
        result = {"sources": 0, "records": 0, "artifacts": 0, "recent_sources": [], "recent_artifacts": []}
        _cached_set(cache_key, result)
        return result
    with sqlite3.connect(settings.KNOWLEDGE_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        source_placeholders = ",".join("?" for _ in source_ids)
        record_count = conn.execute(
            f"""
            SELECT COUNT(*) FROM knowledge_blocks kb
            JOIN knowledge_sources ks ON kb.source_path = ks.location
            WHERE ks.source_id IN ({source_placeholders})
            """,
            source_ids,
        ).fetchone()
        artifact_count = conn.execute(
            f"SELECT COUNT(*) FROM knowledge_artifacts WHERE source_id IN ({source_placeholders})",
            source_ids,
        ).fetchone()
        recent_artifacts_rows = conn.execute(
            f"SELECT * FROM knowledge_artifacts WHERE source_id IN ({source_placeholders}) ORDER BY updated_at DESC, artifact_id LIMIT 8",
            source_ids,
        ).fetchall()
    scoped_artifacts = [store_obj._row_to_artifact(row) for row in recent_artifacts_rows]
    result = {
        "sources": source_count,
        "records": int(record_count[0]) if record_count else 0,
        "artifacts": int(artifact_count[0]) if artifact_count else 0,
        "recent_sources": scoped_sources[:8],
        "recent_artifacts": scoped_artifacts[:8],
    }
    _cached_set(cache_key, result)
    return result


def domain_source_ids(domain: str | None = None) -> set[str]:
    cache_key = _domain_source_ids_cache_key(domain)
    cached = _cached_get(cache_key)
    if cached is not None:
        return {str(item) for item in cached}

    scoped_sources = _domain_scoped_sources(domain)
    result = {str(source.source_id) for source in scoped_sources}
    _cached_set(cache_key, sorted(result))
    return result


def domain_registry_overview(active_domain: str | None = None) -> list[dict[str, Any]]:
    from ki_knowledge.django_site.infosite_models import Domain, InfoSiteProject, SourceDocument

    overview: list[dict[str, Any]] = []
    for domain in Domain.objects.all():
        if domain.slug == "default":
            continue
        knowledge = domain_knowledge_summary(domain.slug)
        projects = InfoSiteProject.objects.filter(domain=domain.slug)
        overview.append(
            {
                "slug": domain.slug,
                "display_name": domain.display_name or domain.slug,
                "is_active": domain.slug == active_domain,
                "knowledge_sources": knowledge["sources"],
                "knowledge_records": knowledge["records"],
                "infosite_project_count": projects.count(),
                "infosite_source_count": SourceDocument.objects.filter(project__domain=domain.slug).count(),
            }
        )
    return overview


def _domain_knowledge_scope(domain: str | None = None) -> tuple[list[str], list[str]]:
    scoped_sources = _domain_scoped_sources(domain)
    source_ids = [source.source_id for source in scoped_sources]
    source_locations = [str(source.location) for source in scoped_sources]
    return source_ids, source_locations


def knowledge_base_clear_domain_artifacts(domain: str | None = None) -> dict[str, Any]:
    normalized_domain = normalize_semantic_domain(domain)
    source_ids, _ = _domain_knowledge_scope(domain)
    invalidate_domain_summary_cache(normalized_domain)
    if not source_ids:
        return {"domain": normalized_domain, "deleted_artifacts": 0}
    with sqlite3.connect(settings.KNOWLEDGE_DB_PATH) as conn:
        placeholders = ",".join("?" for _ in source_ids)
        row = conn.execute(
            f"SELECT COUNT(*) FROM knowledge_artifacts WHERE source_id IN ({placeholders})",
            source_ids,
        ).fetchone()
        deleted_artifacts = int(row[0]) if row else 0
        conn.execute(f"DELETE FROM knowledge_artifacts WHERE source_id IN ({placeholders})", source_ids)
    return {
        "domain": normalize_semantic_domain(domain),
        "sources": len(source_ids),
        "deleted_artifacts": deleted_artifacts,
    }


def knowledge_base_reset_domain(domain: str | None = None) -> dict[str, Any]:
    source_ids, source_locations = _domain_knowledge_scope(domain)
    normalized_domain = normalize_semantic_domain(domain)
    invalidate_domain_summary_cache(normalized_domain)
    if not source_ids and not source_locations:
        return {
            "domain": normalized_domain,
            "sources": 0,
            "deleted_records": 0,
            "deleted_relations": 0,
            "deleted_embeddings": 0,
            "deleted_artifacts": 0,
            "deleted_sources": 0,
        }
    with sqlite3.connect(settings.KNOWLEDGE_DB_PATH) as conn:
        block_ids: list[str] = []
        queries: list[tuple[str, list[str]]] = []
        if source_locations:
            placeholders = ",".join("?" for _ in source_locations)
            queries.append((f"SELECT id FROM knowledge_blocks WHERE source_path IN ({placeholders})", source_locations))
        if source_ids:
            placeholders = ",".join("?" for _ in source_ids)
            queries.append(
                (
                    f"SELECT id FROM knowledge_blocks WHERE json_extract(metadata_json, '$.source_id') IN ({placeholders})",
                    source_ids,
                )
            )
        for query, params in queries:
            rows = conn.execute(query, params).fetchall()
            block_ids.extend(str(row[0]) for row in rows)
        block_ids = sorted(set(block_ids))

        deleted_relations = 0
        deleted_embeddings = 0
        deleted_records = 0
        if block_ids:
            block_placeholders = ",".join("?" for _ in block_ids)
            relation_row = conn.execute(
                f"""
                SELECT COUNT(*) FROM knowledge_relations
                WHERE source_block_id IN ({block_placeholders})
                   OR target_block_id IN ({block_placeholders})
                """,
                [*block_ids, *block_ids],
            ).fetchone()
            deleted_relations = int(relation_row[0]) if relation_row else 0
            embedding_row = conn.execute(
                f"SELECT COUNT(*) FROM knowledge_embeddings WHERE block_id IN ({block_placeholders})",
                block_ids,
            ).fetchone()
            deleted_embeddings = int(embedding_row[0]) if embedding_row else 0
            record_row = conn.execute(
                f"SELECT COUNT(*) FROM knowledge_blocks WHERE id IN ({block_placeholders})",
                block_ids,
            ).fetchone()
            deleted_records = int(record_row[0]) if record_row else 0
            conn.execute(
                f"""
                DELETE FROM knowledge_relations
                WHERE source_block_id IN ({block_placeholders})
                   OR target_block_id IN ({block_placeholders})
                """,
                [*block_ids, *block_ids],
            )
            conn.execute(f"DELETE FROM knowledge_embeddings WHERE block_id IN ({block_placeholders})", block_ids)
            conn.execute(f"DELETE FROM knowledge_blocks WHERE id IN ({block_placeholders})", block_ids)

        deleted_artifacts = 0
        deleted_sources = 0
        if source_ids:
            source_placeholders = ",".join("?" for _ in source_ids)
            artifact_row = conn.execute(
                f"SELECT COUNT(*) FROM knowledge_artifacts WHERE source_id IN ({source_placeholders})",
                source_ids,
            ).fetchone()
            deleted_artifacts = int(artifact_row[0]) if artifact_row else 0
            source_row = conn.execute(
                f"SELECT COUNT(*) FROM knowledge_sources WHERE source_id IN ({source_placeholders})",
                source_ids,
            ).fetchone()
            deleted_sources = int(source_row[0]) if source_row else 0
            conn.execute(f"DELETE FROM knowledge_artifacts WHERE source_id IN ({source_placeholders})", source_ids)
            conn.execute(f"DELETE FROM knowledge_sources WHERE source_id IN ({source_placeholders})", source_ids)

    return {
        "domain": normalized_domain,
        "sources": len(source_ids),
        "deleted_records": deleted_records,
        "deleted_relations": deleted_relations,
        "deleted_embeddings": deleted_embeddings,
        "deleted_artifacts": deleted_artifacts,
        "deleted_sources": deleted_sources,
    }


def knowledge_base_reset_all() -> dict[str, Any]:
    for domain in (default_semantic_domain(), "default"):
        invalidate_domain_summary_cache(domain)
    with sqlite3.connect(settings.KNOWLEDGE_DB_PATH) as conn:
        counts = {}
        for table in (
            "knowledge_relations",
            "knowledge_embeddings",
            "knowledge_artifacts",
            "knowledge_blocks",
            "knowledge_sources",
        ):
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            counts[table] = int(row[0]) if row else 0
        conn.execute("DELETE FROM knowledge_relations")
        conn.execute("DELETE FROM knowledge_embeddings")
        conn.execute("DELETE FROM knowledge_artifacts")
        conn.execute("DELETE FROM knowledge_blocks")
        conn.execute("DELETE FROM knowledge_sources")
    return {"deleted": counts}


def jira_cache_db_path(domain: str | None = None) -> str:
    resolved = normalize_semantic_domain(domain or default_semantic_domain())
    domain_key = f"JIRA_CACHE_DB_{resolved.upper().replace('-', '_')}"
    explicit = os.getenv(domain_key, "").strip()
    if explicit:
        return str(Path(explicit).expanduser())
    if domain is not None and resolved != "default":
        return str(domain_db_paths(resolved)["cache_db"])
    legacy = os.getenv("JIRA_CACHE_DB", "").strip() or os.getenv("KNOWLEDGE_CACHE_DB", "").strip()
    if legacy:
        return str(Path(legacy).expanduser())
    return str(domain_db_paths(resolved)["cache_db"])


def semantic_store(domain: str | None = None) -> SemanticTermStore:
    return SemanticTermStore(jira_cache_db_path(domain))


def semantic_terms(status: str | None = None, limit: int = 300, domain: str | None = None):
    return semantic_store(domain).list_terms(status=status, limit=limit)


def semantic_term_detail(term_id: str, domain: str | None = None) -> dict[str, Any] | None:
    store_obj = semantic_store(domain)
    term = store_obj.get_term(term_id)
    if term is None:
        return None
    return {
        "term": term,
        "facts": store_obj.current_facts(term_id),
        "relations": store_obj.term_relations(term_id),
    }


def semantic_monitoring_snapshot(domain: str | None = None) -> dict[str, Any]:
    return semantic_store(domain).monitoring_snapshot(recent_limit=10)


def semantic_jobs(status: str | None = None, job_type: str | None = None, limit: int = 200, domain: str | None = None):
    return semantic_store(domain).list_jobs(status=status, job_type=job_type, limit=limit)


def semantic_job_detail(job_id: str, domain: str | None = None) -> dict[str, Any] | None:
    store_obj = semantic_store(domain)
    job = store_obj.get_job(job_id)
    if job is None:
        return None
    term = store_obj.get_term(job.term_id)
    related = []
    if term is not None:
        related = store_obj.current_facts(job.term_id)[:8]
    elif job.term_id:
        related = store_obj.list_record_term_links(record_id=job.term_id, limit=20)
    return {
        "job": job,
        "term": term,
        "facts": related,
    }


__all__ = [
    "domain_storage_root",
    "domain_db_paths",
    "store",
    "_domain_scoped_sources",
    "domain_knowledge_summary",
    "domain_source_ids",
    "domain_registry_overview",
    "knowledge_base_clear_domain_artifacts",
    "knowledge_base_reset_domain",
    "knowledge_base_reset_all",
    "jira_cache_db_path",
    "semantic_store",
    "semantic_terms",
    "semantic_term_detail",
    "semantic_monitoring_snapshot",
    "semantic_jobs",
    "semantic_job_detail",
]
