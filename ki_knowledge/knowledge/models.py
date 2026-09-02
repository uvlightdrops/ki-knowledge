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
