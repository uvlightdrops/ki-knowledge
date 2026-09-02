"""Tests for infosite module."""

import tempfile
from pathlib import Path

import pytest

from ki_knowledge.infosite import InfoSiteConfig, InfoSiteGenerator, InfoSiteMetadata
from ki_knowledge.infosite.models import PageSpec


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
