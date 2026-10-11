import json
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server
from socketserver import ThreadingMixIn

import django
import pytest
import requests

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ki_knowledge.django_site.settings")
django.setup()

from django.core.handlers.wsgi import WSGIHandler

from ki_knowledge.django_site import distributed_api, distributed_sync, views_sync
from ki_knowledge.node_sync import SyncClient


class _ThreadedWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True
    allow_reuse_address = True


class _QuietWSGIRequestHandler(WSGIRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture()
def wsgi_servers():
    servers = []

    def start():
        server = make_server(
            "127.0.0.1",
            0,
            WSGIHandler(),
            server_class=_ThreadedWSGIServer,
            handler_class=_QuietWSGIRequestHandler,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append((server, thread))
        return f"http://127.0.0.1:{server.server_port}"

    yield start

    for server, thread in reversed(servers):
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        assert not thread.is_alive()


@pytest.fixture()
def response_server():
    servers = []

    def start(handler):
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append((server, thread))
        return f"http://127.0.0.1:{server.server_port}"

    yield start

    for server, thread in reversed(servers):
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        assert not thread.is_alive()


def test_sync_client_calls_real_django_node_view(wsgi_servers, monkeypatch):
    from ki_knowledge.node_sync import NodeSettings, describe

    node = NodeSettings(node_id="master-a", role="master", shared_secret="never-return-this")
    monkeypatch.setattr(views_sync, "describe_local_node", lambda: describe(node, instance_id="boot-a"))

    description = SyncClient(wsgi_servers()).describe()

    assert description["node_id"] == "master-a"
    assert description["protocol_versions"] == ["0.1"]
    assert "never-return-this" not in json.dumps(description)


def test_real_heartbeat_view_checks_secret_and_accepts_valid_request(wsgi_servers, monkeypatch):
    imported = []
    monkeypatch.setattr(views_sync, "_configured_sync_secret", lambda: "correct-secret")
    monkeypatch.setattr(
        views_sync,
        "import_remote_heartbeat",
        lambda payload: imported.append(payload) or SimpleNamespace(node_id=payload["node_id"], role="host"),
    )
    origin = wsgi_servers()

    for secret in ("", "wrong-secret"):
        with pytest.raises(requests.HTTPError) as error:
            SyncClient(origin, secret=secret).heartbeat({"node_id": "host-a"})
        assert error.value.response.status_code == 403
    assert imported == []

    response = SyncClient(origin, secret="correct-secret").heartbeat({"node_id": "host-a"})

    assert response == {"status": "ok", "node_id": "host-a", "role": "host"}
    assert imported == [{"node_id": "host-a"}]


@pytest.mark.parametrize(
    ("body", "message"),
    [("{", "invalid json body"), ("[]", "json body must be an object")],
)
def test_real_heartbeat_view_rejects_malformed_or_non_object_json(wsgi_servers, monkeypatch, body, message):
    monkeypatch.setattr(views_sync, "_configured_sync_secret", lambda: "secret")
    origin = wsgi_servers()

    response = requests.post(
        origin + "/knowledge/sync/heartbeat/",
        data=body,
        headers={"Content-Type": "application/json", "X-KI-Sync-Secret": "secret"},
        timeout=5,
    )

    assert response.status_code == 400
    assert message in response.text


def test_real_heartbeat_view_rejects_foreign_federation_without_registry_write(wsgi_servers, monkeypatch):
    writes = []
    monkeypatch.setattr(views_sync, "_configured_sync_secret", lambda: "secret")
    monkeypatch.setattr(distributed_sync.Config, "from_env", lambda: SimpleNamespace(distributed_federation_id="lab"))
    monkeypatch.setattr(
        distributed_sync.NodeConfig.objects,
        "update_or_create",
        lambda **kwargs: writes.append(kwargs),
    )
    origin = wsgi_servers()

    with pytest.raises(requests.HTTPError) as error:
        SyncClient(origin, secret="secret").heartbeat(
            {"node_id": "host-a", "federation_id": "other"}
        )

    assert error.value.response.status_code == 400
    assert "federation" in error.value.response.text
    assert writes == []


def test_facade_triggers_host_pull_and_host_fetches_master_export(wsgi_servers, monkeypatch):
    master_origin = wsgi_servers()
    host_origin = wsgi_servers()
    exports = []
    imports = []
    finished = []
    host = SimpleNamespace(node_id="host-a", role="host", base_url=host_origin)
    monkeypatch.setattr(views_sync, "_configured_sync_secret", lambda: "shared-secret")
    monkeypatch.setattr(distributed_sync, "resolved_sync_secret", lambda: "shared-secret")
    monkeypatch.setattr(distributed_sync, "resolved_master_url", lambda: master_origin)
    monkeypatch.setattr(distributed_sync.Config, "from_env", lambda: SimpleNamespace(request_timeout=5))
    monkeypatch.setattr(distributed_sync, "new_operation_id", lambda: "operation-42")
    monkeypatch.setattr(
        distributed_sync.NodeConfig.objects,
        "filter",
        lambda **kwargs: SimpleNamespace(first=lambda: host),
    )
    monkeypatch.setattr(
        views_sync,
        "export_local_sync_payload",
        lambda domains=None, **include: exports.append((domains, include))
        or {"node": {"node_id": "master-a"}, "domains": []},
    )
    monkeypatch.setattr(distributed_sync, "record_sync_run_started", lambda **kwargs: object())
    monkeypatch.setattr(
        distributed_sync,
        "apply_remote_domain_payload",
        lambda payload: imports.append(payload) or {"count": 0, "applied_domains": []},
    )
    monkeypatch.setattr(
        distributed_sync,
        "record_sync_run_finished",
        lambda run, **kwargs: finished.append(kwargs),
    )

    result = distributed_api.send_host_pull_command(host_node_id="host-a", domains=[" alpha ", ""])

    assert result["host_node_id"] == "host-a"
    assert result["requested_domains"] == ["alpha"]
    assert result["operation_id"] == "operation-42"
    assert result["status"] == "ok"
    assert imports == [{"node": {"node_id": "master-a"}, "domains": []}]
    assert exports == [(["alpha"], {
        "include_projects": True,
        "include_documents": True,
        "include_knowledge": True,
    })]
    assert finished[0]["status"] == "succeeded"
    assert finished[0]["summary"]["operation_id"] == "operation-42"


@pytest.mark.parametrize(
    ("body", "expected_exception"),
    [
        ('{"node_id":"n"}', None),
        ("not-json", requests.exceptions.JSONDecodeError),
        ("[]", ValueError),
    ],
)
def test_sync_client_describe_handles_valid_and_invalid_http_json(
    response_server, body, expected_exception
):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            encoded = body.encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, *args):
            pass

    client = SyncClient(response_server(Handler))
    if expected_exception is None:
        assert client.describe() == {"node_id": "n"}
    else:
        with pytest.raises(expected_exception):
            client.describe()


@pytest.mark.parametrize("status", [403, 500])
def test_sync_client_surfaces_real_http_error_status(response_server, status):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args):
            pass

    with pytest.raises(requests.HTTPError) as error:
        SyncClient(response_server(Handler)).describe()

    assert error.value.response.status_code == status


