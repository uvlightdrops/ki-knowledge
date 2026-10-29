"""Verify distribution contents and imports without an editable checkout."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import venv
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
RESOURCE_SUFFIXES = {".html", ".css", ".js", ".ico", ".yaml", ".ttf"}


def run(*args, cwd):
    result = subprocess.run(
        args, cwd=cwd, text=True, capture_output=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def test_sdist_wheel_and_installed_package(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    for name in ("pyproject.toml", "README.md"):
        shutil.copy2(ROOT / name, source / name)
    shutil.copytree(
        ROOT / "ki_knowledge", source / "ki_knowledge",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    run(
        sys.executable, "-c",
        "from setuptools.build_meta import build_sdist; build_sdist('dist')",
        cwd=source,
    )
    archive = next((source / "dist").glob("*.tar.gz"))
    unpacked = tmp_path / "unpacked"
    unpacked.mkdir()
    # Only extract the local build's files, never links or traversal paths.
    with tarfile.open(archive) as distribution:
        for member in distribution.getmembers():
            target = (unpacked / member.name).resolve()
            assert target.is_relative_to(unpacked.resolve()), member.name
            assert member.isfile() or member.isdir(), member.name
        for member in distribution.getmembers():
            target = unpacked / member.name
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with distribution.extractfile(member) as content, target.open("wb") as output:
                    shutil.copyfileobj(content, output)
    rebuilt = next(unpacked.iterdir())
    run(
        sys.executable, "-c",
        "from setuptools.build_meta import build_wheel; build_wheel('dist')",
        cwd=rebuilt,
    )
    wheel = next((rebuilt / "dist").glob("*.whl"))
    with ZipFile(wheel) as distribution:
        names = set(distribution.namelist())
        expected = {
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "ki_knowledge").rglob("*")
            if path.is_file() and path.suffix in RESOURCE_SUFFIXES | {".py"}
        }
        assert expected <= names, sorted(expected - names)
        assert {
            "ki_knowledge/django_site/static/django_site/workbench/manifest.json",
            "ki_knowledge/django_site/static/django_site/workbench/THIRD-PARTY-NOTICES.txt",
        } <= names
        assert not any(name.startswith(("src/", "tests/", "config/")) for name in names)
        assert not any(
            name.endswith((".pyc", ".sqlite", ".sqlite3", ".env"))
            or "creds" in name or "__pycache__" in name for name in names
        )

    environment = tmp_path / "installed"
    # Reuse installed dependencies, but install ki-knowledge non-editably.
    venv.EnvBuilder().create(environment)
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    run(
        sys.executable, "-m", "pip", "--python", str(python),
        "install", "--no-deps", "--no-index", str(wheel), cwd=tmp_path,
    )
    site_packages = Path(run(
        str(python), "-I", "-c",
        "import sysconfig; print(sysconfig.get_path('purelib'))", cwd=tmp_path,
    ).strip())
    (site_packages / "test_dependencies.pth").write_text(
        f"import site; site.addsitedir({sysconfig.get_path('purelib')!r})\n",
        encoding="utf-8",
    )
    run(
        str(python), "-I", "-c",
        """
import importlib
from importlib.resources import files
from pathlib import Path
import sys

for name in (
    "ki_knowledge", "ki_knowledge.cli.main",
    "ki_knowledge.integrations.jira_assistant",
    "ki_knowledge.knowledge.models", "ki_knowledge.services",
    "ki_knowledge.django_site.migrations", "ki_knowledge.wagtail_cms",
    "ki_knowledge.graph.graph_store", "ki_knowledge.ingestion.ingestion",
    "ki_knowledge.search.hybrid_search",
    "ki_knowledge.services.domain_paths",
):
    module = importlib.import_module(name)
    assert Path(module.__file__).is_relative_to(Path(sys.prefix)), module.__file__
assert files("ki_knowledge.cli").joinpath("cli.yaml").is_file()
assert files("ki_knowledge").joinpath("widgetkit_templates/knowledge_overview_summary.html").is_file()
assert files("ki_knowledge.django_site").joinpath("static/django_site/favicon.ico").is_file()
assert files("ki_knowledge.django_site").joinpath("templates/kicli_django/settings_config.html").is_file()
assert files("ki_knowledge.wagtail_cms").joinpath("templates/wagtail_cms/knowledge_block_detail_page.html").is_file()
""",
        cwd=tmp_path,
    )
    output = run(
        str(python), "-I", "-m", "ki_knowledge.cli.main", "--help",
        cwd=tmp_path,
    )
    assert "nextcloud" in output and "infosite" in output
    script = python.parent / ("kictl.exe" if os.name == "nt" else "kictl")
    output = run(str(script), "--help", cwd=tmp_path)
    assert "nextcloud" in output and "infosite" in output
