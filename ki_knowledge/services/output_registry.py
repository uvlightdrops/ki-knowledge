"""Bridges the InfoSite generation/refinement pipelines with the Wagtail-
editable GeneratedDocument snippet layer.

The generator/refinement code only knows about the filesystem (it writes
markdown files under data_out/); this module is the single place that turns
"a file was written" into "Wagtail/the editorial layer knows about it",
without every pipeline call site needing to know about Django models
directly.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable, Optional


def _hash_file(path: Path) -> str:
    """Return a short content hash for change detection, best-effort."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return ""


def register_generated_documents(
    project,
    output_dir: Path,
    used_sources: Optional[Iterable] = None,
    ai_refinement_mode: str = "",
) -> int:
    """Upsert a GeneratedDocument row for every markdown file under output_dir.

    Skips the `_originals/` backup tree (that mirrors input, not output).
    Called right after InfoSiteGeneratorService.generate_infosite() succeeds.

    Returns the number of entries created/updated.
    """
    from ki_knowledge.django_site.infosite_models import GeneratedDocument

    count = 0
    for md_path in sorted(Path(output_dir).glob("**/*.md")):
        if "_originals" in md_path.parts:
            continue
        doc, _created = GeneratedDocument.objects.update_or_create(
            project=project,
            file_path=str(md_path),
            defaults={
                "content_hash": _hash_file(md_path),
                "ai_refinement_mode": ai_refinement_mode,
            },
        )
        if used_sources is not None:
            doc.used_sources.set(list(used_sources))
        count += 1
    return count


def register_refined_document(project, file_path: Path, refinement_mode: str) -> None:
    """Upsert a single GeneratedDocument entry after an AI-refinement write.

    Called from infosite_ai_refine_apply right after a refined file is
    written to disk.
    """
    from ki_knowledge.django_site.infosite_models import GeneratedDocument

    path = Path(file_path)
    GeneratedDocument.objects.update_or_create(
        project=project,
        file_path=str(path),
        defaults={
            "content_hash": _hash_file(path),
            "ai_refinement_mode": refinement_mode,
        },
    )
