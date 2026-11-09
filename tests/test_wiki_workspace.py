import json
import re
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from ki_knowledge.doc_viewer import make_handler
from ki_knowledge.wiki_web import make_workspace_handler
from ki_knowledge.wiki_relations import RELATION_TYPES
from ki_knowledge.wiki_workspace import Workspace, WorkspaceConflict, WorkspaceError


def test_blocks_relations_and_order_persist_as_markdown(tmp_path):
    workspace = Workspace(tmp_path)
    essay = workspace.create("Essay", "Einleitung")
    first = workspace.create("Erster Gedanke", "Erster Text")
    second = workspace.create("", "Zweiter Text")
    assert first["attributes"]["metadaten"]["formulation_origin"] == "human"
    essay = workspace.update(essay["id"], essay["revision"], "relate",
                             {"target": first["id"], "type": "part-of"})
    essay = workspace.update(essay["id"], essay["revision"], "parts",
                             {"parts": [first["id"], second["id"]]})
    essay = workspace.update(essay["id"], essay["revision"], "parts",
                             {"parts": [second["id"], first["id"]]})

    reopened = {block["id"]: block for block in Workspace(tmp_path).list_blocks()}
    assert reopened[essay["id"]]["relations"] == [{"target": first["id"], "type": "part-of"}]
    assert reopened[essay["id"]]["parts"] == [second["id"], first["id"]]
    assert (tmp_path / f'{first["id"]}.md').read_text(encoding="utf-8").endswith("Erster Text")
    assert "formulation_origin: human" in (tmp_path / f'{first["id"]}.md').read_text(encoding="utf-8")


def test_external_edits_cause_conflict_without_overwriting(tmp_path):
    workspace = Workspace(tmp_path)
    block = workspace.create("Titel", "Alter Text")
    path = tmp_path / f'{block["id"]}.md'
    path.write_text(path.read_text(encoding="utf-8").replace("Alter Text", "Externer Text"), encoding="utf-8")
    with pytest.raises(WorkspaceConflict, match="zwischenzeitlich geändert"):
        workspace.update(block["id"], block["revision"], "save", {"title": "Titel", "text": "Neu"})
    assert "Externer Text" in path.read_text(encoding="utf-8")


def test_invalid_targets_duplicate_relations_and_symlinks_are_rejected(tmp_path):
    workspace = Workspace(tmp_path)
    first = workspace.create("Eins", "")
    second = workspace.create("Zwei", "")
    with pytest.raises(WorkspaceError):
        workspace.update(first["id"], first["revision"], "relate", {"target": "../x", "type": "ref"})
    with pytest.raises(WorkspaceError):
        workspace.update(first["id"], first["revision"], "parts", {"parts": [first["id"]]})
    first = workspace.update(first["id"], first["revision"], "relate", {"target": second["id"], "type": "ref"})
    with pytest.raises(WorkspaceError, match="bereits"):
        workspace.update(first["id"], first["revision"], "relate", {"target": second["id"], "type": "ref"})
    first = workspace.update(first["id"], first["revision"], "unrelate", {"index": 0})
    assert first["relations"] == []
    link = tmp_path / ("a" * 32 + ".md")
    link.symlink_to(tmp_path / f'{second["id"]}.md')
    with pytest.raises(WorkspaceError, match="Links"):
        workspace.list_blocks()


def test_http_workspace_requires_same_origin_and_token(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "doc.md").write_text("---\nproject: test\n---\n# Test\n", encoding="utf-8")
    root = tmp_path / "workspace"
    root.mkdir()
    handler = make_workspace_handler(make_handler(docs, workspace_enabled=True), Workspace(root))
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            origin = f"http://127.0.0.1:{server.server_port}"
            with urlopen(origin + "/workspace/") as response:
                page = response.read().decode()
                assert "Links → rechts verbinden" in page
                assert "Rechts → links verbinden" in page
                assert 'id="block-browser"' in page
                assert 'id="block-search"' in page
                assert f'href="{origin.replace(str(server.server_port), "8000")}/"' in page
                assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
            token = re.search(r'<meta name="workspace-token" content="([a-f0-9]+)">', page).group(1)
            for asset, expected in (("/assets/workspace.css", b".columns"),
                                    ("/assets/workspace.js", b"X-Workspace-Token"),
                                    ("/assets/viewer.css", b"nav")):
                with urlopen(origin + asset) as response:
                    assert expected in response.read()
            data = json.dumps({"action": "create", "title": "Gedanke", "text": "Text"}).encode()
            headers = {"Content-Type": "application/json", "Origin": origin, "X-Workspace-Token": token}
            with urlopen(Request(origin + "/workspace/api", data=data, headers=headers)) as response:
                block = json.load(response)
            assert block["title"] == "Gedanke"
            for bad_headers in (
                {**headers, "Origin": "https://example.com"},
                {**headers, "X-Workspace-Token": "invalid"},
                {**headers, "Host": f"example.com:{server.server_port}"},
            ):
                with pytest.raises(HTTPError) as error:
                    urlopen(Request(origin + "/workspace/api", data=data, headers=bad_headers))
                assert error.value.code == 403
            with urlopen(origin + "/workspace/api") as response:
                assert len(json.load(response)["blocks"]) == 1
            with urlopen(origin + "/?file=doc.md") as response:
                assert response.status == 200
                page = response.read()
                assert b'<link rel="stylesheet" href="/assets/viewer.css">' in page
                assert b'href="/workspace/"' in page
        finally:
            server.shutdown()
            thread.join()


