"""Jira retrieval over explicit stores, independent of HTTP and Django."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from ki_knowledge.integrations.embeddings import TFIDFEmbeddingProvider
from ki_knowledge.integrations.jira_assistant import JiraSupportAssistant
from ki_knowledge.integrations.jira_cache import EmbeddingBackend, JiraIssueCache
from ki_knowledge.integrations.jira_graph import JiraKnowledgeGraph


def field_embedding_backend(
    cache: JiraIssueCache, assistant: JiraSupportAssistant, issue_limit: int = 5000,
) -> tuple[EmbeddingBackend, str]:
    if assistant.embedding_backend and assistant.embedding_model:
        return assistant.embedding_backend, assistant.embedding_model
    backend = TFIDFEmbeddingProvider()
    corpus = cache.semantic_text_corpus(issue_limit=issue_limit)
    if not corpus:
        return backend, "tfidf-fields-empty"
    backend.fit(corpus)
    return backend, "tfidf-fields"


class JiraRetrievalService:
    def __init__(
        self, cache: JiraIssueCache, graph: JiraKnowledgeGraph,
        assistant: JiraSupportAssistant,
    ):
        self.cache = cache
        self.graph = graph
        self.assistant = assistant

    @classmethod
    def from_paths(cls, cache_db: str | Path, graph_db: str | Path) -> JiraRetrievalService:
        cache = JiraIssueCache(str(cache_db))
        graph = JiraKnowledgeGraph(str(graph_db))
        corpus = [issue.full_text for issue in cache.list_issues(limit=5000)]
        backend = TFIDFEmbeddingProvider()
        if corpus:
            backend.fit(corpus)
        assistant = JiraSupportAssistant(
            backend=None,
            cache=cache,
            embedding_backend=backend if corpus else None,
            embedding_model="tfidf" if corpus else None,
            graph=graph,
        )
        return cls(cache, graph, assistant)

    def hybrid_search(self, query: str, limit: int = 8) -> dict[str, Any]:
        normalized = (query or "").strip()
        if not normalized:
            raise ValueError("query missing")
        backend, model = field_embedding_backend(self.cache, self.assistant)
        self.cache.build_embeddings(backend, embedding_model=model)
        hits = self.cache.hybrid_search(
            normalized, backend=backend, embedding_model=model, limit=limit,
        )
        return {
            "hits": hits,
            "query": normalized,
            "cache_db": self.cache.db_path,
            "issue_count": self.cache.issue_count(),
            "embedding_model": model,
        }

    def daily_timeline(self, days: int = 14) -> dict[str, Any]:
        return {
            "timeline": self.cache.daily_timeline(limit_days=days),
            "days": days,
            "cache_db": self.cache.db_path,
            "issue_count": self.cache.issue_count(),
        }

    def graph_explorer(
        self, *, issue_key: str | None = None, limit: int = 20, rebuild: bool = False,
    ) -> dict[str, Any]:
        stats = self.graph.rebuild_from_cache(self.cache) if rebuild else None
        selected_key = (issue_key or "").strip()
        if not selected_key:
            issues = self.cache.list_issues(limit=1)
            selected_key = issues[0].key if issues else ""
        neighbors = self.graph.issue_neighbors(selected_key, limit=limit) if selected_key else []
        if stats is None:
            with sqlite3.connect(self.graph.db_path) as connection:
                stats = {
                    "nodes": connection.execute("SELECT COUNT(*) FROM graph_nodes").fetchone()[0],
                    "edges": connection.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0],
                }
        return {
            "issue_key": selected_key,
            "neighbors": neighbors,
            "stats": stats,
            "graph_db": self.graph.db_path,
            "cache_db": self.cache.db_path,
            "issue_count": self.cache.issue_count(),
        }

    def domain_analysis(
        self, *, limit_terms: int = 20, min_count: int = 2,
        query: str = "", limit_hits: int = 8,
    ) -> dict[str, Any]:
        terms = self.cache.extract_domain_terms(limit=limit_terms, min_count=min_count)
        backend, model = field_embedding_backend(self.cache, self.assistant)
        embedded_fields = self.cache.build_field_embeddings(backend, embedding_model=model)
        normalized_query = (query or "").strip()
        hits = []
        if normalized_query:
            hits = self.cache.semantic_field_search(
                query=normalized_query, backend=backend, embedding_model=model, limit=limit_hits,
            )
        return {
            "terms": terms,
            "hits": hits,
            "query": normalized_query,
            "limit_terms": limit_terms,
            "min_count": min_count,
            "limit_hits": limit_hits,
            "embedding_model": model,
            "embedded_fields": embedded_fields,
            "cache_db": self.cache.db_path,
            "issue_count": self.cache.issue_count(),
        }
