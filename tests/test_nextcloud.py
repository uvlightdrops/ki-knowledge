"""Nextcloud WebDAV backend against a loopback WebDAV fixture (no real Nextcloud)."""

from __future__ import annotations

import base64
import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

import pytest
from click.testing import CliRunner

from ki_knowledge.data_layout import DataLayout, LayoutError
from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.integrations.nextcloud import (
    NextcloudAuthError,
    NextcloudConfigError,
    NextcloudConflictError,
    NextcloudPathError,
    NextcloudRedirectError,
    NextcloudResponseError,
    NextcloudSettings,
    NextcloudSizeError,
    NextcloudUnsupportedTypeError,
    NextcloudWebDAVClient,
    parse_xml_safely,
)
from ki_knowledge.services.nextcloud_service import SOURCE_TYPE, NextcloudStorage

USER, PASSWORD = "alice", "app-secret-123"
ROOT = f"/remote.php/dav/files/{USER}"


class FakeNextcloud:
    """In-memory WebDAV tree: path (no leading slash) -> bytes, folders as set."""

    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.file_ids: dict[str, str] = {}
        self.etags: dict[str, str] = {}
        self.folders: set[str] = {""}
        self.requests: list[tuple[str, str, dict]] = []
        self.override: dict[tuple[str, str], tuple[int, dict, bytes]] = {}
        self.extra_hrefs: list[str] = []
        self._next_id = 100

    def add_folder(self, path: str) -> None:
        parts = path.strip("/").split("/")
        for index in range(1, len(parts) + 1):
            self.folders.add("/".join(parts[:index]))

    def put(self, path: str, data: bytes) -> None:
        path = path.strip("/")
        self.add_folder(path.rsplit("/", 1)[0])
        self.files[path] = data
        if path not in self.file_ids:
            self._next_id += 1
            self.file_ids[path] = str(self._next_id)
        self.etags[path] = '"' + hashlib.md5(data).hexdigest()[:12] + '"'

    def response_xml(self, path: str) -> str:
        href = ROOT + "/" + quote(path) if path else ROOT + "/"
        if path in self.folders:
            props = "<d:resourcetype><d:collection/></d:resourcetype><d:getetag>\"dir\"</d:getetag><oc:fileid>1</oc:fileid>"
            href = href.rstrip("/") + "/"
        else:
            data = self.files[path]
            props = (
                f"<d:resourcetype/><d:getetag>{self.etags[path]}</d:getetag><d:getcontentlength>{len(data)}</d:getcontentlength>"
                f"<d:getcontenttype>text/markdown</d:getcontenttype><oc:fileid>{self.file_ids[path]}</oc:fileid>"
                "<d:getlastmodified>Sun, 11 Oct 2026 10:00:00 GMT</d:getlastmodified>"
            )
        return (
            f"<d:response><d:href>{href}</d:href><d:propstat><d:prop>{props}</d:prop>"
            "<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
        )


def _handler(fake: FakeNextcloud):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _path(self) -> str | None:
            raw = urlsplit(self.path).path
            if not raw.startswith(ROOT):
                return None
            return unquote(raw[len(ROOT):]).strip("/")

        def _send(self, status, headers=None, body=b""):
            self.send_response(status)
            headers = dict(headers or {})
            no_length = headers.pop("X-No-Length", None)
            for key, value in headers.items():
                self.send_header(key, value)
            if no_length:
                self.close_connection = True
            else:
                self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if body and self.command != "HEAD":
                self.wfile.write(body)

        def _dispatch(self):
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            path = self._path()
            fake.requests.append((self.command, path, dict(self.headers)))
            override = fake.override.get((self.command, path))
            if override:
                return self._send(*override)
            expected = "Basic " + base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()
            if self.headers.get("Authorization") != expected:
                return self._send(401, {"WWW-Authenticate": 'Basic realm="nc"'})
            if path is None:
                return self._send(404)
            return getattr(self, "do_" + self.command + "_")(path, body)

        def do_PROPFIND_(self, path, _body):
            if path not in fake.folders and path not in fake.files:
                return self._send(404)
            items = [fake.response_xml(path)]
            if self.headers.get("Depth") == "1" and path in fake.folders:
                prefix = path + "/" if path else ""
                children = {p for p in fake.folders | set(fake.files) if p.startswith(prefix) and p != path and "/" not in p[len(prefix):]}
                items += [fake.response_xml(child) for child in sorted(children)]
            items += [f"<d:response><d:href>{href}</d:href></d:response>" for href in fake.extra_hrefs]
            xml = ('<?xml version="1.0"?><d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">'
                   + "".join(items) + "</d:multistatus>").encode()
            self._send(207, {"Content-Type": "application/xml; charset=utf-8"}, xml)

        def do_GET_(self, path, _body):
            if path not in fake.files:
                return self._send(404)
            etag = fake.etags[path]
            if self.headers.get("If-None-Match") == etag:
                return self._send(304, {"ETag": etag})
            self._send(200, {"ETag": etag, "Content-Type": "text/markdown"}, fake.files[path])

        def do_PUT_(self, path, body):
            if self.headers.get("If-None-Match") != "*":
                return self._send(400)
            if path in fake.files:
                return self._send(412)
            if path.rsplit("/", 1)[0] not in fake.folders:
                return self._send(409)
            fake.put(path, body)
            self._send(201, {"ETag": fake.etags[path], "OC-FileId": fake.file_ids[path]})

        def do_MKCOL_(self, path, _body):
            if path in fake.folders:
                return self._send(405)
            if path.rsplit("/", 1)[0] not in fake.folders:
                return self._send(409)
            fake.folders.add(path)
            self._send(201)

        do_PROPFIND = do_GET = do_PUT = do_MKCOL = _dispatch

    return Handler


