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


def test_inventory_merges_files_of_any_format_and_deduplicates_symlinks(domain_dirs, monkeypatch):
    md = domain_dirs.folders["markdown"]
    (md / "imported.md").write_text("# Imported")
    (md / "book.pdf").write_bytes(b"%PDF")
    (md / "new.md").write_text("# New")
    (domain_dirs.cloud / "stored.csv").write_text("x\n1\n")
    (domain_dirs.cloud / "new-alias.md").symlink_to(md / "new.md")
    (domain_dirs.cloud / "photo.png").write_bytes(b"image")
    (domain_dirs.cloud / "unsupported.docx").write_bytes(b"document")
    domain_dirs.folders["owl"].mkdir()
    (domain_dirs.folders["owl"] / "schema.owl").write_text("<rdf/>")
    (domain_dirs.folders["pdf"] / "queued.pdf").write_bytes(b"%PDF")
    (domain_dirs.folders["pdf"] / "done.pdf").write_bytes(b"%PDF")
    jira = domain_dirs.base / "jira"
    jira.mkdir()
    (jira / "issues.csv").write_text("Key\nDEMO-1\n")
    (domain_dirs.cloud / "issues-alias.csv").symlink_to(jira / "issues.csv")
    sources = [
        SimpleNamespace(source_id="md:old", source_type="markdown", title="Stored",
                        location=str(md / "imported.md")),
        SimpleNamespace(source_id="mix:old", source_type="table", title="Table",
                        location=str(domain_dirs.cloud / "stored.csv")),
    ]
    monkeypatch.setattr(sources_browser, "_pdf_job_states", lambda domain: {
        str(md / "book.pdf"): ("failed", "<bad PDF>"),
        str(domain_dirs.folders["pdf"] / "queued.pdf"): ("processing", ""),
        str(domain_dirs.folders["pdf"] / "done.pdf"): ("done", ""),
    })
    scanned = []
    discover = sources_browser.discover_mixed_files

    def tracked(root):
        scanned.append(root)
        return discover(root)

    monkeypatch.setattr(sources_browser, "discover_mixed_files", tracked)
    inventory = sources_browser.source_inventory("demo", sources, {"md:old": {"records": 7}})
    rows = inventory["rows"]
    by_title = {row["title"]: row for row in rows}

    assert len(scanned) == 5 and len(set(scanned)) == 5
    assert len(rows) == 10
    assert by_title["Stored"]["imported"] and by_title["Stored"]["records"] == 7
    assert by_title["Table"]["folder"] == "mix" and by_title["Table"]["linked"]
    assert by_title["book.pdf"]["folder"] == "md" and by_title["book.pdf"]["kind"] == "pdf"
    assert by_title["book.pdf"]["status"] == "failed" and by_title["book.pdf"]["error"] == "<bad PDF>"
    assert by_title["queued.pdf"]["status"] == "queued" and not by_title["queued.pdf"]["can_import"]
    assert by_title["done.pdf"]["status"] == "new" and not by_title["done.pdf"]["imported"]
    assert by_title["schema.owl"]["kind"] == "owl"
    assert by_title["unsupported.docx"]["status"] == "unsupported"
    assert not by_title["unsupported.docx"]["can_import"]
    assert by_title["issues.csv"]["workflow"] == "jira" and not by_title["issues.csv"]["can_import"]
    pending = {item["name"] for group in inventory["pending"]["folders"] for item in group["files"]}
    assert pending == {"book.pdf", "new.md", "photo.png", "schema.owl", "queued.pdf"}
    assert sources_browser.filter_rows(rows, query="book", kind="pdf") == [by_title["book.pdf"]]
    assert sources_browser.kind_counts(rows)[0]["count"] == len(rows)
    assert not {"new-alias.md", "issues-alias.csv", "stored.csv", "imported.md"} & set(by_title)


def test_inventory_matches_unresolved_store_path_to_resolved_discovery(domain_dirs, monkeypatch):
    (domain_dirs.cloud / "stored.pdf").write_bytes(b"%PDF")
    source = SimpleNamespace(source_id="s:pdf", source_type="pdf", title="Stored",
                             location=str(domain_dirs.folders["mix"] / "stored.pdf"))
    folders = sources_browser.domain_folders("demo")
    folders["mix"] = domain_dirs.cloud

    inventory = sources_browser.source_inventory("demo", [source], {}, folders)

    assert [row["source_id"] for row in inventory["rows"]] == ["s:pdf"]
    assert inventory["pending"]["total"] == 0


