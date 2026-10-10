import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit

import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ki_knowledge.django_site.settings")
django.setup()

from ki_knowledge.node_sync import NodeSettings, SyncClient, describe, node_core_available, to_descriptor


def _host(**kwargs):
    defaults = dict(node_id="host-a", role="host", enabled=True, master_url="http://master.lan:8000",
                    legacy_base_url="http://master.lan:8000", shared_secret="s3cret", federation_id="lab")
    return NodeSettings(**{**defaults, **kwargs})


def test_host_base_url_is_master_not_own_endpoint():
    node = _host()
    assert node.endpoint == "" and node.coordinator_endpoint == "http://master.lan:8000"
    assert node.heartbeat_payload(instance_id="i1")["base_url"] == "http://master.lan:8000"  # legacy
    node = _host(public_url="http://host-a.lan:8000")
    payload = node.heartbeat_payload(instance_id="i1")
    assert node.endpoint == payload["base_url"] == "http://host-a.lan:8000"
    assert payload["federation_id"] == "lab" and "knowledge.domain.pull@1.0" in payload["capabilities"]
    assert "s3cret" not in repr(node) and "s3cret" not in json.dumps(payload)


def test_settings_validation_and_readiness():
    with pytest.raises(ValueError):
        NodeSettings(node_id="x", role="leader")
    with pytest.raises(ValueError):
        NodeSettings(node_id=" ")
    assert not _host(enabled=False).heartbeat_ready
    assert not NodeSettings(node_id="m", role="master", enabled=True).heartbeat_ready
    assert _host().heartbeat_ready


def test_describe_lists_role_capabilities_without_secret():
    master = NodeSettings(node_id="m", role="master", legacy_base_url="http://m:8000", shared_secret="topsecret")
    info = describe(master, instance_id="boot-1")
    names = {c["name"] for c in info["capabilities"]}
    assert {"knowledge.node.heartbeat", "knowledge.snapshot.import"} <= names
    assert "knowledge.domain.pull" not in names
    assert info["endpoint"] == info["coordinator_endpoint"] == "http://m:8000"
    assert "topsecret" not in json.dumps(info)


@pytest.mark.skipif(not node_core_available(), reason="ki-node-core nicht installiert")
def test_descriptor_matches_shared_contract_and_negotiates():
    from ki_node_core import Capability, NodeRole, ProtocolVersion, negotiate_version
    from ki_node_core.errors import CompatibilityError

    host = to_descriptor(_host(public_url="http://host-a.lan:8000"), instance_id="b1")
    master = to_descriptor(NodeSettings(node_id="m", role="master", federation_id="lab"), instance_id="b2")
    assert host.role is NodeRole.HOST and host.endpoint == "http://host-a.lan:8000"
    pull = Capability("knowledge.domain.pull", ProtocolVersion(1, 0))
    assert negotiate_version(master, host, required_capabilities=(pull,)) == ProtocolVersion(0, 1)
    with pytest.raises(CompatibilityError):
        negotiate_version(host, master, required_capabilities=(pull,))
    other = to_descriptor(NodeSettings(node_id="x", role="master", federation_id="other"), instance_id="b3")
    with pytest.raises(CompatibilityError):
        negotiate_version(host, other)


class _Recorder(BaseHTTPRequestHandler):
    calls: list = []

    def _reply(self, body):
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlsplit(self.path)
        self.calls.append(("GET", url.path, parse_qs(url.query), dict(self.headers)))
        self._reply([] if url.path.endswith("/node/") else {"domains": []})

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"])).decode()
        self.calls.append(("POST", self.path, body, dict(self.headers)))
        self._reply({"status": "ok"})

    def log_message(self, *args):
        pass


@pytest.fixture()
def server():
    _Recorder.calls = []
    httpd = HTTPServer(("127.0.0.1", 0), _Recorder)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def test_client_paths_headers_and_operation_id(server):
    client = SyncClient(server + "/", secret="s3cret", timeout=1)
    assert client.heartbeat({"node_id": "h"}) == {"status": "ok"}
    client.export(domains=[" a ", "", "b"], include_knowledge=False)
    client.trigger_pull(domains=["a"], operation_id="op-1")
    (_, hb_path, hb_body, hb_headers), (_, ex_path, ex_query, _), (_, pl_path, pl_body, pl_headers) = _Recorder.calls
    assert hb_path == "/knowledge/sync/heartbeat/" and json.loads(hb_body) == {"node_id": "h"}
    assert hb_headers["X-KI-Sync-Secret"] == "s3cret"
    assert ex_path == "/knowledge/sync/export/"
    assert ex_query["domain"] == ["a", "b"] and ex_query["include_knowledge"] == ["0"]
    assert pl_path == "/knowledge/sync/pull/" and parse_qs(pl_body) == {"domain": ["a"], "operation_id": ["op-1"]}
    assert pl_headers["X-KI-Operation-Id"] == "op-1"


def test_client_rejects_non_object_and_missing_origin(server):
    with pytest.raises(ValueError, match="must be an object"):
        SyncClient(server).describe()
    with pytest.raises(ValueError):
        SyncClient("  ")


