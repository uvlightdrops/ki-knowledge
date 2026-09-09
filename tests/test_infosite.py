"""Tests for infosite module."""

import os
import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from ki_knowledge.django_site.services import display_data_path
from ki_knowledge.infosite import InfoSiteConfig, InfoSiteGenerator, InfoSiteMetadata
from ki_knowledge.infosite.models import PageSpec
from ki_knowledge.services.discovery import FileInfo
from ki_knowledge.services.generator import InfoSiteGeneratorService


@pytest.fixture
def temp_output_dir():
    """Create a temporary output directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def infosite_config(temp_output_dir):
    """Create a test infosite configuration."""
    return InfoSiteConfig(
        enabled=True,
        title="Test Knowledge Base",
        domain="test",
        output_base_dir=str(temp_output_dir),
    )


def test_infosite_config_output_dir(infosite_config):
    """Test output directory generation."""
    output_dir = infosite_config.get_output_dir()
    assert output_dir.name == "test-knowledge-base"
    assert output_dir.parent.name == "test"


def test_infosite_config_slugify():
    """Test slug generation."""
    assert InfoSiteConfig._slugify("Hello World") == "hello-world"
    assert InfoSiteConfig._slugify("Test_Knowledge_Base") == "test_knowledge_base"
    assert InfoSiteConfig._slugify("  spaces  ") == "spaces"


def test_infosite_generator_create(infosite_config):
    """Test infosite generator initialization."""
    generator = InfoSiteGenerator(infosite_config)
    assert generator.config == infosite_config
    assert generator.metadata is not None
    assert generator.metadata.title == "Test Knowledge Base"
    assert generator.metadata.domain == "test"


def test_infosite_generate_pages(infosite_config):
    """Test page generation."""
    generator = InfoSiteGenerator(infosite_config)
    pages = InfoSiteGenerator.create_default_pages("Test KB")

    output_dir = generator.generate(pages, create_originals_backup=False)

    # Check output directory was created
    assert output_dir.exists()

    # Check index page exists
    index_file = output_dir / "index.md"
    assert index_file.exists()
    content = index_file.read_text()
    assert "Test KB" in content

    # Check overview page exists
    overview_file = output_dir / "overview" / "index.md"
    assert overview_file.exists()

    # Check metadata file exists
    metadata_file = output_dir / "metadata.yml"
    assert metadata_file.exists()


def test_infosite_generate_with_backup(infosite_config):
    """Test infosite generation with original version backup."""
    generator = InfoSiteGenerator(infosite_config)
    pages = InfoSiteGenerator.create_default_pages("Test KB")

    output_dir = generator.generate(pages, create_originals_backup=True)

    # Check originals backup directory
    originals_dir = output_dir.parent / "_originals" / "v1-original"
    assert originals_dir.exists()
    assert (originals_dir / "index.md").exists()
    assert (originals_dir / "metadata.yml").exists()


def test_page_spec_get_path():
    """Test page path generation."""
    page = PageSpec(slug="test-page", title="Test", content="content")
    path = page.get_path(Path("/output"))
    assert path == Path("/output/test-page/index.md")

    index_page = PageSpec(slug="index", title="Home", content="home")
    index_path = index_page.get_path(Path("/output"))
    assert index_path == Path("/output/index.md")


def test_page_spec_children():
    """Test page hierarchy."""
    child1 = PageSpec(slug="child1", title="Child 1", content="c1")
    child2 = PageSpec(slug="child2", title="Child 2", content="c2")
    parent = PageSpec(
        slug="parent",
        title="Parent",
        content="parent",
        children=[child1, child2],
    )

    assert len(parent.children) == 2
    assert parent.children[0].title == "Child 1"


def test_infosite_metadata():
    """Test metadata generation."""
    metadata = InfoSiteMetadata(
        version="v1-original",
        title="Test",
        domain="test",
        source_documents=["doc1.pdf", "doc2.md"],
    )

    frontmatter = metadata.to_frontmatter_dict()
    assert frontmatter["version"] == "v1-original"
    assert frontmatter["title"] == "Test"
    assert frontmatter["domain"] == "test"
    assert len(frontmatter["source_documents"]) == 2


def test_display_data_path_is_relative_to_domain_data_root(monkeypatch, tmp_path):
    """Display paths relative to the data root instead of absolute filesystem paths."""
    data_root = tmp_path / "dev_data" / "ki-knowledge"
    markdown_file = data_root / "md" / "anthro" / "sstk" / "10_geistige_welt" / "anspruch-und-ziel_bak.md"
    markdown_file.parent.mkdir(parents=True)
    markdown_file.write_text("# test\n", encoding="utf-8")

    monkeypatch.setattr("ki_knowledge.django_site.services.data_root", lambda: data_root)

    assert display_data_path(markdown_file) == "anthro/sstk/10_geistige_welt/anspruch-und-ziel_bak.md"


def test_infosite_project_display_output_dir_uses_relative_path(monkeypatch, tmp_path):
    """Project output dirs should be displayed relative to the shared data root."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ki_knowledge.django_site.settings")
    import django

    django.setup()
    from django.conf import settings

    settings.KI_CONFIG = SimpleNamespace(knowledge_data_root=str(tmp_path / "dev_data" / "ki-knowledge"))

    data_root = Path(settings.KI_CONFIG.knowledge_data_root)
    output_dir = data_root / "data_out" / "anthro" / "sstk"
    output_dir.mkdir(parents=True)

    project = type("ProjectStub", (), {"domain": "anthro", "working_title": "sstk", "output_dir": str(output_dir)})()

    from ki_knowledge.knowledge.adapters import InfoSiteSourceAdapter

    assert InfoSiteSourceAdapter.relative_output_path(project, project.output_dir) == "anthro/sstk"


