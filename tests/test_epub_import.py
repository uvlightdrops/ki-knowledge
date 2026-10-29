"""EPUB materialization, source registration and domain/UI integration."""

import json
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest

from ki_knowledge.data_layout import DataLayout, EPUB
from ki_knowledge.django_site import epub_import, quick_import, source_access, source_workflow, sources_browser
from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.integrations.mixed_ingest import EPUB_KIND, classify_file
from ki_knowledge.services.epub_import import materialize_epub


@pytest.fixture
def book_path(tmp_path):
    path = tmp_path / "demo.epub"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", """<?xml version="1.0"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
<rootfiles><rootfile full-path="OEBPS/book.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>""")
        archive.writestr("OEBPS/book.opf", """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="id">synthetic-book</dc:identifier><dc:title>Testbuch</dc:title>
<dc:creator>Testautor</dc:creator><dc:language>de</dc:language></metadata>
<manifest><item id="a" href="a.xhtml" media-type="application/xhtml+xml"/>
<item id="b" href="b.xhtml" media-type="application/xhtml+xml"/></manifest>
<spine><itemref idref="a"/><itemref idref="b"/></spine></package>""")
        for letter in ("a", "b"):
            archive.writestr(
                f"OEBPS/{letter}.xhtml",
                f'<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Kapitel {letter}</title></head>'
                f'<body><h1>Kapitel {letter}</h1><p>Ein eigener Testtext {letter} 🍒.</p></body></html>',
            )
    return path


def test_materialize_preserves_original_and_refuses_to_overwrite_edits(book_path, tmp_path):
    original = book_path.read_bytes()
    root = tmp_path / "md"
    first = materialize_epub(book_path, root)
    second = materialize_epub(book_path, root)
    assert first["directory"] == second["directory"]
    assert book_path.read_bytes() == original
    assert len(first["chapter_paths"]) == 2
    assert first["manifest"]["title"] == "Testbuch"
    assert first["manifest"]["authors"] == ["Testautor"]
    assert [item.name for item in first["chapter_paths"]] == ["0001.md", "0002.md"]
    metadata = json.loads((first["directory"] / "book.json").read_text())
    assert metadata["source_sha256"] == first["manifest"]["source_sha256"]
    first["chapter_paths"][0].write_text("Meine eigene Änderung.")
    with pytest.raises(ValueError, match="edited"):
        materialize_epub(book_path, root)
    assert first["chapter_paths"][0].read_text() == "Meine eigene Änderung."


def test_registers_original_chapters_and_reference_outline(book_path, tmp_path, monkeypatch):
    store = KnowledgeStore(tmp_path / "test.sqlite3")
    monkeypatch.setattr(source_workflow, "store", lambda: store)
    monkeypatch.setattr(epub_import, "domain_markdown_dir", lambda domain: tmp_path / domain / "md")
    monkeypatch.setattr(epub_import, "invalidate_domain_summary_cache", lambda domain: None)
    result = epub_import.import_epub_file(book_path, domain="anthro-ag")
    assert result["chapters"] == 2 and result["imported"] > 0
    source = store.get_source(result["source_id"])
    assert source.source_type == "epub"
    assert source.metadata["domain"] == "anthro-ag"
    chapters = [item for item in store.list_sources() if item.source_type == "markdown"]
    assert len(chapters) == 2
    assert all(item.metadata["authors"] == ["Testautor"] for item in chapters)
    assert all(Path(item.location).is_file() for item in chapters)
    artifacts = store.list_artifacts(source_id=result["source_id"])
    assert artifacts[0].artifact_type == "reference_structure"
    repeated = epub_import.import_epub_file(book_path, domain="anthro-ag")
    assert repeated["markdown_dir"] == result["markdown_dir"]
    assert len(store.list_sources()) == 3
    monkeypatch.setattr("ki_knowledge.django_site.services.store", lambda: store)
    monkeypatch.setattr(source_workflow, "invalidate_domain_summary_cache", lambda domain: None)
    source_workflow.import_markdown_file(Path(chapters[0].location))
    assert store.get_source(chapters[0].source_id).metadata["epub_source_id"] == result["source_id"]

    def domain_directory(source_type, domain):
        return tmp_path / domain / ("md" if source_type == "markdown" else source_type)

    monkeypatch.setattr(sources_browser, "domain_source_dir", domain_directory)
    monkeypatch.setattr(sources_browser, "domain_jira_dir", lambda domain: tmp_path / domain / "jira")
    monkeypatch.setattr(sources_browser, "_pdf_job_states", lambda domain: {})
    monkeypatch.setattr("ki_knowledge.django_site.knowledge_summary._domain_scoped_sources", lambda domain: store.list_sources())
    inventory = source_access.capture_inventory("anthro-ag")
    assert len(inventory["sources"]) == 2
    assert all("Testbuch" in item["title"] for item in inventory["sources"])
    assert all(item["folder"] == "md" for item in inventory["sources"])


def test_invalid_epub_produces_no_markdown_or_store_success(tmp_path):
    source = tmp_path / "broken.epub"
    source.write_bytes(b"not an EPUB")
    with pytest.raises(ValueError):
        materialize_epub(source, tmp_path / "md")
    assert not (tmp_path / "md").exists()
    result = source_workflow.import_mixed_file(source, domain="anthro-ag")
    assert result["error"] and result["imported"] == 0


