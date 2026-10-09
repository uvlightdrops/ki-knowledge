from __future__ import annotations

from types import SimpleNamespace

from ki_knowledge.integrations import structure_eval as se
from ki_knowledge.integrations.block_embedder import document_text, embed_pending_blocks, model_key, query_text
from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.integrations.mixed_ingest import TEI_KIND, UNSUPPORTED_KIND, classify_file
from ki_knowledge.integrations.sql_backend import StoreTarget
from ki_knowledge.integrations.tei_ingest import is_tei_file, normalize_text, parse_tei

TEI = """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
<teiHeader><fileDesc>
  <titleStmt><title type="main">Versuch über Pflanzen</title><author><persName><surname>Goethe</surname></persName></author></titleStmt>
  <publicationStmt><availability><licence target="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA</licence></availability></publicationStmt>
  <sourceDesc><biblFull><publicationStmt><date type="publication">1790</date></publicationStmt></biblFull></sourceDesc>
</fileDesc></teiHeader>
<text>
<front><pb n="I"/><titlePage><docTitle><titlePart>Versuch über Pflanzen</titlePart></docTitle></titlePage>
<pb n="II"/><div type="contents"><head>Inhalt.</head>
<list><item>Einleitung. 1</item><item>I. Von den Samenblättern. 2</item><item>II. Vom Stengel. 3</item><item>III. Vom Kelch. 3</item></list></div>
</front>
<body>
<pb n="1"/><div n="1"><head>Einleitung.</head>
<div n="2"><head>§. 1.</head><p>Ein jeder, der das Wachs-<lb/>thum der Pflanzen beob¬<lb/>achtet, wird bemerken.<note>Fußnote</note></p>
<fw type="sig">A</fw></div></div>
<pb n="2"/><div n="1"><head>I. Von den Samenblättern.</head><p>Die ſamenblätter ſind einfach.</p></div>
<pb n="3"/><div n="1"><head>II. Vom Stengel.</head><p>Der Stengel waͤchst.</p></div>
<div n="1"><head>III. Vom Kelch.</head><p>Der Kelch entsteht, wenn die Blätter sich zusammenziehen.</p></div>
</body></text></TEI>
"""


def _write(tmp_path, text=TEI, name="werk.TEI-P5.xml"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_tei_is_sniffed_by_content(tmp_path):
    tei = _write(tmp_path)
    other = _write(tmp_path, "<root><a/></root>", "plain.xml")
    assert is_tei_file(tei) and classify_file(tei) == TEI_KIND
    assert not is_tei_file(other) and classify_file(other) == UNSUPPORTED_KIND


def test_parse_tei_pages_text_and_reference_outline(tmp_path):
    document = parse_tei(_write(tmp_path))
    assert (document.title, document.author, document.year) == ("Versuch über Pflanzen", "Goethe", "1790")
    assert "creativecommons" in document.licence
    markdown = document.to_markdown()
    assert "Wachsthum der Pflanzen beobachtet" in markdown
    assert "Fußnote" not in markdown and "\nA\n" not in markdown
    assert "Die samenblätter sind einfach." in markdown
    assert normalize_text("waͤchst") == "wächst"
    titles = [(section.title, section.level) for section in document.sections]
    assert titles == [("Einleitung.", 1), ("§. 1.", 2), ("I. Von den Samenblättern.", 1), ("II. Vom Stengel.", 1), ("III. Vom Kelch.", 1)]
    pages = markdown.split("## Page ")
    for section in document.sections:
        assert section.title.split()[0] in pages[section.page_index]


def _records(document):
    records = []
    for page_index, page in enumerate(document.pages, start=1):
        for order, paragraph in enumerate(page.paragraphs):
            records.append(SimpleNamespace(block_type="paragraph", metadata={"page": page_index}, title=f"Page {page_index}",
                                           content=paragraph, order_index=page_index * 100 + order))
    return records


def test_detectors_find_reference_outline_and_flat_text_needs_toc(tmp_path):
    document = parse_tei(_write(tmp_path))
    reference = [section.to_dict() for section in document.sections]
    pages = se.pages_from_records(_records(document))
    heading_eval = se.evaluate(se.detect(pages, "heading"), reference)
    assert heading_eval.recall == 1.0
    flat = se.pages_from_records(_records(document), flat=True)
    assert se.evaluate(se.detect(flat, "heading"), reference).recall < heading_eval.recall
    toc_eval = se.evaluate(se.detect(flat, "toc"), reference)
    assert toc_eval.precision == 1.0
    assert toc_eval.titled_recall == 1.0  # all worded chapters; only "§. 1." is missing
    assert toc_eval.titled_reference == 4


def test_similarity_accepts_heading_with_subtitle_and_rejects_others():
    assert se.similarity("Erste Vorlesung.", "Erste Vorlesung. Ueber den absoluten Begriff der Wissenschaft") >= 0.8
    assert se.similarity("§. 1.", "§. 12.") < 0.8
    assert se.similarity("II. Vom Stengel.", "III. Vom Stengel.") < 0.8
    assert se.similarity("Zweite Vorlesung", "Zweyte Vorlesung.") >= 0.8
    assert not se.is_titled("§. 12.") and not se.is_titled("IV.") and se.is_titled("IV. Bildung des Kelches")


class _FakeEmbedder:
    def __init__(self, fail_on: str = ""):
        self.fail_on = fail_on
        self.calls: list[list[str]] = []

    def embed_many(self, texts):
        self.calls.append(texts)
        if any(self.fail_on and self.fail_on in text for text in texts):
            raise RuntimeError("boom")
        return [[float(len(text)), 1.0, 0.0] for text in texts]


def test_embed_pending_blocks_is_resumable_and_isolates_failures(tmp_path):
    store = KnowledgeStore(StoreTarget.sqlite(tmp_path / "store.db"))
    store.import_markdown_text("# T\n\nErster Absatz.\n\nZweiter Absatz.\n\nKaputter Absatz.\n", source_path="a.md", source_id="s1")
    embedder = _FakeEmbedder(fail_on="Kaputter")
    run = embed_pending_blocks(store, embedder, ["s1"], model="nomic-embed-text:latest", batch_size=10)
    assert (run.embedded, run.failed, run.model) == (2, 1, "nomic-embed-text")
    assert all(text.startswith("search_document: ") for text in embedder.calls[0])
    assert store.embedding_counts(["s1"], "nomic-embed-text") == {"blocks": 3, "embedded": 2}
    again = embed_pending_blocks(store, _FakeEmbedder(), ["s1"], model="nomic-embed-text")
    assert again.embedded == 1
    hits = store.similar_blocks([16.0, 1.0, 0.0], model="nomic-embed-text", source_ids=["s1"], limit=1)
    assert hits and hits[0][1] > 0.99
    assert query_text("Blatt", "nomic-embed-text") == "search_query: Blatt"
    assert model_key("nomic-embed-text:latest") == "nomic-embed-text"
    assert document_text(SimpleNamespace(title="Page 3", content="x"), "other") == "x"
