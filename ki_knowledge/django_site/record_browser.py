"""Helpers for presenting source records in their original sequence."""

from __future__ import annotations

from typing import Any, Iterable

from ki_knowledge.knowledge.models import KnowledgeBlockRecord


def group_records(records: Iterable[KnowledgeBlockRecord]) -> list[dict[str, Any]]:
    """Group adjacent records by source context without changing their order."""
    groups: list[dict[str, Any]] = []
    for record in records:
        heading_path = record.path.strip()
        title = heading_path or "Dokumentinhalt"
        if not groups or groups[-1]["title"] != title:
            groups.append({"title": title, "records": []})
        provenance = record.metadata.get("provenance") or {}
        groups[-1]["records"].append(
            {
                "record": record,
                "type": record.record_type,
                "content": record.content,
                "metadata": record.metadata,
                "source_format": provenance.get("source_format") or record.metadata.get("source_format", ""),
                "page": record.metadata.get("page") or _page_from_context(heading_path),
            }
        )
    return groups


def _page_from_context(value: str) -> str:
    import re

    match = re.search(r"\bPage\s+(\d+)\b", value, re.IGNORECASE)
    return match.group(1) if match else ""
