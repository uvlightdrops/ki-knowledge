"""Tests for the central on-disk data layout resolver."""

from pathlib import Path

import pytest

from ki_knowledge.data_layout import (
    JIRA,
    MARKDOWN,
    ONTOLOGY,
    PDF,
    DataLayout,
    LayoutError,
    canonical_source_type,
    read_layout_version,
)


@pytest.fixture
def clear_type_root_env(monkeypatch):
    for name in (
        "KNOWLEDGE_MARKDOWN_ROOT",
        "KICLI_MD_ROOT",
        "KNOWLEDGE_JIRA_ROOT",
        "KICLI_JIRA_ROOT",
        "KNOWLEDGE_ONTOLOGY_ROOT",
        "KICLI_OWL_ROOT",
        "KNOWLEDGE_PDF_ROOT",
        "KICLI_PDF_ROOT",
    ):
        monkeypatch.delenv(name, raising=False)


def test_v1_layout_is_source_type_first(tmp_path):
    layout = DataLayout(tmp_path)

    assert layout.source_type_root(MARKDOWN) == tmp_path / "md"
    assert layout.source_type_root(PDF) == tmp_path / "pdf"
    assert layout.source_type_root(JIRA) == tmp_path / "jira"
    assert layout.source_type_root(ONTOLOGY) == tmp_path / "owl"
    assert layout.source_dir(MARKDOWN, "anthro", "sstk") == tmp_path / "md" / "anthro" / "sstk"
    assert layout.source_dir("pdf", "anthro") == tmp_path / "pdf" / "anthro"
    assert layout.output_dir("anthro", "sstk") == tmp_path / "data_out" / "anthro" / "sstk"
    assert layout.domain_state_dir("anthro") == tmp_path / "jira" / "anthro"


def test_global_state_paths(tmp_path):
    layout = DataLayout(tmp_path)

    assert layout.knowledge_db_path() == tmp_path / "knowledge.db"
    assert layout.django_db_path() == tmp_path / "django.sqlite3"
    assert layout.pdf_jobs_db_path() == tmp_path / ".pdf_import_jobs.sqlite"
    assert layout.global_jira_cache_db_path() == tmp_path / ".jira_cache.sqlite"
    assert layout.global_jira_graph_db_path() == tmp_path / ".jira_graph.sqlite"


def test_source_type_aliases():
    assert canonical_source_type("md") == MARKDOWN
    assert canonical_source_type("Markdown") == MARKDOWN
    assert canonical_source_type("ontology") == ONTOLOGY
    with pytest.raises(ValueError):
        canonical_source_type("docx")


def test_type_root_override_only_moves_that_type(tmp_path):
    external_pdf = tmp_path / "elsewhere" / "pdfs"
    layout = DataLayout(tmp_path / "root", {"pdf": external_pdf})

    assert layout.source_dir(PDF, "anthro") == external_pdf / "anthro"
    assert layout.source_dir(MARKDOWN, "anthro") == tmp_path / "root" / "md" / "anthro"


