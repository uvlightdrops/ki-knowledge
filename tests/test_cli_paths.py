"""Path inspection uses the app's resolver and does not create directories."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from ki_knowledge.cli.framework import CLIBuilder
from ki_knowledge.data_layout import DataLayout
from ki_knowledge.services import domain_paths


@pytest.fixture
def paths_cli():
    config = Path(__file__).parents[1] / "ki_knowledge/cli/cli.yaml"
    return CLIBuilder.from_yaml_file(config).build_cli()


@pytest.mark.parametrize("version", [1, 2, 3])
def test_paths_resolve_epub(paths_cli, monkeypatch, tmp_path, version):
    root = tmp_path / "data"
    root.mkdir()
    (root / ".layout-version").write_text(str(version))
    layout = DataLayout(root)
    monkeypatch.setattr(domain_paths, "data_layout", lambda: layout)
    runner = CliRunner()

    result = runner.invoke(paths_cli, ["paths", "Anthro", "epub"])
    expected = layout.source_dir("epub", "anthro")
    assert result.exit_code == 0, result.output
    assert result.output == f"{expected}\n"
    assert not expected.exists()


def test_paths_honour_source_override(paths_cli, monkeypatch, tmp_path):
    layout = DataLayout(tmp_path, {"epub": tmp_path / "books"})
    monkeypatch.setattr(domain_paths, "data_layout", lambda: layout)
    result = CliRunner().invoke(paths_cli, ["paths", "anthro", "epub"])
    assert result.exit_code == 0, result.output
    assert result.output == f"{tmp_path / 'books' / 'anthro'}\n"


@pytest.mark.parametrize("args", [
    [],
    [" ", "epub"],
    ["anthro", "unknown"],
])
def test_paths_reject_invalid_usage(paths_cli, args):
    result = CliRunner().invoke(paths_cli, ["paths", *args])
    assert result.exit_code == 2


@pytest.mark.parametrize("version", [1, 2, 3])
def test_paths_list_only_existing_source_dirs(paths_cli, monkeypatch, tmp_path, version):
    layout = DataLayout(tmp_path, version=version)
    monkeypatch.setattr(domain_paths, "data_layout", lambda: layout)
    epub = layout.source_dir("epub", "anthro")
    epub.mkdir(parents=True)
    markdown = layout.source_dir("md", "anthro")
    markdown.mkdir(parents=True)
    result = CliRunner().invoke(paths_cli, ["paths", "Anthro"])
    assert result.exit_code == 0, result.output
    assert result.output == f"data_root: {tmp_path}\nlayout_version: {version}\nmd: {markdown}\nepub: {epub}\n"
    assert not layout.source_dir("pdf", "anthro").exists()


def test_paths_show_effective_root_when_config_value_is_empty(paths_cli, monkeypatch, tmp_path):
    from ki_knowledge.app_config import ConfigDict

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("KNOWLEDGE_DATA_ROOT", raising=False)
    monkeypatch.delenv("KICLI_DATA_ROOT", raising=False)
    monkeypatch.setattr(
        "ki_knowledge.app_config.load_config_cached",
        lambda path=None: ConfigDict({"knowledge": {"data_root": ""}}),
    )
    result = CliRunner().invoke(paths_cli, ["paths", "anthro"])
    assert result.exit_code == 0, result.output
    assert result.output == (
        f"data_root: {tmp_path / 'dev_data' / 'ki-knowledge'}\n"
        "layout_version: 3\n"
        "No source directories exist for this domain.\n"
    )


@pytest.mark.parametrize("domain", ["ab", "md", "pdf", "EPUB", "jira", "csv", "markdown"])
def test_paths_reject_invalid_domain_names(paths_cli, domain):
    result = CliRunner().invoke(paths_cli, ["paths", domain])
    assert result.exit_code == 1
    assert "Domain name" in result.output
