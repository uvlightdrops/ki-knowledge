"""Tests for record browsing and InfoSite composition from the shared record model."""

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from ki_knowledge.data_layout import MARKDOWN, DataLayout
from ki_knowledge.django_site.record_browser import group_records
from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.knowledge.record_export import records_to_markdown
from ki_knowledge.services.block_extractor import KnowledgeBlockData
from ki_knowledge.services.block_storage import InfoSiteBlockStorage
from ki_knowledge.services.discovery import FileInfo
from ki_knowledge.services.generator import InfoSiteGeneratorService


def test_record_groups_follow_document_context_in_sequence(tmp_path: Path):
    store = KnowledgeStore(tmp_path / "knowledge.sqlite")
    store.import_markdown_text(
        "# Intro\n\nFirst passage.\n\n## Details\n\nSecond passage.\n",
        source_path="/tmp/original.md",
        source_id="markdown:original",
    )

    records = store.list_records(source_id="markdown:original")
    groups = group_records(records)

    assert [group["title"] for group in groups] == ["Intro", "Intro / Details"]
    assert [item["content"] for item in groups[0]["records"]] == ["First passage."]
    assert groups[1]["records"][0]["type"] == "text"


def test_infosite_generates_from_records_using_format_neutral_contract(tmp_path: Path):
    layout_marker = tmp_path / ".layout-version"
    layout_marker.write_text("2\n", encoding="utf-8")
    layout = DataLayout(tmp_path)
    source_dir = layout.source_dir(MARKDOWN, "demo", "from-records")
    source_dir.mkdir(parents=True)

    store = KnowledgeStore(tmp_path / "knowledge.sqlite")
    store.import_markdown_text(
        "# Overview\n\nA complete passage from a source.\n\n## Details\n\nA second passage.\n",
        source_path="/tmp/source.md",
        source_id="pdf:mix/books/source.pdf",
        source_type="pdf",
    )
    records = store.list_records(source_id="pdf:mix/books/source.pdf")
    markdown = records_to_markdown(records, title="Source document")
    source_file = source_dir / "source-records.md"
    source_file.write_text(markdown, encoding="utf-8")
    source_doc = FileInfo(
        path=source_file,
        name=source_file.name,
        file_type="md",
        size=source_file.stat().st_size,
        modified_at=datetime.now(timezone.utc),
    )

    result = InfoSiteGeneratorService(tmp_path).generate_infosite(
        domain="demo",
        working_title="from-records",
        source_docs=[source_doc],
    )

    generated_file = result.output_dir / source_file.name
    assert result.success, result.message
    assert generated_file.exists()
    generated = generated_file.read_text(encoding="utf-8")
    assert "## Overview" in generated and "A complete passage from a source." in generated
    assert "## Overview / Details" in generated and "A second passage." in generated


def test_infosite_block_storage_persists_content_not_heading_records(tmp_path: Path):
    store = KnowledgeStore(tmp_path / "infosite-blocks.sqlite")
    project = SimpleNamespace(
        id=7,
        domain="demo",
        title="Demo",
        working_title="record-export",
        source_directory=str(tmp_path),
        output_dir="",
        version_count=0,
        created_at=None,
    )
    heading = KnowledgeBlockData(
        title="Long chapter",
        content="",
        level=1,
        block_type="section",
        order_index=0,
    )
    paragraph = KnowledgeBlockData(
        title="Long passage",
        content="x" * 700,
        level=4,
        block_type="paragraph",
        parent_index=0,
        order_index=1,
    )

    class Extractor:
        def extract_from_directory(self):
            return {"chapter.md": [heading, paragraph]}

    storage = InfoSiteBlockStorage(project, knowledge_store=store)
    storage.extractor = Extractor()

    result = storage.extract_and_store()
    records = storage.get_stored_blocks()

    assert result["blocks_stored"] == 1
    assert len(records) == 1
    assert records[0].record_type == "text"
    assert records[0].path == "chapter.md / Long chapter"
    assert len(records[0].content) == 700
