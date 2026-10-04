from __future__ import annotations

import os
from pathlib import Path

from ki_knowledge.app_config import AppConfig as Config
from ki_knowledge.data_layout import JIRA, DataLayout


def config() -> Config:
    return Config.from_env()


def knowledge_data_root(cfg: Config | None = None) -> Path:
    resolved = cfg or config()
    if resolved.knowledge_data_root:
        return Path(resolved.knowledge_data_root).expanduser()

    env_root = os.getenv("KNOWLEDGE_DATA_ROOT", "").strip()
    if env_root:
        return Path(env_root).expanduser()

    legacy_root = os.getenv("KICLI_DATA_ROOT", "").strip()
    if legacy_root:
        return Path(legacy_root).expanduser()

    return Path.home() / "dev_data" / "ki-knowledge"


def knowledge_api_url() -> str:
    return os.getenv("KNOWLEDGE_API_URL", "http://localhost:8090/api/knowledge").rstrip("/")


def knowledge_db_path(cfg: Config | None = None) -> Path:
    override = os.getenv("KNOWLEDGE_DB_PATH", "").strip()
    if override:
        return Path(override).expanduser()
    return DataLayout.from_config(cfg).knowledge_db_path()


def jira_csv_path(cfg: Config | None = None, domain: str = "default") -> Path:
    override = os.getenv("JIRA_CSV_PATH", "").strip()
    if override:
        return Path(override).expanduser()
    return DataLayout.from_config(cfg).source_dir(JIRA, domain, "issues.csv")


def jira_cache_db_path(cfg: Config | None = None) -> Path:
    resolved = cfg or config()
    override = os.getenv("JIRA_CACHE_DB", "").strip() or os.getenv("KNOWLEDGE_CACHE_DB", "").strip()
    if override:
        return Path(override).expanduser()
    if resolved.knowledge_cache_db:
        return Path(resolved.knowledge_cache_db).expanduser()
    return DataLayout.from_config(resolved).global_jira_cache_db_path()


def jira_graph_db_path(cfg: Config | None = None) -> Path:
    resolved = cfg or config()
    override = os.getenv("JIRA_GRAPH_DB", "").strip() or os.getenv("KNOWLEDGE_GRAPH_DB", "").strip()
    if override:
        return Path(override).expanduser()
    if resolved.knowledge_graph_db:
        return Path(resolved.knowledge_graph_db).expanduser()
    return DataLayout.from_config(resolved).global_jira_graph_db_path()