@pytest.fixture
def no_django_database(monkeypatch):
    from django.db.backends.utils import CursorWrapper

    def forbidden(*args, **kwargs):
        pytest.fail("Sources inventory must not access the configured Django database")

    monkeypatch.setattr(CursorWrapper, "execute", forbidden)
    monkeypatch.setattr(CursorWrapper, "executemany", forbidden)


def test_pdf_states_read_existing_queue_without_initializing_it(tmp_path, monkeypatch, no_django_database):
    import sqlite3
    from ki_knowledge.django_site import services

    path = tmp_path / "queue.sqlite"
    monkeypatch.setattr(services, "pdf_batch_db_path", lambda: str(path))
    monkeypatch.setattr(services, "get_pdf_batch_processor", lambda: pytest.fail("queue initialized"))
    assert sources_browser._pdf_job_states("demo") == {}
    assert not path.exists()
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE pdf_import_jobs (pdf_path TEXT, domain TEXT, status TEXT, "
            "error_message TEXT, created_at TEXT)"
        )
        connection.executemany("INSERT INTO pdf_import_jobs VALUES (?, ?, ?, ?, ?)", [
            (str(tmp_path / "a.pdf"), "demo", "failed", "bad PDF", "2026-10-08"),
            (str(tmp_path / "a.pdf"), "demo", "done", "", "2026-10-07"),
            (str(tmp_path / "other.pdf"), "other", "pending", "", "2026-10-09"),
        ])
    before = path.read_bytes()

    states = sources_browser._pdf_job_states("demo")

    assert states == {str(tmp_path / "a.pdf"): ("failed", "bad PDF")}
    assert path.read_bytes() == before


def test_file_import_queues_pdf_from_md_and_rejects_jira(domain_dirs, monkeypatch, no_django_database):
    from ki_knowledge.django_site import source_workflow

    path = domain_dirs.folders["markdown"] / "book.pdf"
    path.write_bytes(b"%PDF")
    jira = domain_dirs.base / "jira"
    jira.mkdir()
    (jira / "issues.csv").write_text("Key\nDEMO-1\n")
    queued = []
    monkeypatch.setattr(sources_browser, "_queue_pdf", lambda path, domain: queued.append((path, domain)) or "job")
    monkeypatch.setattr(source_workflow, "import_mixed_file", lambda *args, **kwargs: pytest.fail("wrong importer"))

    assert sources_browser.import_folder_file("demo", "md", "book.pdf")["ok"]
    assert queued == [(path, "demo")]
    assert not sources_browser.import_folder_file("demo", "jira", "issues.csv")["ok"]


@pytest.mark.parametrize("display", ["table", "cards"])
def test_inventory_widget_renders_file_actions_and_preserves_preview_defaults(display, no_django_database):
    from django.test import RequestFactory
    from ki_knowledge.django_site.page_widgets import build_sources_widget_cards

    common = {"source_id": "", "imported": False, "kind": "pdf", "kind_label": "PDF",
              "folder": "md", "relative": "new.pdf", "icon": "📄", "records": 0,
              "artifacts": 0, "updated_at": "", "status": "new", "can_import": True}
    rows = [
        {**common, "title": "Fresh PDF"},
        {**common, "title": "Queued PDF", "status": "queued", "can_import": False},
        {**common, "title": "Failed PDF", "status": "failed", "error": "<bad PDF>"},
        {**common, "title": "Unsupported", "status": "unsupported", "can_import": False},
        {**common, "title": "Jira CSV", "workflow": "jira", "workflow_url": "/data-sources/"},
        # Old sample payloads do not supply imported/status.
        {"source_id": "s:1", "title": "Store source", "detail_url": "/detail/s:1/",
         "kind": "pdf", "records": 3, "can_reimport": True},
    ]
    ctx = {"rows": rows, "display": display, "total_all": 6, "total": 6,
           "first_index": 1, "last_index": 6, "action_url": "/action/",
           "generate_url": "/generate/", "filter_params": {"q": "needle", "display": display}}

    html = build_sources_widget_cards(
        request=RequestFactory().get("/"), ctx=ctx,
        widget_ids=["datasources.sources.list.v1"],
    )[0]["body"]

    assert 'value="import_file"' in html and 'name="folder" value="md"' in html
    assert 'name="file" value="new.pdf"' in html
    assert 'name="csrfmiddlewaretoken"' in html and 'name="q" value="needle"' in html
    assert 'value="import_file" disabled' in html
    assert "neu · noch nicht importiert" in html and "in Warteschlange" in html
    assert "fehlgeschlagen" in html and "&lt;bad PDF&gt;" in html and "<bad PDF>" not in html
    assert "Format nicht unterstützt" in html and "Jira-Workflow öffnen" in html
    assert '<a href="/detail/s:1/">Store source · Records ansehen</a>' in html
    assert "Fresh PDF · Records ansehen" not in html and 'name="action" value="delete"' in html


