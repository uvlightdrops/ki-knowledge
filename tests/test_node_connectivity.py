import json
import os
import time
from types import SimpleNamespace
from unittest.mock import Mock

import django
import pytest
import requests

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ki_knowledge.django_site.settings")
django.setup()

from django.core.cache import cache
from django.test import RequestFactory
from django.urls import reverse

from ki_knowledge.django_site import node_connectivity as nc


@pytest.fixture(autouse=True)
def isolated_cache():
    cache.clear()
    yield
    cache.clear()


def request(method="get", query=""):
    req = getattr(RequestFactory(), method)("/knowledge/sync/connectivity/" + query)
    req.user = SimpleNamespace(is_authenticated=True)
    return req


def peer(node_id="remote", url="http://remote.test", label="Remote"):
    return nc.Peer(node_id, label, url, node_id)


def candidates(monkeypatch, rows, **overrides):
    runtime = SimpleNamespace(node_id="local", role="master", distributed_enabled=True, master_url="")
    for name, value in overrides.items():
        setattr(runtime, name, value)
    monkeypatch.setattr(nc, "get_runtime_node_settings", lambda: runtime)

    class Query:
        def __init__(self, items):
            self.items = items

        def exclude(self, **kwargs):
            assert kwargs == {"node_id": "local"}
            return Query([row for row in self.items if row.node_id != "local"])

        def order_by(self, *args):
            assert args == ("node_id",)
            return self

        def only(self, *args):
            assert set(args) == {"node_id", "display_name", "base_url"}
            return self.items

    def filtered(**kwargs):
        assert kwargs == {"is_enabled": True}
        return Query([row for row in rows if row.is_enabled])

    monkeypatch.setattr(nc.NodeConfig.objects, "filter", filtered)


def row(node_id, url, enabled=True):
    return SimpleNamespace(node_id=node_id, display_name=node_id, base_url=url, is_enabled=enabled)


def test_candidates_exclude_local_disabled_and_same_origin(monkeypatch):
    candidates(monkeypatch, [
        row("local", "http://local.test"), row("disabled", "http://disabled.test", False),
        row("alias", "http://testserver:80"), row("other", "http://other.test"), row("missing", ""),
    ])
    peers, local_id = nc.configured_peers(request(query="?url=http://untrusted.test"))
    assert local_id == "local"
    assert [p.node_id for p in peers] == ["other", "missing"]


def test_host_legacy_master_target_is_used_once(monkeypatch):
    candidates(monkeypatch, [], role="host", master_url="http://master.test")
    peers, _ = nc.configured_peers(request())
    assert peers == [nc.Peer("configured-master", "Master", "http://master.test", "")]
    candidates(monkeypatch, [row("master", "http://master.test/")], role="host", master_url="http://master.test")
    assert len(nc.configured_peers(request())[0]) == 1


@pytest.mark.parametrize("overrides", [
    {"role": "host", "distributed_enabled": False, "master_url": "http://master.test"},
    {"role": "standalone", "master_url": "http://master.test"},
    {"role": "host", "master_url": "http://testserver"},
])
def test_no_master_guessing_or_self_probe(monkeypatch, overrides):
    candidates(monkeypatch, [], **overrides)
    assert nc.configured_peers(request())[0] == []


@pytest.mark.parametrize("url", [
    "ftp://remote.test", "http://user:password@remote.test", "http://remote.test?sync_secret=secret",
    "http://remote.test#secret", "http://remote.test:bad", "http://[", "http://remote.test/\n",
])
def test_invalid_urls_never_make_requests(monkeypatch, url):
    get = Mock(side_effect=AssertionError("Network must not be used"))
    monkeypatch.setattr(requests.Session, "get", get)
    result = nc.probe_peer(peer(url=url), "local")
    assert result["status"] == "error"
    assert "secret" not in json.dumps(result) and "password" not in json.dumps(result)
    get.assert_not_called()


def fake_http(monkeypatch, payload=None, status=200, chunks=None, error=None):
    response = Mock(status_code=status)
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.iter_content.return_value = chunks if chunks is not None else [json.dumps(payload).encode()]
    session = Mock()
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    session.get.return_value = response
    if error:
        session.get.side_effect = error
    monkeypatch.setattr(nc.requests, "Session", lambda: session)
    return session


def test_success_has_actual_ms_and_no_auth_or_redirects(monkeypatch):
    session = fake_http(monkeypatch, {"node_id": "remote", "protocol_versions": ["0.1"], "secret": "never-return"})
    clock = iter([10, 10.01, 10.023])
    monkeypatch.setattr(nc.time, "monotonic", lambda: next(clock))
    result = nc.probe_peer(peer(), "local")
    assert result["status"] == "reachable" and result["rtt_ms"] == 23
    assert "never-return" not in json.dumps(result)
    assert session.trust_env is False
    session.get.assert_called_once_with(
        "http://remote.test/knowledge/sync/node/", timeout=(0.4, 0.6),
        allow_redirects=False, stream=True,
        headers={"Accept": "application/json", "Accept-Encoding": "identity"},
    )


@pytest.mark.parametrize("status", [301, 302, 403, 404, 500])
def test_http_errors_are_not_success(monkeypatch, status):
    fake_http(monkeypatch, status=status)
    result = nc.probe_peer(peer(), "local")
    assert result["status"] == "error" and result["error"] == f"HTTP {status}"
    assert result["rtt_ms"] is None


