"""Tests for markdown knowledge block extraction and graphing."""

from pathlib import Path

from ki_knowledge.integrations.pdf_batch import PDFBatchProcessor
from ki_knowledge.django_site.services import source_in_domain
from ki_knowledge.integrations.block_embeddings import BlockEmbeddingService, SimpleBagOfWordsEmbeddingBackend
from ki_knowledge.integrations.knowledge_graph import KnowledgeGraph
from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.integrations.markdown_blocks import MarkdownBlockParser
from ki_knowledge.knowledge.models import KnowledgeArtifact


def test_parser_extracts_headings_and_paragraphs(tmp_path: Path):
    source = tmp_path / "notes.md"
    source.write_text("# Intro\n\nHello world\n\n## Details\n\nMore text\n", encoding="utf-8")

    parser = MarkdownBlockParser()
    blocks = parser.parse_markdown(source.read_text(encoding="utf-8"), source_path=str(source))

    assert any(block.block_type == "heading" and block.content == "Intro" for block in blocks)
    assert any(block.block_type == "paragraph" and "Hello world" in block.content for block in blocks)
    assert any(block.block_type == "heading" and block.content == "Details" for block in blocks)


def test_store_imports_blocks_and_relations(tmp_path: Path):
    db_path = tmp_path / "knowledge.sqlite"
    store = KnowledgeStore(db_path)
    blocks = store.import_markdown_text(
        "# Topic\n\nAlpha text\n",
        source_path="/tmp/topic.md",
        source_name="topic.md",
    )

    assert len(blocks) >= 2
    relation_id = store.add_relation(blocks[0].id, blocks[1].id, relation="related_to")
    assert relation_id
    relations = store.list_relations(blocks[0].id)
    assert len(relations) >= 1


def test_graph_rebuilds_neighbors(tmp_path: Path):
    db_path = tmp_path / "graph.sqlite"
    store = KnowledgeStore(db_path)
    blocks = store.import_markdown_text(
        "# Topic\n\nAlpha text\n\n## Details\n\nBeta text\n",
        source_path="/tmp/graph.md",
        source_name="graph.md",
    )
    store.add_relation(blocks[0].id, blocks[1].id, relation="related_to")

    graph = KnowledgeGraph(str(db_path))
    stats = graph.rebuild_from_store(store)
    neighbors = graph.neighbors(blocks[0].id)

    assert stats["nodes"] > 0
    assert stats["edges"] > 0
    assert any(n.relation == "related_to" for n in neighbors)


def test_embeddings_are_built(tmp_path: Path):
    db_path = tmp_path / "embeddings.sqlite"
    store = KnowledgeStore(db_path)
    store.import_markdown_text("# Sample\n\nThis is a sample block\n", source_path="/tmp/sample.md")

    count = BlockEmbeddingService(SimpleBagOfWordsEmbeddingBackend()).build_embeddings(store)
    assert count >= 1
    assert store.get_embedding(store.list_blocks()[0].id) is not None


def test_store_deletes_records_and_artifacts(tmp_path: Path):
    db_path = tmp_path / "delete.sqlite"
    store = KnowledgeStore(db_path)
    blocks = store.import_markdown_text("# Topic\n\nAlpha text\n", source_path="/tmp/topic.md", source_name="topic.md")

    artifact = KnowledgeArtifact(
        artifact_id="artifact:demo",
        artifact_type="summary_note",
        source_id="markdown:/tmp/topic.md",
        source_block_ids=[blocks[0].id],
        content="Example summary",
    )
    store.upsert_artifact(artifact)

    assert store.delete_record(blocks[0].id) is True
    assert store.get_record(blocks[0].id) is None
    assert store.delete_artifact("artifact:demo") is True
    assert store.get_artifact("artifact:demo") is None


def test_source_in_domain_includes_pdf_sources(tmp_path: Path, monkeypatch):
    domain = "demo-domain"
    data_root = tmp_path / "data"
    monkeypatch.setenv("KNOWLEDGE_DATA_ROOT", str(data_root))
    domain_root = data_root / "pdf" / domain
    domain_root.mkdir(parents=True)
    pdf_path = domain_root / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    class DummySource:
        location = str(pdf_path)
        source_id = "pdf:sample.pdf"

    assert source_in_domain(DummySource(), domain=domain) is True


def test_empty_pdf_import_fails_without_records_or_artifacts(tmp_path: Path, monkeypatch):
    pdf_db = tmp_path / "pdf.sqlite"
    knowledge_db = tmp_path / "knowledge.sqlite"
    monkeypatch.setenv("KNOWLEDGE_DB_PATH", str(knowledge_db))

    processor = PDFBatchProcessor(pdf_db)
    pdf_file = tmp_path / "empty.pdf"
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with pdf_file.open("wb") as handle:
        writer.write(handle)

    job_id = processor.create_job(pdf_file, domain="demo-domain")
    result = processor.process_job(job_id)

    assert result["status"] == "failed"
    assert "no extractable text" in result["error"].lower()
    job = processor.get_job(job_id)
    assert job is not None and job.status == "failed"
