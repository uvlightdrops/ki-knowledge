from __future__ import annotations

import csv
import json
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import networkx as nx

from ki_knowledge.api.app import _field_embedding_backend, _get_components
from ki_knowledge.app_config import AppConfig as Config
from ki_knowledge.config_runtime import knowledge_data_root, knowledge_jira_root
from ki_knowledge.integrations.embeddings import OllamaEmbeddingProvider, TFIDFEmbeddingProvider
from ki_knowledge.integrations.jira_cache import DomainTerm, JiraIssueCache
from ki_knowledge.integrations.jira_csv import JiraCSVImporter
from ki_knowledge.integrations.jira_graph import JiraKnowledgeGraph
from ki_knowledge.integrations.semantic_terms import SemanticTermStore
from ki_knowledge.django_site.domain_paths import (
    default_semantic_domain,
    domain_jira_dir,
    domain_markdown_dir,
    domain_ontology_dir,
    domain_pdf_dir,
    normalize_semantic_domain,
    _resolve_domain_file,
    _resolve_existing_domain_dir,
)
from ki_knowledge.django_site.knowledge_summary import semantic_store


def domain_storage_root() -> Path:
    raw = os.getenv("KNOWLEDGE_JIRA_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser()
    return knowledge_jira_root(Config.from_env())


def domain_db_paths(domain: str | None = None) -> dict[str, Path]:
    resolved = normalize_semantic_domain(domain or default_semantic_domain())
    domain_dir = _resolve_existing_domain_dir(domain_storage_root(), resolved)
    return {
        "domain": domain_dir,
        "cache_db": _resolve_domain_file(domain_dir, "cache.sqlite", "jira_cache.sqlite"),
        "graph_db": _resolve_domain_file(domain_dir, "graph.sqlite", "jira_graph.sqlite"),
        "cypher_path": _resolve_domain_file(domain_dir, "graph.cypher", "jira_graph.cypher"),
    }


@contextmanager
def domain_env(domain: str | None):
    paths = domain_db_paths(domain)
    cache_path = str(paths["cache_db"])
    graph_path = str(paths["graph_db"])
    cypher_path = str(paths["cypher_path"]) if paths.get("cypher_path") else ""
    previous = {k: os.environ.get(k) for k in ("JIRA_CACHE_DB", "JIRA_GRAPH_DB", "JIRA_GRAPH_CYPHER_PATH")}
    os.environ["JIRA_CACHE_DB"] = cache_path
    os.environ["JIRA_GRAPH_DB"] = graph_path
    if cypher_path:
        os.environ["JIRA_GRAPH_CYPHER_PATH"] = cypher_path
    elif "JIRA_GRAPH_CYPHER_PATH" in os.environ:
        del os.environ["JIRA_GRAPH_CYPHER_PATH"]
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


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


def jira_graph_db_path(domain: str | None = None) -> str:
    resolved = normalize_semantic_domain(domain or default_semantic_domain())
    domain_key = f"JIRA_GRAPH_DB_{resolved.upper().replace('-', '_')}"
    explicit = os.getenv(domain_key, "").strip()
    if explicit:
        return str(Path(explicit).expanduser())
    if domain is not None and resolved != "default":
        return str(domain_db_paths(resolved)["graph_db"])
    legacy = os.getenv("JIRA_GRAPH_DB", "").strip() or os.getenv("KNOWLEDGE_GRAPH_DB", "").strip()
    if legacy:
        return str(Path(legacy).expanduser())
    return str(domain_db_paths(resolved)["graph_db"])


def jira_csv_path(domain: str | None = None) -> str:
    resolved = normalize_semantic_domain(domain or default_semantic_domain())
    domain_key = f"JIRA_CSV_PATH_{resolved.upper().replace('-', '_')}"
    explicit = os.getenv(domain_key, "").strip()
    if explicit:
        return str(Path(explicit).expanduser())
    if domain is not None and resolved != "default":
        jira_dir = domain_jira_dir(resolved)
        if not jira_dir.exists() or not jira_dir.is_dir():
            return ""
        candidates = sorted(path for path in jira_dir.glob("*.csv") if path.is_file())
        if not candidates:
            return ""
        for preferred in ("jira.csv", "issues.csv", f"{resolved}.csv"):
            exact = next((path for path in candidates if path.name.lower() == preferred), None)
            if exact is not None:
                return str(exact)
        return str(candidates[0])
    legacy = os.getenv("JIRA_CSV_PATH", "").strip()
    if legacy:
        return str(Path(legacy).expanduser())
    jira_dir = domain_jira_dir(resolved)
    if not jira_dir.exists() or not jira_dir.is_dir():
        return ""
    candidates = sorted(path for path in jira_dir.glob("*.csv") if path.is_file())
    if not candidates:
        return ""
    for preferred in ("jira.csv", "issues.csv", f"{resolved}.csv"):
        exact = next((path for path in candidates if path.name.lower() == preferred), None)
        if exact is not None:
            return str(exact)
    return str(candidates[0])


def jira_issue_count(domain: str | None = None) -> int:
    cache_path = Path(jira_cache_db_path(domain)).expanduser()
    if not cache_path.exists():
        return 0
    return JiraIssueCache(str(cache_path)).issue_count()


def jira_domain_terms(limit: int = 200, min_count: int = 2, *, sort: str = "relevance", order: str = "desc", domain: str | None = None) -> list[DomainTerm]:
    cache_path = Path(jira_cache_db_path(domain)).expanduser()
    if not cache_path.exists():
        return []
    cache = JiraIssueCache(str(cache_path))
    store_obj = semantic_store(domain)
    ingest_limit = max(limit * 5, 300)
    extracted = cache.extract_domain_terms(limit=ingest_limit, min_count=min_count)
    store_obj.store_domain_candidates(extracted)
    store_obj.promote_candidates(limit=ingest_limit)
    return store_obj.list_domain_terms(limit=limit, min_count=min_count, sort=sort, order=order)


def jira_reset_data(domain: str | None = None) -> dict[str, Any]:
    paths = domain_db_paths(domain)
    cache_db = Path(paths["cache_db"]).expanduser()
    graph_db = Path(paths["graph_db"]).expanduser()
    cypher_path = paths.get("cypher_path")
    removed = []
    for path in (cache_db, graph_db, cypher_path):
        if path is not None and path.exists():
            path.unlink()
            removed.append(str(path))
    return {
        "removed": removed,
        "cache_db": str(cache_db),
        "graph_db": str(graph_db),
        "cypher_path": str(cypher_path) if cypher_path else "",
    }


def jira_reimport_data(domain: str | None = None) -> dict[str, Any]:
    config = Config.from_env()
    csv_path = jira_csv_path(domain)
    if not csv_path:
        raise ValueError("JIRA_CSV_PATH missing")
    csv_encoding = os.getenv("JIRA_CSV_ENCODING", "utf-8-sig").strip() or "utf-8-sig"
    csv_delimiter = os.getenv("JIRA_CSV_DELIMITER", "").strip() or None
    cache_db = jira_cache_db_path(domain)
    graph_db = jira_graph_db_path(domain)
    cypher_path = str(domain_db_paths(domain).get("cypher_path") or "")
    embed_model = (
        os.getenv("KNOWLEDGE_EMBED_MODEL")
        or os.getenv("JIRA_EMBED_MODEL")
        or config.knowledge_embed_model
        or "nomic-embed-text"
    ).strip()
    use_hybrid = os.getenv("KI_USE_HYBRID_SEARCH") or os.getenv("JIRA_USE_HYBRID_SEARCH", "true")
    use_hybrid = use_hybrid.lower() in {"1", "true", "yes"}

    issues = JiraCSVImporter.from_csv(csv_path, encoding=csv_encoding, delimiter=csv_delimiter)
    cache = JiraIssueCache(cache_db)
    ingested = cache.ingest_issues(issues)

    embedded_issues = 0
    embedded_fields = 0
    embedding_backend = "none"
    if use_hybrid:
        try:
            backend = OllamaEmbeddingProvider(
                base_url=config.ollama_base_url or "http://localhost:11434",
                model=embed_model,
            )
            backend.embed("probe")
            embedded_issues = cache.build_embeddings(backend, embedding_model=embed_model)
            embedded_fields = cache.build_field_embeddings(backend, embedding_model=embed_model)
            embedding_backend = f"ollama:{embed_model}"
        except Exception:
            tfidf = TFIDFEmbeddingProvider()
            tfidf.fit(i.full_text for i in cache.list_issues(limit=5000))
            embedded_issues = cache.build_embeddings(tfidf, embedding_model="tfidf")
            embedded_fields = cache.build_field_embeddings(tfidf, embedding_model="tfidf-fields")
            embedding_backend = "tfidf"

    graph = JiraKnowledgeGraph(graph_db)
    graph_stats = graph.rebuild_from_cache(cache)
    semantic_store_obj = SemanticTermStore(cache_db)
    candidates = cache.extract_domain_terms(limit=300, min_count=2)
    created_candidates = semantic_store_obj.store_domain_candidates(candidates)
    promoted_terms = semantic_store_obj.promote_candidates(limit=300)

    if cypher_path:
        Path(cypher_path).write_text(graph.export_cypher(), encoding="utf-8")

    return {
        "csv_path": csv_path,
        "cache_db": cache_db,
        "graph_db": graph_db,
        "ingested": ingested,
        "issues": cache.issue_count(),
        "graph_nodes": graph_stats["nodes"],
        "graph_edges": graph_stats["edges"],
        "embedded_issues": embedded_issues,
        "embedded_fields": embedded_fields,
        "embedding_backend": embedding_backend,
        "term_candidates": created_candidates,
        "promoted_terms": promoted_terms,
        "cypher_path": cypher_path,
    }


def jira_excluded_terms(kind: str | None = None, domain: str | None = None) -> list[dict[str, str]]:
    return JiraIssueCache(jira_cache_db_path(domain)).list_excluded_terms(kind=kind)


def jira_exclusion_add(term: str, kind: str = "exception", domain: str | None = None) -> bool:
    return JiraIssueCache(jira_cache_db_path(domain)).add_excluded_term(term, kind=kind)


def jira_exclusion_remove(term: str, domain: str | None = None) -> bool:
    return JiraIssueCache(jira_cache_db_path(domain)).remove_excluded_term(term)


def jira_forget_jira_term(term: str, kind: str = "exception", domain: str | None = None) -> dict[str, bool]:
    cache = JiraIssueCache(jira_cache_db_path(domain))
    added = cache.add_excluded_term(term, kind=kind)
    forgotten = semantic_store(domain).forget_term(term)
    return {"excluded": added, "forgotten": forgotten}


def jira_hybrid_search(query: str, limit: int = 8, domain: str | None = None) -> dict[str, Any]:
    normalized = (query or "").strip()
    if not normalized:
        raise ValueError("query missing")
    with domain_env(domain):
        cache, _, assistant = _get_components()
    backend = assistant.embedding_backend
    embedding_model = assistant.embedding_model
    if backend is None or not embedding_model:
        backend, embedding_model = _field_embedding_backend(cache=cache, assistant=assistant)
    cache.build_embeddings(backend, embedding_model=embedding_model)
    hits = cache.hybrid_search(normalized, backend=backend, embedding_model=embedding_model, limit=limit)
    return {
        "hits": hits,
        "query": normalized,
        "cache_db": jira_cache_db_path(domain),
        "issue_count": cache.issue_count(),
        "embedding_model": embedding_model,
    }


def jira_daily_timeline(days: int = 14, domain: str | None = None) -> dict[str, Any]:
    with domain_env(domain):
        cache, _, _ = _get_components()
    items = cache.daily_timeline(limit_days=days)
    return {
        "timeline": items,
        "days": days,
        "cache_db": jira_cache_db_path(domain),
        "issue_count": cache.issue_count(),
    }


def jira_graph_explorer(*, issue_key: str | None = None, limit: int = 20, rebuild: bool = False, domain: str | None = None) -> dict[str, Any]:
    with domain_env(domain):
        cache, _, _ = _get_components()
    graph = JiraKnowledgeGraph(jira_graph_db_path(domain))
    stats = None
    if rebuild:
        stats = graph.rebuild_from_cache(cache)
    selected_key = (issue_key or "").strip()
    if not selected_key:
        issues = cache.list_issues(limit=1)
        selected_key = issues[0].key if issues else ""
    neighbors = graph.issue_neighbors(selected_key, limit=limit) if selected_key else []
    if stats is None:
        with sqlite3.connect(jira_graph_db_path(domain)) as conn:
            node_row = conn.execute("SELECT COUNT(*) FROM graph_nodes").fetchone()
            edge_row = conn.execute("SELECT COUNT(*) FROM graph_edges").fetchone()
            stats = {"nodes": int(node_row[0]) if node_row else 0, "edges": int(edge_row[0]) if edge_row else 0}
    return {"issue_key": selected_key, "neighbors": neighbors, "stats": stats, "graph_db": jira_graph_db_path(domain), "cache_db": jira_cache_db_path(domain), "issue_count": cache.issue_count()}


def jira_domain_analysis(*, limit_terms: int = 20, min_count: int = 2, query: str = "", limit_hits: int = 8, domain: str | None = None) -> dict[str, Any]:
    with domain_env(domain):
        cache, _, assistant = _get_components()
    terms = cache.extract_domain_terms(limit=limit_terms, min_count=min_count)
    backend, embedding_model = _field_embedding_backend(cache=cache, assistant=assistant)
    embedded_fields = cache.build_field_embeddings(backend, embedding_model=embedding_model)
    normalized_query = (query or "").strip()
    hits = []
    if normalized_query:
        hits = cache.semantic_field_search(query=normalized_query, backend=backend, embedding_model=embedding_model, limit=limit_hits)
    return {
        "terms": terms,
        "hits": hits,
        "query": normalized_query,
        "limit_terms": limit_terms,
        "min_count": min_count,
        "limit_hits": limit_hits,
        "embedding_model": embedding_model,
        "embedded_fields": embedded_fields,
        "cache_db": jira_cache_db_path(domain),
        "issue_count": cache.issue_count(),
    }


__all__ = [
    "domain_storage_root",
    "domain_db_paths",
    "domain_env",
    "jira_cache_db_path",
    "jira_graph_db_path",
    "jira_csv_path",
    "jira_issue_count",
    "jira_domain_terms",
    "jira_reset_data",
    "jira_reimport_data",
    "jira_excluded_terms",
    "jira_exclusion_add",
    "jira_exclusion_remove",
    "jira_forget_jira_term",
    "jira_hybrid_search",
    "jira_daily_timeline",
    "jira_graph_explorer",
    "jira_domain_analysis",
]