@pytest.mark.parametrize("payload", [
    [], {}, {"node_id": "", "protocol_versions": ["0.1"]},
    {"node_id": "remote", "protocol_versions": []},
    {"node_id": "remote", "protocol_versions": ["bad"]},
    {"node_id": "remote", "protocol_versions": [1]},
    {"node_id": "local", "protocol_versions": ["0.1"]},
    {"node_id": "wrong-peer", "protocol_versions": ["0.1"]},
])
def test_invalid_descriptors_and_identities(monkeypatch, payload):
    fake_http(monkeypatch, payload)
    assert nc.probe_peer(peer(), "local")["status"] == "error"


@pytest.mark.parametrize("chunks", [[b"{invalid"], [b"\xff"], [b"x" * (nc.MAX_RESPONSE_BYTES + 1)]])
def test_malformed_and_oversized_body(monkeypatch, chunks):
    fake_http(monkeypatch, chunks=chunks)
    assert nc.probe_peer(peer(), "local")["status"] == "error"


@pytest.mark.parametrize("error,expected", [
    (requests.exceptions.Timeout("secret-url"), "Descriptor timeout (1 s)"),
    (requests.exceptions.ConnectionError("secret-url"), "Descriptor connection failed"),
])
def test_network_error_is_sanitized(monkeypatch, error, expected):
    fake_http(monkeypatch, error=error)
    result = nc.probe_peer(peer(), "local")
    assert result["error"] == expected and result["rtt_ms"] is None
    assert "secret-url" not in json.dumps(result)


def test_missing_url_is_not_configured():
    assert nc.probe_peer(peer(url=""), "local")["status"] == "not_configured"


def test_probe_deadline(monkeypatch):
    fake_http(monkeypatch, {"node_id": "remote", "protocol_versions": ["0.1"]})
    clock = iter([10, 11.01])
    monkeypatch.setattr(nc.time, "monotonic", lambda: next(clock))
    assert "timeout" in nc.probe_peer(peer(), "local")["error"]


def test_polling_capped_cached_and_read_only(monkeypatch):
    peers = [peer(str(i)) for i in range(9)]
    monkeypatch.setattr(nc, "configured_peers", lambda req: (peers, "local"))
    probe = Mock(side_effect=lambda p, local_id: nc._result(p, "reachable", rtt_ms=5))
    monkeypatch.setattr(nc, "probe_peer", probe)
    response = nc.node_connectivity_view(request(query="?url=http://untrusted.test"))
    payload = json.loads(response.content)
    assert probe.call_count == 4
    assert len(payload["peers"]) == 3 and payload["overflow"] == 6 and payload["unprobed"] == 5
    assert payload["cache_seconds"] == 30 and payload["timeout_ms"] == 1000
    assert response["Cache-Control"] == "no-store"
    assert json.loads(nc.node_connectivity_view(request()).content) == payload
    assert probe.call_count == 4
    assert nc.node_connectivity_view(request("post")).status_code == 405


def test_empty_candidates_and_login(monkeypatch):
    monkeypatch.setattr(nc, "configured_peers", lambda req: ([], "local"))
    assert json.loads(nc.node_connectivity_view(request()).content)["status"] == "not_configured"
    req = request()
    req.user.is_authenticated = False
    assert nc.node_connectivity_view(req).status_code == 302
    assert reverse("node-connectivity") == "/knowledge/sync/connectivity/"


def test_stampede_returns_checking_without_probe(monkeypatch):
    monkeypatch.setattr(nc, "configured_peers", lambda req: ([peer()], "local"))
    monkeypatch.setattr(nc.cache, "add", lambda *args, **kwargs: False)
    monkeypatch.setattr(nc, "probe_peer", Mock(side_effect=AssertionError("Duplicate probe")))
    assert json.loads(nc.node_connectivity_view(request()).content)["status"] == "checking"


def test_cache_expiry_refreshes_and_lock_is_released(monkeypatch):
    monkeypatch.setattr(nc, "configured_peers", lambda req: ([peer()], "local"))
    probe = Mock(side_effect=lambda p, local_id: nc._result(p, "reachable", rtt_ms=5))
    monkeypatch.setattr(nc, "probe_peer", probe)
    save = Mock(wraps=cache.set)
    monkeypatch.setattr(nc.cache, "set", save)
    nc.node_connectivity_view(request())
    key = save.call_args.args[0]
    assert save.call_args.kwargs == {"timeout": 30}
    assert cache.get(key + ":lock") is None
    cache.delete(key)
    nc.node_connectivity_view(request())
    assert probe.call_count == 2


def test_concurrent_overall_wait_is_bounded(monkeypatch):
    peers = [peer(str(i)) for i in range(4)]
    monkeypatch.setattr(nc, "configured_peers", lambda req: (peers, "local"))

    def slow_probe(p, local_id):
        time.sleep(0.2)
        return nc._result(p, "reachable", rtt_ms=200)

    monkeypatch.setattr(nc, "probe_peer", slow_probe)
    started = time.monotonic()
    payload = json.loads(nc.node_connectivity_view(request()).content)
    assert time.monotonic() - started < 0.6
    assert all(p["status"] == "reachable" for p in payload["peers"])


def test_overall_deadline_does_not_wait_for_workers(monkeypatch):
    import threading

    release = threading.Event()
    monkeypatch.setattr(nc, "configured_peers", lambda req: ([peer()], "local"))

    def stuck_probe(p, local_id):
        release.wait(3)
        return nc._result(p, "reachable", rtt_ms=2000)

    monkeypatch.setattr(nc, "probe_peer", stuck_probe)
    started = time.monotonic()
    try:
        payload = json.loads(nc.node_connectivity_view(request()).content)
        assert time.monotonic() - started < 1.5
        assert payload["peers"][0]["status"] == "error"
        assert "timeout" in payload["peers"][0]["error"]
    finally:
        release.set()
