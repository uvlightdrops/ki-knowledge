from __future__ import annotations

import os
from pathlib import Path

from ki_knowledge.app_config import AppConfig, ConfigDict, clear_config_cache, load_config_cached


def test_load_config_cached_reuses_payload_until_inputs_change(tmp_path, monkeypatch):
    clear_config_cache()
    config_path = tmp_path / "ki.yaml"
    config_path.write_text("knowledge:\n  data_root: first\n", encoding="utf-8")
    calls: list[str] = []

    def fake_load_config(path: Path | None = None) -> ConfigDict:
        calls.append(Path(path).read_text(encoding="utf-8"))
        return ConfigDict({"knowledge": {"data_root": "first" if "first" in calls[-1] else "second"}})

    monkeypatch.setattr("ki_knowledge.app_config.load_config", fake_load_config)

    first = load_config_cached(config_path)
    second = load_config_cached(config_path)
    assert first["knowledge"]["data_root"] == "first"
    assert second["knowledge"]["data_root"] == "first"
    assert len(calls) == 1

    config_path.write_text("knowledge:\n  data_root: second\n", encoding="utf-8")
    third = load_config_cached(config_path)
    assert third["knowledge"]["data_root"] == "second"
    assert len(calls) == 2


def test_load_config_cached_returns_isolated_copies(tmp_path, monkeypatch):
    clear_config_cache()
    config_path = tmp_path / "ki.yaml"
    config_path.write_text("knowledge:\n  data_root: first\n", encoding="utf-8")
    monkeypatch.setattr(
        "ki_knowledge.app_config.load_config",
        lambda path=None: ConfigDict({"knowledge": {"data_root": "first"}}),
    )

    first = load_config_cached(config_path)
    first["knowledge"]["data_root"] = "changed"
    second = load_config_cached(config_path)

    assert second["knowledge"]["data_root"] == "first"


def test_app_config_from_env_uses_cached_loader(monkeypatch):
    clear_config_cache()
    calls = 0

    def fake_cached(path=None) -> ConfigDict:
        nonlocal calls
        calls += 1
        return ConfigDict({"knowledge": {"data_root": "/tmp/data"}})

    monkeypatch.setattr("ki_knowledge.app_config.load_config_cached", fake_cached)

    first = AppConfig.from_env()
    second = AppConfig.from_env()

    assert first.knowledge_data_root == "/tmp/data"
    assert second.knowledge_data_root == "/tmp/data"
    assert calls == 2


def test_env_change_invalidate_config_cache(tmp_path, monkeypatch):
    clear_config_cache()
    config_path = tmp_path / "ki.yaml"
    config_path.write_text("knowledge:\n  data_root: yaml\n", encoding="utf-8")
    seen: list[str] = []

    def fake_load_config(path=None) -> ConfigDict:
        seen.append(os.getenv("KI_CFG_KNOWLEDGE__DATA_ROOT", ""))
        return ConfigDict({"knowledge": {"data_root": seen[-1] or "yaml"}})

    monkeypatch.setattr("ki_knowledge.app_config.load_config", fake_load_config)

    assert load_config_cached(config_path)["knowledge"]["data_root"] == "yaml"
    monkeypatch.setenv("KI_CFG_KNOWLEDGE__DATA_ROOT", "/tmp/override")
    assert load_config_cached(config_path)["knowledge"]["data_root"] == "/tmp/override"
    assert seen == ["", "/tmp/override"]
