"""HTTP client helpers for the Streamlit knowledge UI."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin

import requests


def default_knowledge_api_url() -> str:
    """Return the configured knowledge API base URL."""
    return os.getenv("KNOWLEDGE_API_URL", "http://localhost:8090/api/knowledge").rstrip("/")


def default_markdown_directory() -> str:
    """Return the default data directory used for markdown discovery in the UI."""
    override = os.getenv("KNOWLEDGE_MARKDOWN_DIR", "").strip()
    if override:
        return str(Path(override).expanduser())
    
    default_root = Path.home() / "dev_data" / "ki-knowledge"
    if default_root.exists() and default_root.is_dir():
        return str(default_root)
    return str(default_root)


def discover_markdown_files(directory: str | Path) -> list[Path]:
    """Find all markdown files below a directory."""
    base = Path(directory).expanduser()
    if not base.exists() or not base.is_dir():
        return []
    return sorted(path for path in base.glob("**/*.md") if path.is_file())


def discover_ontology_files(directory: str | Path) -> list[Path]:
    """Find ontology files below a directory."""
    base = Path(directory).expanduser()
    if not base.exists() or not base.is_dir():
        return []
    suffixes = {".owl", ".rdf", ".ttl", ".n3", ".jsonld"}
    return sorted(path for path in base.glob("**/*") if path.is_file() and path.suffix.lower() in suffixes)


class KnowledgeAPIClient:
    """Thin requests-based client for the knowledge FastAPI service."""

    def __init__(self, base_url: str, timeout: int = 15):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def health(self) -> dict[str, Any]:
        return self._get_json("/health")

    def list_sources(self, source_type: Optional[str] = None) -> list[dict[str, Any]]:
        params = {"source_type": source_type} if source_type else None
        return self._get_json("/sources", params=params)

    def get_source(self, source_id: str) -> dict[str, Any]:
        return self._get_json(f"/sources/{source_id}")

    def get_source_graph(self, source_id: str, limit: int = 400) -> dict[str, Any]:
        return self._get_json(f"/sources/{source_id}/graph", params={"limit": limit})

    def search_blocks(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        return self._get_json("/search", params={"q": query, "limit": limit})

    def list_records(
        self,
        *,
        source_id: Optional[str] = None,
        block_type: Optional[str] = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if source_id:
            params["source_id"] = source_id
        if block_type:
            params["block_type"] = block_type
        return self._get_json("/records", params=params)

    def get_record(self, block_id: str) -> dict[str, Any]:
        return self._get_json(f"/records/{block_id}")

    def list_artifacts(
        self,
        *,
        source_id: Optional[str] = None,
        artifact_type: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if source_id:
            params["source_id"] = source_id
        if artifact_type:
            params["artifact_type"] = artifact_type
        return self._get_json("/artifacts", params=params or None)

    def generate_artifact(
        self,
        *,
        source_id: str,
        artifact_type: str,
        max_items: int,
    ) -> dict[str, Any]:
        return self._post_json(
            "/generate",
            {
                "source_id": source_id,
                "artifact_type": artifact_type,
                "max_items": max_items,
            },
        )

    def import_source(
        self,
        *,
        path: str,
        import_format: str = "markdown",
        source_name: Optional[str] = None,
        block_types: Optional[list[str]] = None,
        build_embeddings: bool = False,
        rebuild_graph: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "path": path,
            "import_format": import_format,
            "build_embeddings": build_embeddings,
            "rebuild_graph": rebuild_graph,
        }
        if source_name:
            payload["source_name"] = source_name
        if block_types:
            payload["block_types"] = block_types
        return self._post_json("/import", payload)

    def list_neighbors(self, block_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return self._get_json(f"/blocks/{block_id}/neighbors", params={"limit": limit})

    def add_relation(
        self,
        *,
        source_block_id: str,
        target_block_id: str,
        relation: str = "related_to",
        weight: float = 1.0,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source_block_id": source_block_id,
            "target_block_id": target_block_id,
            "relation": relation,
            "weight": weight,
            "metadata": metadata or {},
        }
        return self._post_json("/relations", payload)

    def artifact_payload(self, artifact: dict[str, Any]) -> dict[str, Any]:
        content = artifact.get("content", "")
        if not content:
            return {}
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"raw_content": content}

    def _get_json(self, path: str, params: Optional[dict[str, Any]] = None) -> Any:
        response = requests.get(self._url(path), params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _post_json(self, path: str, payload: dict[str, Any]) -> Any:
        response = requests.post(self._url(path), json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _url(self, path: str) -> str:
        return urljoin(f"{self.base_url}/", path.lstrip("/"))


def artifact_title(artifact: dict[str, Any]) -> str:
    """Return a short display title for an artifact."""
    artifact_type = artifact.get("artifact_type", "artifact")
    artifact_id = artifact.get("artifact_id", artifact_type)
    metadata = artifact.get("metadata") or {}
    count = metadata.get("question_count") or metadata.get("card_count") or metadata.get("section_count") or metadata.get("term_count") or metadata.get("item_count")
    if count:
        return f"{artifact_type} ({count}) — {artifact_id}"
    return f"{artifact_type} — {artifact_id}"


def short_text(value: str, limit: int = 120) -> str:
    """Shorten long text values for compact UI lists."""
    normalized = " ".join((value or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"
