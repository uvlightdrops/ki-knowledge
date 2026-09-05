"""
InfoSite Generator Service

Generates structured markdown output from discovered documents.
Creates versioning baseline and metadata for tracking.
"""

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
import yaml

from .discovery import DocumentDiscoveryService, FileInfo


@dataclass
class GenerationResult:
    """Result of generation operation"""
    success: bool
    message: str
    output_dir: Optional[Path] = None
    files_created: int = 0
    version: str = "v1-original"


class InfoSiteGeneratorService:
    """
    Generates structured markdown output and versioning baseline.
    
    Output structure:
        data_out/<domain>/<working_title>/
        ├── index.md
        ├── overview.md
        ├── metadata.yml
        ├── _originals/
        │   └── v1-original/
        │       ├── topic1/
        │       ├── topic2/
        │       └── ...
        └── topics/
            ├── topic1.md
            ├── topic2.md
            └── ...
    """

    def __init__(self, data_root_or_config):
        """
        Initialize generator service.
        
        Args:
            data_root_or_config: Either a Path/str to data root or a Config object
        """
        from ki_knowledge.app_config import AppConfig as Config
        
        if isinstance(data_root_or_config, (str, Path)):
            self.data_root = Path(data_root_or_config)
            # Create a minimal config-like object
            class MinimalConfig:
                def __init__(self, root):
                    self.knowledge_data_root = str(root)
            self.config = MinimalConfig(self.data_root)
        else:
            # Assume it's a Config object
            self.config = data_root_or_config
            self.data_root = Path(self.config.knowledge_data_root)
        
        self.discovery = DocumentDiscoveryService(self.config)
        self.output_base = self.data_root / "data_out"

    def generate_infosite(
        self,
        domain: str,
        working_title: str,
        source_docs: list[FileInfo],
    ) -> GenerationResult:
        """
        Generate complete infosite output from discovered documents.
        
        Args:
            domain: Domain name (e.g., 'anthro')
            working_title: Project working title (e.g., 'sstk')
            source_docs: List of discovered source documents
        
        Returns:
            GenerationResult with success status and output directory
        """
        try:
            # Create output directory structure
            output_dir = self._create_output_structure(domain, working_title)
            
            # Copy source documents to versioning baseline
            originals_dir = self._copy_originals(
                domain, working_title, source_docs, output_dir
            )
            
            # Generate index and overview files
            self._generate_index(domain, working_title, source_docs, output_dir)
            self._generate_overview(domain, working_title, source_docs, output_dir)
            
            # Create metadata
            metadata = self._generate_metadata(
                domain, working_title, source_docs, output_dir
            )
            self._write_metadata(output_dir, metadata)
            
            return GenerationResult(
                success=True,
                message=f"Generated infosite {domain}/{working_title} ({len(source_docs)} documents)",
                output_dir=output_dir,
                files_created=len(source_docs) + 3,  # docs + index + overview + metadata
                version="v1-original",
            )

        except Exception as e:
            return GenerationResult(
                success=False,
                message=f"Generation failed: {str(e)}",
            )

    def _create_output_structure(self, domain: str, working_title: str) -> Path:
        """Create output directory structure with required subdirectories."""
        output_dir = self.output_base / domain / working_title
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (output_dir / "_originals" / "v1-original").mkdir(parents=True, exist_ok=True)
        (output_dir / "topics").mkdir(parents=True, exist_ok=True)
        
        return output_dir

    def _copy_originals(
        self,
        domain: str,
        working_title: str,
        source_docs: list[FileInfo],
        output_dir: Path,
    ) -> Path:
        """
        Copy source documents to _originals/v1-original as immutable baseline.
        Preserves directory structure from source.
        """
        originals_dir = output_dir / "_originals" / "v1-original"
        
        for doc in source_docs:
            # Reconstruct relative path structure
            rel_path = doc.path.relative_to(
                self.data_root / "md" / domain / working_title
            )
            dest_path = originals_dir / rel_path
            
            # Create parent directory
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            shutil.copy2(doc.path, dest_path)
        
        return originals_dir

    def _generate_index(
        self,
        domain: str,
        working_title: str,
        source_docs: list[FileInfo],
        output_dir: Path,
    ) -> None:
        """Generate main index.md with all topics and documents."""
        # Group documents by directory/topic
        topics = {}
        for doc in source_docs:
            topic = doc.path.parent.name
            if topic not in topics:
                topics[topic] = []
            topics[topic].append(doc)
        
        # Build index content
        lines = [
            f"# {working_title.upper()} - Complete Index",
            "",
            f"**Domain:** {domain}  ",
            f"**Generated:** {datetime.now().isoformat()}  ",
            f"**Total Documents:** {len(source_docs)}  ",
            f"**Topics:** {len(topics)}  ",
            "",
            "---",
            "",
            "## Table of Contents",
            "",
        ]
        
        # Add topics to TOC
        for topic in sorted(topics.keys()):
            lines.append(f"- [{topic}](#{topic.lower().replace(' ', '-')})")
        
        lines.extend(["", "---", ""])
        
        # Add topic sections
        for topic in sorted(topics.keys()):
            lines.extend([
                f"## {topic}",
                "",
                f"**Documents:** {len(topics[topic])}",
                "",
            ])
            
            for doc in sorted(topics[topic], key=lambda d: d.path.name):
                rel_path = doc.path.relative_to(
                    self.data_root / "md" / domain / working_title
                )
                lines.append(f"- {doc.path.stem}")
            
            lines.append("")
        
        # Write index
        index_path = output_dir / "index.md"
        index_path.write_text("\n".join(lines), encoding="utf-8")

    def _generate_overview(
        self,
        domain: str,
        working_title: str,
        source_docs: list[FileInfo],
        output_dir: Path,
    ) -> None:
        """Generate overview.md with summary and statistics."""
        # Group by topic
        topics = {}
        total_size = 0
        
        for doc in source_docs:
            topic = doc.path.parent.name
            if topic not in topics:
                topics[topic] = {"count": 0, "size": 0}
            topics[topic]["count"] += 1
            topics[topic]["size"] += doc.size or 0
            total_size += doc.size or 0
        
        lines = [
            f"# {working_title} - Overview",
            "",
            "## Summary",
            "",
            f"- **Domain:** {domain}",
            f"- **Working Title:** {working_title}",
            f"- **Total Documents:** {len(source_docs)}",
            f"- **Topics:** {len(topics)}",
            f"- **Total Size:** {total_size:,} bytes ({total_size / 1024 / 1024:.2f} MB)",
            f"- **Generated:** {datetime.now().isoformat()}",
            "",
            "## Topics Breakdown",
            "",
        ]
        
        # Add topic statistics
        for topic in sorted(topics.keys(), key=lambda t: topics[t]["count"], reverse=True):
            stats = topics[topic]
            lines.append(f"### {topic}")
            lines.extend([
                f"- Documents: {stats['count']}",
                f"- Size: {stats['size']:,} bytes",
                "",
            ])
        
        # Write overview
        overview_path = output_dir / "overview.md"
        overview_path.write_text("\n".join(lines), encoding="utf-8")

    def _generate_metadata(
        self,
        domain: str,
        working_title: str,
        source_docs: list[FileInfo],
        output_dir: Path,
    ) -> dict:
        """Generate metadata dictionary for YAML export."""
        # Group documents by topic
        topics = {}
        for doc in source_docs:
            topic = doc.path.parent.name
            if topic not in topics:
                topics[topic] = []
            topics[topic].append(str(doc.path.name))
        
        # Calculate statistics
        total_size = sum(doc.size or 0 for doc in source_docs)
        
        return {
            "generation": {
                "timestamp": datetime.now().isoformat(),
                "version": "v1-original",
            },
            "project": {
                "domain": domain,
                "working_title": working_title,
                "description": f"InfoSite project for {domain}/{working_title}",
            },
            "statistics": {
                "total_documents": len(source_docs),
                "total_topics": len(topics),
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / 1024 / 1024, 2),
            },
            "topics": topics,
            "output_structure": {
                "_originals": "Immutable baseline of original source documents",
                "topics": "Placeholder for refined/generated content (Phase 3)",
                "index.md": "Complete index of all documents",
                "overview.md": "Summary statistics and breakdown by topic",
                "metadata.yml": "This file - generation metadata",
            },
        }

    def _write_metadata(self, output_dir: Path, metadata: dict) -> None:
        """Write metadata to YAML file."""
        metadata_path = output_dir / "metadata.yml"
        with open(metadata_path, "w") as f:
            yaml.dump(metadata, f, default_flow_style=False, allow_unicode=True)

    def get_output_directory(self, domain: str, working_title: str) -> Path:
        """Get output directory path for a project."""
        return self.output_base / domain / working_title

    def list_versions(self, domain: str, working_title: str) -> list[str]:
        """List all available versions in _originals directory."""
        originals_dir = self.output_base / domain / working_title / "_originals"
        
        if not originals_dir.exists():
            return []
        
        return sorted([d.name for d in originals_dir.iterdir() if d.is_dir()])

    def get_version_metadata(self, domain: str, working_title: str, version: str) -> Optional[dict]:
        """Get metadata for a specific version."""
        metadata_path = self.output_base / domain / working_title / "metadata.yml"
        
        if not metadata_path.exists():
            return None
        
        with open(metadata_path) as f:
            return yaml.safe_load(f)
