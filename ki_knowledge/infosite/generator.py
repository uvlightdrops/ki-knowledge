"""Generator for knowledge presentation sites."""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from .models import InfoSiteConfig, InfoSiteMetadata, PageSpec
from .importer import import_directory, DocumentImporterRegistry


class InfoSiteGenerator:
    """Generate markdown-based browsable knowledge websites."""

    def __init__(
        self,
        config: InfoSiteConfig,
        metadata: Optional[InfoSiteMetadata] = None,
    ):
        """Initialize the infosite generator.

        Args:
            config: InfoSite configuration
            metadata: Optional metadata (generated if not provided)
        """
        self.config = config
        self.metadata = metadata or InfoSiteMetadata(
            title=config.title,
            domain=config.domain,
        )
        self.output_dir = config.get_output_dir()

    def generate(
        self,
        pages: List[PageSpec],
        create_originals_backup: bool = True,
    ) -> Path:
        """Generate the infosite.

        Args:
            pages: List of page specifications to generate
            create_originals_backup: Create backup of original version

        Returns:
            Path to the generated output directory
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)

        for page in pages:
            self._write_page(page)

        self._write_metadata()

        if create_originals_backup:
            self._backup_original_version()

        return self.output_dir

    def _write_page(self, page: PageSpec, parent_path: Optional[Path] = None) -> None:
        """Write a single page to disk.

        Args:
            page: Page specification
            parent_path: Parent directory path (defaults to output_dir)
        """
        if parent_path is None:
            parent_path = self.output_dir

        # Create directory if needed
        page_dir = parent_path / page.slug if page.slug != "index" else parent_path
        if page.slug != "index":
            page_dir.mkdir(parents=True, exist_ok=True)

        # Write page file
        page_path = page_dir / "index.md" if page.slug != "index" else parent_path / "index.md"
        with page_path.open("w", encoding="utf-8") as f:
            f.write(self._render_page(page))

        # Recursively write child pages
        for child in page.children:
            self._write_page(child, page_dir)

    def _render_page(self, page: PageSpec) -> str:
        """Render a page as markdown.

        Args:
            page: Page specification

        Returns:
            Rendered markdown string
        """
        lines = [f"# {page.title}\n"]
        lines.append(page.content)
        lines.append("")
        return "\n".join(lines)

    def _write_metadata(self) -> None:
        """Write metadata file."""
        metadata_path = self.output_dir / "metadata.yml"
        with metadata_path.open("w", encoding="utf-8") as f:
            yaml.dump(self.metadata.to_frontmatter_dict(), f, default_flow_style=False)

    def _backup_original_version(self) -> None:
        """Create a backup of the original version."""
        originals_dir = self.output_dir.parent / "_originals" / self.metadata.version
        originals_dir.mkdir(parents=True, exist_ok=True)

        # Copy all markdown files to originals directory
        for md_file in self.output_dir.glob("**/*.md"):
            if "_originals" not in md_file.parts:
                relative_path = md_file.relative_to(self.output_dir)
                target_path = originals_dir / relative_path
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(md_file.read_text(encoding="utf-8"))

        # Copy metadata
        metadata_path = self.output_dir / "metadata.yml"
        if metadata_path.exists():
            (originals_dir / "metadata.yml").write_text(
                metadata_path.read_text(encoding="utf-8")
            )

    @staticmethod
    def create_default_pages(title: str) -> List[PageSpec]:
        """Create default page structure.

        Args:
            title: Site title

        Returns:
            List of default page specifications
        """
        return [
            PageSpec(
                slug="index",
                title=title,
                content=f"""
Welcome to the {title} knowledge base.

This is a browsable, markdown-based knowledge resource designed for easy
navigation and future enhancement with AI assistance.

## Getting Started

- [Overview](overview/index.md) - High-level overview of topics
- Explore topics and content through the navigation structure

## Features

- **Markdown-based** - Content is stored as clean, version-controllable markdown
- **Structured** - Organized hierarchical information architecture
- **SSG-ready** - Compatible with static site generators (Hugo, Jekyll, MkDocs)
- **AI-enhanced** - Designed for incremental improvements with AI assistance

---

*Generated: {datetime.now().isoformat()}*
""".strip(),
                order=0,
            ),
            PageSpec(
                slug="overview",
                title="Overview",
                content="""
This section provides a high-level overview of the knowledge base structure.

## Topics

The knowledge base is organized into the following main topics:

1. **Introduction** - Basic concepts and getting started
2. **Core Concepts** - Fundamental ideas and principles
3. **Advanced Topics** - Deeper exploration of specialized areas
4. **Resources** - References, tools, and external resources

## Navigation

Each topic contains related subtopics and detailed information. 
Follow the links in the left navigation or use search to explore content.

## About This Knowledge Base

This knowledge base is automatically generated from source documents and
is continuously improved through AI-assisted enhancements.
""".strip(),
                order=1,
            ),
        ]

    def generate_from_documents(
        self,
        source_dir: Path,
        create_originals_backup: bool = True,
    ) -> Path:
        """Generate infosite from source documents.

        Args:
            source_dir: Directory containing source documents
            create_originals_backup: Create backup of original version

        Returns:
            Path to the generated output directory
        """
        # Import documents
        registry = DocumentImporterRegistry()
        documents = registry.import_directory(source_dir)

        if not documents:
            # Use default pages if no documents found
            pages = self.create_default_pages(self.config.title or "Knowledge Base")
        else:
            # Create pages from documents
            pages = self._pages_from_documents(documents)

        # Generate site
        return self.generate(pages, create_originals_backup=create_originals_backup)

    def _pages_from_documents(self, documents: Dict[str, str]) -> List[PageSpec]:
        """Convert imported documents to pages.

        Args:
            documents: Dictionary mapping file paths to content

        Returns:
            List of page specifications
        """
        pages = []

        # Add index page
        pages.append(
            PageSpec(
                slug="index",
                title=self.config.title or "Knowledge Base",
                content=f"""
# {self.config.title or "Knowledge Base"}

This knowledge base was generated from {len(documents)} source document(s).

## Content

The following content has been imported:

""" + "\n".join([f"- {path}" for path in sorted(documents.keys())]),
                order=0,
            )
        )

        # Add overview
        pages.append(
            PageSpec(
                slug="overview",
                title="Overview",
                content="""
## Overview

This knowledge base contains imported content from various sources.

### Organization

Content is organized by source document for easy reference.

### Navigation

Navigate through the topics using the directory structure.
""".strip(),
                order=1,
            )
        )

        # Add pages for each document
        for idx, (file_path, content) in enumerate(sorted(documents.items()), 2):
            slug = self._path_to_slug(file_path)
            title = self._path_to_title(file_path)

            pages.append(
                PageSpec(
                    slug=slug,
                    title=title,
                    content=content[:2000] + "...\n\n*Content truncated for preview*"
                    if len(content) > 2000
                    else content,
                    order=idx,
                )
            )

        return pages

    @staticmethod
    def _path_to_slug(file_path: str) -> str:
        """Convert file path to page slug.

        Args:
            file_path: File path

        Returns:
            URL-friendly slug
        """
        import re

        # Get filename without extension
        name = Path(file_path).stem
        # Convert to slug
        slug = name.lower().strip()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[-\s]+", "-", slug)
        return slug.strip("-")

    @staticmethod
    def _path_to_title(file_path: str) -> str:
        """Convert file path to page title.

        Args:
            file_path: File path

        Returns:
            Display title
        """
        # Get filename without extension
        name = Path(file_path).stem
        # Convert underscores and hyphens to spaces, capitalize
        return name.replace("_", " ").replace("-", " ").title()
