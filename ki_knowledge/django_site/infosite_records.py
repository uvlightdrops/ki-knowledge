"""Create InfoSite project inputs from imported knowledge records."""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Iterable
from pathlib import Path

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from ki_knowledge.data_layout import MARKDOWN, DataLayout
from ki_knowledge.knowledge.models import KnowledgeBlockRecord, KnowledgeSource
from ki_knowledge.knowledge.record_export import records_to_markdown

from .infosite_models import InfoSiteProject, SourceDocument


def source_project_working_title(source_id: str, source_title: str) -> str:
    """Return a stable, source-specific working title within the model limit."""
    title_slug = slugify(source_title) or "source"
    suffix = hashlib.sha256(source_id.encode("utf-8")).hexdigest()[:8]
    return f"{title_slug[:90].rstrip('-')}-{suffix}"


def find_source_infosite_project(
    *, domain: str, source_id: str, source_title: str
) -> InfoSiteProject | None:
    working_title = source_project_working_title(source_id, source_title)
    return InfoSiteProject.objects.filter(domain=domain, working_title=working_title).first()


def create_infosite_project_from_records(
    *,
    source: KnowledgeSource,
    records: Iterable[KnowledgeBlockRecord],
    domain: str,
    data_root: str | Path,
) -> tuple[InfoSiteProject, bool]:
    """Persist a markdown source and register it as the first document of a project."""
    records = list(records)
    if not records:
        raise ValueError("Für diese Quelle gibt es keine Records, aus denen eine InfoSite erstellt werden kann.")

    project_title = source.title.strip() or Path(source.location).stem or "InfoSite"
    working_title = source_project_working_title(source.source_id, project_title)
    layout = DataLayout(data_root)
    source_dir = layout.source_dir(MARKDOWN, domain, working_title)
    source_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{slugify(project_title)[:120].rstrip('-') or 'source'}-records.md"
    output_path = source_dir / filename
    existing_project = find_source_infosite_project(
        domain=domain,
        source_id=source.source_id,
        source_title=project_title,
    )
    if existing_project:
        return existing_project, False

    if output_path.exists():
        stem = output_path.stem
        suffix = 2
        while output_path.exists():
            output_path = source_dir / f"{stem}-{suffix}.md"
            suffix += 1

    content = records_to_markdown(records, title=project_title)
    temp_path = None
    registered = False
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=source_dir,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temp_path = Path(temporary_file.name)
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temp_path, output_path)

        now = timezone.now()
        with transaction.atomic():
            project = InfoSiteProject.objects.create(
                title=project_title,
                domain=domain,
                working_title=working_title,
                description=f"Automatisch aus der importierten Quelle {source.title} erstellt.",
                source_directory=str(source_dir),
                sync_status="completed",
                last_sync_at=now,
            )
            SourceDocument.objects.create(
                project=project,
                file_path=str(output_path),
                file_type="markdown",
                title=project_title,
                file_size=output_path.stat().st_size,
                modified_at=now,
                import_status="discovered",
            )
        registered = True
        return project, True
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        if not registered:
            output_path.unlink(missing_ok=True)
