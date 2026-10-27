"""Multi-source knowledge ingestion pipeline."""
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

@dataclass
class KnowledgeBlockData:
    """Unified format for knowledge blocks."""
    id: str
    title: str
    content: str
    source_type: str
    metadata: Dict[str, Any]

class SourceAdapter(ABC):
    """Base class for source adapters (PDF, JIRA, CSV, Web, RDF)."""
    
    @abstractmethod
    def read(self, source_path: str) -> List[KnowledgeBlockData]:
        pass

class IngestionPipeline:
    """Main orchestrator for multi-source ingestion."""
    
    def __init__(self):
        self.adapters = {}
        logger.info("IngestionPipeline initialized")
    
    def register_adapter(self, source_type: str, adapter: SourceAdapter):
        """Register a source adapter."""
        self.adapters[source_type] = adapter
        logger.info(f"Registered adapter for {source_type}")
    
    def ingest(self, source_type: str, source_path: str) -> List[KnowledgeBlockData]:
        """Ingest from source and return knowledge blocks."""
        if source_type not in self.adapters:
            raise ValueError(f"Unknown source type: {source_type}")
        
        adapter = self.adapters[source_type]
        blocks = adapter.read(source_path)
        logger.info(f"Ingested {len(blocks)} blocks from {source_type}")
        return blocks
