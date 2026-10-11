import json
from unittest.mock import Mock
from types import SimpleNamespace

import pytest
import requests

from ki_knowledge import observation as obs
from ki_knowledge.data_layout import DataLayout
from ki_knowledge.integrations.knowledge_store import KnowledgeStore

URL = "http://127.0.0.1:17081/state?compact=true"


def state(tick, **overrides):
    return {"tick": tick, "nodeId": "ia3-1", "createdAt": "2026-10-10T22:47:38Z",
            "events": [f"event {i}" for i in range(50)], "agents": [{"id": 1}],
            **overrides}


@pytest.fixture
def stores(tmp_path):
    return obs.ObservationStore(tmp_path / "observation.sqlite"), KnowledgeStore(tmp_path / "knowledge.db")


@pytest.mark.parametrize("end", [1100, 1137])
def test_observed_threshold_raw_and_fidelity(stores, end):
    journal, knowledge = stores
    assert journal.capture(state(100), URL, "2026-10-10T23:00:00+00:00") is None
    assert journal.capture(state(1099), URL, "2026-10-10T23:00:10+00:00") is None
    assert journal.import_completed(knowledge) == 0
    completed = journal.capture(state(end), URL, "2026-10-10T23:00:20+00:00")
    assert completed
    artifact = journal.artifact(completed)
    assert artifact["status"] == "completed"
    assert artifact["actual_tick_span"] == end - 100
    assert artifact["requested_tick_span"] == 1000
    assert artifact["tick_gaps"] == [999, end - 1099]
    assert artifact["time_gaps_seconds"] == [10, 10]
    assert artifact["sample_count"] == 3
    assert artifact["unsampled_interior_ticks"] == sum(max(0, gap - 1) for gap in artifact["tick_gaps"])
    assert artifact["samples"][0]["state"] == state(100)
    assert "50 string events" in " ".join(artifact["limitations"])
    assert "complete event history is not guaranteed" in " ".join(artifact["limitations"])
    assert journal.import_completed(knowledge) == 1
    source = knowledge.get_source(completed)
    assert source.source_type == "ia3_observation"
    assert source.metadata["provenance"]["transport"] == "offline_local_import"
    raw = knowledge.get_artifact(completed + ":raw")
    assert json.loads(raw.content) == artifact
    assert raw.metadata["provenance"]["sha256"] == obs.hashlib.sha256(raw.content.encode()).hexdigest()
    assert knowledge.get_record(completed + ":summary").record_type == "text"
    active = [w for w in journal.status()["windows"] if w["status"] == "active"][0]
    assert active["start_tick"] == active["end_tick"] == end


def test_restart_and_duplicate_prevention_after_partial_import(stores, monkeypatch):
    journal, knowledge = stores
    journal.capture(state(500), URL)
    restarted = obs.ObservationStore(journal.path)
    completed = restarted.capture(state(1501), URL)
    original = knowledge.upsert_artifact
    attempts = []

    def fail_after_write(artifact):
        attempts.append(artifact.artifact_id)
        original(artifact)
        raise RuntimeError("simulated crash after knowledge write before receipt")

    monkeypatch.setattr(knowledge, "upsert_artifact", fail_after_write)
    with pytest.raises(RuntimeError, match="simulated crash"):
        restarted.import_completed(knowledge)
    assert restarted.status()["failure_count"] == 1
    assert restarted.status()["windows"][0]["imported_at"] is None
    monkeypatch.setattr(knowledge, "upsert_artifact", original)
    resumed = obs.ObservationStore(journal.path)
    assert resumed.import_completed(knowledge) == 1
    assert resumed.import_completed(knowledge) == 0
    assert len(knowledge.list_sources("ia3_observation")) == 1
    assert len(knowledge.list_records(source_id=completed)) == 1
    assert len(knowledge.list_artifacts(source_id=completed)) == 1
    assert attempts == [completed + ":raw"]


