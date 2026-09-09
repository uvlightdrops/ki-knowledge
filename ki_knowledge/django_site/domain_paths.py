from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from django.core.cache import cache as django_cache

from ki_knowledge.app_config import AppConfig as Config
from ki_knowledge.config_runtime import (
    knowledge_data_root,
    knowledge_jira_root,
    knowledge_markdown_root,
    knowledge_ontology_root,
    knowledge_pdf_root,
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


def default_semantic_domain() -> str:
    env_override = (os.getenv("KNOWLEDGE_DOMAIN", "") or os.getenv("KICLI_DOMAIN", "")).strip()
    if env_override:
        return normalize_semantic_domain(env_override)
    return "default"


def normalize_semantic_domain(value: str | None) -> str:
    raw = (value or "").strip().lower().replace("\\", "/")
    if not raw:
        return "default"
    normalized = re.sub(r"[^a-z0-9._-]+", "-", raw)
    normalized = normalized.strip("-._")
    return normalized or "default"


def data_root() -> Path:
    return knowledge_data_root(Config.from_env())


def markdown_type_root() -> Path:
    return knowledge_markdown_root(Config.from_env())


def jira_type_root() -> Path:
    return knowledge_jira_root(Config.from_env())


def ontology_type_root() -> Path:
    return knowledge_ontology_root(Config.from_env())


def pdf_type_root() -> Path:
    return knowledge_pdf_root(Config.from_env())


def _resolve_existing_domain_dir(base: Path, normalized_domain: str) -> Path:
    if base.exists() and base.is_dir():
        for child in base.iterdir():
            if child.is_dir() and normalize_semantic_domain(child.name) == normalized_domain:
                return child
    return base / normalized_domain


def _detect_domain_label(base: Path, normalized_domain: str) -> str:
    if base.exists() and base.is_dir():
        for child in base.iterdir():
            if child.is_dir() and normalize_semantic_domain(child.name) == normalized_domain:
                return child.name
    return normalized_domain


def _resolve_domain_file(domain_dir: Path, preferred: str, legacy: str) -> Path:
    preferred_path = domain_dir / preferred
    legacy_path = domain_dir / legacy
    if legacy_path.exists() and not preferred_path.exists():
        preferred_path.parent.mkdir(parents=True, exist_ok=True)
        legacy_path.rename(preferred_path)
    return preferred_path


def domain_markdown_dir(domain: str | None = None) -> Path:
    resolved = normalize_semantic_domain(domain or default_semantic_domain())
    return _resolve_existing_domain_dir(markdown_type_root(), resolved)


def domain_jira_dir(domain: str | None = None) -> Path:
    resolved = normalize_semantic_domain(domain or default_semantic_domain())
    return _resolve_existing_domain_dir(jira_type_root(), resolved)


def domain_ontology_dir(domain: str | None = None) -> Path:
    resolved = normalize_semantic_domain(domain or default_semantic_domain())
    return _resolve_existing_domain_dir(ontology_type_root(), resolved)


def domain_pdf_dir(domain: str | None = None) -> Path:
    resolved = normalize_semantic_domain(domain or default_semantic_domain())
    pdf_dir = _resolve_existing_domain_dir(pdf_type_root(), resolved)
    if not pdf_dir.exists():
        pdf_dir.mkdir(parents=True, exist_ok=True)
    return pdf_dir


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
    "_DOMAIN_SUMMARY_CACHE_TTL",
    "_FALLBACK_CACHE",
    "_domain_summary_cache_key",
    "_domain_source_ids_cache_key",
    "_cached_get",
    "_cached_set",
    "_cached_delete",
    "default_semantic_domain",
    "normalize_semantic_domain",
    "data_root",
    "markdown_type_root",
    "jira_type_root",
    "ontology_type_root",
    "pdf_type_root",
    "_resolve_existing_domain_dir",
    "_detect_domain_label",
    "_resolve_domain_file",
    "domain_markdown_dir",
    "domain_jira_dir",
    "domain_ontology_dir",
    "domain_pdf_dir",
    "invalidate_domain_summary_cache",
]
