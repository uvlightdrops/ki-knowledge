"""Canonical data source abstraction for content ingestion and publishing.

This layer is intentionally source-agnostic: markdown files, PDFs, CMS content,
Notion pages, and other content stores all describe themselves through the same
canonical record types.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

from ki_knowledge.knowledge.adapters import InfoSiteSourceAdapter
from ki_knowledge.knowledge.models import DataSourceDescriptor, SourceDocumentRecord


class CanonicalDataSourceService:
    """Normalize project-specific documents into canonical source descriptors."""

    @staticmethod
    def make_source_id(source_type: str, title: str, uri: str) -> str:
        return InfoSiteSourceAdapter.make_source_id(source_type, title, uri)

    @staticmethod
    def from_infosite_project(project: Any, source_directory: str | None = None) -> DataSourceDescriptor:
        """Map an existing InfoSiteProject into the canonical source model."""
        return InfoSiteSourceAdapter.to_descriptor(project, source_directory=source_directory)

    @staticmethod
    def from_document(document: Any, project: Any | None = None) -> SourceDocumentRecord:
        """Map a SourceDocument-like object into the canonical document model."""
        source = project or getattr(document, "project", None)
        if source is not None:
            return InfoSiteSourceAdapter.to_document(source, document)

        file_path = getattr(document, "file_path", "") or ""
        title = getattr(document, "title", "") or Path(file_path).name
        uri = file_path
        document_type = getattr(document, "file_type", "other") or "other"
        return SourceDocumentRecord(
            document_id=CanonicalDataSourceService.make_source_id(document_type, title, uri),
            source_id="unknown-source",
            document_type=document_type,
            title=title,
            uri=uri,
            version="v1",
            status=getattr(document, "import_status", "discovered") or "discovered",
            checksum=getattr(document, "checksum", None),
            metadata={
                "file_size": getattr(document, "file_size", None),
                "modified_at": getattr(document, "modified_at", None),
                "imported": getattr(document, "imported", False),
            },
        )

    @staticmethod
    def describe_documents(documents: Iterable[Any], project: Any | None = None) -> list[SourceDocumentRecord]:
        """Convenience method for normalizing a list of document-like objects."""
        return [CanonicalDataSourceService.from_document(doc, project=project) for doc in documents]
