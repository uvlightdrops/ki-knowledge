from __future__ import annotations

import os
from pathlib import Path

from ki_core.config import Config


def config() -> Config:
    return Config.from_env()


def knowledge_data_root(cfg: Config | None = None) -> Path:
    resolved = cfg or config()
    if resolved.knowledge_data_root:
        return Path(resolved.knowledge_data_root).expanduser()

    legacy_root = os.getenv("KICLI_DATA_ROOT", "").strip()
    if legacy_root:
        return Path(legacy_root).expanduser()

    return Path.home() / "dev_data" / "ki-knowledge"


def knowledge_markdown_root(cfg: Config | None = None) -> Path:
    override = os.getenv("KNOWLEDGE_MARKDOWN_ROOT", "").strip()
    if override:
        return Path(override).expanduser()

    legacy = os.getenv("KICLI_MD_ROOT", "").strip()
    if legacy:
        return Path(legacy).expanduser()

    return knowledge_data_root(cfg) / "md"


def knowledge_jira_root(cfg: Config | None = None) -> Path:
    override = os.getenv("KNOWLEDGE_JIRA_ROOT", "").strip()
    if override:
        return Path(override).expanduser()

    legacy = os.getenv("KICLI_JIRA_ROOT", "").strip()
    if legacy:
        return Path(legacy).expanduser()

    return knowledge_data_root(cfg) / "jira"


def knowledge_ontology_root(cfg: Config | None = None) -> Path:
    override = os.getenv("KNOWLEDGE_ONTOLOGY_ROOT", "").strip()
    if override:
        return Path(override).expanduser()

    legacy = os.getenv("KICLI_OWL_ROOT", "").strip()
    if legacy:
        return Path(legacy).expanduser()

    return knowledge_data_root(cfg) / "owl"


def knowledge_pdf_root(cfg: Config | None = None) -> Path:
    override = os.getenv("KNOWLEDGE_PDF_ROOT", "").strip()
    if override:
        return Path(override).expanduser()

    legacy = os.getenv("KICLI_PDF_ROOT", "").strip()
    if legacy:
        return Path(legacy).expanduser()

    return knowledge_data_root(cfg) / "pdf"


def knowledge_api_url() -> str:
    return os.getenv("KNOWLEDGE_API_URL", "http://localhost:8090/api/knowledge").rstrip("/")


def knowledge_db_path(cfg: Config | None = None) -> Path:
    override = os.getenv("KNOWLEDGE_DB_PATH", "").strip()
    if override:
        return Path(override).expanduser()
    return knowledge_data_root(cfg) / "knowledge.db"


def jira_csv_path(cfg: Config | None = None, domain: str = "default") -> Path:
    override = os.getenv("JIRA_CSV_PATH", "").strip()
    if override:
        return Path(override).expanduser()
    return knowledge_jira_root(cfg) / domain / "issues.csv"


def jira_cache_db_path(cfg: Config | None = None) -> Path:
    resolved = cfg or config()
    override = os.getenv("JIRA_CACHE_DB", "").strip() or os.getenv("KNOWLEDGE_CACHE_DB", "").strip()
    if override:
        return Path(override).expanduser()
    if resolved.knowledge_cache_db:
        return Path(resolved.knowledge_cache_db).expanduser()
    return knowledge_data_root(resolved) / ".jira_cache.sqlite"


def jira_graph_db_path(cfg: Config | None = None) -> Path:
    resolved = cfg or config()
    override = os.getenv("JIRA_GRAPH_DB", "").strip() or os.getenv("KNOWLEDGE_GRAPH_DB", "").strip()
    if override:
        return Path(override).expanduser()
    if resolved.knowledge_graph_db:
        return Path(resolved.knowledge_graph_db).expanduser()
    return knowledge_data_root(resolved) / ".jira_graph.sqlite"
