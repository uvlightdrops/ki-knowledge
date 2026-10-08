from __future__ import annotations

import os
from pathlib import Path

import pytest
from pypdf import PdfWriter

from ki_knowledge.data_layout import DataLayout
from ki_knowledge.integrations.pdf_inventory import (
    TITLE_SOURCE_FILENAME,
    TITLE_SOURCE_METADATA,
    configured_inventory_roots,
    domain_inventory_roots,
    scan_pdf_inventory,
)


def _write_pdf(path: Path, *, title: str | None = None, author: str | None = None, pages: int = 1, password: str | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    metadata = {}
    if title is not None:
        metadata["/Title"] = title
    if author is not None:
        metadata["/Author"] = author
    if metadata:
        writer.add_metadata(metadata)
    if password:
        writer.encrypt(user_password=password, owner_password=password)
    with path.open("wb") as handle:
        writer.write(handle)
    return path


def _scan(root: Path, **kwargs):
    return scan_pdf_inventory([("data root", root)], **kwargs)


@pytest.mark.parametrize("version", [1, 2, 3])
def test_domain_inventory_excludes_other_domains(tmp_path, version):
    from ki_knowledge.data_layout import MARKDOWN, PDF

    layout = DataLayout(tmp_path, version=version)
    _write_pdf(layout.source_dir(PDF, "anthro") / "book.pdf", title="Selected")
    _write_pdf(layout.source_dir(MARKDOWN, "anthro") / "embedded.PDF", title="Embedded")
    _write_pdf(layout.output_dir("anthro") / "output.pdf", title="Output")
    _write_pdf(layout.source_dir(PDF, "other") / "private.pdf", title="Other")
    inventory = scan_pdf_inventory(domain_inventory_roots("anthro", layout))
    assert {entry.title for entry in inventory.entries} == {"Selected", "Embedded", "Output"}


def test_scan_reads_metadata_and_labels_filename_fallback(tmp_path):
    _write_pdf(tmp_path / "pdf" / "anthro" / "book_one.pdf", title="Zebra Book", author="A. Author", pages=3)
    _write_pdf(tmp_path / "md" / "people" / "Scanned_Book.PDF")
    _write_pdf(tmp_path / "pdf" / "x" / "placeholder.pdf", title="untitled")
    (tmp_path / "pdf" / "notes.txt").write_text("no pdf")

    inventory = _scan(tmp_path)

    assert [entry.title for entry in inventory.entries] == ["placeholder", "Scanned Book", "Zebra Book"]
    by_title = {entry.title: entry for entry in inventory.entries}
    assert by_title["Zebra Book"].title_source == TITLE_SOURCE_METADATA
    assert by_title["Zebra Book"].author == "A. Author"
    assert by_title["Zebra Book"].page_count == 3
    assert by_title["Zebra Book"].relative_path == "pdf/anthro/book_one.pdf"
    assert by_title["Scanned Book"].title_source == TITLE_SOURCE_FILENAME
    assert by_title["Scanned Book"].relative_path == "md/people/Scanned_Book.PDF"
    assert by_title["placeholder"].title_source == TITLE_SOURCE_FILENAME
    assert by_title["placeholder"].metadata_title == "untitled"
    assert inventory.summary["total"] == 3
    assert inventory.summary["metadata_titles"] == 1


def test_scan_reports_corrupt_and_encrypted_files(tmp_path):
    (tmp_path / "pdf").mkdir()
    (tmp_path / "pdf" / "broken.pdf").write_bytes(b"not a pdf at all")
    _write_pdf(tmp_path / "pdf" / "locked.pdf", title="Secret", password="pw")

    inventory = _scan(tmp_path)

    errors = {entry.relative_path: entry.error for entry in inventory.entries}
    assert errors["pdf/broken.pdf"].startswith("unreadable PDF")
    assert errors["pdf/locked.pdf"].startswith("encrypted")
    locked = next(entry for entry in inventory.entries if entry.relative_path == "pdf/locked.pdf")
    assert locked.title_source == TITLE_SOURCE_FILENAME
    assert inventory.summary["file_errors"] == 2


def test_scan_follows_symlinks_dedups_and_guards_cycles(tmp_path):
    external = tmp_path / "external"
    _write_pdf(external / "linked.pdf", title="Linked")
    root = tmp_path / "root"
    (root / "md").mkdir(parents=True)
    (root / "md" / "a").symlink_to(external, target_is_directory=True)
    (root / "md" / "b").symlink_to(external, target_is_directory=True)
    (external / "loop").symlink_to(external, target_is_directory=True)
    (root / "dangling.pdf").symlink_to(tmp_path / "missing.pdf")

    inventory = _scan(root)

    readable = [entry for entry in inventory.entries if not entry.error]
    assert [entry.relative_path for entry in readable] == ["md/a/linked.pdf"]
    assert readable[0].via_symlink is True
    assert inventory.skipped_cycles  # loop and second link are reported, not silently dropped
    dangling = next(entry for entry in inventory.entries if entry.relative_path == "dangling.pdf")
    assert dangling.error == "broken symlink"


def test_scan_reports_duplicate_file_links(tmp_path):
    original = _write_pdf(tmp_path / "pdf" / "orig.pdf", title="Orig")
    (tmp_path / "pdf" / "zz_link.pdf").symlink_to(original)

    inventory = _scan(tmp_path)

    assert [entry.relative_path for entry in inventory.entries] == ["pdf/orig.pdf"]
    assert inventory.duplicates == [{"relative_path": "pdf/zz_link.pdf", "same_as": "pdf/orig.pdf"}]


def test_missing_root_is_visible(tmp_path):
    inventory = _scan(tmp_path / "nope")

    assert inventory.roots == [{"label": "data root", "path": str(tmp_path / "nope"), "status": "missing"}]
    assert inventory.entries == []


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores permissions")
def test_unreadable_directory_is_reported(tmp_path):
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0)
    try:
        inventory = _scan(tmp_path)
    finally:
        locked.chmod(0o755)

    assert inventory.scan_errors and inventory.scan_errors[0]["path"] == "locked"