@pytest.mark.parametrize("version", [1, 2, 3])
def test_epub_layout_and_domain_recognition(tmp_path, monkeypatch, version):
    monkeypatch.delenv("KNOWLEDGE_EPUB_ROOT", raising=False)
    if version != 1:
        (tmp_path / ".layout-version").write_text(str(version))
    layout = DataLayout(tmp_path)
    directory = layout.source_dir(EPUB, "anthro-ag")
    expected = {
        1: tmp_path / "epub" / "anthro-ag",
        2: tmp_path / "domains" / "anthro-ag" / "sources" / "epub",
        3: tmp_path / "anthro-ag" / "epub",
    }
    assert directory == expected[version]
    directory.mkdir(parents=True)
    path = directory / "book.epub"
    path.touch()
    assert "anthro-ag" in layout.domain_names()
    assert layout.locate_source(path) == (EPUB, "anthro-ag", Path("book.epub"))


def test_epub_browser_import_and_upload(book_path, tmp_path, monkeypatch):
    monkeypatch.setattr(sources_browser, "domain_source_dir", lambda source_type, domain: tmp_path / source_type)
    monkeypatch.setattr(sources_browser, "domain_jira_dir", lambda domain: tmp_path / "jira")
    monkeypatch.setattr(sources_browser, "invalidate_domain_summary_cache", lambda domain: None)
    monkeypatch.setattr(sources_browser, "_pdf_job_states", lambda domain: {})
    directory = tmp_path / "epub"
    directory.mkdir()
    (directory / "book.epub").write_bytes(book_path.read_bytes())
    inventory = sources_browser.source_inventory("anthro-ag", [], {})
    epub_row = next(row for row in inventory["rows"] if row["kind"] == "epub")
    assert epub_row["folder"] == "epub" and epub_row["status"] == "new"
    calls = []

    def convert(path, *, domain=None, image_processing="ocr"):
        calls.append((path, domain))
        return {"imported": 5, "chapters": 2, "source_id": "epub:test", "warnings": []}

    monkeypatch.setattr(source_workflow, "import_mixed_file", convert)
    assert sources_browser.import_folder_file("anthro-ag", "epub", "book.epub")["ok"]
    monkeypatch.setattr(quick_import, "domain_source_dir", lambda source_type, domain: tmp_path / source_type)
    monkeypatch.setattr(quick_import, "invalidate_domain_summary_cache", lambda domain: None)
    monkeypatch.setattr(quick_import, "_queue_pdf", lambda domain: None)
    upload = SimpleNamespace(name="upload.epub", chunks=lambda: iter([book_path.read_bytes()]))
    result = quick_import.save_and_import_uploads([upload], "anthro-ag")
    assert not result["warnings"]
    assert calls == [(directory / "book.epub", "anthro-ag"), (directory / "upload.epub", "anthro-ag")]
    assert classify_file("BOOK.EPUB") == EPUB_KIND
    assert ".epub" in quick_import.UPLOAD_ACCEPT


def test_epub_quick_import_counts_and_reports_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(quick_import, "domain_source_dir", lambda source_type, domain: tmp_path)
    monkeypatch.setattr(quick_import, "invalidate_domain_summary_cache", lambda domain: None)
    state = {"epub_files": 2}
    sources = [SimpleNamespace(source_type="epub", source_id="epub:a")]
    rows = {item["key"]: item for item in quick_import.quick_import_rows("anthro-ag", state, sources)}
    assert rows["epub"]["files"] == 2 and rows["epub"]["imported"] == 1
    monkeypatch.setattr(source_workflow, "import_mixed_directory", lambda *a, **kw: {
        "source_ids": [], "imported": 0, "errors": [{"file": "bad.epub", "error": "Invalid EPUB"}],
    })
    result = quick_import.run_source_import("epub", "anthro-ag")
    assert not result["ok"] and "Invalid EPUB" in result["warnings"][0]


def test_management_command_uses_domain_relative_selection(tmp_path, monkeypatch):
    from django.core.management.base import CommandError
    from ki_knowledge.django_site.management.commands.import_epub import Command

    directory = tmp_path / "epub"
    directory.mkdir()
    (directory / "book.epub").touch()
    monkeypatch.setattr(sources_browser, "domain_source_dir", lambda source_type, domain: tmp_path / source_type)
    monkeypatch.setattr(sources_browser, "domain_jira_dir", lambda domain: tmp_path / "jira")
    imported = []

    def convert(path, *, domain):
        imported.append((path, domain))
        return {"chapters": 2, "imported": 4, "markdown_dir": str(tmp_path / "md"), "warnings": []}

    monkeypatch.setattr(epub_import, "import_epub_file", convert)
    Command().handle(domain="anthro-ag", file="book.epub")
    assert imported == [(directory / "book.epub", "anthro-ag")]
    for path in ("../book.epub", "/etc/passwd", "missing.epub"):
        with pytest.raises(CommandError):
            Command().handle(domain="anthro-ag", file=path)
    assert len(imported) == 1
