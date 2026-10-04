"""Tests for mixed-format source conversion (tables, OCR) and mix-aware PDF ids."""

from pathlib import Path

import pytest

from ki_knowledge.integrations import mixed_ingest
from ki_knowledge.integrations.mixed_ingest import (
    IMAGE_KIND,
    MARKDOWN_KIND,
    PDF_KIND,
    TABLE_KIND,
    UNSUPPORTED_KIND,
    OcrUnavailableError,
    classify_file,
    discover_mixed_files,
    image_to_markdown,
    read_table_sheets,
    table_to_markdown,
)


def _write_ods(path: Path, rows: list[list[str]], *, padding: int = 0) -> None:
    from odf.opendocument import OpenDocumentSpreadsheet
    from odf.table import Table, TableCell, TableRow
    from odf.text import P

    document = OpenDocumentSpreadsheet()
    table = Table(name="Tore")
    for values in rows:
        row = TableRow()
        for value in values:
            cell = TableCell(valuetype="string")
            cell.addElement(P(text=value))
            row.addElement(cell)
        if padding:
            row.addElement(TableCell(numbercolumnsrepeated=padding))
        table.addElement(row)
    if padding:
        table.addElement(TableRow(numberrowsrepeated=padding))
    document.spreadsheet.addElement(table)
    document.save(str(path))


def test_classify_file_by_extension():
    assert classify_file("a/b.PDF") == PDF_KIND
    assert classify_file("x.md") == MARKDOWN_KIND
    assert classify_file("t.ods") == TABLE_KIND
    assert classify_file("t.csv") == TABLE_KIND
    assert classify_file("img.JPEG") == IMAGE_KIND
    assert classify_file("notes.docx") == UNSUPPORTED_KIND


def test_discover_mixed_files_groups_and_skips_hidden(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.pdf").write_bytes(b"%PDF")
    (tmp_path / "sub" / "b.csv").write_text("x\n1\n")
    (tmp_path / ".hidden.png").write_bytes(b"")
    (tmp_path / "~$lock.ods").write_bytes(b"")
    (tmp_path / "c.docx").write_bytes(b"")

    grouped = discover_mixed_files(tmp_path)

    assert [p.name for p in grouped[PDF_KIND]] == ["a.pdf"]
    assert [p.name for p in grouped[TABLE_KIND]] == ["b.csv"]
    assert grouped[IMAGE_KIND] == []
    assert [p.name for p in grouped[UNSUPPORTED_KIND]] == ["c.docx"]


def test_discover_mixed_files_follows_symlinked_dir(tmp_path):
    target = tmp_path / "cloud"
    target.mkdir()
    (target / "t.csv").write_text("a\n1\n")
    mix = tmp_path / "mix"
    mix.symlink_to(target, target_is_directory=True)
    (target / "loop").symlink_to(target, target_is_directory=True)

    grouped = discover_mixed_files(mix)

    assert [p.name for p in grouped[TABLE_KIND]] == ["t.csv"]


def test_csv_with_header_becomes_key_value_rows(tmp_path):
    path = tmp_path / "gates.csv"
    path.write_text("Tor;Name\n1;Selbstausdruck\n2;Richtung\n", encoding="cp1252")

    markdown = table_to_markdown(path)

    assert markdown.startswith("# gates")
    assert "- Tor: 1; Name: Selbstausdruck" in markdown
    assert "- Tor: 2; Name: Richtung" in markdown


def test_single_numeric_column_without_header_is_one_line(tmp_path):
    path = tmp_path / "numbers.csv"
    path.write_text("1\n2\n3\n")

    assert "Werte: 1, 2, 3" in table_to_markdown(path)


def test_ods_is_read_with_padding_capped(tmp_path):
    path = tmp_path / "tore.ods"
    _write_ods(path, [["Tor", "Name"], ["1", "Selbstausdruck"]], padding=100000)

    sheets = read_table_sheets(path)

    assert len(sheets) == 1
    assert sheets[0].name == "Tore"
    assert sheets[0].rows == [["Tor", "Name"], ["1", "Selbstausdruck"]]
    assert "- Tor: 1; Name: Selbstausdruck" in table_to_markdown(path)


def test_invalid_ods_raises_ingest_error(tmp_path):
    path = tmp_path / "broken.ods"
    path.write_bytes(b"not a zip")

    with pytest.raises(mixed_ingest.MixedIngestError):
        read_table_sheets(path)


def test_ocr_unavailable_raises_helpful_error(tmp_path, monkeypatch):
    monkeypatch.setattr(mixed_ingest.shutil, "which", lambda _name: None)
    path = tmp_path / "chart.png"
    path.write_bytes(b"")

    with pytest.raises(OcrUnavailableError, match="tesseract-ocr"):
        image_to_markdown(path)


def test_image_import_always_keeps_asset_and_can_toggle_ocr(tmp_path, monkeypatch):
    from ki_knowledge.django_site import source_workflow
    from ki_knowledge.integrations.knowledge_store import KnowledgeStore

    path = tmp_path / "chart.png"
    path.write_bytes(b"image bytes")
    store = KnowledgeStore(tmp_path / "knowledge.sqlite")
    monkeypatch.setattr(source_workflow, "store", lambda: store)
    monkeypatch.setattr(source_workflow, "invalidate_domain_summary_cache", lambda _domain: None)
    monkeypatch.setattr(source_workflow, "image_to_markdown", lambda _path: "# chart.png\n\nRecognized words\n")

    atomic = source_workflow.import_image_file(path, domain="demo", image_processing="asset")
    assert atomic["imported"] == 1
    records = store.list_records(source_id=atomic["source_id"])
    assert len(records) == 1
    assert records[0].record_type == "image"
    assert records[0].metadata["relative_path"] == "chart.png"
    assert store.get_source(atomic["source_id"]).metadata["domain"] == "demo"

    ocr = source_workflow.import_image_file(path, domain="demo", image_processing="ocr")
    records = store.list_records(source_id=ocr["source_id"])
    assert {record.record_type for record in records} == {"image", "text"}
    text_record = next(record for record in records if record.record_type == "text")
    assert text_record.metadata["provenance"]["extractor"] == "tesseract_ocr"

    source_workflow.import_image_file(path, domain="demo", image_processing="asset")
    records = store.list_records(source_id=atomic["source_id"])
    assert [record.record_type for record in records] == ["image"]


def test_pdf_ids_from_mix_folder_get_prefix(tmp_path, monkeypatch):
    from ki_knowledge.data_layout import MIX, PDF, DataLayout
    from ki_knowledge.integrations.pdf_paths import pdf_source_id

    (tmp_path / ".layout-version").write_text("2\n")
    monkeypatch.setenv("KNOWLEDGE_DATA_ROOT", str(tmp_path))
    for name in ("KNOWLEDGE_PDF_ROOT", "KICLI_PDF_ROOT", "KNOWLEDGE_MIX_ROOT"):
        monkeypatch.delenv(name, raising=False)
    layout = DataLayout(tmp_path)
    mix_dir = layout.source_dir(MIX, "human-design")
    pdf_dir = layout.source_dir(PDF, "human-design")

    assert mix_dir == tmp_path / "domains" / "human-design" / "sources" / "mix"
    assert pdf_source_id(mix_dir / "books" / "x.pdf", domain="human-design") == "pdf:mix/books/x.pdf"
    assert pdf_source_id(pdf_dir / "y.pdf", domain="human-design") == "pdf:y.pdf"
