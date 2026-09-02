"""Document Discovery Service - unified file finder for knowledge sources."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from datetime import datetime
import logging

from ki_core.config import Config

logger = logging.getLogger(__name__)


@dataclass
class FileInfo:
    """Information about a discovered file."""
    
    path: Path
    name: str
    file_type: str  # md, pdf, txt, etc.
    size: int
    modified_at: datetime
    
    @property
    def is_markdown(self) -> bool:
        return self.file_type.lower() == 'md'
    
    @property
    def is_pdf(self) -> bool:
        return self.file_type.lower() == 'pdf'


class DocumentDiscoveryService:
    """
    Unified service for discovering source documents.
    
    Used by:
    - Infosite (find markdown in md/<domain>/<working_title>/)
    - Data Sources (find PDFs, markdown, etc.)
    - Import pipelines (locate files to import)
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize discovery service.
        
        Args:
            config: Ki-core Config object. If None, loads from environment.
        """
        self.config = config or Config.from_env()
        self.data_root = Path(self.config.knowledge_data_root)
    
    def find_infosite_documents(
        self,
        domain: str,
        working_title: str,
    ) -> List[FileInfo]:
        """
        Find source documents for an infosite.
        
        Searches in: md/<domain>/<working_title>/
        
        Args:
            domain: Domain name (e.g., "anthro")
            working_title: Working title/project name (e.g., "sstk")
        
        Returns:
            List of FileInfo for discovered documents
        """
        source_dir = self.data_root / "md" / domain / working_title
        
        if not source_dir.exists():
            logger.warning(f"Source directory not found: {source_dir}")
            return []
        
        return self._discover_files(source_dir, recursive=True)
    
    def find_markdown_sources(
        self,
        domain: str,
    ) -> List[FileInfo]:
        """
        Find all markdown files in a domain.
        
        Searches in: md/<domain>/
        
        Args:
            domain: Domain name
        
        Returns:
            List of FileInfo for markdown files
        """
        source_dir = self.data_root / "md" / domain
        
        if not source_dir.exists():
            logger.warning(f"Domain directory not found: {source_dir}")
            return []
        
        return self._discover_files(source_dir, recursive=True, pattern="*.md")
    
    def find_pdf_sources(
        self,
        domain: str,
    ) -> List[FileInfo]:
        """
        Find all PDF files in a domain.
        
        Searches in: pdf/<domain>/
        
        Args:
            domain: Domain name
        
        Returns:
            List of FileInfo for PDF files
        """
        source_dir = self.data_root / "pdf" / domain
        
        if not source_dir.exists():
            logger.warning(f"PDF directory not found: {source_dir}")
            return []
        
        return self._discover_files(source_dir, recursive=True, pattern="*.pdf")
    
    def _discover_files(
        self,
        root_dir: Path,
        recursive: bool = True,
        pattern: Optional[str] = None,
    ) -> List[FileInfo]:
        """
        Recursively discover files in directory.
        
        Args:
            root_dir: Directory to search
            recursive: Search subdirectories
            pattern: Glob pattern (e.g., "*.md")
        
        Returns:
            List of FileInfo for discovered files
        """
        if not root_dir.exists():
            return []
        
        discovered = []
        
        try:
            if recursive:
                entries = root_dir.rglob(pattern or "*") if pattern else root_dir.rglob("*")
            else:
                entries = root_dir.glob(pattern or "*") if pattern else root_dir.glob("*")
            
            for entry in entries:
                if entry.is_file():
                    file_info = self._get_file_info(entry)
                    if file_info:
                        discovered.append(file_info)
            
            # Sort by modified time (newest first)
            discovered.sort(key=lambda x: x.modified_at, reverse=True)
            
        except Exception as e:
            logger.error(f"Error discovering files in {root_dir}: {e}")
        
        return discovered
    
    def _get_file_info(self, file_path: Path) -> Optional[FileInfo]:
        """
        Extract file information.
        
        Args:
            file_path: Path to file
        
        Returns:
            FileInfo or None if file cannot be read
        """
        try:
            stat = file_path.stat()
            file_type = file_path.suffix.lstrip(".").lower()
            
            return FileInfo(
                path=file_path,
                name=file_path.name,
                file_type=file_type,
                size=stat.st_size,
                modified_at=datetime.fromtimestamp(stat.st_mtime),
            )
        except Exception as e:
            logger.error(f"Error reading file info for {file_path}: {e}")
            return None
    
    def get_infosite_output_dir(self, domain: str, working_title: str) -> Path:
        """
        Get output directory for generated infosite.
        
        Returns: data_out/<domain>/<working_title>/
        
        Args:
            domain: Domain name
            working_title: Working title
        
        Returns:
            Path to output directory (may not exist yet)
        """
        return self.data_root / "data_out" / domain / working_title
    
    def list_domains(self) -> List[str]:
        """
        List all available domains.
        
        Returns:
            List of domain directory names
        """
        md_dir = self.data_root / "md"
        
        if not md_dir.exists():
            return []
        
        domains = [d.name for d in md_dir.iterdir() if d.is_dir()]
        return sorted(domains)
    
    def list_working_titles(self, domain: str) -> List[str]:
        """
        List all working titles in a domain.
        
        Returns:
            List of working title directory names
        """
        domain_dir = self.data_root / "md" / domain
        
        if not domain_dir.exists():
            return []
        
        titles = [d.name for d in domain_dir.iterdir() if d.is_dir()]
        return sorted(titles)
