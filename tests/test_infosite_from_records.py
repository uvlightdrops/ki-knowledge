from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from django.urls import reverse

from ki_knowledge.django_site.infosite_records import create_infosite_project_from_records
from ki_knowledge.django_site.infosite_models import InfoSiteProject, SourceDocument
from ki_knowledge.integrations.knowledge_store import KnowledgeStore


@pytest.mark.django_db
def test_source_records_create_a_registered_infosite_project(tmp_path: Path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / ".layout-version").write_text("2\n", encoding="utf-8")
    store = KnowledgeStore(tmp_path / "knowledge.sqlite")
    source_id = "pdf:mix/books/guide.pdf"
    store.import_markdown_text(
        "# Chapter\n\nA complete source passage.\n",
        source_path="/workspace/mix/books/guide.pdf",
        source_id=source_id,
        source_type="pdf",
    )
    source = store.get_source(source_id)
    assert source is not None
    records = store.list_records(source_id=source_id)

    project, created = create_infosite_project_from_records(
        source=source,
        records=records,
        domain="human-design",
        data_root=data_root,
    )

    document = SourceDocument.objects.get(project=project)
    exported_markdown = Path(document.file_path).read_text(encoding="utf-8")
    assert created
    assert project.sync_status == "completed"
    assert project.working_title
    assert "A complete source passage." in exported_markdown
    assert InfoSiteProject.objects.filter(domain="human-design").count() == 1

    same_project, created_again = create_infosite_project_from_records(
        source=source,
        records=records,
        domain="human-design",
        data_root=data_root,
    )
    assert same_project.id == project.id
    assert not created_again
    assert SourceDocument.objects.filter(project=project).count() == 1


@pytest.mark.django_db(transaction=True)
def test_source_browser_can_create_and_open_an_infosite_project(tmp_path: Path, client):
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / ".layout-version").write_text("2\n", encoding="utf-8")
    store = KnowledgeStore(tmp_path / "knowledge.sqlite")
    source_id = "pdf:mix/books/guide.pdf"
    store.import_markdown_text(
        "# Chapter\n\nA passage to publish.\n",
        source_path="/workspace/mix/books/guide.pdf",
        source_id=source_id,
        source_type="pdf",
    )
    session = client.session
    session["semantic_active_domain"] = "human-design"
    session.save()

    with (
        override_settings(KI_CONFIG=SimpleNamespace(knowledge_data_root=str(data_root))),
        patch("ki_knowledge.django_site.views_data_sources.store", return_value=store),
        patch(
            "ki_knowledge.django_site.views_data_sources.domain_source_ids",
            return_value={source_id},
        ),
    ):
        detail_response = client.get(reverse("source-detail", args=[source_id]))
        assert b"InfoSite-Projekt aus dieser Quelle anlegen" in detail_response.content
        ContentType.objects.clear_cache()

        response = client.post(
            reverse("source-infosite-create"),
            {"source_id": source_id},
        )

    project = InfoSiteProject.objects.get(domain="human-design")
    assert response.status_code == 302
    assert response.url == reverse("infosite:project_detail", args=[project.id])
    assert SourceDocument.objects.filter(project=project).exists()
