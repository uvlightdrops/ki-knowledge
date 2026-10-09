"""Semantic block search of a domain on top of the stored Ollama embeddings."""

from __future__ import annotations

import os
from typing import Any

from django.conf import settings

from ki_knowledge.app_config import AppConfig as Config
from ki_knowledge.integrations.block_embedder import DEFAULT_EMBED_MODEL, model_key, query_text
from ki_knowledge.integrations.embeddings import OllamaEmbeddingProvider
from ki_knowledge.integrations.knowledge_store import KnowledgeStore

from .domain_paths import normalize_semantic_domain


def embedding_settings() -> tuple[str, str]:
    """Ollama base URL and embedding model (env ``KNOWLEDGE_EMBED_MODEL`` > ``knowledge.embed_model``)."""
    config = Config.from_env()
    base_url = (config.ollama_base_url or "http://localhost:11434").strip()
    model = (os.getenv("KNOWLEDGE_EMBED_MODEL") or config.knowledge_embed_model or DEFAULT_EMBED_MODEL).strip()
    return base_url, model_key(model)


def domain_source_ids(domain: str) -> list[str]:
    from .knowledge_summary import _domain_scoped_sources

    return [source.source_id for source in _domain_scoped_sources(normalize_semantic_domain(domain))]


def semantic_block_search(domain: str, query: str, *, limit: int = 20) -> dict[str, Any]:
    """Blocks of the domain most similar to ``query``; ``error`` is set when Ollama is unavailable."""
    base_url, model = embedding_settings()
    store = KnowledgeStore(settings.KNOWLEDGE_STORE_TARGET)
    source_ids = domain_source_ids(domain)
    counts = store.embedding_counts(source_ids, model)
    result: dict[str, Any] = {"model": model, "hits": [], "error": "", **counts}
    if not query.strip() or not counts["embedded"]:
        return result
    try:
        vector = OllamaEmbeddingProvider(base_url=base_url, model=model, timeout=60).embed_many(
            [query_text(query, model)]
        )[0]
    except Exception as exc:
        result["error"] = f"Ollama nicht erreichbar ({base_url}, {model}): {exc}"
        return result
    result["hits"] = store.similar_blocks(vector, model=model, source_ids=source_ids, limit=limit)
    return result