def test_infosite_generator_applies_mapping_rules(tmp_path):
    """A project mapping rule should move a document into the configured target section."""
    data_root = tmp_path / "dev_data" / "ki-knowledge"
    source_dir = data_root / "md" / "anthro" / "sstk" / "10_geistige_welt"
    source_dir.mkdir(parents=True)
    source_file = source_dir / "anspruch-und-ziel.md"
    source_file.write_text("# Anspruch und Ziel\n", encoding="utf-8")

    generator = InfoSiteGeneratorService(data_root)
    result = generator.generate_infosite(
        domain="anthro",
        working_title="sstk",
        source_docs=[
            FileInfo(
                path=source_file,
                name=source_file.name,
                file_type="md",
                size=source_file.stat().st_size,
                modified_at=datetime.now(),
            )
        ],
        mapping_rules=[
            {
                "source_path": "10_geistige_welt/anspruch-und-ziel.md",
                "target_parent": "10_geistige_welt",
                "target_section": "Anspruch und Ziel",
                "order_index": 1,
                "active": True,
            }
        ],
    )

    assert result.success is True
    output_dir = result.output_dir
    assert output_dir is not None
    index_content = (output_dir / "index.md").read_text(encoding="utf-8")
    overview_content = (output_dir / "overview.md").read_text(encoding="utf-8")
    metadata_content = (output_dir / "metadata.yml").read_text(encoding="utf-8")
    assert "Anspruch und Ziel" in index_content
    assert "Anspruch und Ziel" in overview_content
    assert "source_path: 10_geistige_welt/anspruch-und-ziel.md" in metadata_content


