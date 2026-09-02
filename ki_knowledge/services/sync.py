"""Document synchronization service for Infosite."""

import logging
from datetime import datetime
from typing import Optional, Tuple
from pathlib import Path

from ki_core.config import Config

from .discovery import DocumentDiscoveryService, FileInfo

logger = logging.getLogger(__name__)


class DocumentSyncService:
    """
    Synchronizes discovered documents with Infosite project model.
    
    Used by:
    - Infosite project views (manual sync button)
    - Import pipelines (automatic sync)
    - Django signals (on project creation/update)
    """
    
    def __init__(self, config: Optional[Config] = None):
        """Initialize sync service with discovery service."""
        self.discovery = DocumentDiscoveryService(config)
        self.config = config or Config.from_env()
    
    def sync_project_documents(
        self,
        project: "InfoSiteProject",  # type: ignore
        force: bool = False,
    ) -> Tuple[int, int, Optional[str]]:
        """
        Synchronize documents for an InfoSiteProject.
        
        Args:
            project: InfoSiteProject instance to sync
            force: If True, re-discover even if recently synced
        
        Returns:
            Tuple of (documents_discovered, documents_updated, error_message)
            error_message is None if successful
        """
        try:
            # Check if working_title is configured
            if not project.working_title:
                return 0, 0, "working_title not configured"
            
            # Discover documents
            discovered = self.discovery.find_infosite_documents(
                project.domain,
                project.working_title,
            )
            
            if not discovered:
                project.sync_status = "completed"
                project.last_sync_error = ""
                project.last_sync_at = datetime.now()
                project.save()
                return 0, 0, None
            
            # Update or create SourceDocument records
            updated_count = 0
            for doc_info in discovered:
                doc, created = self._upsert_document(project, doc_info)
                if created:
                    updated_count += 1
            
            # Mark sync as successful
            project.sync_status = "completed"
            project.last_sync_error = ""
            project.last_sync_at = datetime.now()
            project.save()
            
            return len(discovered), updated_count, None
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error syncing project {project.id}: {error_msg}", exc_info=True)
            
            # Mark sync as failed
            project.sync_status = "failed"
            project.last_sync_error = error_msg
            project.last_sync_at = datetime.now()
            project.save()
            
            return 0, 0, error_msg
    
    def _upsert_document(
        self,
        project: "InfoSiteProject",  # type: ignore
        file_info: FileInfo,
    ) -> Tuple["SourceDocument", bool]:  # type: ignore
        """
        Create or update a SourceDocument from FileInfo.
        
        Args:
            project: Parent InfoSiteProject
            file_info: FileInfo from discovery
        
        Returns:
            Tuple of (document, created)
        """
        from ki_knowledge.django_site.infosite_models import SourceDocument
        
        # Determine file type
        file_type = "other"
        if file_info.is_markdown:
            file_type = "markdown"
        elif file_info.is_pdf:
            file_type = "pdf"
        elif file_info.path.suffix.lower() == ".txt":
            file_type = "text"
        
        doc, created = SourceDocument.objects.update_or_create(
            project=project,
            file_path=str(file_info.path),
            defaults={
                "title": file_info.name,
                "file_type": file_type,
                "file_size": file_info.size,
                "modified_at": file_info.modified_at,
                "import_status": "discovered",
            },
        )
        
        return doc, created


# Re-export for easy access
__all__ = ["DocumentSyncService"]
