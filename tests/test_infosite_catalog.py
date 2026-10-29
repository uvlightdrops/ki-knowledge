"""Stored-block catalogs must not extract files or initialize databases."""

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from ki_knowledge.data_layout import DataLayout
from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.knowledge.models import KnowledgeBlockRecord, KnowledgeSource
from ki_knowledge.services.data_source_service import CanonicalDataSourceService
from ki_knowledge.services.infosite_catalog import InfoSiteBlockReader


@pytest.fixture
def catalog(tmp_path):
    layout = DataLayout(tmp_path, version=3)
    project = SimpleNamespace(
        id=1, title="Project", domain="alpha", working_title="book",
        source_directory=str(tmp_path / "source"), sync_status="completed",
    )
    source_id = CanonicalDataSourceService.from_infosite_project(project).source_id
    store = KnowledgeStore(layout.block_store_db_path())
    store.upsert_source(KnowledgeSource(source_id, "infosite", "Project", "/output"))
    for index in range(2):
        store.upsert_source(KnowledgeSource("other-project", "infosite", "Other", "/other"))
        store.upsert_record(KnowledgeBlockRecord(
            block_id=f"b{index}", source_id=source_id, block_type="paragraph",
            title=f"Stored {index}", content="Published text", order_index=index,
            metadata={"source_document": "book.md"},
        ))
    store.upsert_record(KnowledgeBlockRecord(
        block_id="other", source_id="other-project", block_type="paragraph",
        title="Other", content="Not part of this project",
    ))
    return layout, project


def test_catalog_uses_stored_records_and_does_not_initialize(catalog, monkeypatch):
    layout, project = catalog
    path = layout.block_store_db_path()
    before = path.read_bytes()

    def forbidden(*args, **kwargs):
        raise AssertionError("Catalog must not initialize a store")

    monkeypatch.setattr(KnowledgeStore, "_init_schema", forbidden)
    result = InfoSiteBlockReader(layout).read(project)
    assert [block.block_id for block in result["blocks"]] == ["b0", "b1"]
    assert result["stats"] == {
        "total_blocks": 2, "total_files": 1, "sections": 0, "subsections": 0,
        "subsubsections": 0, "paragraphs": 2, "type_counts": {"paragraph": 2},
    }
    assert path.read_bytes() == before
    assert not Path(project.source_directory).exists()


def test_read_only_store_rejects_writes(catalog):
    layout, _ = catalog
    store = KnowledgeStore(layout.block_store_db_path(), read_only=True)
    assert len(store.list_records()) == 3
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        store.upsert_source(KnowledgeSource("new", "infosite", "New", "/new"))


def test_missing_store_is_an_error_not_an_empty_initialized_store(tmp_path):
    layout = DataLayout(tmp_path / "missing", version=3)
    project = SimpleNamespace(title="Project", source_directory="/source", domain="alpha")
    with pytest.raises(sqlite3.OperationalError):
        InfoSiteBlockReader(layout).read(project)
    assert not layout.root.exists()


def test_invalid_schema_is_not_reported_as_zero_blocks(tmp_path):
    layout = DataLayout(tmp_path, version=3)
    path = layout.block_store_db_path()
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE unrelated (id INTEGER)")
    before = path.read_bytes()
    project = SimpleNamespace(title="Project", source_directory="/source", domain="alpha")
    with pytest.raises(sqlite3.OperationalError, match="knowledge_blocks"):
        InfoSiteBlockReader(layout).read(project)
    assert path.read_bytes() == before