def test_sources_get_scans_every_time_and_never_imports(domain_dirs, monkeypatch, no_django_database):
    from django.http import HttpResponse
    from django.test import RequestFactory
    from ki_knowledge.django_site import knowledge_summary, page_widgets, views_data_sources

    monkeypatch.setattr(views_data_sources, "_active_semantic_domain", lambda request: "demo")
    monkeypatch.setattr(views_data_sources, "store", lambda: SimpleNamespace(source_stats=lambda: {}))
    monkeypatch.setattr(knowledge_summary, "_domain_scoped_sources", lambda domain: [])
    monkeypatch.setattr(views_data_sources, "_load_dashboard_widget_ids", lambda *args, **kwargs: [])
    monkeypatch.setattr(views_data_sources, "_load_dashboard_widget_widths", lambda *args, **kwargs: {})

    def forbidden(*args, **kwargs):
        pytest.fail("GET must not import, queue, generate, or start workers")

    for name in ("import_folder_file", "import_all_unimported", "_queue_pdf"):
        monkeypatch.setattr(sources_browser, name, forbidden)
    for name in ("create_pdf_import_job", "start_pdf_worker", "import_mixed_file",
                 "import_markdown_file", "generate_all_artifacts"):
        monkeypatch.setattr(views_data_sources, name, forbidden)
    contexts = []
    monkeypatch.setattr(page_widgets, "build_sources_widget_cards",
                        lambda **kwargs: contexts.append(kwargs["ctx"]) or [])
    monkeypatch.setattr(views_data_sources, "render", lambda *args, **kwargs: HttpResponse("ok"))
    scans = []
    discover = sources_browser.discover_domain_files
    monkeypatch.setattr(sources_browser, "discover_domain_files",
                        lambda domain, folders: scans.append(domain) or discover(domain, folders))
    md = domain_dirs.folders["markdown"]
    (md / "first.pdf").write_bytes(b"%PDF")
    factory = RequestFactory()

    assert views_data_sources.sources(factory.get("/data-sources/sources/")).status_code == 200
    assert contexts[-1]["total_all"] == 1
    assert contexts[-1]["rows"][0]["title"] == "first.pdf"
    assert contexts[-1]["rows"][0]["detail_url"] == ""
    (md / "new.md").write_text("# New")
    views_data_sources.sources(factory.get("/data-sources/sources/?kind=markdown&q=new"))
    assert contexts[-1]["total_all"] == 2 and contexts[-1]["total"] == 1
    assert contexts[-1]["rows"][0]["title"] == "new.md"
    for number in range(101):
        (md / f"page-{number:03}.md").write_text("# Page")
    views_data_sources.sources(factory.get("/data-sources/sources/?q=page-&page=2"))
    assert contexts[-1]["total"] == 101 and len(contexts[-1]["rows"]) == 1
    assert contexts[-1]["first_index"] == 101 and contexts[-1]["prev_href"]
    assert scans == ["demo", "demo", "demo"]


def test_filter_rows_status_folder_path_and_new_sorts():
    rows = [
        {"source_id": "a", "title": "Alpha", "kind": "pdf", "status": "new", "folder": "md", "relative": "sub/a.pdf", "records": 2, "updated_at": "2026-01-01"},
        {"source_id": "b", "title": "Beta", "kind": "markdown", "status": "failed", "folder": "mix", "relative": "b.md", "records": 5, "updated_at": "2026-01-03"},
        {"source_id": "c", "title": "Gamma", "kind": "pdf", "status": "imported", "folder": "md", "relative": "other/c.pdf", "records": 1, "updated_at": "2026-01-02"},
    ]

    assert [row["source_id"] for row in sources_browser.filter_rows(rows, status="new")] == ["a"]
    assert [row["source_id"] for row in sources_browser.filter_rows(rows, folder="md", path="sub")] == ["a"]
    assert [row["source_id"] for row in sources_browser.filter_rows(rows, path="../bad")] == ["b", "c", "a"]
    assert [row["source_id"] for row in sources_browser.filter_rows(rows, sort="path")] == ["c", "a", "b"]
    assert [row["source_id"] for row in sources_browser.filter_rows(rows, sort="status")] == ["c", "a", "b"]
    assert sources_browser.status_counts(rows)["failed"] == 1
    assert sources_browser.folder_counts(rows)["md"] == 2


