import json
import re
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

import pytest

from ki_knowledge.doc_viewer import make_handler
from ki_knowledge.wiki_documents import DocumentDomain
from ki_knowledge.wiki_web import make_workspace_handler
from ki_knowledge.wiki_workspace import WorkspaceConflict, WorkspaceError


def test_document_nodes_and_relations_are_read_without_modifying_sources(tmp_path):
    source = tmp_path / "docs"
    source.mkdir()
    storage = tmp_path / "relations"
    storage.mkdir()
    original = "---\nstatus: draft\ncreated: 2026-11-08\nrelations:\n  - source: '#one'\n    target: 'other.md#two'\n    type: extends\n---\n# First\n## One [one]\nText\n## Unstable\nMore\n"
    first = source / "first.md"
    first.write_text(original)
    (source / "other.md").write_text("---\n{}\n---\n# Second\n## Two [two]\nOther\n")
    domain = DocumentDomain(source, storage)
    snapshot = domain.snapshot()
    nodes = {node["id"]: node for node in snapshot["blocks"]}
    assert nodes["doc:first.md#one"]["relations"] == [{"target": "doc:other.md#two", "type": "extends"}]
    assert nodes["doc:first.md#one"]["attributes"]["block_id"] == "one"
    assert nodes["doc:first.md#one"]["attributes"]["dokument_metadaten"]["status"] == "draft"
    assert nodes["doc:first.md"]["attributes"]["dokument_metadaten"]["created"] == "2026-11-08"
    assert nodes["doc:first.md"]["attributes"]["ordner"] == "."
    assert nodes["doc:first.md#!unstable-1"]["linkable"] is False
    data = {"id": "doc:first.md#one", "target": "doc:other.md#two",
            "type": "references", "revision": snapshot["revision"]}
    updated = domain.relate(data)
    assert domain.snapshot() == updated
    assert first.read_text() == original
    assert json.loads((storage / "dokument-beziehungen.json").read_text()) == [{
        "source": "doc:first.md#one", "target": "doc:other.md#two", "type": "references"
    }]
    with pytest.raises(WorkspaceConflict):
        domain.relate(data)
    data.update(revision=updated["revision"], target="doc:first.md#!unstable-1")
    with pytest.raises(WorkspaceError, match="stabiler ID"):
        domain.relate(data)


def test_domain_routes_are_isolated_and_not_writable_from_other_origin(tmp_path):
    roots = []
    for name in ("one", "two"):
        source, storage = tmp_path / name, tmp_path / (name + "-relations")
        source.mkdir()
        storage.mkdir()
        (source / "doc.md").write_text("---\n{}\n---\n# " + name + "\n## A [a]\nA\n## B [b]\nB\n")
        roots.append((source, storage))
    domains = {name: DocumentDomain(*root) for name, root in zip(("Dokumente", "Andere"), roots)}
    with ThreadingHTTPServer(("127.0.0.1", 0), make_workspace_handler(make_handler(roots[0][0]), None, domains)) as server:
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            origin = f"http://127.0.0.1:{server.server_port}"
            with urlopen(origin + "/workspace/graph/") as response:
                page = response.read().decode()
            assert "?domain=Dokumente" in page and "?domain=Andere" in page
            assert "__DOMAIN_LINKS__" not in page
            assert "__RELATION_OPTIONS__" not in page
            token = re.search(r'<meta name="workspace-token" content="([a-f0-9]+)">', page).group(1)
            url = origin + "/workspace/api?domain=" + quote("Dokumente")
            with urlopen(url) as response:
                snapshot = json.load(response)
            data = {"action": "graph-relate", "domain": "Dokumente", "revision": snapshot["revision"],
                    "id": "doc:doc.md#a", "target": "doc:doc.md#b", "type": "part-of"}
            headers = {"Content-Type": "application/json", "Origin": origin, "X-Workspace-Token": token}
            with pytest.raises(HTTPError) as error:
                urlopen(Request(origin + "/workspace/api", json.dumps(data).encode(),
                                headers={**headers, "Origin": "https://example.com"}))
            assert error.value.code == 403
            with urlopen(Request(origin + "/workspace/api", json.dumps(data).encode(), headers=headers)) as response:
                assert json.load(response)["revision"] != snapshot["revision"]
            assert not (roots[1][1] / "dokument-beziehungen.json").exists()
            assert len(domains["Andere"].snapshot()["blocks"]) == 3
        finally:
            server.shutdown()
            thread.join()


def test_lenient_domain_reads_headerless_files_and_derives_section_ids(tmp_path):
    source = tmp_path / "docs"
    source.mkdir()
    storage = tmp_path / "relations"
    storage.mkdir()
    text = "# Buch\n## Grüße aus Köln\nA\n## Grüße aus Köln\nB\n## Fest [fest]\nC\n"
    (source / "buch.md").write_text(text)

    assert DocumentDomain(source, storage).snapshot()["blocks"] == []
    snapshot = DocumentDomain(source, storage, lenient=True).snapshot()
    ids = [node["id"] for node in snapshot["blocks"]]
    assert ids == ["doc:buch.md", "doc:buch.md#auto-gruesse-aus-koeln",
                   "doc:buch.md#auto-gruesse-aus-koeln-2", "doc:buch.md#fest"]
    assert all(node["linkable"] for node in snapshot["blocks"])
    assert (source / "buch.md").read_text() == text