def test_heartbeat_from_other_federation_is_rejected(monkeypatch):
    from types import SimpleNamespace

    from ki_knowledge.django_site import distributed_sync

    monkeypatch.setattr(distributed_sync.Config, "from_env", lambda: SimpleNamespace(distributed_federation_id="lab"))
    with pytest.raises(ValueError, match="federation"):
        distributed_sync.apply_remote_node_heartbeat({"node_id": "h", "federation_id": "other"})


def test_invalid_runtime_role_is_not_silently_coerced(monkeypatch):
    from types import SimpleNamespace

    from ki_knowledge.django_site import distributed_api

    monkeypatch.setattr(
        distributed_api,
        "get_runtime_node_settings",
        lambda: SimpleNamespace(
            node_id="node-a",
            role="leader",
            distributed_enabled=True,
            sync_on_connect=True,
            master_url="",
            base_url="",
            sync_shared_secret="",
        ),
    )
    monkeypatch.setattr(
        distributed_api.NodeConfig.objects,
        "filter",
        lambda **kwargs: SimpleNamespace(values_list=lambda *args, **options: SimpleNamespace(first=lambda: "")),
    )
    monkeypatch.setattr(
        distributed_api.Config,
        "from_env",
        lambda: SimpleNamespace(distributed_federation_id="lab", distributed_public_url=""),
    )

    with pytest.raises(ValueError, match="role must be one of"):
        distributed_api.get_node_settings()


def test_node_view_returns_description(monkeypatch):
    from django.test import RequestFactory

    from ki_knowledge.django_site import views_sync

    monkeypatch.setattr(views_sync, "describe_local_node", lambda: describe(_host(), instance_id="b1"))
    response = views_sync.sync_node_view(RequestFactory().get("/knowledge/sync/node/"))
    data = json.loads(response.content)
    assert response.status_code == 200 and data["node_id"] == "host-a" and data["protocol_versions"] == ["0.1"]


def _post(path, headers=None, data="{}"):
    from django.test import RequestFactory

    request = RequestFactory().post(path, data=data, content_type="application/json", headers=headers or {})
    request._dont_enforce_csrf_checks = False
    return request


def test_machine_endpoints_skip_csrf_but_block_cross_site_without_secret(monkeypatch):
    from django.middleware.csrf import CsrfViewMiddleware

    from ki_knowledge.django_site import views_sync

    monkeypatch.setattr(views_sync, "_configured_sync_secret", lambda: "")
    monkeypatch.setattr(views_sync, "import_remote_heartbeat", lambda payload: type("N", (), {"node_id": "h", "role": "host"})())
    csrf = CsrfViewMiddleware(lambda request: None)
    for view in (views_sync.sync_heartbeat_view, views_sync.sync_push_view, views_sync.sync_pull_view):
        assert csrf.process_view(_post("/x/"), view, (), {}) is None  # csrf_exempt
    assert views_sync.sync_heartbeat_view(_post("/knowledge/sync/heartbeat/", data='{"node_id": "h"}')).status_code == 200
    evil = _post("/knowledge/sync/heartbeat/", {"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"})
    assert views_sync.sync_heartbeat_view(evil).status_code == 403


def test_secret_required_when_configured(monkeypatch):
    from ki_knowledge.django_site import views_sync

    monkeypatch.setattr(views_sync, "_configured_sync_secret", lambda: "s3cret")
    assert views_sync.sync_push_view(_post("/knowledge/sync/push/")).status_code == 403


def test_export_passes_include_switches_instead_of_discarding(monkeypatch):
    from django.test import RequestFactory

    from ki_knowledge.django_site import views_sync

    seen = {}

    def fake_export(domains=None, **include):
        seen.update(include, domains=domains)
        return {"domains": []}

    monkeypatch.setattr(views_sync, "_configured_sync_secret", lambda: "")
    monkeypatch.setattr(views_sync, "export_local_sync_payload", fake_export)
    request = RequestFactory().get("/knowledge/sync/export/?include_projects=0&include_knowledge=0&domain=a")
    assert views_sync.sync_export_view(request).status_code == 200
    assert seen == {"domains": ["a"], "include_projects": False, "include_documents": False, "include_knowledge": False}


def test_pull_view_forwards_operation_id(monkeypatch):
    from django.test import RequestFactory

    from ki_knowledge.django_site import distributed_api, views_sync

    monkeypatch.setattr(views_sync, "_configured_sync_secret", lambda: "")
    monkeypatch.setattr(
        distributed_api,
        "pull_from_master",
        lambda *, domains=None, operation_id="": {
            "requested_domains": domains,
            "operation_id": operation_id,
        },
    )
    request = RequestFactory().post(
        "/knowledge/sync/pull/",
        data={"domain": ["alpha"]},
        headers={"X-KI-Operation-Id": "operation-1"},
    )

    response = views_sync.sync_pull_view(request)

    assert response.status_code == 200
    assert json.loads(response.content) == {
        "status": "ok",
        "requested_domains": ["alpha"],
        "operation_id": "operation-1",
    }
