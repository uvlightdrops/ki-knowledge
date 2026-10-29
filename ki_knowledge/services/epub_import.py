"""Materialize immutable, chapter-sized Markdown inputs from an EPUB."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from ki_knowledge.integrations.epub_ingest import EpubIngestError, parse_epub

CONVERTER_VERSION = "epub-markdown-v1"
MAX_CHAPTER_BYTES = 2 * 1024 * 1024


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def materialize_epub(path: Path, markdown_root: Path) -> dict:
    """Create once, or verify identical output; never overwrite edited Markdown."""
    path = path.expanduser().resolve(strict=True)
    digest = _digest(path)
    book = parse_epub(path)
    if _digest(path) != digest:
        raise EpubIngestError("EPUB changed while it was being converted; retry the import.")
    stem = re.sub(r"[^a-zA-Z0-9._-]+", "-", path.stem).strip(".-")[:70] or "book"
    parent = markdown_root / "epub"
    parent.mkdir(parents=True, exist_ok=True)
    destination = parent / f"{stem}-{digest[:16]}"
    chapters = []
    texts = {}
    for index, chapter in enumerate(book.chapters, 1):
        filename = f"{index:04d}.md"
        text = chapter.markdown.strip() + "\n"
        if len(text.encode("utf-8")) > MAX_CHAPTER_BYTES:
            raise EpubIngestError(f"Chapter {index} exceeds the workbench limit of 2 MiB.")
        texts[filename] = text
        chapters.append({
            "file": filename, "title": chapter.title, "href": chapter.href,
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        })
    manifest = {
        "converter": CONVERTER_VERSION,
        "source_path": str(path), "source_sha256": digest,
        "title": book.title, "authors": book.authors,
        "language": book.language, "identifier": book.identifier,
        "metadata": book.metadata, "chapters": chapters, "warnings": book.warnings,
    }

    def verify_existing():
        try:
            metadata_file = destination / "book.json"
            if destination.is_symlink() or metadata_file.is_symlink():
                raise EpubIngestError("Generated EPUB folder must not be a symlink.")
            existing = json.loads(metadata_file.read_text(encoding="utf-8"))
            # The same content may have been moved; preserve its original provenance.
            if any(existing.get(key) != manifest[key] for key in ("converter", "source_sha256", "chapters")):
                raise EpubIngestError("Existing EPUB conversion has a different manifest; nothing overwritten.")
            for name, text in texts.items():
                output = destination / name
                if output.is_symlink() or output.read_text(encoding="utf-8") != text:
                    raise EpubIngestError(f"Generated chapter {name} has been edited; nothing overwritten.")
        except (OSError, ValueError) as error:
            if isinstance(error, EpubIngestError):
                raise
            raise EpubIngestError(f"Cannot verify existing EPUB conversion: {error}") from error

    if destination.exists() or destination.is_symlink():
        verify_existing()
    else:
        temporary = Path(tempfile.mkdtemp(prefix=".epub-", dir=parent))
        try:
            for filename, text in texts.items():
                (temporary / filename).write_text(text, encoding="utf-8")
            (temporary / "book.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
            )
            try:
                os.rename(temporary, destination)
            except OSError:
                if not destination.exists():
                    raise
                verify_existing()
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
    return {
        "directory": destination, "manifest": manifest,
        "chapter_paths": [destination / chapter["file"] for chapter in chapters],
        "warnings": book.warnings,
    }
