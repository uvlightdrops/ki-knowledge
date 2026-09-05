"""App-specific configuration accessor for ki-knowledge.

ki-core no longer exposes a fat, cross-app config dataclass. This module
wraps ki_core.load_config() and exposes the resolved settings this app owns
as plain attributes, while keeping the full resolved config available via
`raw` for callers that need nested sections.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

try:
    from ki_core import ConfigDict, load_config
except ImportError:  # pragma: no cover - compatibility with stale editable installs
    sibling_core_src = Path(__file__).resolve().parents[2] / "ki-core" / "src"
    sibling_yaml_cfg_src = Path(__file__).resolve().parents[2] / "yaml_cfg_wizard" / "src"
    if str(sibling_core_src) not in sys.path:
        sys.path.insert(0, str(sibling_core_src))
    if str(sibling_yaml_cfg_src) not in sys.path:
        sys.path.insert(0, str(sibling_yaml_cfg_src))
    sys.modules.pop("ki_core", None)
    sys.modules.pop("ki_core.config", None)
    from ki_core import ConfigDict, load_config


@dataclass
class AppConfig:
    """Resolved ki-knowledge configuration."""

    # LLM providers (ki-core base schema: llm.providers.*)
    ki_base_url: str = ""
    ki_api_key: str = ""
    ki_model: str = "google/gemma-4-26B-A4B-it"
    ki_endpoint: Optional[str] = None

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    openai_api_key: str = ""
    openai_model: str = "gpt-4"
    openai_base_url: str = "https://api.openai.com/v1"

    # HTTP (ki-core base schema: http.*)
    request_timeout: int = 30
    http_verify_ssl: bool = True

    # Knowledge base (ki-knowledge schema: knowledge.*)
    knowledge_data_root: str = ""
    knowledge_cache_db: str = ""
    knowledge_graph_db: str = ""
    knowledge_embed_model: str = "nomic-embed-text"
    knowledge_default_domain: str = "default"
    knowledge_markdown_root: str = ""
    knowledge_jira_root: str = ""
    knowledge_ontology_root: str = ""
    knowledge_pdf_root: str = ""

    # Infosite (ki-knowledge schema: infosite.*)
    infosite_enabled: bool = False
    infosite_title: str = ""
    infosite_output_base_dir: str = ""
    infosite_domain: str = "default"

    # Jira integration (ki-knowledge schema: jira.*)
    jira_url: str = ""
    jira_username: str = ""
    jira_api_token: str = ""
    jira_csv_path: str = ""
    jira_cache_db: str = ""
    jira_graph_db: str = ""
    jira_graph_cypher_path: str = ""
    jira_csv_delimiter: str = ","
    jira_csv_encoding: str = "utf-8"
    jira_timeline_days: int = 90
    jira_embed_model: str = "nomic-embed-text"
    jira_use_hybrid_search: bool = True
    jira_use_graph: bool = False
    jira_cache_refresh: bool = False

    raw: ConfigDict = field(default_factory=ConfigDict)

    @classmethod
    def from_yaml(cls, path: Optional[Union[str, Path]] = None) -> "AppConfig":
        """Load and resolve config from YAML + environment variables."""
        payload = load_config(path)

        providers = payload.get_path("llm.providers", {}) or {}
        ki_cfg = providers.get("ki", {}) or {}
        ollama_cfg = providers.get("ollama", {}) or {}
        openai_cfg = providers.get("openai", {}) or {}

        knowledge_cfg = payload.get("knowledge", {}) or {}
        knowledge_paths = knowledge_cfg.get("paths", {}) or {}
        infosite_cfg = payload.get("infosite", {}) or {}
        jira_cfg = payload.get("jira", {}) or {}

        return cls(
            ki_base_url=ki_cfg.get("base_url", ""),
            ki_api_key=ki_cfg.get("api_key", ""),
            ki_model=ki_cfg.get("model", "google/gemma-4-26B-A4B-it"),
            ki_endpoint=ki_cfg.get("endpoint") or None,
            ollama_base_url=ollama_cfg.get("base_url", "http://localhost:11434"),
            ollama_model=ollama_cfg.get("model", "llama3.2"),
            openai_api_key=openai_cfg.get("api_key", ""),
            openai_model=openai_cfg.get("model", "gpt-4"),
            openai_base_url=openai_cfg.get("base_url", "https://api.openai.com/v1"),
            request_timeout=payload.get_path("http.request_timeout", 30),
            http_verify_ssl=payload.get_path("http.verify_ssl", True),
            knowledge_data_root=knowledge_cfg.get("data_root", ""),
            knowledge_cache_db=knowledge_cfg.get("cache_db", ""),
            knowledge_graph_db=knowledge_cfg.get("graph_db", ""),
            knowledge_embed_model=knowledge_cfg.get("embed_model", "nomic-embed-text"),
            knowledge_default_domain=knowledge_cfg.get("default_domain", "default"),
            knowledge_markdown_root=knowledge_paths.get("markdown_root", ""),
            knowledge_jira_root=knowledge_paths.get("jira_root", ""),
            knowledge_ontology_root=knowledge_paths.get("ontology_root", ""),
            knowledge_pdf_root=knowledge_paths.get("pdf_root", ""),
            infosite_enabled=infosite_cfg.get("enabled", False),
            infosite_title=infosite_cfg.get("title", ""),
            infosite_output_base_dir=infosite_cfg.get("output_base_dir", ""),
            infosite_domain=infosite_cfg.get("domain", "default"),
            jira_url=jira_cfg.get("url", ""),
            jira_username=jira_cfg.get("username", ""),
            jira_api_token=jira_cfg.get("api_token", ""),
            jira_csv_path=jira_cfg.get("csv_path", ""),
            jira_cache_db=jira_cfg.get("cache_db", ""),
            jira_graph_db=jira_cfg.get("graph_db", ""),
            jira_graph_cypher_path=jira_cfg.get("graph_cypher_path", ""),
            jira_csv_delimiter=jira_cfg.get("csv_delimiter", ","),
            jira_csv_encoding=jira_cfg.get("csv_encoding", "utf-8"),
            jira_timeline_days=jira_cfg.get("timeline_days", 90),
            jira_embed_model=jira_cfg.get("embed_model", "nomic-embed-text"),
            jira_use_hybrid_search=jira_cfg.get("use_hybrid_search", True),
            jira_use_graph=jira_cfg.get("use_graph", False),
            jira_cache_refresh=jira_cfg.get("cache_refresh", False),
            raw=payload,
        )

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Load config from environment variables (KI_CFG_* prefix) plus any discovered YAML."""
        return cls.from_yaml(None)

    def validate(self) -> None:
        """Legacy compatibility shim for example scripts."""
        return None
