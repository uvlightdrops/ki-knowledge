"""Hybrid search combining semantic and full-text."""
import logging
from dataclasses import dataclass
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

@dataclass
class SearchResult:
    """Search result with relevance scores."""
    doc_id: str
    title: str
    content: str
    semantic_score: float
    fulltext_score: float
    hybrid_score: float
    entity_type: Optional[str] = None

class HybridSearchEngine:
    """Combines semantic and full-text search."""
    
    def __init__(self, embedding_model=None, db_connection=None):
        """Initialize search engine."""
        self.embedding_model = embedding_model
        self.db = db_connection
        logger.info("HybridSearchEngine initialized")
    
    def semantic_search(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """Search using embeddings."""
        logger.debug(f"Semantic search: {query}")
        return []
    
    def fulltext_search(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """Full-text search using SQLite FTS."""
        logger.debug(f"Full-text search: {query}")
        return []
    
    def search(self, query: str, top_k: int = 10, 
              semantic_weight: float = 0.6) -> List[SearchResult]:
        """Hybrid search combining both methods."""
        logger.info(f"Hybrid search: {query}")
        
        semantic_results = self.semantic_search(query, top_k)
        fulltext_results = self.fulltext_search(query, top_k)
        
        combined = {}
        for r in semantic_results:
            combined[r.doc_id] = r
        
        for r in fulltext_results:
            if r.doc_id in combined:
                combined[r.doc_id].hybrid_score = (
                    semantic_weight * combined[r.doc_id].semantic_score +
                    (1 - semantic_weight) * r.fulltext_score
                )
        
        return sorted(combined.values(), 
                     key=lambda x: x.hybrid_score, reverse=True)[:top_k]
