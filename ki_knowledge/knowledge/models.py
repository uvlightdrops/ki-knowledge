"""Generic knowledge-core models shared across sources and apps."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class KnowledgeSource:
    """Describes the origin of imported knowledge."""

    source_id: str
    source_type: str
    title: str
    location: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DataSourceDescriptor:
    """Canonical descriptor for any external or internal source system.

    This is the abstraction layer underneath infosite markdown imports and future
    connectors such as Notion, Confluence, PDFs, Git repositories, or CMS content.
    """

    source_id: str
    source_type: str
    title: str
    uri: str
    provider: str
    status: str = "discovered"
    checksum: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceDocumentRecord:
    """Canonical document item that belongs to a data source.

    This separates the content source lifecycle from the specific infosite project
    model and makes it possible to handle markdown files, PDFs, and CMS content
    through the same abstraction.
    """

    document_id: str
    source_id: str
    document_type: str
    title: str
    uri: str
    version: str = "v1"
    status: str = "discovered"
    checksum: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeBlockRecord:
    """Generic, source-neutral knowledge block."""

    block_id: str
    source_id: str
    block_type: str
    title: str
    content: str
    parent_block_id: Optional[str] = None
    path: str = ""
    order_index: int = 0
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeRelationRecord:
    """Generic relation between two knowledge blocks or concepts."""

    source_block_id: str
    target_block_id: str
    relation: str
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeArtifact:
    """Reusable generated artifact derived from knowledge blocks."""

    artifact_id: str
    artifact_type: str
    source_id: str
    source_block_ids: list[str]
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
