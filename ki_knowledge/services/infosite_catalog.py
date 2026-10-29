"""Read the existing InfoSite block store without extracting or initializing it."""

from __future__ import annotations

from collections import Counter

from ki_knowledge.data_layout import DataLayout
from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.services.data_source_service import CanonicalDataSourceService


class InfoSiteBlockReader:
    def __init__(self, layout: DataLayout):
        self.path = layout.block_store_db_path()

    def read(self, project: object) -> dict:
        source_id = CanonicalDataSourceService.from_infosite_project(project).source_id
        store = KnowledgeStore(self.path, read_only=True)
        blocks = store.list_records(source_id=source_id)
        counts = Counter(block.block_type for block in blocks)
        files = {
            block.metadata["source_document"]
            for block in blocks if block.metadata.get("source_document")
        }
        return {
            "blocks": blocks,
            "stats": {
                "total_blocks": len(blocks),
                "total_files": len(files),
                "sections": counts["section"],
                "subsections": counts["subsection"],
                "subsubsections": counts["subsubsection"],
                "paragraphs": counts["paragraph"],
                "type_counts": dict(counts),
            },
        }
