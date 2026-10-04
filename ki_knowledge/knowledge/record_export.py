"""Render ordered knowledge records as a readable Markdown document."""

from __future__ import annotations

from collections.abc import Iterable

from ki_knowledge.knowledge.models import KnowledgeBlockRecord


def records_to_markdown(records: Iterable[KnowledgeBlockRecord], *, title: str) -> str:
    """Preserve record order and source context when composing an InfoSite input."""
    lines = [f"# {title}", ""]
    current_context = None
    for record in records:
        context = record.path.strip()
        if context != current_context:
            if context:
                lines.extend((f"## {context}", ""))
            current_context = context

        content = record.content.strip()
        if record.record_type == "image":
            relative_path = str(record.metadata.get("relative_path", "")).strip()
            content = f"![{record.title}]({relative_path})" if relative_path else f"Bildobjekt: {record.title}"
        elif record.block_type == "list_item" and content:
            content = f"- {content}"

        if content:
            lines.extend((content, ""))

    return "\n".join(lines).rstrip() + "\n"