def test_from_config_reads_env_overrides(tmp_path, monkeypatch, clear_type_root_env):
    monkeypatch.setenv("KNOWLEDGE_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("KICLI_JIRA_ROOT", str(tmp_path / "legacy-jira"))
    monkeypatch.setenv("KNOWLEDGE_MARKDOWN_ROOT", str(tmp_path / "markdown"))
    monkeypatch.setenv("KICLI_MD_ROOT", str(tmp_path / "ignored"))

    from ki_knowledge.app_config import AppConfig

    layout = DataLayout.from_config(AppConfig())

    assert layout.root == tmp_path
    assert layout.source_type_root(MARKDOWN) == tmp_path / "markdown"
    assert layout.source_type_root(JIRA) == tmp_path / "legacy-jira"
    assert layout.source_type_root(PDF) == tmp_path / "pdf"


def test_locate_source(tmp_path):
    layout = DataLayout(tmp_path)
    document = layout.source_dir(MARKDOWN, "Anthro", "sstk") / "intro.md"
    document.parent.mkdir(parents=True)
    document.write_text("# Intro")

    location = layout.locate_source(document)

    assert location is not None
    assert location.source_type == MARKDOWN
    assert location.domain_dir_name == "Anthro"
    assert location.relative_path == Path("sstk/intro.md")
    assert layout.locate_source(tmp_path / "data_out" / "anthro" / "x.md") is None
    assert layout.locate_source(layout.source_type_root(MARKDOWN)) is None


def test_locate_source_through_symlinked_domain_dir(tmp_path):
    external = tmp_path / "cloud" / "anthro"
    (external / "sstk").mkdir(parents=True)
    (external / "sstk" / "a.md").write_text("# A")
    layout = DataLayout(tmp_path / "root")
    layout.source_type_root(MARKDOWN).mkdir(parents=True)
    (layout.source_type_root(MARKDOWN) / "anthro").symlink_to(external, target_is_directory=True)

    via_link = layout.locate_source(layout.source_dir(MARKDOWN, "anthro", "sstk", "a.md"))
    via_target = layout.locate_source(external / "sstk" / "a.md")

    assert via_link == (MARKDOWN, "anthro", Path("sstk/a.md"))
    assert via_target == (MARKDOWN, "anthro", Path("sstk/a.md"))


def test_display_relative_hides_markdown_type_dir():
    layout = DataLayout(Path("/data"))

    assert layout.display_relative(Path("md/anthro/sstk/a.md")) == Path("anthro/sstk/a.md")
    assert layout.display_relative(Path("md")) == Path(".")
    assert layout.display_relative(Path("pdf/anthro/b.pdf")) == Path("pdf/anthro/b.pdf")


def _v2_root(tmp_path: Path) -> Path:
    root = tmp_path / "root"
    root.mkdir()
    (root / ".layout-version").write_text("2\n")
    return root


def test_layout_version_is_read_from_root(tmp_path):
    assert read_layout_version(tmp_path) == 1
    assert DataLayout(tmp_path).version == 1
    root = _v2_root(tmp_path)
    assert DataLayout(root).version == 2
    assert DataLayout(root, version=1).version == 1
    (root / ".layout-version").write_text("9")
    with pytest.raises(LayoutError):
        DataLayout(root)


def test_v2_layout_is_domain_first(tmp_path):
    root = _v2_root(tmp_path)
    layout = DataLayout(root)
    domain = root / "domains" / "anthro"

    assert layout.source_dir(MARKDOWN, "anthro", "sstk") == domain / "sources" / "md" / "sstk"
    assert layout.source_dir(PDF, "anthro") == domain / "sources" / "pdf"
    assert layout.source_dir(JIRA, "anthro", "issues.csv") == domain / "sources" / "jira" / "issues.csv"
    assert layout.source_dir(ONTOLOGY, "anthro") == domain / "sources" / "owl"
    assert layout.domain_state_dir("anthro") == domain / "derived"
    assert layout.output_dir("anthro", "sstk") == domain / "output" / "sstk"
    assert layout.knowledge_db_path() == root / "system" / "knowledge.db"
    assert layout.django_db_path() == root / "system" / "django.sqlite3"
    assert layout.pdf_jobs_db_path() == root / "system" / "pdf_import_jobs.sqlite"
    assert layout.global_jira_cache_db_path() == root / "system" / "jira_cache.sqlite"
    assert layout.pipeline_jobs_db_path() == root / "system" / "pipeline_jobs.db"
    assert layout.block_store_db_path() == root / "system" / "block_store.db"
    with pytest.raises(LayoutError):
        layout.source_type_root(MARKDOWN)


def test_v1_has_no_domain_or_system_dirs(tmp_path):
    layout = DataLayout(tmp_path)
    with pytest.raises(LayoutError):
        layout.domains_root()
    with pytest.raises(LayoutError):
        layout.system_dir()


def test_domain_names(tmp_path):
    v1 = DataLayout(tmp_path / "v1")
    for path in (v1.source_dir(MARKDOWN, "Anthro"), v1.source_dir(PDF, "politik"), v1.domain_state_dir("hd")):
        path.mkdir(parents=True)
    assert v1.domain_names() == ["Anthro", "hd", "politik"]
    assert v1.source_domain_names(MARKDOWN) == ["Anthro"]

    v2 = DataLayout(_v2_root(tmp_path))
    v2.source_dir(MARKDOWN, "Anthro").mkdir(parents=True)
    v2.domain_state_dir("hd").mkdir(parents=True)
    assert v2.domain_names() == ["Anthro", "hd"]
    assert v2.source_domain_names(PDF) == ["Anthro", "hd"]


def test_v2_type_override_keeps_domain_subdirs(tmp_path):
    external = tmp_path / "pdfs"
    layout = DataLayout(_v2_root(tmp_path), {"pdf": external})

    assert layout.source_dir(PDF, "anthro") == external / "anthro"
    assert layout.source_dir(MARKDOWN, "anthro") == layout.root / "domains" / "anthro" / "sources" / "md"


def test_v2_locate_source_through_symlinked_source_dir(tmp_path):
    external = tmp_path / "cloud" / "anthro"
    (external / "sstk").mkdir(parents=True)
    (external / "sstk" / "a.md").write_text("# A")
    layout = DataLayout(_v2_root(tmp_path))
    link = layout.source_dir(MARKDOWN, "anthro")
    link.parent.mkdir(parents=True)
    link.symlink_to(external, target_is_directory=True)
    pdf = layout.source_dir(PDF, "anthro", "b.pdf")
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF")

    assert layout.locate_source(link / "sstk" / "a.md") == (MARKDOWN, "anthro", Path("sstk/a.md"))
    assert layout.locate_source(external / "sstk" / "a.md") == (MARKDOWN, "anthro", Path("sstk/a.md"))
    assert layout.locate_source(pdf) == (PDF, "anthro", Path("b.pdf"))
    assert layout.locate_source(layout.output_dir("anthro", "x.md")) is None


def test_v2_display_and_output_relative(tmp_path):
    layout = DataLayout(_v2_root(tmp_path))

    assert layout.display_relative(Path("domains/anthro/sources/md/sstk/a.md")) == Path("anthro/sstk/a.md")
    assert layout.display_relative(Path("domains/anthro/sources/pdf/b.pdf")) == Path("anthro/pdf/b.pdf")
    assert layout.display_relative(Path("domains/anthro/output/sstk")) == Path("anthro/output/sstk")
    assert layout.display_relative(Path("system/knowledge.db")) == Path("system/knowledge.db")
    assert layout.output_relative(layout.output_dir("anthro", "sstk", "a.md")) == Path("anthro/sstk/a.md")
    assert layout.output_relative(layout.source_dir(MARKDOWN, "anthro", "a.md")) is None
