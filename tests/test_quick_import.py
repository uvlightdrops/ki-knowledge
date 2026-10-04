"""Tests for the path-free quick import (upload routing, per-folder rows)."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from ki_knowledge.django_site import quick_import


class _Upload:
    def __init__(self, name: str, data: bytes):
        self.name = name
        self._data = data

    def chunks(self):
        yield self._data


@pytest.fixture
def domain_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(quick_import, "domain_source_dir", lambda source_type, domain: tmp_path / source_type)
    monkeypatch.setattr(quick_import, "invalidate_domain_summary_cache", lambda domain: None)
    return tmp_path


def test_uploads_are_routed_by_format_and_never_overwrite(domain_dirs, monkeypatch):
    queued: list[Path] = []
    imported: list[Path] = []
    image_modes: list[str] = []
    monkeypatch.setattr(quick_import, "_queue_pdf", lambda domain: queued.append)
    monkeypatch.setattr(
        "ki_knowledge.django_site.source_workflow.import_mixed_file",
        lambda path, domain=None, image_processing="ocr": (
            imported.append(path),
            image_modes.append(image_processing),
            {"imported": 1},
        )[-1],
    )
    (domain_dirs / "mix").mkdir()
    (domain_dirs / "mix" / "t.csv").write_text("old")

    result = quick_import.save_and_import_uploads(
        [
            _Upload("t.csv", b"a\n1\n"),
            _Upload("../../evil/doc.pdf", b"%PDF"),
            _Upload("pic.png", b"png"),
            _Upload("notes.md", b"# x"),
            _Upload("report.docx", b"z"),
            _Upload(".hidden.md", b"z"),
        ],
        "demo",
    )

    assert (domain_dirs / "mix" / "t.csv").read_text() == "old"
    assert (domain_dirs / "mix" / "t-2.csv").exists()
    assert queued == [domain_dirs / "pdf" / "doc.pdf"]
    assert domain_dirs / "mix" / "pic.png" in imported
    assert domain_dirs / "markdown" / "notes.md" in imported
    assert not (domain_dirs / "evil").exists()
    assert any("report.docx" in warning for warning in result["warnings"])
    assert any(".hidden.md" in warning for warning in result["warnings"])
    assert len(result["imported"]) == 4
    assert image_modes == ["ocr", "ocr", "ocr"]

    quick_import.save_and_import_uploads([_Upload("asset.png", b"png")], "demo", image_processing="asset")
    assert image_modes[-1] == "asset"


def test_rows_cover_every_format_equally(domain_dirs, monkeypatch):
    monkeypatch.setattr("ki_knowledge.django_site.services.display_data_path", lambda path: str(path))
    state = {"markdown_files": 2, "pdf_files": 0, "ontology_files": 1, "jira_csv_files": 0, "mix_files": 23, "issues": 5}
    sources = [
        SimpleNamespace(source_type="markdown", source_id="md:a"),
        SimpleNamespace(source_type="table", source_id="mix:t.ods"),
        SimpleNamespace(source_type="pdf", source_id="pdf:mix/b.pdf"),
        SimpleNamespace(source_type="pdf", source_id="pdf:c.pdf"),
    ]

    rows = {row["key"]: row for row in quick_import.quick_import_rows("demo", state, sources)}

    assert list(rows) == ["md", "pdf", "owl", "jira", "mix"]
    assert rows["md"]["imported"] == 1 and rows["md"]["can_import"]
    assert rows["pdf"]["imported"] == 1 and not rows["pdf"]["can_import"]
    assert rows["mix"]["imported"] == 2 and rows["mix"]["files"] == 23
    assert rows["jira"]["imported"] == 5 and rows["jira"]["imported_unit"] == "Issues"


def test_unknown_source_is_rejected():
    assert quick_import.run_source_import("nope", "demo")["ok"] is False
