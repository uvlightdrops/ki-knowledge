"""Tests for the sources browser helpers and the store additions they rely on."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from ki_knowledge.django_site import sources_browser
from ki_knowledge.integrations.knowledge_store import KnowledgeStore


@pytest.fixture
def domain_dirs(tmp_path, monkeypatch):
    base = tmp_path / "domain"
    cloud = tmp_path / "cloud"
    cloud.mkdir()
    (base / "md").mkdir(parents=True)
    (base / "pdf").mkdir()
    (base).joinpath("mix").symlink_to(cloud, target_is_directory=True)
    folders = {"markdown": base / "md", "pdf": base / "pdf", "owl": base / "owl", "mix": base / "mix"}
    monkeypatch.setattr(sources_browser, "domain_source_dir", lambda source_type, domain: folders[source_type])
    monkeypatch.setattr(sources_browser, "domain_jira_dir", lambda domain: base / "jira")
    monkeypatch.setattr(sources_browser, "invalidate_domain_summary_cache", lambda domain: None)
    monkeypatch.setattr(sources_browser, "_pdf_job_states", lambda domain: {})
    return SimpleNamespace(base=base, cloud=cloud, folders=folders)


def test_unimported_files_skips_imported_and_matches_symlink_targets(domain_dirs):
    (domain_dirs.folders["markdown"] / "a.md").write_text("# a")
    (domain_dirs.folders["markdown"] / "b.md").write_text("# b")
    (domain_dirs.cloud / "t.csv").write_text("x\n1\n")
    (domain_dirs.cloud / "u.ods").write_bytes(b"")
    (domain_dirs.cloud / "skip.docx").write_bytes(b"")
    sources = [
        SimpleNamespace(location=str((domain_dirs.folders["markdown"] / "a.md").resolve())),
        # tables store the unresolved path below the domain folder
        SimpleNamespace(location=str(domain_dirs.folders["mix"] / "t.csv")),
    ]

    pending = sources_browser.unimported_files("demo", sources)

    listed = {(group["key"], item["relative"]) for group in pending["folders"] for item in group["files"]}
    assert listed == {("md", "b.md"), ("mix", "u.ods")}
    assert pending["new"] == 2


def test_unimported_files_marks_queued_and_hides_done_pdfs(domain_dirs, monkeypatch):
    for name in ("queued.pdf", "done.pdf", "failed.pdf"):
        (domain_dirs.folders["pdf"] / name).write_bytes(b"%PDF")
    pdf_dir = domain_dirs.folders["pdf"]
    monkeypatch.setattr(
        sources_browser,
        "_pdf_job_states",
        lambda domain: {
            str(pdf_dir / "queued.pdf"): ("pending", ""),
            str(pdf_dir / "done.pdf"): ("done", ""),
            str(pdf_dir / "failed.pdf"): ("failed", "boom"),
        },
    )

    files = {item["name"]: item for group in sources_browser.unimported_files("demo", [])["folders"] for item in group["files"]}

    assert set(files) == {"queued.pdf", "failed.pdf"}
    assert files["queued.pdf"]["status"] == "queued"
    assert files["failed.pdf"]["status"] == "failed" and files["failed.pdf"]["error"] == "boom"


@pytest.mark.parametrize("relative", ["../secret.md", "/etc/passwd", "a/../../x.md", "", "."])
def test_resolve_folder_file_rejects_escapes(domain_dirs, relative):
    (domain_dirs.base / "secret.md").write_text("x")
    assert sources_browser.resolve_folder_file("demo", "md", relative) is None


def test_resolve_folder_file_allows_files_behind_symlinked_folder(domain_dirs):
    (domain_dirs.cloud / "sub").mkdir()
    (domain_dirs.cloud / "sub" / "t.csv").write_text("x")

    assert sources_browser.resolve_folder_file("demo", "mix", "sub/t.csv") == domain_dirs.folders["mix"] / "sub" / "t.csv"
    assert sources_browser.resolve_folder_file("demo", "nope", "sub/t.csv") is None


def test_source_rows_filter_and_origin(domain_dirs):
    sources = [
        SimpleNamespace(source_id="mix:t.csv", source_type="table", title="Tore", location=str(domain_dirs.folders["mix"] / "t.csv")),
        SimpleNamespace(source_id="pdf:mix/b.pdf", source_type="pdf", title="Buch", location=str(domain_dirs.cloud / "b.pdf")),
        SimpleNamespace(source_id="x", source_type="iasem_quiz", title="Quiz", location="elsewhere"),
    ]
    stats = {"mix:t.csv": {"records": 5, "updated_at": "2026-09-01T10:00:00"}, "pdf:mix/b.pdf": {"records": 9, "updated_at": "2026-09-02T10:00:00"}}

    rows = sources_browser.source_rows("demo", sources, stats)
    by_id = {row["source_id"]: row for row in rows}

    assert by_id["mix:t.csv"]["folder"] == "mix" and by_id["mix:t.csv"]["linked"]
    assert by_id["pdf:mix/b.pdf"]["folder"] == "mix" and by_id["pdf:mix/b.pdf"]["relative"] == "b.pdf"
    assert by_id["x"]["kind"] == "other" and by_id["x"]["folder"] == ""
    assert [row["source_id"] for row in sources_browser.filter_rows(rows)] == ["pdf:mix/b.pdf", "mix:t.csv", "x"]
    assert [row["source_id"] for row in sources_browser.filter_rows(rows, sort="records")][0] == "pdf:mix/b.pdf"
    assert [row["source_id"] for row in sources_browser.filter_rows(rows, kind="table")] == ["mix:t.csv"]
    assert [row["source_id"] for row in sources_browser.filter_rows(rows, query="BUCH")] == ["pdf:mix/b.pdf"]
    chips = {chip["key"]: chip["count"] for chip in sources_browser.kind_counts(rows)}
    assert chips[""] == 3 and chips["table"] == 1 and chips["other"] == 1 and chips["image"] == 0


def test_image_source_row_exposes_saved_processing_choice(domain_dirs):
    source = SimpleNamespace(
        source_id="mix:chart.png",
        source_type="image",
        title="Chart",
        location=str(domain_dirs.folders["mix"] / "chart.png"),
        metadata={"image_processing": "asset"},
    )

    row = sources_browser.source_rows("demo", [source], {})[0]

    assert row["kind"] == "image"
    assert row["image_processing"] == "asset"


def test_store_source_stats_and_delete_source(tmp_path):
    store = KnowledgeStore(tmp_path / "k.db")
    store.import_markdown_text("# A\n\nText eins\n\nText zwei\n", source_path=str(tmp_path / "a.md"), source_name="a", source_id="s:a", source_type="table")
    store.import_markdown_text("# B\n\nNur eins\n", source_path=str(tmp_path / "b.md"), source_name="b", source_id="s:b", source_type="table")

    stats = store.source_stats()
    assert stats["s:a"]["records"] > stats["s:b"]["records"] > 0
    assert stats["s:a"]["updated_at"]

    removed = store.delete_source("s:a")

    assert removed["sources"] == 1 and removed["records"] == stats["s:a"]["records"]
    assert store.get_source("s:a") is None
    assert store.list_records(source_id="s:a") == []
    assert store.get_source("s:b") is not None