@pytest.mark.parametrize("new_state,reason", [
    (state(2000, nodeId="ia3-2"), "source_identity_changed"),
    (state(2000, createdAt="2026-10-11T00:00:00Z"), "source_identity_changed"),
    (state(10), "tick_regressed"),
])
def test_reset_interrupts_without_joining_distinct_runs(stores, new_state, reason):
    journal, knowledge = stores
    journal.capture(state(100), URL)
    journal.capture(state(900), URL)
    assert journal.capture(new_state, URL) is None
    assert journal.import_completed(knowledge) == 0
    partial, active = journal.status()["windows"]
    assert partial["status"] == "interrupted"
    assert partial["interruption_reason"] == reason
    assert partial["actual_tick_span"] == 800
    assert active["start_tick"] == new_state["tick"]
    assert active["sample_count"] == 1
    assert knowledge.list_sources("ia3_observation") == []


def test_changed_url_and_paused_ticks(stores):
    journal, _ = stores
    journal.capture(state(100), URL)
    journal.capture(state(100), URL)
    assert journal.status()["windows"][0]["actual_tick_span"] == 0
    journal.capture(state(1200), URL.replace("17081", "17082"))
    assert [w["status"] for w in journal.status()["windows"]] == ["interrupted", "active"]


def test_capture_failure_does_not_fabricate_sample_and_recovers(stores, monkeypatch, caplog):
    journal, knowledge = stores
    journal.capture(state(0), URL)
    monkeypatch.setattr(obs, "fetch_state", Mock(side_effect=requests.Timeout("bounded request timeout")))
    assert obs.cycle(journal, knowledge, URL, 0.1) is False
    assert "capture failed" in caplog.text
    assert journal.status()["failure_count"] == 1
    assert journal.status()["windows"][0]["sample_count"] == 1
    monkeypatch.setattr(obs, "fetch_state", Mock(return_value=state(1010)))
    assert obs.cycle(journal, knowledge, URL, 0.1) is True
    completed = journal.status()["windows"][0]
    assert completed["actual_tick_span"] == completed["max_tick_gap"] == 1010
    assert len(completed["capture_failures"]) == 1
    assert completed["imported_at"]


def test_import_retry_works_when_source_is_unavailable(stores, monkeypatch):
    journal, knowledge = stores
    journal.capture(state(0), URL)
    journal.capture(state(1000), URL)
    monkeypatch.setattr(obs, "fetch_state", Mock(side_effect=requests.ConnectionError("offline")))
    assert not obs.cycle(journal, knowledge, URL, 1)
    assert journal.status()["windows"][0]["imported_at"]
    assert len(knowledge.list_sources("ia3_observation")) == 1


def test_worker_import_failure_does_not_stop_captures(stores, monkeypatch, caplog):
    journal, knowledge = stores
    journal.capture(state(0), URL)
    monkeypatch.setattr(obs, "fetch_state", Mock(return_value=state(1000)))
    monkeypatch.setattr(knowledge, "upsert_source", Mock(side_effect=RuntimeError("store unavailable")))
    assert not obs.cycle(journal, knowledge, URL, 1)
    assert journal.status()["windows"][0]["status"] == "completed"
    assert journal.status()["windows"][0]["imported_at"] is None
    monkeypatch.setattr(obs, "fetch_state", Mock(return_value=state(1001)))
    assert not obs.cycle(journal, knowledge, URL, 1)
    assert journal.status()["windows"][1]["sample_count"] == 2
    assert "store unavailable" in caplog.text


@pytest.mark.parametrize("bad", [
    [], state(True), state(-1), state(1, nodeId=""), state(1, createdAt=None),
    state(1, events=[{}]), state(1, events=["x"] * 51),
])
def test_invalid_state_is_explicitly_rejected(stores, bad):
    journal, _ = stores
    with pytest.raises(ValueError):
        journal.capture(bad, URL)
    assert journal.status()["windows"] == []


@pytest.mark.parametrize("url", ["http://flowpad/state", "https://127.0.0.1/state",
                                "http://user:secret@localhost/state"])
def test_only_local_transport(url):
    with pytest.raises(ValueError, match="loopback"):
        obs.local_url(url)


