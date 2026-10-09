from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.integrations.pdf_ingest import reflow_page_text

PAGE = """Erstes Kapitel
Durch das Selbstbewußtsein bezeichnet sich der Mensch als ein selbständiges, von
allem übrigen abgeschlossenes Wesen, als «Ich». Im «Ich» faßt der Mensch alles
zusammen, was er als leibliche und seelische Wesenheit erlebt. Die Philo-
sophie spricht hier vom Ich.
Ein neuer Absatz beginnt hier und ist so lang wie eine normale Zeile im Satz,
und er endet kurz.
# kein Markdown"""


def test_reflow_splits_paragraphs_and_joins_hyphenation():
    paragraphs = reflow_page_text(PAGE)
    assert paragraphs[0] == "Erstes Kapitel"
    assert paragraphs[1].startswith("Durch das Selbstbewußtsein")
    assert "Philosophie spricht hier vom Ich." in paragraphs[1]
    assert paragraphs[2].startswith("Ein neuer Absatz") and paragraphs[2].endswith("endet kurz.")
    assert paragraphs[3] == "\\# kein Markdown"


def test_replace_import_removes_stale_blocks(tmp_path):
    store = KnowledgeStore(tmp_path / "store.sqlite")
    kwargs = {"source_path": "/books/a.pdf", "source_id": "pdf:a", "source_type": "pdf"}
    store.import_markdown_text("## Page 1\n\nganze Seite als ein Block", **kwargs)
    store.import_markdown_text("## Page 1\n\nErster Absatz\n\nZweiter Absatz", replace=True, **kwargs)
    records = store.list_records(source_id="pdf:a")
    assert sorted(record.content for record in records) == ["Erster Absatz", "Zweiter Absatz"]
    assert {record.metadata.get("page") for record in records} == {1}


def test_repeated_footer_lines_are_dropped():
    from ki_knowledge.integrations.pdf_ingest import _drop_repeated_lines

    words = "Alpha Beta Gamma Delta Epsilon Zeta Eta Theta Iota Kappa Lambda My".split()
    pages = [(n, f"Text über {words[n - 1]} um-\nCopyright Verlag Buch: 4 Seite: {n // 10} {n % 10}\n{n}") for n in range(1, 13)]
    cleaned = _drop_repeated_lines(pages)
    assert all(text == f"Text über {words[n - 1]} um-" for n, text in cleaned)
