from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from ki_knowledge.doc_viewer import DocumentError, make_handler, parse_document, render_page, resolve_path


def write_document(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_block_relations_show_titles_direction_and_metadata(tmp_path):
    source = write_document(tmp_path / "source.md", """---
project: ki-knowledge
status: draft
relations:
  - source: "#example"
    target: "target.md#concept"
    type: extends
    reason: "Ein Beispiel erweitert den Begriff."
---
# Ausgangsdokument
## Ein Beispiel [example]
Ein **Gedanke**.
""")
    target = write_document(tmp_path / "target.md", """---
project: ki-knowledge
---
# Ziel
## Ein Begriff [concept]
Ein Text.
""")
    output = render_page(tmp_path, parse_document(source), [source, target])
    assert "<strong>extends</strong> →" in output
    assert "Ein Begriff (target.md)" in output
    assert "/?file=target.md#concept" in output
    assert "Ein Beispiel erweitert den Begriff." in output
    assert "<strong>Gedanke</strong>" in output
    assert "<dt>status</dt><dd>draft</dd>" in output


def test_untagged_sections_and_headings_inside_fences_are_preserved(tmp_path):
    source = write_document(tmp_path / "doc.md", """---
project: example
---
# Titel
## Abschnitt
```text
## Kein Abschnitt
<a id="example"></a>
```
""")
    document = parse_document(source)
    assert len(document.blocks) == 1
    assert document.blocks[0].block_id is None
    output = render_page(tmp_path, document, [source])
    assert "ohne ID" in output
    assert "## Kein Abschnitt" in output
    assert "&lt;a id=" in output


def test_invalid_metadata_reports_a_specific_error(tmp_path):
    source = write_document(tmp_path / "doc.md", "---\nrelations: invalid\n---\n# Test\n")
    with pytest.raises(DocumentError, match="relations muss eine Liste sein"):
        parse_document(source)


def test_unresolved_relation_is_visible(tmp_path):
    source = write_document(tmp_path / "doc.md", """---
relations:
  - source: "#missing"
    target: "#absent"
    type: reference
---
# Test
## Sichtbar [visible]
Text
""")
    output = render_page(tmp_path, parse_document(source), [source])
    assert "Ausgangsblock nicht gefunden: #missing" in output
    assert "#absent (Block nicht gefunden)" in output


def test_html_and_unsafe_links_are_not_executable(tmp_path):
    source = write_document(tmp_path / "doc.md", """---
project: example
---
# Test
## Beispiel [example]
<script>alert(1)</script>
[click](javascript:alert)
""")
    output = render_page(tmp_path, parse_document(source), [source])
    assert "<script>" not in output
    assert 'href="javascript:' not in output


def test_existing_anchor_and_link_are_preserved_without_duplicate_block_ids(tmp_path):
    source = write_document(tmp_path / "doc.md", """---
project: example
---
# Test
<a id="old-name"></a>
<a id="example"></a>
## Beispiel [example]
[Link](#old-name)
""")
    output = render_page(tmp_path, parse_document(source), [source])
    assert 'id="old-name"' in output
    assert 'href="/?file=doc.md#old-name"' in output
    assert output.count('id="example"') == 1


def test_resolve_path_rejects_traversal_and_external_symlinks(tmp_path):
    root = tmp_path / "docs"
    root.mkdir()
    outside = write_document(tmp_path / "outside.md", "---\n{}\n---\n# Outside")
    (root / "link.md").symlink_to(outside)
    for name in ("../outside.md", "link.md"):
        with pytest.raises(DocumentError, match="nicht verfügbar"):
            resolve_path(root, name)


def test_local_http_server_serves_documents_read_only(tmp_path):
    doc = write_document(tmp_path / "doc.md", "---\nproject: test\n---\n# Test\n## Inhalt [content]\nText.")
    original = doc.read_bytes()
    with ThreadingHTTPServer(("127.0.0.1", 0), make_handler(tmp_path)) as server:
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            with urlopen(f"http://127.0.0.1:{server.server_port}/?file=doc.md") as response:
                assert response.status == 200
                assert "Inhalt" in response.read().decode()
            with pytest.raises(HTTPError) as error:
                urlopen(f"http://127.0.0.1:{server.server_port}/?file=../outside.md")
            assert error.value.code == 400
            with pytest.raises(HTTPError) as error:
                urlopen(Request(f"http://127.0.0.1:{server.server_port}/", data=b"change", method="POST"))
            assert error.value.code == 501
        finally:
            server.shutdown()
            thread.join()
    assert doc.read_bytes() == original


def test_existing_concept_relations_resolve_to_block_titles():
    root = Path(__file__).resolve().parents[1] / "doc"
    path = root / "architecture" / "KI-KNOWLEDGE-KONZEPT.md"
    output = render_page(root, parse_document(path), [path])
    assert "<strong>part-of</strong>" in output
    assert "Zweck (architecture/KI-KNOWLEDGE-KONZEPT.md)" in output
    assert "<strong>composed-of</strong>" in output
    assert "Interne Repräsentation (architecture/KI-KNOWLEDGE-KONZEPT.md)" in output
    assert "<dt>created</dt><dd>nicht angegeben</dd>" in output


def test_existing_text_block_relations_resolve_locally_and_across_documents():
    root = Path(__file__).resolve().parents[1] / "doc"
    path = root / "architecture" / "TEXT-AND-KNOWLEDGE-BLOCKS.md"
    output = render_page(root, parse_document(path), [path])
    assert "<strong>extends</strong> →" in output
    assert "/?file=architecture/KI-KNOWLEDGE-KONZEPT.md#knowledge-core" in output
    assert "<strong>depends-on</strong> →" in output
    assert "/?file=architecture/TEXT-AND-KNOWLEDGE-BLOCKS.md#distinction" in output
    assert "<strong>reference</strong> →" in output