@pytest.fixture
def fake_server():
    fake = FakeNextcloud()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(fake))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    fake.base_url = f"http://127.0.0.1:{server.server_address[1]}"
    yield fake
    server.shutdown()
    server.server_close()


def _settings(fake, **overrides):
    data = {
        "enabled": True,
        "base_url": fake.base_url,
        "username": USER,
        "app_password": PASSWORD,
        "allow_insecure_http_loopback": True,
        "domains": {"anthro": {"input_root": "KI/anthro/input", "output_root": "KI/anthro/output"}},
    }
    data.update(overrides)
    return NextcloudSettings.from_mapping(data)


@pytest.fixture
def layout(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    (root / ".layout-version").write_text("3")
    return DataLayout(root)


@pytest.fixture
def storage(fake_server, layout):
    fake_server.add_folder("KI/anthro/input")
    fake_server.add_folder("KI/anthro/output")
    fake_server.put("KI/anthro/input/notes.md", b"# Title\n\nFirst paragraph.\n\nSecond paragraph.\n")
    fake_server.put("KI/anthro/input/scan.pdf", b"%PDF-1.4")
    fake_server.add_folder("KI/anthro/input/sub")
    return NextcloudStorage(_settings(fake_server), layout)


# --- config -------------------------------------------------------------------------


def test_disabled_and_missing_config_errors():
    with pytest.raises(NextcloudConfigError, match="disabled"):
        NextcloudSettings.from_mapping({}).require_ready()
    with pytest.raises(NextcloudConfigError, match="app_password.*creds.yaml"):
        NextcloudSettings.from_mapping({"enabled": True, "base_url": "https://cloud.example.org", "username": "a"}).require_ready()
    ok = {"enabled": True, "base_url": "https://cloud.example.org", "username": "a", "app_password": "x"}
    NextcloudSettings.from_mapping(ok).require_ready()
    with pytest.raises(NextcloudConfigError, match="no Nextcloud mapping"):
        NextcloudSettings.from_mapping(ok).roots_for("anthro")


@pytest.mark.parametrize("base_url, extra, match", [
    ("http://cloud.example.org", {}, "https"),
    ("http://cloud.example.org", {"allow_insecure_http_loopback": True}, "https"),
    ("http://127.0.0.1:8080", {}, "allow_insecure_http_loopback"),
    ("https://u:p@cloud.example.org", {}, "credentials"),
])
def test_tls_and_url_rules(base_url, extra, match):
    data = {"enabled": True, "base_url": base_url, "username": "a", "app_password": "x", **extra}
    with pytest.raises(NextcloudConfigError, match=match):
        NextcloudSettings.from_mapping(data).require_ready()


def test_overlapping_roots_and_bad_root_rejected():
    base = {"enabled": True, "base_url": "https://c.example.org", "username": "a", "app_password": "x"}
    overlapping = {**base, "domains": {"d": {"input_root": "KI/d", "output_root": "KI/d/out"}}}
    with pytest.raises(NextcloudConfigError, match="overlap"):
        NextcloudSettings.from_mapping(overlapping).require_ready()
    with pytest.raises(NextcloudConfigError):
        NextcloudSettings.from_mapping({**base, "domains": {"d": {"input_root": "KI/../x", "output_root": "o"}}})
    with pytest.raises(NextcloudConfigError, match="invalid domain"):
        NextcloudSettings.from_mapping({**base, "domains": {"../x": {"input_root": "a", "output_root": "b"}}})


def test_secret_not_in_repr_or_summary(fake_server):
    settings = _settings(fake_server)
    client = NextcloudWebDAVClient(settings)
    for text in (repr(settings), repr(client), json.dumps(settings.safe_summary())):
        assert PASSWORD not in text


def test_settings_from_ki_core_config_defaults_disabled():
    from ki_knowledge.app_config import AppConfig, clear_config_cache

    clear_config_cache()
    settings = NextcloudSettings.from_config(AppConfig.from_env())
    assert settings.enabled is False
    assert settings.dav_path == "remote.php/dav/files/{user_id}"


# --- list / download / import ---------------------------------------------------------


def test_list_input_root(storage):
    records = {r.metadata["path"]: r for r in storage.list("anthro")}
    assert set(records) == {"notes.md", "scan.pdf", "sub"}
    notes = records["notes.md"]
    assert notes.uri.endswith("/remote.php/dav/files/alice/KI/anthro/input/notes.md")
    assert notes.checksum and notes.metadata["file_id"] and notes.metadata["importable"]
    assert records["scan.pdf"].document_type == "unsupported"
    assert records["sub"].document_type == "folder"
    assert storage.describe_domain("anthro").provider == "nextcloud"


def test_paths_cannot_escape_input_root(storage, fake_server):
    for bad in ("../output/x.md", "a/../../b", "a\\b", "sub/./x"):
        with pytest.raises(NextcloudPathError):
            storage.download("anthro", bad)
    assert not [r for r in fake_server.requests if r[0] == "GET"]


@pytest.mark.parametrize("href", [
    "http://evil.example/remote.php/dav/files/alice/KI/anthro/input/x.md",
    "/remote.php/dav/files/bob/KI/anthro/input/x.md",
    "/remote.php/dav/files/alice/KI/anthro/output/x.md",
    "/remote.php/dav/files/alice/KI/anthro/input/sub/deeper.md",
    "/remote.php/dav/files/alice/KI/anthro/input/%2E%2E/x.md",
    "/remote.php/dav/files/alice/KI/anthro/input/a%2Fb.md",
])
def test_server_hrefs_outside_root_rejected(storage, fake_server, href):
    fake_server.extra_hrefs = [href]
    with pytest.raises(NextcloudPathError):
        storage.list("anthro")


def test_download_atomic_and_conditional(storage, fake_server, layout):
    first = storage.download("anthro", "notes.md")
    assert not first.not_modified
    assert first.local_path.read_bytes().startswith(b"# Title")
    cache_root = layout.remote_input_cache_dir("anthro", "nextcloud")
    assert first.local_path.is_relative_to(cache_root)
    assert not first.local_path.is_relative_to(layout.output_dir("anthro"))
    assert not first.local_path.is_relative_to(layout.source_dir("markdown", "anthro"))
    second = storage.download("anthro", "notes.md")
    assert second.not_modified and second.etag == first.etag and second.sha256 == first.sha256
    gets = [r for r in fake_server.requests if r[0] == "GET"]
    assert gets[-1][2].get("If-None-Match") == first.etag
    assert not list(first.local_path.parent.glob(".*.part"))


def test_download_size_limit_cleans_up(fake_server, layout):
    fake_server.add_folder("KI/anthro/input")
    fake_server.put("KI/anthro/input/big.md", b"x" * 2048)
    storage = NextcloudStorage(_settings(fake_server, max_download_bytes=1024), layout)
    with pytest.raises(NextcloudSizeError):
        storage.download("anthro", "big.md")
    cache = layout.remote_input_cache_dir("anthro", "nextcloud")
    assert not [p for p in cache.rglob("*") if p.is_file()]


def test_streaming_limit_without_content_length_leaves_no_partial(fake_server, tmp_path):
    fake_server.put("x.md", b"y" * 5000)
    client = NextcloudWebDAVClient(_settings(fake_server, max_download_bytes=1000))
    target = tmp_path / "cache" / "x.md"
    target.parent.mkdir()
    target.write_bytes(b"old")
    fake_server.override[("GET", "x.md")] = (200, {"Content-Type": "text/markdown", "X-No-Length": "1"}, b"y" * 5000)
    with pytest.raises(NextcloudSizeError):
        client.download("x.md", target)
    assert target.read_bytes() == b"old"
    assert list(target.parent.iterdir()) == [target]


def test_import_markdown_with_remote_provenance_and_stable_ids(storage, fake_server, tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    result = storage.import_file("anthro", "notes.md", store)
    source = store.get_source(result.source_id)
    assert source.source_type == SOURCE_TYPE
    assert source.location == result.remote_url
    prov = source.metadata["provenance"]
    assert prov["remote_url"] == result.remote_url and prov["file_id"] == result.file_id and prov["etag"] == result.etag
    assert prov["local_cache_path"] != prov["remote_url"]
    records = store.list_records(source_id=result.source_id)
    assert len(records) == 2 and result.records == 2
    assert all(r.metadata["remote"]["remote_url"] == result.remote_url for r in records)
    first_ids = {r.block_id for r in records}

    fake_server.put("KI/anthro/input/notes.md", b"# Title\n\nFirst paragraph.\n\nChanged paragraph.\n")
    again = storage.import_file("anthro", "notes.md", store)
    assert again.source_id == result.source_id and again.file_id == result.file_id
    assert again.etag != result.etag and not again.not_modified
    records = store.list_records(source_id=result.source_id)
    assert {r.content for r in records} == {"First paragraph.", "Changed paragraph."}
    assert len({r.block_id for r in records} & first_ids) == 1
    assert store.get_source(result.source_id).metadata["provenance"]["etag"] == again.etag


def test_import_unsupported_type_never_downloads_or_imports(storage, fake_server, tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    with pytest.raises(NextcloudUnsupportedTypeError):
        storage.import_file("anthro", "scan.pdf", store)
    assert not [r for r in fake_server.requests if r[0] == "GET"]
    assert store.list_sources() == []


def test_import_folder_reports_skipped(storage, tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    result = storage.import_folder("anthro", "", store)
    assert [item["path"] for item in result["imported"]] == ["notes.md"]
    assert {item["path"] for item in result["skipped"]} == {"scan.pdf", "sub"}
    assert result["errors"] == []


def test_import_invalid_utf8_not_marked_success(fake_server, layout, tmp_path):
    fake_server.add_folder("KI/anthro/input")
    fake_server.put("KI/anthro/input/bad.md", b"\xff\xfe\x00bad")
    storage = NextcloudStorage(_settings(fake_server), layout)
    store = KnowledgeStore(tmp_path / "knowledge.db")
    with pytest.raises(NextcloudUnsupportedTypeError, match="UTF-8"):
        storage.import_file("anthro", "bad.md", store)
    assert store.list_sources() == []


# --- errors ---------------------------------------------------------------------------


def test_auth_error(fake_server, layout):
    storage = NextcloudStorage(_settings(fake_server, app_password="wrong"), layout)
    with pytest.raises(NextcloudAuthError) as info:
        storage.list("anthro")
    assert info.value.status == 401 and "wrong" not in str(info.value)


def test_redirect_not_followed(storage, fake_server):
    fake_server.override[("PROPFIND", "KI/anthro/input")] = (302, {"Location": "http://evil.example/steal"}, b"")
    with pytest.raises(NextcloudRedirectError):
        storage.list("anthro")
    assert len([r for r in fake_server.requests if r[0] == "PROPFIND"]) == 1


@pytest.mark.parametrize("headers, body, match", [
    ({"Content-Type": "text/html"}, b"<html></html>", "non-XML"),
    ({"Content-Type": "application/xml"}, b"<d:multistatus xmlns:d='DAV:'><d:response>", "malformed"),
    ({"Content-Type": "application/xml"},
     b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><d:multistatus xmlns:d="DAV:">&a;</d:multistatus>',
     "DTD"),
    ({"Content-Type": "application/xml"}, b"<other/>", "multistatus"),
])
def test_bad_propfind_responses(storage, fake_server, headers, body, match):
    fake_server.override[("PROPFIND", "KI/anthro/input")] = (207, headers, body)
    with pytest.raises(NextcloudResponseError, match=match):
        storage.list("anthro")


def test_listing_size_limit(fake_server, layout):
    fake_server.add_folder("KI/anthro/input")
    for index in range(50):
        fake_server.put(f"KI/anthro/input/f{index}.md", b"x")
    storage = NextcloudStorage(_settings(fake_server, max_listing_bytes=2000), layout)
    with pytest.raises(NextcloudSizeError):
        storage.list("anthro")


def test_xml_parser_rejects_external_entities():
    with pytest.raises(NextcloudResponseError):
        parse_xml_safely(b'<!DOCTYPE x SYSTEM "file:///etc/passwd"><x/>')


# --- upload ---------------------------------------------------------------------------


def _output_file(layout, relative="site/index.html", content=b"<h1>out</h1>"):
    path = layout.output_dir("anthro") / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_upload_create_only_and_conflict(storage, fake_server, layout):
    path = _output_file(layout)
    with pytest.raises(NextcloudConflictError) as missing_parent:
        storage.upload_output("anthro", path)
    assert missing_parent.value.status == 409
    result = storage.upload_output("anthro", "site/index.html", create_parents=True)
    assert result.path == "KI/anthro/output/site/index.html"
    assert fake_server.files[result.path] == b"<h1>out</h1>" and result.file_id
    puts = [r for r in fake_server.requests if r[0] == "PUT"]
    assert all(r[2].get("If-None-Match") == "*" for r in puts)
    mkcols = [r[1] for r in fake_server.requests if r[0] == "MKCOL"]
    assert mkcols == ["KI/anthro/output/site"]

    path.write_bytes(b"<h1>changed</h1>")
    with pytest.raises(NextcloudConflictError) as conflict:
        storage.upload_output("anthro", path)
    assert conflict.value.status == 412
    assert fake_server.files[result.path] == b"<h1>out</h1>"


def test_upload_only_from_output_tree(storage, layout, tmp_path):
    _output_file(layout)
    outside = tmp_path / "secret.txt"
    outside.write_text("x")
    source_md = layout.source_dir("markdown", "anthro", "doc.md")
    source_md.parent.mkdir(parents=True)
    source_md.write_text("# local")
    link = layout.output_dir("anthro") / "link.txt"
    link.symlink_to(outside)
    for bad in (outside, source_md, link, "../md/doc.md", "site"):
        with pytest.raises(LayoutError):
            storage.upload_output("anthro", bad)


def test_upload_overwrite_status_is_not_success(storage, fake_server, layout):
    _output_file(layout, "a.txt")
    fake_server.override[("PUT", "KI/anthro/output/a.txt")] = (204, {}, b"")
    with pytest.raises(NextcloudResponseError, match="204"):
        storage.upload_output("anthro", "a.txt")


# --- CLI ------------------------------------------------------------------------------


def test_cli_status_and_disabled_error(monkeypatch):
    from ki_knowledge.cli.commands import nextcloud as cli

    monkeypatch.setattr(NextcloudSettings, "from_config", classmethod(lambda cls, cfg=None: cls.from_mapping({})))
    runner = CliRunner()
    status = runner.invoke(cli.status)
    assert status.exit_code == 0 and json.loads(status.output)["ready"] is False
    listed = runner.invoke(cli.list_remote, ["--domain", "anthro"])
    assert listed.exit_code == 1 and "disabled" in listed.output


def test_cli_list_import_upload(storage, monkeypatch, tmp_path, layout):
    from ki_knowledge.cli.commands import nextcloud as cli
    from ki_knowledge.services import nextcloud_service

    store = KnowledgeStore(tmp_path / "knowledge.db")
    monkeypatch.setattr(cli, "_storage", lambda: storage)
    monkeypatch.setattr(nextcloud_service, "open_store", lambda cfg=None: store)
    runner = CliRunner()
    listed = runner.invoke(cli.list_remote, ["-d", "anthro"])
    assert listed.exit_code == 0, listed.output
    assert {item["metadata"]["path"] for item in json.loads(listed.output)} == {"notes.md", "scan.pdf", "sub"}
    imported = runner.invoke(cli.import_remote, ["-d", "anthro", "notes.md"])
    assert imported.exit_code == 0, imported.output
    assert json.loads(imported.output)["records"] == 2
    unsupported = runner.invoke(cli.import_remote, ["-d", "anthro", "scan.pdf"])
    assert unsupported.exit_code == 1 and "not importable" in unsupported.output
    _output_file(layout, "report.md", b"# report")
    uploaded = runner.invoke(cli.upload, ["-d", "anthro", "report.md"])
    assert uploaded.exit_code == 0, uploaded.output
    conflict = runner.invoke(cli.upload, ["-d", "anthro", "report.md"])
    assert conflict.exit_code == 1 and "412" in conflict.output


def test_cli_yaml_registers_nextcloud_group():
    from ki_knowledge.cli.framework import CLIBuilder

    cli = CLIBuilder.from_yaml_file(
        Path(__file__).resolve().parents[1] / "ki_knowledge/cli/cli.yaml"
    ).build_cli()
    group = cli.commands["nextcloud"]
    assert set(group.commands) == {"status", "list", "download", "import", "upload"}


def test_download_time_bound_leaves_previous_file(fake_server, tmp_path):
    fake_server.put("slow.md", b"z" * 100)
    client = NextcloudWebDAVClient(_settings(fake_server, max_download_seconds=1e-9))
    target = tmp_path / "slow.md"
    target.write_bytes(b"previous")
    with pytest.raises(Exception, match="download time"):
        client.download("slow.md", target)
    assert target.read_bytes() == b"previous" and list(tmp_path.iterdir()) == [target]
