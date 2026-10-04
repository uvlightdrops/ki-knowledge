from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from django.core.cache import cache as django_cache

from ki_knowledge.app_config import AppConfig as Config
from ki_knowledge.data_layout import DOMAIN_STATE_FILES, JIRA, MARKDOWN, MIX, ONTOLOGY, PDF, DataLayout

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


def data_layout() -> DataLayout:
    """The configured on-disk layout. All data paths must be derived from it."""
    return DataLayout.from_config(Config.from_env())


def data_root() -> Path:
    return data_layout().root


def _match_domain_name(names: list[str], normalized_domain: str) -> str:
    """Existing directory name for a normalized domain (e.g. ``Anthro`` for ``anthro``)."""
    for name in names:
        if normalize_semantic_domain(name) == normalized_domain:
            return name
    return normalized_domain


def domain_dir_name(normalized_domain: str, source_type: str | None = None) -> str:
    """On-disk directory name of a domain, preferring an existing folder."""
    layout = data_layout()
    names = layout.source_domain_names(source_type) if source_type else layout.domain_names()
    return _match_domain_name(names, normalized_domain)


def _resolve_domain_file(domain_dir: Path, preferred: str, legacy: str) -> Path:
    preferred_path = domain_dir / preferred
    legacy_path = domain_dir / legacy
    if legacy_path.exists() and not preferred_path.exists():
        preferred_path.parent.mkdir(parents=True, exist_ok=True)
        legacy_path.rename(preferred_path)
    return preferred_path


def domain_state_paths(resolved_domain: str) -> dict[str, Path]:
    """Paths of a domain's derived DBs; ``resolved_domain`` must already be normalized."""
    layout = data_layout()
    domain_dir = layout.domain_state_dir(_match_domain_name(layout.state_domain_names(), resolved_domain))
    paths = {"domain": domain_dir}
    for key, (preferred, legacy) in DOMAIN_STATE_FILES.items():
        paths[key] = _resolve_domain_file(domain_dir, preferred, legacy)
    return paths


def infer_domain_from_path(path: Path | str | None) -> str | None:
    """Normalized domain of a source file or directory, or ``None`` if outside the source tree."""
    raw = str(path or "").strip()
    if not raw:
        return None
    location = data_layout().locate_source(raw)
    return normalize_semantic_domain(location.domain_dir_name) if location else None


def domain_source_dir(source_type: str, domain: str | None = None) -> Path:
    """Source directory of a type for a domain (existing folder name preferred)."""
    resolved = normalize_semantic_domain(domain or default_semantic_domain())
    return data_layout().source_dir(source_type, domain_dir_name(resolved, source_type))


def domain_markdown_dir(domain: str | None = None) -> Path:
    return domain_source_dir(MARKDOWN, domain)


def domain_jira_dir(domain: str | None = None) -> Path:
    return domain_source_dir(JIRA, domain)


def domain_ontology_dir(domain: str | None = None) -> Path:
    return domain_source_dir(ONTOLOGY, domain)


def domain_pdf_dir(domain: str | None = None) -> Path:
    pdf_dir = domain_source_dir(PDF, domain)
    if not pdf_dir.exists():
        pdf_dir.mkdir(parents=True, exist_ok=True)
    return pdf_dir


def domain_mix_dir(domain: str | None = None) -> Path:
    """Folder for mixed formats (PDF, tables, images, ...); usually a symlink."""
    return domain_source_dir(MIX, domain)


def domain_source_roots(domain: str | None = None) -> list[Path]:
    """All source folders of a domain (as configured and symlink-resolved) for scoping queries."""
    roots: list[Path] = []
    for directory in (
        domain_markdown_dir(domain),
        domain_jira_dir(domain),
        domain_ontology_dir(domain),
        domain_source_dir(PDF, domain),
        domain_mix_dir(domain),
    ):
        for candidate in (directory.expanduser(), directory.expanduser().resolve()):
            if candidate not in roots:
                roots.append(candidate)
    return roots


def domain_label(normalized_domain: str) -> str:
    """Display label of a domain: its existing directory name, if any."""
    return domain_dir_name(normalized_domain)


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
    "data_layout",
    "data_root",
    "_match_domain_name",
    "domain_dir_name",
    "domain_label",
    "domain_source_dir",
    "_resolve_domain_file",
    "domain_state_paths",
    "infer_domain_from_path",
    "domain_markdown_dir",
    "domain_jira_dir",
    "domain_ontology_dir",
    "domain_pdf_dir",
    "domain_mix_dir",
    "domain_source_roots",
    "invalidate_domain_summary_cache",
]
