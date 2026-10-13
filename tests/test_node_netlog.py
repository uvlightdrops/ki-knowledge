import requests

from ki_knowledge.node_sync import netlog
from ki_knowledge.node_sync.client import SyncClient


def test_outgoing_logged_without_secret(tmp_path, monkeypatch):
    log = tmp_path / "net.log"
    monkeypatch.setenv(netlog.ENV_PATH, str(log))

    class R:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {}

    monkeypatch.setattr(requests, "request", lambda *a, **k: R())
    SyncClient("http://10.0.0.2:8000/", secret="TOPSECRET").trigger_pull(domains=["d"], operation_id="op1")
    text = log.read_text()
    assert "out http://10.0.0.2:8000 POST /knowledge/sync/pull/ 200" in text and "op=op1" in text
    assert "TOPSECRET" not in text and "?" not in text.split(" ", 2)[-1]


def test_connection_failure_logged_and_reraised(tmp_path, monkeypatch):
    log = tmp_path / "net.log"
    monkeypatch.setenv(netlog.ENV_PATH, str(log))

    def boom(*a, **k):
        raise requests.exceptions.ConnectionError("x")

    monkeypatch.setattr(requests, "request", boom)
    try:
        SyncClient("http://10.0.0.2:8000").describe()
        raise AssertionError
    except requests.exceptions.ConnectionError:
        pass
    assert "connection_failed" in log.read_text()


def test_probe_logs_only_state_changes(tmp_path, monkeypatch):
    log = tmp_path / "net.log"
    monkeypatch.setenv(netlog.ENV_PATH, str(log))
    netlog._last_probe.clear()
    for _ in range(3):
        netlog.log_probe("http://h:1", "reachable", "", 5)
    netlog.log_probe("http://h:1", "error", "Descriptor connection failed", None)
    assert len(log.read_text().splitlines()) == 2


def test_logging_failure_is_swallowed(monkeypatch):
    monkeypatch.setenv(netlog.ENV_PATH, "/proc/nope/x.log")
    netlog.log_event("out", "http://h", "GET", "/p", "200")
