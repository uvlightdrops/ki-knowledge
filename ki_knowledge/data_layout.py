"""Single source of truth for where ki-knowledge keeps its files on disk.

Every path below the data root must be derived from :class:`DataLayout`, so the
on-disk structure can be changed in one place. Nothing else should build paths
such as ``data_root / "md" / domain``.

The layout version is stored in ``<root>/.layout-version``; a root without
that file uses v1. ``python manage.py migrate_data_layout`` converts v1 to v2.

v2 (domain first)::

    <root>/
      .layout-version                    "2"
      domains/<domain>/
        sources/md/<working_title>/...   Markdown sources (may be a symlink)
        sources/pdf/...                  PDF sources
        sources/jira/                    Jira CSVs
        sources/owl/...                  ontology sources
        sources/mix/...                  mixed formats (PDF, tables, images, ...)
        derived/                         cache.sqlite, graph.sqlite, graph.cypher
        output/<working_title>/          generated output
      system/
        knowledge.db                     knowledge store
        django.sqlite3                   Django/Wagtail DB
        pdf_import_jobs.sqlite           PDF batch job queue
        jira_cache.sqlite                legacy global Jira cache
        jira_graph.sqlite                legacy global Jira graph
        pipeline_jobs.db                 import/extraction job queue
        block_store.db                   store of InfoSiteBlockStorage
      archive/                           unexpected files found by the migration

v1 (source type first, legacy)::

    <root>/
      md/<domain>/<working_title>/...    Markdown sources
      pdf/<domain>/...                   PDF sources
      jira/<domain>/                     Jira CSVs and per-domain derived DBs
      owl/<domain>/...                   ontology sources
      data_out/<domain>/<working_title>/ generated output
      knowledge.db, django.sqlite3, .pdf_import_jobs.sqlite,
      .jira_cache.sqlite, .jira_graph.sqlite
    ~/.ki-knowledge/pipeline_jobs.db, ~/.ki-knowledge/knowledge.db

``KNOWLEDGE_*_ROOT`` env overrides keep the ``<override>/<domain>/`` form in
both versions.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from ki_knowledge.app_config import AppConfig

LAYOUT_VERSION = 2
"""Newest layout version; roots without a version file are treated as v1."""
LAYOUT_VERSION_FILE = ".layout-version"
SUPPORTED_LAYOUT_VERSIONS = (1, 2)

MARKDOWN = "markdown"
PDF = "pdf"
JIRA = "jira"
ONTOLOGY = "owl"
MIX = "mix"
SOURCE_TYPES: tuple[str, ...] = (MARKDOWN, JIRA, ONTOLOGY, PDF, MIX)

_SOURCE_TYPE_ALIASES = {
    "markdown": MARKDOWN,
    "md": MARKDOWN,
    "pdf": PDF,
    "jira": JIRA,
    "owl": ONTOLOGY,
    "ontology": ONTOLOGY,
    "mix": MIX,
    "mixed": MIX,
}
_SOURCE_TYPE_DIRS = {MARKDOWN: "md", PDF: "pdf", JIRA: "jira", ONTOLOGY: "owl", MIX: "mix"}
_SOURCE_TYPE_ENV_OVERRIDES = {
    MARKDOWN: ("KNOWLEDGE_MARKDOWN_ROOT", "KICLI_MD_ROOT"),
    JIRA: ("KNOWLEDGE_JIRA_ROOT", "KICLI_JIRA_ROOT"),
    ONTOLOGY: ("KNOWLEDGE_ONTOLOGY_ROOT", "KICLI_OWL_ROOT"),
    PDF: ("KNOWLEDGE_PDF_ROOT", "KICLI_PDF_ROOT"),
    MIX: ("KNOWLEDGE_MIX_ROOT",),
}
_V1_OUTPUT_DIR = "data_out"
_DOMAINS_DIR = "domains"
_SYSTEM_DIR = "system"
_ARCHIVE_DIR = "archive"
_SOURCES_DIR = "sources"
_DERIVED_DIR = "derived"
_DOMAIN_OUTPUT_DIR = "output"

# Global state files as (v1 path relative to the root, v2 name inside system/).
_GLOBAL_FILES: dict[str, tuple[str, str]] = {
    "knowledge_db": ("knowledge.db", "knowledge.db"),
    "django_db": ("django.sqlite3", "django.sqlite3"),
    "pdf_jobs_db": (".pdf_import_jobs.sqlite", "pdf_import_jobs.sqlite"),
    "jira_cache_db": (".jira_cache.sqlite", "jira_cache.sqlite"),
    "jira_graph_db": (".jira_graph.sqlite", "jira_graph.sqlite"),
}
# v1 files in ~/.ki-knowledge as (v1 name, v2 name inside system/).
_HOME_STATE_FILES: dict[str, tuple[str, str]] = {
    "pipeline_jobs_db": ("pipeline_jobs.db", "pipeline_jobs.db"),
    "block_store_db": ("knowledge.db", "block_store.db"),
}


class LayoutError(RuntimeError):
    """The requested path does not exist in this layout version."""


def read_layout_version(root: str | Path) -> int:
    """Layout version of a data root (1 when no version file exists)."""
    marker = Path(root).expanduser() / LAYOUT_VERSION_FILE
    try:
        raw = marker.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return 1
    try:
        version = int(raw)
    except ValueError:
        raise LayoutError(f"invalid layout version in {marker}: {raw!r}") from None
    if version not in SUPPORTED_LAYOUT_VERSIONS:
        raise LayoutError(f"unsupported layout version {version} in {marker}")
    return version


def source_type_dir_name(source_type: str) -> str:
    """Directory name of a source type (``md``, ``pdf``, ``jira``, ``owl``)."""
    return _SOURCE_TYPE_DIRS[canonical_source_type(source_type)]

# Derived per-domain state files as (current name, legacy name).
DOMAIN_STATE_FILES: dict[str, tuple[str, str]] = {
    "cache_db": ("cache.sqlite", "jira_cache.sqlite"),
    "graph_db": ("graph.sqlite", "jira_graph.sqlite"),
    "cypher_path": ("graph.cypher", "jira_graph.cypher"),
}


def canonical_source_type(value: str) -> str:
    """Map a source type or alias (``md``, ``ontology``, ...) to its canonical key."""
    key = (value or "").strip().lower()
    try:
        return _SOURCE_TYPE_ALIASES[key]
    except KeyError:
        raise ValueError(f"unknown source type: {value!r}") from None


def source_type_env_override(source_type: str) -> Path | None:
    """Return the env-configured root for a source type, if one is set."""
    for name in _SOURCE_TYPE_ENV_OVERRIDES[canonical_source_type(source_type)]:
        raw = os.getenv(name, "").strip()
        if raw:
            return Path(raw).expanduser()
    return None


class SourceLocation(NamedTuple):
    """Where a file sits inside the source tree."""

    source_type: str
    domain_dir_name: str
    relative_path: Path


def _safe_resolve(path: Path) -> Path:
    try:
        return path.resolve()
    except (OSError, RuntimeError):
        return path


def _relative_parts(path: Path, base: Path) -> tuple[str, ...] | None:
    try:
        return path.relative_to(base).parts
    except ValueError:
        return None


def _symlinked_children(base: Path) -> list[Path]:
    try:
        return [child for child in base.iterdir() if child.is_symlink() and child.is_dir()]
    except OSError:
        return []


def _child_dir_names(base: Path) -> list[str]:
    try:
        return sorted(child.name for child in base.iterdir() if child.is_dir())
    except OSError:
        return []


def _relative_to_tree(candidate: Path, resolved: Path, base: Path) -> Path | None:
    """``candidate`` relative to ``base``, following a symlinked base or symlinked children."""
    relative = _relative_parts(candidate, base)
    if relative is None:
        relative = _relative_parts(resolved, _safe_resolve(base))
    if relative is not None:
        return Path(*relative)
    for child in _symlinked_children(base):
        inner = _relative_parts(resolved, _safe_resolve(child))
        if inner is not None:
            return Path(child.name, *inner)
    return None


@dataclass(frozen=True, eq=False)
class DataLayout:
    """Resolve every data path from one root.

    ``version`` defaults to the version stored in the root (see
    :func:`read_layout_version`). ``type_root_overrides`` lets single source
    types live outside the root (see the ``KNOWLEDGE_*_ROOT`` env variables);
    :meth:`from_config` fills it.
    """

    root: Path
    type_root_overrides: dict[str, Path] = field(default_factory=dict)
    version: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root).expanduser())
        object.__setattr__(
            self,
            "type_root_overrides",
            {canonical_source_type(key): Path(value).expanduser() for key, value in self.type_root_overrides.items()},
        )
        version = read_layout_version(self.root) if self.version is None else int(self.version)
        if version not in SUPPORTED_LAYOUT_VERSIONS:
            raise LayoutError(f"unsupported layout version {version}")
        object.__setattr__(self, "version", version)

    @classmethod
    def from_config(cls, cfg: AppConfig | None = None) -> DataLayout:
        """Build the layout for the configured data root, honouring env overrides."""
        from ki_knowledge.config_runtime import knowledge_data_root

        overrides = {}
        for source_type in SOURCE_TYPES:
            override = source_type_env_override(source_type)
            if override is not None:
                overrides[source_type] = override
        return cls(knowledge_data_root(cfg), overrides)

    @property
    def is_domain_first(self) -> bool:
        return self.version >= 2

    def version_file(self) -> Path:
        return self.root / LAYOUT_VERSION_FILE

    # --- domains ---------------------------------------------------------------

    def domains_root(self) -> Path:
        """``<root>/domains`` (v2 only)."""
        self._require_domain_first("domains_root")
        return self.root / _DOMAINS_DIR

    def domain_root(self, domain: str) -> Path:
        """``<root>/domains/<domain>`` (v2 only)."""
        return self.domains_root() / domain

    def domain_names(self) -> list[str]:
        """Directory names of every domain that has sources or derived state."""
        names: set[str] = set(self.state_domain_names())
        for source_type in SOURCE_TYPES:
            names.update(self.source_domain_names(source_type))
        return sorted(names)

    # --- sources -------------------------------------------------------------

    def _source_base(self, source_type: str) -> Path | None:
        """Parent of ``<domain>/`` dirs for a type, or ``None`` if sources live per domain."""
        canonical = canonical_source_type(source_type)
        override = self.type_root_overrides.get(canonical)
        if override is not None:
            return override
        if self.is_domain_first:
            return None
        return self.root / _SOURCE_TYPE_DIRS[canonical]

    def source_type_root(self, source_type: str) -> Path:
        """Common parent of all domains' sources of one type.

        Only exists in v1 or for overridden types; v2 raises :class:`LayoutError`.
        """
        base = self._source_base(source_type)
        if base is None:
            raise LayoutError(f"layout v{self.version} has no common {source_type} root")
        return base

    def source_domain_names(self, source_type: str) -> list[str]:
        """Existing domain directory names that can hold sources of a type.

        In v2 every domain directory qualifies, so callers matching a domain
        name case-insensitively find the shared domain folder.
        """
        base = self._source_base(source_type)
        if base is None:
            return _child_dir_names(self.domains_root())
        return _child_dir_names(base)

    def source_dir(self, source_type: str, domain: str, *parts: str) -> Path:
        """Directory of one domain's sources of a type (+ optional sub path)."""
        base = self._source_base(source_type)
        if base is None:
            return self.domain_root(domain).joinpath(_SOURCES_DIR, source_type_dir_name(source_type), *parts)
        return base.joinpath(domain, *parts)

    def locate_source(self, path: str | Path) -> SourceLocation | None:
        """Tell which source type and domain directory ``path`` belongs to.

        Source directories may be symlinks (e.g. ``md/anthro`` or
        ``domains/anthro/sources/md`` -> cloud storage), so both the path as
        given and its resolved target are matched.
        """
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = candidate.absolute()
        resolved = _safe_resolve(candidate)

        for source_type in SOURCE_TYPES:
            base = self._source_base(source_type)
            if base is not None:
                relative = _relative_to_tree(candidate, resolved, base)
                if relative is not None and relative.parts:
                    return SourceLocation(source_type, relative.parts[0], Path(*relative.parts[1:]))
                continue
            for domain in self.source_domain_names(source_type):
                relative = _relative_to_tree(candidate, resolved, self.source_dir(source_type, domain))
                if relative is not None:
                    return SourceLocation(source_type, domain, relative)
        return None

    # --- derived per-domain state ---------------------------------------------

    def state_domain_names(self) -> list[str]:
        """Existing domain directory names that can hold derived state."""
        if self.is_domain_first:
            return _child_dir_names(self.domains_root())
        return _child_dir_names(self.source_type_root(JIRA))

    def domain_state_dir(self, domain: str) -> Path:
        """Directory of a domain's derived DBs (cache, graph).

        v1 keeps them next to the Jira CSVs in ``jira/<domain>/``.
        """
        if self.is_domain_first:
            return self.domain_root(domain) / _DERIVED_DIR
        return self.source_type_root(JIRA) / domain

    # --- generated output ------------------------------------------------------

    def output_dir(self, domain: str, *parts: str) -> Path:
        if self.is_domain_first:
            return self.domain_root(domain).joinpath(_DOMAIN_OUTPUT_DIR, *parts)
        return self.root.joinpath(_V1_OUTPUT_DIR, domain, *parts)

    def output_relative(self, path: str | Path) -> Path | None:
        """``<domain>/<rest>`` for a generated file, or ``None`` outside the output tree."""
        candidate = Path(path).expanduser()
        if self.is_domain_first:
            parts = _relative_parts(candidate, self.domains_root())
            if parts and len(parts) >= 2 and parts[1] == _DOMAIN_OUTPUT_DIR:
                return Path(parts[0], *parts[2:])
            return None
        parts = _relative_parts(candidate, self.root / _V1_OUTPUT_DIR)
        return Path(*parts) if parts else None

    # --- global state ------------------------------------------------------------

    def system_dir(self) -> Path:
        """``<root>/system`` (v2 only)."""
        self._require_domain_first("system_dir")
        return self.root / _SYSTEM_DIR

    def archive_dir(self) -> Path:
        return self.root / _ARCHIVE_DIR

    def _global_file(self, key: str) -> Path:
        v1_name, v2_name = _GLOBAL_FILES[key]
        if self.is_domain_first:
            return self.system_dir() / v2_name
        return self.root / v1_name

    def knowledge_db_path(self) -> Path:
        return self._global_file("knowledge_db")

    def django_db_path(self) -> Path:
        return self._global_file("django_db")

    def pdf_jobs_db_path(self) -> Path:
        return self._global_file("pdf_jobs_db")

    def global_jira_cache_db_path(self) -> Path:
        return self._global_file("jira_cache_db")

    def global_jira_graph_db_path(self) -> Path:
        return self._global_file("jira_graph_db")

    # --- pipeline state (v1: outside the data root) -----------------------------

    @staticmethod
    def home_state_dir() -> Path:
        """``~/.ki-knowledge``: where v1 keeps pipeline state outside the data root."""
        return Path.home() / ".ki-knowledge"

    def _home_state_file(self, key: str) -> Path:
        v1_name, v2_name = _HOME_STATE_FILES[key]
        if self.is_domain_first:
            return self.system_dir() / v2_name
        return self.home_state_dir() / v1_name

    def pipeline_jobs_db_path(self) -> Path:
        """Job DB shared by the import and knowledge-extraction runners."""
        return self._home_state_file("pipeline_jobs_db")

    def block_store_db_path(self) -> Path:
        """Default knowledge store of ``InfoSiteBlockStorage``.

        Note: this is a different file than :meth:`knowledge_db_path`.
        """
        return self._home_state_file("block_store_db")

    # --- display -------------------------------------------------------------------

    def display_relative(self, relative: Path) -> Path:
        """Shorten a root-relative path for the UI.

        Markdown sources are shown as ``<domain>/<working_title>/...``; other
        per-domain paths as ``<domain>/<kind>/...`` in v2.
        """
        parts = relative.parts
        if self.is_domain_first:
            if len(parts) < 2 or parts[0] != _DOMAINS_DIR:
                return relative
            domain, rest = parts[1], parts[2:]
            if len(rest) >= 2 and rest[0] == _SOURCES_DIR:
                if rest[1] == _SOURCE_TYPE_DIRS[MARKDOWN]:
                    return Path(domain, *rest[2:])
                return Path(domain, *rest[1:])
            return Path(domain, *rest)
        markdown_dir = _SOURCE_TYPE_DIRS[MARKDOWN]
        if parts and parts[0] == markdown_dir:
            return relative.relative_to(markdown_dir)
        return relative

    def _require_domain_first(self, what: str) -> None:
        if not self.is_domain_first:
            raise LayoutError(f"{what} requires layout v2 (root {self.root} is v{self.version})")


__all__ = [
    "DOMAIN_STATE_FILES",
    "JIRA",
    "LAYOUT_VERSION",
    "LAYOUT_VERSION_FILE",
    "LayoutError",
    "MARKDOWN",
    "MIX",
    "ONTOLOGY",
    "PDF",
    "SOURCE_TYPES",
    "DataLayout",
    "SourceLocation",
    "canonical_source_type",
    "read_layout_version",
    "source_type_dir_name",
    "source_type_env_override",
]