def test_sources_action_import_selected_validates_and_caps(domain_dirs, monkeypatch, no_django_database):
    from django.test import RequestFactory
    from ki_knowledge.django_site import views_data_sources

    md = domain_dirs.folders["markdown"]
    for index in range(105):
        (md / f"file-{index}.md").write_text("# x")
    calls = []
    monkeypatch.setattr(views_data_sources, "_active_semantic_domain", lambda request: "demo")
    monkeypatch.setattr(views_data_sources, "store", lambda: SimpleNamespace())
    monkeypatch.setattr(views_data_sources.messages, "success", lambda *args, **kwargs: None)
    monkeypatch.setattr(views_data_sources.messages, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(views_data_sources.messages, "info", lambda *args, **kwargs: None)
    monkeypatch.setattr(sources_browser, "import_folder_file", lambda domain, folder, relative, image_processing="ocr": calls.append((folder, relative)) or {"ok": True, "message": relative})
    factory = RequestFactory()
    selected = [f"md:file-{index}.md" for index in range(105)]
    request = factory.post("/data-sources/sources/action/", data={"action": "import_selected", "item": selected})

    response = views_data_sources.sources_action(request)

    assert response.status_code == 302
    assert len(calls) == 100
    assert calls[0] == ("md", "file-0.md") and calls[-1] == ("md", "file-99.md")
    bad = factory.post("/data-sources/sources/action/", data={"action": "import_selected", "item": ["jira:issues.csv"]})
    assert views_data_sources.sources_action(bad).status_code == 400
    bad = factory.post("/data-sources/sources/action/", data={"action": "import_selected", "item": ["nope:file.md"]})
    assert views_data_sources.sources_action(bad).status_code == 400


def test_source_rows_map_symlinked_subfolder_targets(domain_dirs, tmp_path):
    books = tmp_path / "books"
    books.mkdir()
    (domain_dirs.folders["pdf"] / "GA").symlink_to(books, target_is_directory=True)
    (books / "GA001.pdf").write_bytes(b"%PDF")
    source = SimpleNamespace(
        source_id="pdf:GA001.pdf",
        source_type="pdf",
        location=str(books / "GA001.pdf"),
        title="",
        updated_at="",
        metadata={},
    )

    rows = sources_browser.source_rows("demo", [source], {}, folders=domain_dirs.folders)

    assert rows[0]["folder"] == "pdf"
    assert rows[0]["relative"] == "GA/GA001.pdf"
    assert rows[0]["linked"] is True


def test_linked_subdirectories_and_domain_roots_include_link_targets(tmp_path, monkeypatch):
    from ki_knowledge.django_site import domain_paths

    domain_paths._LINKED_DIRS_CACHE.clear()
    pdf_dir = tmp_path / "domain" / "pdf"
    (pdf_dir / "plain").mkdir(parents=True)
    books = tmp_path / "cloud" / "books"
    books.mkdir(parents=True)
    (pdf_dir / "GA").symlink_to(books, target_is_directory=True)
    (pdf_dir / "loop").symlink_to(pdf_dir, target_is_directory=True)

    links = domain_paths.linked_subdirectories(pdf_dir)

    assert (pdf_dir / "GA", books.resolve()) in links
    for name in ("domain_markdown_dir", "domain_jira_dir", "domain_ontology_dir", "domain_mix_dir"):
        monkeypatch.setattr(domain_paths, name, lambda domain, _n=name: tmp_path / "domain" / _n)
    monkeypatch.setattr(domain_paths, "domain_source_dir", lambda source_type, domain: pdf_dir)
    assert books.resolve() in domain_paths.domain_source_roots("demo")
    domain_paths._LINKED_DIRS_CACHE.clear()


def test_query_records_scopes_to_sources_and_pages_in_sql(tmp_path):
    store = KnowledgeStore(tmp_path / "k.db")
    for sid in ("s:a", "s:b", "s:c"):
        store.import_markdown_text(
            "# T\n\n" + "\n\n".join(f"Absatz {i}" for i in range(5)) + "\n",
            source_path=str(tmp_path / f"{sid[2]}.md"),
            source_name=sid,
            source_id=sid,
        )
    per_source = len(store.list_records(source_id="s:a"))

    page, total = store.query_records({"s:a", "s:b"}, limit=3, offset=0)
    rest, _ = store.query_records({"s:a", "s:b"}, limit=100, offset=3)

    assert total == 2 * per_source
    assert len(page) == 3 and len(rest) == total - 3
    assert {r.source_id for r in page + rest} == {"s:a", "s:b"}
    assert store.query_records([], limit=10) == ([], 0)
    paragraphs, count = store.query_records(["s:c"], block_type="paragraph")
    assert count == len(paragraphs) > 0 and all(r.block_type == "paragraph" for r in paragraphs)
