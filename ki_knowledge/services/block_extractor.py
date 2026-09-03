"""Service for parsing Markdown documents into hierarchical Knowledge Blocks."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import re


@dataclass
class KnowledgeBlockData:
    """Represents a single knowledge block extracted from markdown."""
    
    title: str
    content: str
    level: int  # 1 for h1, 2 for h2, etc.
    block_type: str  # "section", "subsection", "paragraph"
    parent_index: Optional[int] = None  # Index of parent block in list
    order_index: int = 0
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    
    @property
    def block_id(self) -> str:
        """Generate unique block ID from title."""
        # Convert title to slug-like format
        slug = re.sub(r'[^\w\s-]', '', self.title.lower())
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug


class MarkdownBlockParser:
    """Parse Markdown files into hierarchical Knowledge Blocks."""
    
    def __init__(self, source_id: str, domain: str = "default"):
        """Initialize parser.
        
        Args:
            source_id: Identifier for the knowledge source (e.g., "infosite_sstk_anthro")
            domain: Domain/namespace (e.g., "anthropology")
        """
        self.source_id = source_id
        self.domain = domain
    
    def parse_file(self, file_path: Path) -> list[KnowledgeBlockData]:
        """Parse a markdown file into knowledge blocks.
        
        Args:
            file_path: Path to markdown file
            
        Returns:
            List of KnowledgeBlockData blocks in hierarchical order
        """
        if not file_path.exists():
            return []
        
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        return self.parse_content(content, file_path.name)
    
    def parse_content(self, content: str, source_name: str = "") -> list[KnowledgeBlockData]:
        """Parse markdown content into knowledge blocks.
        
        Args:
            content: Markdown content string
            source_name: Name of source file (for metadata)
            
        Returns:
            List of KnowledgeBlockData blocks
        """
        blocks = []
        current_sections = {}  # Keep track of last section at each level
        
        lines = content.split("\n")
        i = 0
        content_buffer = []
        
        while i < len(lines):
            line = lines[i]
            
            # Check for heading
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            
            if heading_match:
                # Flush any accumulated content as paragraph block
                if content_buffer:
                    content_text = "\n".join(content_buffer).strip()
                    if content_text:
                        blocks.append(self._create_content_block(
                            content_text,
                            blocks,
                            current_sections
                        ))
                    content_buffer = []
                
                # Create heading block
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                
                block = KnowledgeBlockData(
                    title=title,
                    content="",
                    level=level,
                    block_type=self._level_to_type(level),
                    order_index=len(blocks),
                    tags=[self.domain, source_name.replace(".md", "")]
                )
                
                # Set parent based on hierarchy
                if level > 1:
                    # Find the closest parent (previous block with lower level)
                    for j in range(len(blocks) - 1, -1, -1):
                        if blocks[j].level < level:
                            block.parent_index = j
                            break
                
                blocks.append(block)
                current_sections[level] = len(blocks) - 1
                
                # Clear sections deeper than current level
                levels_to_remove = [l for l in current_sections if l > level]
                for l in levels_to_remove:
                    del current_sections[l]
            
            else:
                # Accumulate content
                if line.strip():  # Skip empty lines at buffer start
                    content_buffer.append(line)
            
            i += 1
        
        # Flush remaining content
        if content_buffer:
            content_text = "\n".join(content_buffer).strip()
            if content_text:
                blocks.append(self._create_content_block(
                    content_text,
                    blocks,
                    current_sections
                ))
        
        return blocks
    
    def _level_to_type(self, level: int) -> str:
        """Map heading level to block type."""
        if level == 1:
            return "section"
        elif level == 2:
            return "subsection"
        elif level == 3:
            return "subsubsection"
        else:
            return "paragraph"
    
    def _create_content_block(
        self,
        content: str,
        blocks: list,
        current_sections: dict
    ) -> KnowledgeBlockData:
        """Create a content/paragraph block."""
        # Determine parent: most recent section at any level
        parent_index = None
        if current_sections:
            parent_index = max(current_sections.values())
        
        return KnowledgeBlockData(
            title=self._extract_title_from_content(content),
            content=content[:500],  # Limit to first 500 chars for preview
            level=4,  # Content is deeper than headings
            block_type="paragraph",
            parent_index=parent_index,
            order_index=len(blocks),
        )
    
    def _extract_title_from_content(self, content: str, max_length: int = 80) -> str:
        """Extract a title from paragraph content."""
        # Take first sentence or first N chars
        first_line = content.split("\n")[0]
        # Remove markdown formatting
        clean = re.sub(r'[*_`\[\]()#]', '', first_line)
        if len(clean) > max_length:
            clean = clean[:max_length].rsplit(" ", 1)[0] + "..."
        return clean or "[Paragraph]"


class InfoSiteBlockExtractor:
    """Extract knowledge blocks from an InfoSite project."""
    
    def __init__(self, project_or_domain, working_title: str = None):
        """Initialize extractor for a specific domain/project.
        
        Args:
            project_or_domain: Either an InfoSiteProject object or a domain string
            working_title: Required if first arg is a domain string
        """
        # Support both InfoSiteProject objects and (domain, working_title) args
        try:
            from ki_knowledge.django_site.infosite_models import InfoSiteProject
            if isinstance(project_or_domain, InfoSiteProject):
                self.project = project_or_domain
                self.domain = project_or_domain.domain
                self.working_title = project_or_domain.working_title
            else:
                self.project = None
                self.domain = project_or_domain
                self.working_title = working_title
        except ImportError:
            # Fallback if Django models not available
            self.project = None
            self.domain = project_or_domain
            self.working_title = working_title
        
        self.source_id = f"infosite_{self.working_title}_{self.domain}".lower()
        self.parser = MarkdownBlockParser(self.source_id, self.domain)
    
    def extract_from_directory(self, directory: Path = None) -> dict[str, list[KnowledgeBlockData]]:
        """Extract blocks from all markdown files in directory.
        
        Args:
            directory: Path to scan. If None and project provided, auto-detect.
        
        Returns:
            Dict mapping file paths to block lists
        """
        if directory is None:
            if self.project and getattr(self.project, "source_directory", ""):
                directory = Path(self.project.source_directory)
            else:
                from ki_knowledge.knowledge.adapters import InfoSiteSourceAdapter

                directory = InfoSiteSourceAdapter.resolve_markdown_root(self.domain, self.working_title)
        
        blocks_by_file = {}
        
        if not directory.exists():
            return blocks_by_file
        
        for md_file in sorted(directory.rglob("*.md")):
            blocks = self.parser.parse_file(md_file)
            if blocks:
                rel_path = str(md_file.relative_to(directory))
                blocks_by_file[rel_path] = blocks
        
        return blocks_by_file
    
    def get_block_hierarchy(self, blocks: list[KnowledgeBlockData]) -> dict:
        """Convert flat block list to hierarchical structure.
        
        Returns:
            Nested dict representing block hierarchy
        """
        hierarchy = {"sections": []}
        stack = [{"level": 0, "blocks": hierarchy["sections"]}]
        
        for block in blocks:
            # Find appropriate level in stack
            while len(stack) > 1 and stack[-1]["level"] >= block.level:
                stack.pop()
            
            block_dict = {
                "block": block,
                "children": []
            }
            
            stack[-1]["blocks"].append(block_dict)
            
            if block.level > 0:
                stack.append({"level": block.level, "blocks": block_dict["children"]})
        
        return hierarchy
    
    def get_statistics(self, blocks_by_file: dict[str, list[KnowledgeBlockData]] = None) -> dict:
        """Calculate statistics about extracted blocks.
        
        Args:
            blocks_by_file: Dict of blocks. If None, extracts from directory first.
        
        Returns:
            Dict with counts and summaries
        """
        if blocks_by_file is None:
            blocks_by_file = self.extract_from_directory()
        
        total_files = len(blocks_by_file)
        total_blocks = sum(len(b) for b in blocks_by_file.values())
        sections = sum(1 for blocks in blocks_by_file.values() for b in blocks if b.level == 1)
        subsections = sum(1 for blocks in blocks_by_file.values() for b in blocks if b.level == 2)
        paragraphs = sum(1 for blocks in blocks_by_file.values() for b in blocks if b.level >= 3)
        
        return {
            "total_files": total_files,
            "total_blocks": total_blocks,
            "sections": sections,
            "subsections": subsections,
            "paragraphs": paragraphs,
            "by_file": {
                path: len(blocks)
                for path, blocks in blocks_by_file.items()
            }
        }
