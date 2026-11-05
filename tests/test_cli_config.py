"""Config inspection follows the same layered loader as the app."""

import os
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from ki_knowledge.app_config import ConfigDict, clear_config_cache
from ki_knowledge.cli.framework import CLIBuilder


@pytest.fixture
def config_cli():
    config = Path(__file__).parents[1] / "ki_knowledge/cli/cli.yaml"
    return CLIBuilder.from_yaml_file(config).build_cli()


@pytest.mark.parametrize(("key", "expected"), [
    ("knowledge.data_root", "/private/books\n"),
    ("enabled", "false\n"),
    ("count", "0\n"),
    ("unset", "null\n"),
    ("empty", "\n"),
    ("knowledge", "data_root: /private/books\n"),
])
def test_config_show_values(config_cli, monkeypatch, key, expected):
    payload = ConfigDict({
        "knowledge": {"data_root": "/private/books"},
        "enabled": False, "count": 0, "unset": None, "empty": "",
    })
    monkeypatch.setattr("ki_knowledge.app_config.load_config_cached", lambda path=None: payload)
    result = CliRunner().invoke(config_cli, ["config", "show", key])
    assert result.exit_code == 0, result.output
    assert result.output == expected


def test_config_show_whole_config(config_cli, monkeypatch):
    payload = ConfigDict({"knowledge": {"data_root": "/private/books"}})
    monkeypatch.setattr("ki_knowledge.app_config.load_config_cached", lambda path=None: payload)
    result = CliRunner().invoke(config_cli, ["config", "show"])
    assert result.exit_code == 0, result.output
    assert yaml.safe_load(result.output) == payload


@pytest.mark.parametrize("key", ["missing", "knowledge.missing", "knowledge.data_root.child"])
def test_config_show_missing_key_fails(config_cli, monkeypatch, key):
    payload = ConfigDict({"knowledge": {"data_root": "/private/books"}})
    monkeypatch.setattr("ki_knowledge.app_config.load_config_cached", lambda path=None: payload)
    result = CliRunner().invoke(config_cli, ["config", "show", key])
    assert result.exit_code == 1
    assert f"Configuration key not found: {key}" in result.output


@pytest.mark.parametrize(("top_layer", "expected"), [
    ("defaults", "/defaults"),
    ("main", "/main"),
    ("profile", "/profile"),
    ("stage", "/stage"),
    ("runtime", "/runtime"),
    ("env", "/env"),
    ("creds", "/creds"),
])
def test_config_show_real_layer_precedence(config_cli, monkeypatch, tmp_path, top_layer, expected):
    for name in os.environ:
        if name.startswith("KI_CFG_") or name in {"KI_STAGE", "KI_PROFILE"}:
            monkeypatch.delenv(name)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    clear_config_cache()
    files = [
        ("config/defaults/app.yaml", "/defaults"),
        ("ki.yaml", "/main"),
        ("config/profiles/test.yaml", "/profile"),
        ("config/stages/test.yaml", "/stage"),
        ("config/runtime/runtime.yaml", "/runtime"),
    ]
    layers = ["defaults", "main", "profile", "stage", "runtime", "env", "creds"]
    for (filename, value), layer in zip(files, layers):
        if layers.index(layer) > layers.index(top_layer):
            break
        path = tmp_path / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump({"knowledge": {"data_root": value}}))
        if layer == "profile":
            monkeypatch.setenv("KI_PROFILE", "test")
        elif layer == "stage":
            monkeypatch.setenv("KI_STAGE", "test")
    if top_layer in {"env", "creds"}:
        monkeypatch.setenv("KI_CFG_KNOWLEDGE__DATA_ROOT", "/env")
    if top_layer == "creds":
        (tmp_path / "creds.yaml").write_text("knowledge:\n  data_root: /creds\n")

    result = CliRunner().invoke(config_cli, ["config", "show", "knowledge.data_root"])
    assert result.exit_code == 0, result.output
    assert result.output == f"{expected}\n"