def test_sync_client_surfaces_socket_close(response_server):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.connection.close()

        def log_message(self, *args):
            pass

    with pytest.raises(requests.exceptions.ConnectionError):
        SyncClient(response_server(Handler)).describe()


def test_sync_client_connection_refusal():
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        port = reserved.getsockname()[1]
    with pytest.raises(requests.exceptions.ConnectionError):
        SyncClient(f"http://127.0.0.1:{port}").describe()


def test_sync_client_timeout_is_bounded_and_does_not_retry(response_server):
    hits = []
    complete = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            time.sleep(5.2)
            try:
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"{}")
            except OSError:
                pass
            finally:
                complete.set()

        def log_message(self, *args):
            pass

    client = SyncClient(response_server(Handler), timeout=0.01)
    started = time.monotonic()
    with pytest.raises(requests.exceptions.Timeout):
        client.describe()
    elapsed = time.monotonic() - started
    assert 4.5 <= elapsed < 6.5
    assert complete.wait(timeout=2)
    assert hits == ["/knowledge/sync/node/"]


def test_sync_client_recovers_after_explicit_retry_without_implicit_retry(response_server):
    hits = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            if len(hits) == 1:
                self.send_response(500)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            body = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    client = SyncClient(response_server(Handler))
    with pytest.raises(requests.HTTPError):
        client.describe()
    assert hits == ["/knowledge/sync/node/"]
    assert client.describe() == {"status": "ok"}
    assert hits == ["/knowledge/sync/node/", "/knowledge/sync/node/"]
