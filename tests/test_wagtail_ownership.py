"""Verify ownership against a migrated in-memory DB in a separate process."""

from pathlib import Path
import subprocess
import sys


def test_catalog_and_editorial_ownership(tmp_path):
    result = subprocess.run(
        [sys.executable, "-c", """
import runpy, sys
runpy.run_path(sys.argv[1])["_exercise_ownership"](sys.argv[2])
""", str(Path(__file__).resolve()), str(tmp_path)],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _exercise_ownership(directory):
    import os
    from unittest.mock import patch

    os.environ["DJANGO_SETTINGS_MODULE"] = "ki_knowledge.django_site.settings"
    from django.conf import settings
    settings.DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
    settings.WAGTAILSEARCH_BACKENDS = {"default": {"BACKEND": "wagtail.search.backends.dummy"}}
    import django
    django.setup()

    from django.core.management import call_command, CommandError
    from django.db import connection
    from django.template.loader import render_to_string
    from django.test import RequestFactory
    from wagtail.models import Page, Revision, Site

    from ki_knowledge.data_layout import DataLayout
    from ki_knowledge.django_site.infosite_models import (
        GeneratedDocument, InfoSiteProject, SourceDocument,
    )
    from ki_knowledge.integrations.knowledge_store import KnowledgeStore
    from ki_knowledge.knowledge.models import KnowledgeBlockRecord, KnowledgeSource
    from ki_knowledge.services.data_source_service import CanonicalDataSourceService
    from ki_knowledge.services.output_registry import (
        register_generated_documents, register_refined_document,
    )
    from ki_knowledge.wagtail_cms import models
    from ki_knowledge.wagtail_cms.wagtail_hooks import (
        GeneratedDocumentViewSet, SourceDocumentViewSet,
    )

    call_command("migrate", verbosity=0, interactive=False, run_syncdb=True)
    root = Path(directory)
    layout = DataLayout(root, version=3)
    project = InfoSiteProject.objects.create(title="Project", source_directory=str(root / "source"))
    source = SourceDocument.objects.create(
        project=project, file_path="input.md", import_status="imported", imported=True,
        review_status="approved", editor_notes="Source review",
    )
    source_id = CanonicalDataSourceService.from_infosite_project(project).source_id
    store = KnowledgeStore(layout.block_store_db_path())
    store.upsert_source(KnowledgeSource(source_id, "infosite", "Project", "/output"))
    store.upsert_record(KnowledgeBlockRecord(
        "block", source_id, "paragraph", "Stored title", "Stored content",
        metadata={"source_document": "book.md"},
    ))
    # A separate global store is not the InfoSite extraction store.
    KnowledgeStore(layout.knowledge_db_path())
    call_command("setup_wagtail_cms", verbosity=0)
    pages = Page.objects.count()
    revisions = Revision.objects.count()
    call_command("setup_wagtail_cms", verbosity=0)
    assert Page.objects.count() == pages
    assert Revision.objects.count() == revisions
    index = models.DataSourceIndexPage.objects.get()
    block_index = models.KnowledgeBlockIndexPage.objects.get()
    detail = models.KnowledgeBlockDetailPage.objects.get(infosite_project_id=project.pk)
    detail.editorial_notes = "Editorial page notes"
    detail.save()
    fresh = InfoSiteProject.objects.create(title="Later", source_directory=str(root / "later"))
    request = RequestFactory().get("/")

    def forbid_writes(execute, sql, params, many, context):
        assert sql.lstrip().upper().startswith("SELECT"), sql
        return execute(sql, params, many, context)

    before = layout.block_store_db_path().read_bytes()
    with patch.object(models.DataLayout, "from_config", return_value=layout):
        with connection.execute_wrapper(forbid_writes):
            sources = index.get_context(request)["data_sources"]
            entries = block_index.get_context(request)["knowledge_projects"]
            context = detail.get_context(request)
            assert context["stats"]["total_blocks"] == 1
            assert context["blocks"][0].content == "Stored content"
            assert context["block_error"] == ""
    assert Page.objects.count() == pages
    assert Revision.objects.count() == revisions
    assert layout.block_store_db_path().read_bytes() == before
    assert not (root / "source").exists()
    assert next(item for item in sources if item["project"].id == fresh.pk)["detail_page"] is None
    assert next(item for item in entries if item["project"].id == project.pk)["block_count"] == 1
    assert next(item for item in entries if item["project"].id == fresh.pk)["block_count"] == 0

    # Live reads reflect the block store, not a copied page body or source reparse.
    store.upsert_record(KnowledgeBlockRecord(
        "block", source_id, "paragraph", "Updated title", "Updated content",
        metadata={"source_document": "book.md"},
    ))
    with patch.object(models.DataLayout, "from_config", return_value=layout):
        assert detail.get_context(request)["blocks"][0].content == "Updated content"
        detail.refresh_from_db()
        assert detail.editorial_notes == "Editorial page notes"
        with patch.object(models.InfoSiteBlockReader, "read", side_effect=OSError("unavailable")):
            context = detail.get_context(request)
            assert context["block_error"] and context["stats"] == {}
            html = render_to_string(detail.get_template(request), context)
            assert 'role="alert"' in html
            broken = block_index.get_context(request)["knowledge_projects"]
            assert all(item["block_count"] is None and item["block_error"] for item in broken)

    # Draft detail pages are never published or linked by reading the index.
    detail.unpublish()
    with patch.object(models.DataLayout, "from_config", return_value=layout):
        entry = next(
            item for item in block_index.get_context(request)["knowledge_projects"]
            if item["project"].pk == project.pk
        )
        assert entry["detail_page"] is None
    detail.refresh_from_db()
    assert not detail.live
    call_command("setup_wagtail_cms", verbosity=0)
    assert models.KnowledgeBlockDetailPage.objects.filter(infosite_project_id=fresh.pk).exists()
    detail.refresh_from_db()
    assert not detail.live  # Explicit bootstrap also respects an existing draft.

    assert SourceDocumentViewSet.model is SourceDocument
    assert GeneratedDocumentViewSet.model is GeneratedDocument
    output = root / "output"
    output.mkdir()
    first = output / "first.md"
    second = output / "second.md"
    first.write_text("# First", encoding="utf-8")
    second.write_text("# Second", encoding="utf-8")
    assert register_generated_documents(project, output, iter([source])) == 2
    document = GeneratedDocument.objects.get(project=project, file_path=str(first))
    document.review_status = "approved"
    document.editor_notes = "Editorial output review"
    document.save()
    document.tags.add("curated")
    previous_hash = document.content_hash
    first.write_text("# New content", encoding="utf-8")
    register_generated_documents(project, output, iter([source]))
    document.refresh_from_db()
    assert document.content_hash != previous_hash
    assert document.review_status == "approved" and document.editor_notes == "Editorial output review"
    assert list(document.tags.names()) == ["curated"]
    assert all(row.used_sources.count() == 1 for row in project.generated_documents.all())
    source.refresh_from_db()
    assert source.import_status == "imported" and source.review_status == "approved"
    assert source.editor_notes == "Source review"
    register_refined_document(project, first, "improve")
    document.refresh_from_db()
    assert document.ai_refinement_mode == "improve" and document.review_status == "approved"
    first.unlink()
    try:
        register_refined_document(project, first, "summarize")
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("Missing canonical output must not look synchronized")
    document.refresh_from_db()
    assert document.ai_refinement_mode == "improve"
    Site.objects.all().delete()
    try:
        call_command("setup_wagtail_cms", verbosity=0)
    except CommandError as error:
        assert "No default Wagtail Site" in str(error)
    else:
        raise AssertionError("Failed CMS setup must return an explicit command error")