@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan")])
def test_bounded_positive_configuration(value):
    with pytest.raises(ValueError, match="finite positive"):
        obs.positive_seconds(value)


def test_http_contract_timeout_redirects_and_proxy_settings(monkeypatch):
    session = Mock()
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    response = session.get.return_value
    response.status_code = 200
    response.json.return_value = state(42)
    monkeypatch.setattr(obs.requests, "Session", Mock(return_value=session))
    assert obs.fetch_state(URL, 2) == state(42)
    assert session.trust_env is False
    session.get.assert_called_once_with(URL, timeout=2, allow_redirects=False)
    for code in (302, 500):
        response.status_code = code
        with pytest.raises(ValueError, match=f"HTTP {code}"):
            obs.fetch_state(URL, 2)
    response.status_code = 200
    response.json.side_effect = ValueError("invalid JSON")
    with pytest.raises(ValueError, match="invalid JSON"):
        obs.fetch_state(URL, 2)


def test_exclusive_worker_lock(stores):
    journal, _ = stores
    with journal.worker_lock():
        with pytest.raises(RuntimeError, match="another observation"):
            with obs.ObservationStore(journal.path).worker_lock():
                pass
    with journal.worker_lock():
        pass


@pytest.mark.parametrize("version", [1, 2, 3])
def test_observation_journal_follows_data_layout(tmp_path, version):
    (tmp_path / ".layout-version").write_text(str(version))
    layout = DataLayout(root=tmp_path)
    expected = tmp_path / "observation.sqlite" if version == 1 else tmp_path / "system" / "observation.sqlite"
    assert layout.observation_db_path() == expected


def test_cli_offline_import_and_status(stores, monkeypatch, capsys):
    journal, knowledge = stores
    journal.capture(state(0), URL)
    journal.capture(state(1000), URL)
    cfg = SimpleNamespace(raw=SimpleNamespace(get_path=lambda *args: {}))
    monkeypatch.setattr(obs.AppConfig, "from_env", lambda: cfg)
    monkeypatch.setattr(obs.DataLayout, "from_config", lambda cfg: SimpleNamespace(
        observation_db_path=lambda: journal.path,
    ))
    monkeypatch.setattr(obs, "knowledge_store_target", lambda cfg: knowledge.target)
    monkeypatch.setattr(obs, "fetch_state", Mock(side_effect=AssertionError("offline import must not fetch")))
    assert obs.main(["import"]) == 0
    assert obs.main(["import"]) == 0
    assert obs.main(["status"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["windows"][0]["imported_at"]
    assert len(knowledge.list_sources("ia3_observation")) == 1
    obs.fetch_state.assert_not_called()


def test_cli_periodic_run_recovers_and_retains_active_on_stop(stores, monkeypatch):
    journal, knowledge = stores
    cfg = SimpleNamespace(raw=SimpleNamespace(get_path=lambda *args: {}))
    monkeypatch.setattr(obs.AppConfig, "from_env", lambda: cfg)
    monkeypatch.setattr(obs.DataLayout, "from_config", lambda cfg: SimpleNamespace(
        observation_db_path=lambda: journal.path,
    ))
    monkeypatch.setattr(obs, "knowledge_store_target", lambda cfg: knowledge.target)
    monkeypatch.setattr(obs, "fetch_state", Mock(side_effect=[
        requests.Timeout("timeout"), state(50), state(1055),
    ]))
    sleep = Mock(side_effect=[None, None, KeyboardInterrupt()])
    monkeypatch.setattr(obs.time, "sleep", sleep)
    assert obs.main(["run", "--interval", "0.1", "--timeout", "0.2"]) == 0
    assert sleep.call_count == 3
    sleep.assert_called_with(0.1)
    windows = journal.status()["windows"]
    assert windows[0]["status"] == "completed"
    assert windows[0]["actual_tick_span"] == 1005
    assert windows[0]["imported_at"]
    assert windows[1]["status"] == "active"
    with journal.worker_lock():
        pass