def test_configured_roots_use_layout_root_and_external_pdf_override(tmp_path):
    layout = DataLayout(tmp_path / "data", {"pdf": tmp_path / "books"}, version=1)
    assert configured_inventory_roots(layout) == [
        ("data root", tmp_path / "data"),
        ("PDF root override", tmp_path / "books"),
    ]
    inside = DataLayout(tmp_path / "data", {"pdf": tmp_path / "data" / "pdf"}, version=1)
    assert configured_inventory_roots(inside) == [("data root", tmp_path / "data")]


def test_unexpected_programming_errors_are_not_swallowed(tmp_path, monkeypatch):
    _write_pdf(tmp_path / "a.pdf", title="A")

    def boom(*args, **kwargs):
        raise RuntimeError("bug")

    monkeypatch.setattr("ki_knowledge.integrations.pdf_inventory.PdfReader", boom)

    with pytest.raises(RuntimeError, match="bug"):
        _scan(tmp_path)


def test_uninspectable_non_pdf_entry_is_reported(tmp_path, monkeypatch):
    _write_pdf(tmp_path / "ok.pdf", title="Ok")
    (tmp_path / "weird").mkdir()
    real_scandir = os.scandir

    class BrokenEntry:
        def __init__(self, entry):
            self._entry = entry
            self.name = entry.name
            self.path = entry.path

        def is_dir(self, follow_symlinks=True):
            raise PermissionError(13, "Permission denied")

        is_file = is_dir

        def is_symlink(self):
            return False

    def fake_scandir(path):
        return [BrokenEntry(e) if e.name == "weird" else e for e in real_scandir(path)]

    monkeypatch.setattr("ki_knowledge.integrations.pdf_inventory.os.scandir", fake_scandir)

    inventory = _scan(tmp_path)

    assert [entry.title for entry in inventory.entries] == ["Ok"]
    assert inventory.scan_errors == [{"path": "weird", "error": "entry not inspectable: Permission denied"}]
