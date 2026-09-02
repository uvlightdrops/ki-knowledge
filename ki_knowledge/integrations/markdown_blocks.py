"""Markdown block parser for knowledge block extraction."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone


@dataclass
class KnowledgeBlock:
    """A single extracted knowledge block from a markdown document."""

    id: str
    source_type: str
    source_path: str
    block_type: str
    parent_id: Optional[str]
    heading_path: str
    content: str
    order_index: int
    metadata: dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_type": self.source_type,
            "source_path": self.source_path,
            "block_type": self.block_type,
            "parent_id": self.parent_id,
            "heading_path": self.heading_path,
            "content": self.content,
            "order_index": self.order_index,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class MarkdownBlockParser:
    """Parse markdown into hierarchical knowledge blocks."""

    def __init__(self) -> None:
        self._heading_pattern = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
        self._list_item_pattern = re.compile(r"^([-*+]\s+|\d+\.\s+)(.+)")
        self._fence_pattern = re.compile(r"^```")

    def parse_markdown(self, text: str, source_path: str) -> list[KnowledgeBlock]:
        """Parse markdown text into a list of blocks."""
        lines = text.splitlines()
        blocks: list[KnowledgeBlock] = []
        heading_stack: list[tuple[str, int]] = []
        section_id_stack: list[tuple[str, int]] = []
        paragraph_lines: list[str] = []
        list_items: list[str] = []
        code_lines: list[str] = []
        code_fence = False
        current_parent_id: Optional[str] = None

        def flush_paragraph() -> None:
            nonlocal paragraph_lines
            if paragraph_lines:
                content = " ".join(part.strip() for part in paragraph_lines if part.strip())
                if content:
                    blocks.append(
                        self._make_block(
                            source_path=source_path,
                            block_type="paragraph",
                            content=content,
                            parent_id=current_parent_id,
                            heading_path=self._heading_path(heading_stack),
                            order_index=len(blocks),
                        )
                    )
                paragraph_lines = []

        def flush_list_items() -> None:
            nonlocal list_items
            if list_items:
                for item in list_items:
                    blocks.append(
                        self._make_block(
                            source_path=source_path,
                            block_type="list_item",
                            content=item.strip(),
                            parent_id=current_parent_id,
                            heading_path=self._heading_path(heading_stack),
                            order_index=len(blocks),
                        )
                    )
                list_items = []

        def flush_code_block() -> None:
            nonlocal code_lines
            if code_lines:
                blocks.append(
                    self._make_block(
                        source_path=source_path,
                        block_type="code_block",
                        content="\n".join(code_lines).strip(),
                        parent_id=current_parent_id,
                        heading_path=self._heading_path(heading_stack),
                        order_index=len(blocks),
                    )
                )
                code_lines = []

        for line in lines:
            stripped = line.strip()
            if self._fence_pattern.match(stripped):
                if code_fence:
                    flush_code_block()
                    code_fence = False
                else:
                    flush_paragraph()
                    flush_list_items()
                    code_fence = True
                continue

            if code_fence:
                code_lines.append(stripped)
                continue

            heading_match = self._heading_pattern.match(stripped)
            if heading_match:
                flush_paragraph()
                flush_list_items()
                flush_code_block()

                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                while heading_stack and heading_stack[-1][1] >= level:
                    heading_stack.pop()
                while section_id_stack and section_id_stack[-1][1] >= level:
                    section_id_stack.pop()
                heading_stack.append((title, level))

                parent_id = section_id_stack[-1][0] if section_id_stack else None
                heading_block = self._make_block(
                    source_path=source_path,
                    block_type="heading",
                    content=title,
                    parent_id=parent_id,
                    heading_path=self._heading_path(heading_stack),
                    order_index=len(blocks),
                )
                current_parent_id = heading_block.id
                blocks.append(heading_block)
                section_id_stack.append((heading_block.id, level))
                continue

            if not stripped:
                flush_paragraph()
                flush_list_items()
                continue

            list_match = self._list_item_pattern.match(stripped)
            if list_match:
                flush_paragraph()
                list_items.append(list_match.group(2).strip())
                continue

            flush_list_items()
            paragraph_lines.append(stripped)

        flush_paragraph()
        flush_list_items()
        flush_code_block()

        return blocks

    def _make_block(
        self,
        *,
        source_path: str,
        block_type: str,
        content: str,
        parent_id: Optional[str],
        heading_path: str,
        order_index: int,
    ) -> KnowledgeBlock:
        block_id = self._generate_block_id(source_path, block_type, content, order_index)
        return KnowledgeBlock(
            id=block_id,
            source_type="markdown",
            source_path=source_path,
            block_type=block_type,
            parent_id=parent_id,
            heading_path=heading_path,
            content=content,
            order_index=order_index,
            metadata={"source_file": Path(source_path).name if source_path else "unknown"},
        )

    def _parent_id_from_stack(self, heading_stack: list[tuple[str, int]]) -> Optional[str]:
        if len(heading_stack) <= 1:
            return None
        return self._generate_block_id(
            "",
            "heading",
            heading_stack[-2][0],
            0,
        )

    def _heading_path(self, heading_stack: list[tuple[str, int]]) -> str:
        return " / ".join(title for title, _ in heading_stack)

    def _generate_block_id(
        self,
        source_path: str,
        block_type: str,
        content: str,
        order_index: int,
    ) -> str:
        payload = f"{source_path}:{block_type}:{content}:{order_index}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:16]
