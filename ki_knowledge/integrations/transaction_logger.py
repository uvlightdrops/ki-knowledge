"""Enhanced knowledge store with transaction logging and validation."""

import logging
import json
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@dataclass
class TransactionLog:
    """Log entry for knowledge store transactions."""
    operation: str
    timestamp: str
    entity_id: str
    status: str
    error: Optional[str] = None


class EnhancedKnowledgeStore:
    """Knowledge store with transaction logging and validation."""
    
    def __init__(self, db_path: Path):
        """Initialize with transaction logging."""
        self.db_path = db_path
        self.transaction_log = []
        logger.info(f"Initialized EnhancedKnowledgeStore at {db_path}")
    
    @contextmanager
    def transaction(self, operation: str, entity_id: str):
        """Context manager for transactional operations."""
        from datetime import datetime
        
        try:
            logger.info(f"Starting transaction: {operation} for {entity_id}")
            yield
            self.transaction_log.append(
                TransactionLog(operation, datetime.now().isoformat(), 
                             entity_id, "success")
            )
            logger.info(f"Transaction committed: {operation}")
        except Exception as e:
            logger.error(f"Transaction failed: {e}")
            self.transaction_log.append(
                TransactionLog(operation, datetime.now().isoformat(),
                             entity_id, "failed", str(e))
            )
            raise
    
    def validate_schema(self, data: Dict[str, Any]) -> bool:
        """Validate data against schema."""
        required_fields = {'id', 'type', 'content'}
        if not all(f in data for f in required_fields):
            raise ValueError(f"Missing required fields: {required_fields - set(data.keys())}")
        return True
    
    def get_transaction_history(self) -> list:
        """Get transaction log."""
        return self.transaction_log.copy()
