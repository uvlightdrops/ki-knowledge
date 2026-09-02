"""Data models for Infosite configuration and metadata."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class InfoSiteConfig:
    """Configuration for knowledge presentation generation."""

    enabled: bool = False
    title: str = ""
    domain: str = "default"
    output_base_dir: str = ""

    def get_output_dir(self) -> Path:
        """Get the full output directory path."""
        if not self.output_base_dir:
            raise ValueError("infosite_output_base_dir must be configured")
        base = Path(self.output_base_dir)
        return base / self.domain / self._slugify(self.title)

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert text to URL-friendly slug."""
        import re
        text = text.lower().strip()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '-', text)
        return text.strip('-')


@dataclass
class InfoSiteMetadata:
    """Metadata for generated infosite."""

    version: str = "v1-original"
    generated_at: datetime = field(default_factory=datetime.now)
    title: str = ""
    domain: str = "default"
    source_documents: List[str] = field(default_factory=list)
    custom_fields: Dict[str, Any] = field(default_factory=dict)

    def to_frontmatter_dict(self) -> Dict[str, Any]:
        """Convert to YAML frontmatter dict."""
        return {
            "version": self.version,
            "generated_at": self.generated_at.isoformat(),
            "title": self.title,
            "domain": self.domain,
            "source_documents": self.source_documents,
            **self.custom_fields,
        }


@dataclass
class PageSpec:
    """Specification for a page to generate."""

    slug: str
    title: str
    content: str
    order: int = 0
    children: List["PageSpec"] = field(default_factory=list)

    def get_path(self, base_path: Path) -> Path:
        """Get the file path for this page."""
        if self.slug == "index":
            return base_path / "index.md"
        return base_path / self.slug / "index.md"
