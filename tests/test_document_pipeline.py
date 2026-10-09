"""Book pipeline: stage table, derived stages, funnel and overview view."""

from __future__ import annotations

import os
import sqlite3

import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ki_knowledge.django_site.settings")
django.setup()

from django.db.backends.utils import CursorWrapper  # noqa: E402
from django.http import HttpResponse  # noqa: E402
from django.test import RequestFactory  # noqa: E402
from django.urls import reverse  # noqa: E402

from ki_knowledge.django_site import views_pipeline  # noqa: E402
from ki_knowledge.django_site.layout_targets import layout_targets_for_area  # noqa: E402
from ki_knowledge.integrations.document_pipeline import (  # noqa: E402
    DocumentInput,
    DocumentStageStore,
    funnel,
    quality_metrics,
    record_document,
    sync_documents,
)
from ki_knowledge.integrations.knowledge_store import KnowledgeStore  # noqa: E402
from ki_knowledge.integrations.sql_backend import StoreTarget  # noqa: E402


@pytest.fixture(autouse=True)
def _no_database(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("database access is not allowed in this test")

    monkeypatch.setattr(CursorWrapper, "execute", forbidden)
    monkeypatch.setattr(CursorWrapper, "executemany", forbidden)


def _pages_markdown(pages: list[str]) -> str:
    return "\n\n".join(f"## Page {index}\n\n{text}" for index, text in enumerate(pages, start=1)) + "\n"


@pytest.fixture
def stores(tmp_path):
    db = tmp_path / "knowledge.db"
    knowledge = KnowledgeStore(db)
    knowledge.import_markdown_text(
        _pages_markdown(["Ein langer Absatz " * 40, "Noch ein Absatz " * 40]),
        source_path=str(tmp_path / "book.pdf"),
        source_name="book.pdf",
        source_id="pdf:book.pdf",
        source_type="pdf",
    )
    target = StoreTarget.parse(db, schema="knowledge")
    return knowledge, DocumentStageStore(target), target, db


def _documents():
    return [
        DocumentInput("pdf:book.pdf", title="Book", imported=True, pages_total=2, job_status="done"),
        DocumentInput("pdf:broken.pdf", title="Broken", job_status="failed", job_error="Stream has ended"),
    ]


def test_quality_metrics_flags_scans_empty_pages_and_running_headers():
    good = quality_metrics(2, {"Page 1": 2000, "Page 2": 1800}, ["a", "b", "c", "d", "e"])
    assert good["flags"] == [] and good["chars_per_page"] == 1900 and good["empty_page_ratio"] == 0.0

    scan = quality_metrics(10, {"Page 1": 50, "Page 2": 40}, ["Kopf"] * 6)
    assert set(scan["flags"]) == {"needs_ocr", "many_empty_pages", "boilerplate"}
    assert scan["empty_page_ratio"] == 0.8


def test_sync_derives_stages_keeps_worker_results_and_prunes(stores):
    _knowledge, stage_store, target, _db = stores

    result = sync_documents(stage_store, target, "demo", _documents())

    assert result["ingest:done"] == 1 and result["ingest:failed"] == 1
    by_id = {doc.source_id: doc for doc in stage_store.documents("demo")}
    book, broken = by_id["pdf:book.pdf"], by_id["pdf:broken.pdf"]
    assert book.effective_status("ingest") == "done"
    assert book.effective_status("quality") == "done"
    assert book.state("quality").metrics["pages_with_text"] == 2
    assert book.effective_status("embeddings") == "pending"
    assert broken.effective_status("ingest") == "failed" and "Stream" in broken.state("ingest").error
    assert broken.effective_status("quality") == "pending"

    stage_store.record("pdf:book.pdf", "structure", domain="demo", status="done", metrics={"chapters": 3})
    sync_documents(stage_store, target, "demo", _documents())
    assert stage_store.documents("demo")[0].state("structure").metrics == {"chapters": 3}

    removed = sync_documents(stage_store, target, "demo", _documents()[:1])["removed"]
    assert removed == 1 and [doc.source_id for doc in stage_store.documents("demo")] == ["pdf:book.pdf"]


def test_record_document_updates_one_book_without_pruning_others(stores):
    _knowledge, stage_store, target, _db = stores
    sync_documents(stage_store, target, "demo", _documents())

    record_document(target, "demo", DocumentInput("pdf:new.pdf", job_status="failed", job_error="kaputt"))

    ids = {doc.source_id for doc in stage_store.documents("demo")}
    assert ids == {"pdf:book.pdf", "pdf:broken.pdf", "pdf:new.pdf"}


def test_funnel_counts_books_blocks_and_stale_versions(stores):
    knowledge, stage_store, target, db = stores
    block_ids = [record.block_id for record in knowledge.list_records(source_id="pdf:book.pdf")]
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO knowledge_embeddings (block_id, model, vector_json, created_at) VALUES (?, 'm', '[]', 'now')",
            (block_ids[0],),
        )
    sync_documents(stage_store, target, "demo", _documents(), linked_record_ids=set(block_ids))
    stage_store.record("pdf:book.pdf", "review", domain="demo", status="done", version=0)

    stages = {item["key"]: item for item in funnel(stage_store.documents("demo"))}

    assert stages["ingest"]["done"] == 1 and stages["ingest"]["percent"] == 50.0
    assert stages["embeddings"]["statuses"]["partial"] == 1
    assert stages["embeddings"]["blocks_done"] == 1 and stages["embeddings"]["blocks"] == len(block_ids)
    assert stages["terms"]["blocks_percent"] == 100.0
    assert stages["review"]["statuses"]["stale"] == 1 and stages["review"]["done"] == 0


def test_pipeline_route_is_in_knowledge_navigation():
    assert reverse("book-pipeline") == "/knowledge/pipeline/"
    assert any(target.path == "/knowledge/pipeline/" for target in layout_targets_for_area("knowledge"))


def test_pipeline_view_filters_by_stage_status_and_flag(stores, monkeypatch):
    _knowledge, stage_store, target, _db = stores
    sync_documents(stage_store, target, "demo", _documents())
    documents = stage_store.documents("demo")
    monkeypatch.setattr(views_pipeline, "_active_semantic_domain", lambda request: "demo")
    monkeypatch.setattr(
        views_pipeline,
        "book_pipeline_overview",
        lambda domain: {"documents": documents, "funnel": funnel(documents), "last_updated": "2026-10-08T20:00:00"},
    )
    calls = []

    def fake_render(request, template, context):
        calls.append(context)
        return HttpResponse("ok")

    monkeypatch.setattr(views_pipeline, "render", fake_render)
    monkeypatch.setattr(views_pipeline, "reverse", lambda name, args=None: f"/{name}/" + "/".join(args or []))

    views_pipeline.book_pipeline_view(RequestFactory().get("/knowledge/pipeline/?stage=ingest&status=failed"))
    views_pipeline.book_pipeline_view(RequestFactory().get("/knowledge/pipeline/?sort=progress"))
    views_pipeline.book_pipeline_view(RequestFactory().get("/knowledge/pipeline/?flag=needs_ocr"))

    failed, by_progress, ocr = calls
    assert [row["source_id"] for row in failed["rows"]] == ["pdf:broken.pdf"]
    assert failed["rows"][0]["error"] and failed["active_stage"] == "Text importiert"
    assert [row["source_id"] for row in by_progress["rows"]] == ["pdf:book.pdf", "pdf:broken.pdf"]
    assert by_progress["rows"][0]["records_url"] and not by_progress["rows"][1]["detail_url"]
    assert ocr["total"] == 0
