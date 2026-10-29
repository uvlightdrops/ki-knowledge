"""Compatibility exports for filesystem paths and Django summary caching."""

from __future__ import annotations

from typing import Any

from django.core.cache import cache as django_cache

from ki_knowledge.services.domain_paths import (
    _LINKED_DIRS_CACHE,
    _LINKED_DIRS_MAX_DEPTH,
    _LINKED_DIRS_TTL,
    _match_domain_name,
    _resolve_domain_file,
    data_layout,
    data_root,
    default_semantic_domain,
    domain_dir_name,
    domain_jira_dir,
    domain_label,
    domain_markdown_dir,
    domain_mix_dir,
    domain_ontology_dir,
    domain_pdf_dir,
    domain_source_dir,
    domain_source_roots,
    domain_state_paths,
    infer_domain_from_path,
    linked_subdirectories,
    normalize_semantic_domain,
)

_DOMAIN_SUMMARY_CACHE_TTL = 60
_FALLBACK_CACHE: dict[str, Any] = {}


def _domain_summary_cache_key(domain: str | None = None) -> str:
    resolved = normalize_semantic_domain(domain or default_semantic_domain())
    return f"ki-knowledge:domain-summary:{resolved}"


def _domain_source_ids_cache_key(domain: str | None = None) -> str:
    resolved = normalize_semantic_domain(domain or default_semantic_domain())
    return f"ki-knowledge:domain-source-ids:{resolved}"


def _cached_get(key: str) -> Any:
    try:
        return django_cache.get(key)
    except Exception:
        return _FALLBACK_CACHE.get(key)


def _cached_set(key: str, value: Any, timeout: int = _DOMAIN_SUMMARY_CACHE_TTL) -> None:
    try:
        django_cache.set(key, value, timeout=timeout)
    except Exception:
        _FALLBACK_CACHE[key] = value


def _cached_delete(key: str) -> None:
    try:
        django_cache.delete(key)
    except Exception:
        _FALLBACK_CACHE.pop(key, None)


def invalidate_domain_summary_cache(domain: str | None = None) -> None:
    if domain:
        resolved = normalize_semantic_domain(domain)
        for key in (
            _domain_summary_cache_key(resolved),
            _domain_source_ids_cache_key(resolved),
        ):
            _cached_delete(key)
    else:
        for base in (default_semantic_domain(), "default"):
            for key in (
                _domain_summary_cache_key(base),
                _domain_source_ids_cache_key(base),
            ):
                _cached_delete(key)


__all__ = [
    "_DOMAIN_SUMMARY_CACHE_TTL", "_FALLBACK_CACHE",
    "_domain_summary_cache_key", "_domain_source_ids_cache_key",
    "_cached_get", "_cached_set", "_cached_delete",
    "default_semantic_domain", "normalize_semantic_domain", "data_layout",
    "data_root", "_match_domain_name", "domain_dir_name", "domain_label",
    "domain_source_dir", "_resolve_domain_file", "domain_state_paths",
    "infer_domain_from_path", "domain_markdown_dir", "domain_jira_dir",
    "domain_ontology_dir", "domain_pdf_dir", "domain_mix_dir",
    "domain_source_roots", "linked_subdirectories", "invalidate_domain_summary_cache",
]