def test_infosite_generator_creates_static_html_site(tmp_path):
    """The project can also emit a browsable HTML website alongside markdown output."""
    data_root = tmp_path / "dev_data" / "ki-knowledge"
    source_dir = data_root / "md" / "anthro" / "sstk"
    source_dir.mkdir(parents=True)
    source_file = source_dir / "anspruch-und-ziel.md"
    source_file.write_text("# Anspruch und Ziel\n\nEin kurzer Text.\n", encoding="utf-8")

    generator = InfoSiteGeneratorService(data_root)
    generation = generator.generate_infosite(
        domain="anthro",
        working_title="sstk",
        source_docs=[
            FileInfo(
                path=source_file,
                name=source_file.name,
                file_type="md",
                size=source_file.stat().st_size,
                modified_at=datetime.now(),
            )
        ],
    )
    assert generation.success is True

    html_result = generator.generate_html_site(generation.output_dir)
    assert html_result.success is True
    assert (generation.output_dir / "html" / "index.html").exists()
    assert (generation.output_dir / "html" / "overview.html").exists()
    html_content = (generation.output_dir / "html" / "index.html").read_text(encoding="utf-8")
    assert "Complete Index" in html_content or "Overview" in html_content


def test_infosite_generator_uses_site_hierarchy_for_output_paths(tmp_path):
    """When the project uses a custom hierarchy, generated markdown should follow it."""
    data_root = tmp_path / "dev_data" / "ki-knowledge"
    source_dir = data_root / "md" / "anthro" / "sstk" / "20_integrale-theorie"
    source_dir.mkdir(parents=True)
    source_file = source_dir / "Integrale Weltsicht.md"
    source_file.write_text("# Integrale Weltsicht\n", encoding="utf-8")

    generator = InfoSiteGeneratorService(data_root)
    generation = generator.generate_infosite(
        domain="anthro",
        working_title="sstk",
        source_docs=[
            FileInfo(
                path=source_file,
                name=source_file.name,
                file_type="md",
                size=source_file.stat().st_size,
                modified_at=datetime.now(),
            )
        ],
        site_structure=[
            {"title": "70_sstk", "children": [{"title": "20_integrale-theorie", "children": []}]}
        ],
    )

    assert generation.success is True
    assert (generation.output_dir / "70_sstk" / "20_integrale-theorie" / "Integrale Weltsicht.md").exists()

    html_result = generator.generate_html_site(generation.output_dir)
    assert html_result.success is True
    assert (generation.output_dir / "html" / "70_sstk" / "20_integrale-theorie" / "Integrale Weltsicht.html").exists()


def test_infosite_generator_creates_admin_metadata_pages(tmp_path):
    """Admin metadata pages are generated in a separate HTML admin subfolder."""
    data_root = tmp_path / "dev_data" / "ki-knowledge"
    source_dir = data_root / "md" / "anthro" / "sstk"
    source_dir.mkdir(parents=True)
    source_file = source_dir / "anspruch-und-ziel.md"
    source_file.write_text("# Anspruch und Ziel\n\nEin kurzer Text.\n", encoding="utf-8")

    generator = InfoSiteGeneratorService(data_root)
    generation = generator.generate_infosite(
        domain="anthro",
        working_title="sstk",
        source_docs=[
            FileInfo(
                path=source_file,
                name=source_file.name,
                file_type="md",
                size=source_file.stat().st_size,
                modified_at=datetime.now(),
            )
        ],
    )
    assert generation.success is True

    admin_result = generator.generate_admin_metadata_pages(generation.output_dir)
    assert admin_result.success is True
    assert (generation.output_dir / "html" / "admin" / "index.html").exists()
    assert (generation.output_dir / "html" / "admin" / "overview.html").exists()
    assert (generation.output_dir / "html" / "admin" / "metadata.html").exists()


def test_infosite_generator_flattens_nested_site_structure_order():
    """Nested hierarchy structures should be flattened into stable ordering keys."""
    generator = InfoSiteGeneratorService(Path("/tmp/test-root"))
    structure = [
        {"title": "Top", "children": [{"title": "Second"}, {"title": "First"}]},
        {"title": "Third"},
    ]

    assert generator._topic_order("First", structure)[0] < generator._topic_order("Third", structure)[0]
    assert generator._topic_order("Second", structure)[0] < generator._topic_order("First", structure)[0]
