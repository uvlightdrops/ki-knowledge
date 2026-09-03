"""Phase B: Store InfoSite Knowledge Blocks in knowledge_store.py"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from django.utils import timezone

from ki_knowledge.django_site.infosite_models import InfoSiteProject, SourceDocument
from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.knowledge.models import KnowledgeBlockRecord, KnowledgeSource
from ki_knowledge.services.block_extractor import KnowledgeBlockData, InfoSiteBlockExtractor
from ki_knowledge.services.data_source_service import CanonicalDataSourceService


class InfoSiteBlockStorage:
    """Stores extracted InfoSite blocks into knowledge_store.py with domain tagging."""

    def __init__(self, project: InfoSiteProject, knowledge_store: Optional[KnowledgeStore] = None):
        self.project = project
        self.extractor = InfoSiteBlockExtractor(project)
        
        # Initialize knowledge store (default to ki-knowledge database)
        if knowledge_store is None:
            db_path = Path.home() / ".ki-knowledge" / "knowledge.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self.store = KnowledgeStore(str(db_path))
        else:
            self.store = knowledge_store

    def get_source_id(self) -> str:
        """Generate a canonical source_id for this project."""
        descriptor = CanonicalDataSourceService.from_infosite_project(self.project)
        return descriptor.source_id

    def create_knowledge_source(self) -> KnowledgeSource:
        """Create KnowledgeSource entry for this InfoSite project."""
        location = self.project.output_dir or self.project.source_directory or ""
        return KnowledgeSource(
            source_id=self.get_source_id(),
            source_type="infosite",
            title=self.project.title,
            location=location,
            metadata={
                "project_id": self.project.id,
                "domain": self.project.domain,
                "working_title": self.project.working_title,
                "version_count": self.project.version_count,
                "created_at": self.project.created_at.isoformat() if self.project.created_at else None,
            },
        )

    def block_data_to_record(
        self, block: KnowledgeBlockData, file_path: str, source_id: str, blocks: list[KnowledgeBlockData]
    ) -> KnowledgeBlockRecord:
        """Convert InfoSiteBlockData to KnowledgeBlockRecord for storage."""
        parent_block_id = (
            blocks[block.parent_index].block_id
            if block.parent_index is not None and 0 <= block.parent_index < len(blocks)
            else None
        )
        return KnowledgeBlockRecord(
            block_id=block.block_id,
            source_id=source_id,
            block_type=block.block_type,
            title=block.title,
            content=block.content,
            parent_block_id=parent_block_id,
            path=file_path,
            order_index=block.order_index,
            tags=[
                self.project.domain or "general",
                f"level-{block.level}",
                block.block_type,
            ],
            metadata={
                "file_path": file_path,
                "level": block.level,
                "parent_index": block.parent_index,
                "extracted_at": datetime.now().isoformat(),
            },
        )

    def extract_and_store(self) -> dict:
        """Extract all blocks from project and store in knowledge_store."""
        results = {
            "project_id": self.project.id,
            "source_id": self.get_source_id(),
            "files_processed": 0,
            "blocks_stored": 0,
            "errors": [],
        }

        # Create knowledge source
        source = self.create_knowledge_source()
        self.store.upsert_source(source)

        # Extract blocks by file
        blocks_by_file = self.extractor.extract_from_directory()

        # Store each block
        for file_path, blocks in blocks_by_file.items():
            results["files_processed"] += 1
            for block in blocks:
                try:
                    record = self.block_data_to_record(block, file_path, source.source_id, blocks)
                    self.store.upsert_record(record)
                    results["blocks_stored"] += 1
                except Exception as e:
                    results["errors"].append(
                        {
                            "file": file_path,
                            "block_id": block.block_id,
                            "error": str(e),
                        }
                    )

        return results

    def update_document_status(self) -> None:
        """Record that blocks were extracted for this project's imported documents.

        SourceDocument has no free-form metadata column, so extraction status is
        tracked on the KnowledgeExtractionJob record (job history) rather than by
        mutating each document row. This method just bumps `updated_at` on the
        affected documents so their sync timestamp reflects the extraction pass.
        """
        SourceDocument.objects.filter(
            project=self.project,
            import_status="imported",
        ).update(updated_at=timezone.now())

    def get_stored_blocks(self) -> list[KnowledgeBlockRecord]:
        """Retrieve all stored blocks for this project from knowledge_store."""
        source_id = self.get_source_id()
        return self.store.list_records(source_id=source_id)

    def get_statistics(self) -> dict:
        """Get statistics about stored blocks."""
        blocks_by_file = self.extractor.extract_from_directory()
        stats = self.extractor.get_statistics()

        # Count by type
        type_counts = {}
        for blocks in blocks_by_file.values():
            for block in blocks:
                block_type = block.block_type
                type_counts[block_type] = type_counts.get(block_type, 0) + 1

        return {
            "total_files": stats.get("total_files", 0),
            "total_blocks": stats.get("total_blocks", 0),
            "sections": type_counts.get("section", 0),
            "subsections": type_counts.get("subsection", 0),
            "subsubsections": type_counts.get("subsubsection", 0),
            "paragraphs": type_counts.get("paragraph", 0),
            "type_counts": type_counts,
        }