def test_workspace_accepts_address_of_connected_interface(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    root = tmp_path / "workspace"
    root.mkdir()
    handler = make_workspace_handler(make_handler(docs), Workspace(root))
    with ThreadingHTTPServer(("0.0.0.0", 0), handler) as server:
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            host = f"127.0.0.2:{server.server_port}"
            connection = HTTPConnection("127.0.0.2", server.server_port)
            connection.request("GET", "/workspace/")
            response = connection.getresponse()
            page = response.read().decode()
            assert response.status == 200
            assert 'href="http://127.0.0.2:8000/"' in page
            token = re.search(r'<meta name="workspace-token" content="([a-f0-9]+)">', page).group(1)
            headers = {"Content-Type": "application/json", "Origin": f"http://{host}",
                       "X-Workspace-Token": token}
            connection.request("POST", "/workspace/api",
                               json.dumps({"action": "create", "title": "Netz", "text": ""}), headers)
            response = connection.getresponse()
            assert response.status == 200
            assert json.loads(response.read())["title"] == "Netz"
            connection.request("GET", "/workspace/", headers={"Host": f"127.0.0.1:{server.server_port}"})
            response = connection.getresponse()
            assert response.status == 403
            response.read()
            connection.close()
        finally:
            server.shutdown()
            thread.join()


def test_graph_view_uses_documented_types_and_saves_relation(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    root = tmp_path / "workspace"
    root.mkdir()
    workspace = Workspace(root)
    first = workspace.create("Eins", "Text eins")
    second = workspace.create("Zwei", "Text zwei")
    handler = make_workspace_handler(make_handler(docs), workspace)
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            origin = f"http://127.0.0.1:{server.server_port}"
            with urlopen(origin + "/workspace/graph/") as response:
                page = response.read().decode()
            token = re.search(r'<meta name="workspace-token" content="([a-f0-9]+)">', page).group(1)
            assert re.findall(r'name="relation-type" value="([^"]+)"', page) == [name for name, _ in RELATION_TYPES]
            assert 'src="/assets/graph.js"' in page
            assert '<strong>Ausgang</strong>' not in page
            assert '<strong>Ziel</strong>' not in page
            assert 'id="source-label" aria-label="Ausgang"' in page
            assert 'id="target-label" aria-label="Ziel"' in page
            assert page.index('id="graph"') < page.index('id="detail-attributes"')
            with urlopen(origin + "/workspace/graph-header/") as response:
                header_page = response.read().decode()
            filters = header_page[header_page.index("<header>"):header_page.index("</header>")]
            assert 'href="/workspace/"' not in filters and 'href="/"' not in filters
            assert 'id="folder-legend"' not in header_page
            assert filters.index('id="count"') < filters.index('id="reset-settings"')
            for control in ("filter", "folder-filter", "file-filter", "relation-filter", "attribute-filter"):
                assert f'id="{control}"' in filters
            assert 'href="/workspace/graph-header/">Wiki</a>' in header_page
            assert 'src="/assets/graph.js"' in header_page
            assert 'id="attribute-compare"' in header_page and 'id="detail-attributes"' not in header_page
            with urlopen(origin + "/assets/graph-header.css") as response:
                assert response.headers["Content-Type"].startswith("text/css")
            with urlopen(origin + "/workspace/settings/") as response:
                settings_page = response.read().decode()
            assert 'id="attribute-options"' in settings_page
            assert 'href="/workspace/settings/">Wiki</a>' in settings_page
            assert settings_page.index("attribute-settings.js") < settings_page.index("/assets/settings.js")
            for asset in ("attribute-settings.js", "settings.js", "settings.css"):
                with urlopen(origin + "/assets/" + asset) as response:
                    assert response.status == 200
            data = {"action": "graph-relate", "id": first["id"], "revision": first["revision"],
                    "target": second["id"], "type": "references"}
            headers = {"Content-Type": "application/json", "Origin": origin, "X-Workspace-Token": token}
            with urlopen(Request(origin + "/workspace/api", data=json.dumps(data).encode(), headers=headers)) as response:
                updated = json.load(response)
            assert updated["relations"] == [{"target": second["id"], "type": "references"}]
            data.update(revision=updated["revision"], type="reference")
            with pytest.raises(HTTPError) as error:
                urlopen(Request(origin + "/workspace/api", data=json.dumps(data).encode(), headers=headers))
            assert error.value.code == 400
            assert workspace.list_blocks() == sorted(
                [updated, second], key=lambda block: block["id"])
        finally:
            server.shutdown()
            thread.join()
