"""Knowledge-store adapter for EPUB originals and converted Markdown chapters."""

from __future__ import annotations

import hashlib
from pathlib import Path

from ki_knowledge.knowledge.models import KnowledgeArtifact, KnowledgeSource
from ki_knowledge.services.domain_paths import domain_markdown_dir, infer_domain_from_path
from ki_knowledge.services.epub_import import materialize_epub

from .domain_paths import invalidate_domain_summary_cache


def import_epub_file(path: Path, *, domain: str | None = None) -> dict:
    from .source_workflow import store

    domain = domain or infer_domain_from_path(path)
    if not domain:
        raise ValueError("EPUB import requires an explicit domain.")
    converted = materialize_epub(path, domain_markdown_dir(domain))
    manifest = converted["manifest"]
    store_obj = store()
    source_id = f"epub:{path.expanduser().absolute()}"
    imported = 0
    try:
        for index, (chapter_path, chapter) in enumerate(
            zip(converted["chapter_paths"], manifest["chapters"], strict=True), 1,
        ):
            chapter_id = f"markdown:{chapter_path.resolve()}"
            blocks = store_obj.import_markdown_text(
                chapter_path.read_text(encoding="utf-8"),
                source_path=str(chapter_path), source_id=chapter_id, source_type="markdown",
                source_name=f"{manifest['title']} · {chapter['title']}", replace=True,
            )
            imported += len(blocks)
            chapter_source = store_obj.get_source(chapter_id)
            chapter_source.metadata = {
                **chapter_source.metadata, "domain": domain, "origin_type": "epub",
                "epub_source_id": source_id, "epub_sha256": manifest["source_sha256"],
                "epub_href": chapter["href"], "book_title": manifest["title"],
                "chapter_index": index, "chapter_title": chapter["title"],
                "authors": manifest["authors"], "language": manifest["language"],
                "identifier": manifest["identifier"],
            }
            store_obj.upsert_source(chapter_source)
        store_obj.upsert_source(KnowledgeSource(
            source_id=source_id, source_type="epub", title=manifest["title"],
            location=str(path.expanduser().absolute()),
            metadata={**manifest, "domain": domain, "markdown_directory": str(converted["directory"])},
        ))
        store_obj.upsert_artifact(KnowledgeArtifact(
            artifact_id=hashlib.sha256(f"{source_id}:reference_structure".encode()).hexdigest()[:24],
            artifact_type="reference_structure", source_id=source_id, source_block_ids=[],
            content="\n".join(f"{i}. {item['title']}" for i, item in enumerate(manifest["chapters"], 1)),
            metadata={**manifest, "origin": "epub"},
        ))
    finally:
        invalidate_domain_summary_cache(domain)
    return {
        "file": str(path), "source_id": source_id, "kind": "epub",
        "imported": imported, "chapters": len(manifest["chapters"]),
        "markdown_dir": str(converted["directory"]), "warnings": converted["warnings"],
    }
