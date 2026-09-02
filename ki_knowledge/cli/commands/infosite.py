"""Infosite CLI commands.

This module provides CLI commands for infosite management.
Django models are optional and only loaded when needed.
"""

from pathlib import Path

import click
from tabulate import tabulate

from ki_core.config import Config
from ki_knowledge.infosite import InfoSiteConfig, InfoSiteGenerator
from ki_knowledge.infosite.importer import DocumentImporterRegistry


def _get_django_project():
    """Lazily import Django models only when needed.

    Returns:
        InfoSiteProject class or None if Django not available
    """
    try:
        import os
        import django

        # Check if Django is configured
        if not os.environ.get("DJANGO_SETTINGS_MODULE"):
            # Set default Django settings if available
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ki_knowledge.django_site.settings")

        if not django.apps.apps.ready:
            django.setup()

        from ki_knowledge.django_site.infosite_models import InfoSiteProject

        return InfoSiteProject
    except Exception:
        return None


def init_project():
    """Initialize a new infosite project."""
    click.echo("🚀 Initializing new infosite project...\n")

    title = click.prompt("Project title", default="My Knowledge Base")
    domain = click.prompt("Domain", default="default")
    source_dir = click.prompt("Source documents directory", default="", show_default=False)

    click.echo(f"\n✓ Project initialized:")
    click.echo(f"  Title: {title}")
    click.echo(f"  Domain: {domain}")
    if source_dir:
        click.echo(f"  Source: {source_dir}")

    click.echo("\nNext steps:")
    click.echo("  1. Configure infosite_output_base_dir in ki.yaml")
    click.echo("  2. Run: ki infosite generate")


def generate_infosite():
    """Generate infosite from source documents."""
    click.echo("📚 Generating infosite...\n")

    try:
        config = Config.from_yaml()

        if not config.infosite_output_base_dir:
            raise click.ClickException("infosite_output_base_dir not configured in ki.yaml")

        if not config.infosite_title:
            raise click.ClickException("infosite_title not configured in ki.yaml")

        click.echo(f"Title: {config.infosite_title}")
        click.echo(f"Domain: {config.infosite_domain}")
        click.echo(f"Output: {config.infosite_output_base_dir}")

        infosite_config = InfoSiteConfig(
            enabled=True,
            title=config.infosite_title,
            domain=config.infosite_domain,
            output_base_dir=config.infosite_output_base_dir,
        )

        generator = InfoSiteGenerator(infosite_config)

        with click.progressbar(
            length=3,
            label="Generating",
            show_eta=True,
        ) as bar:
            # Determine source
            if config.knowledge_data_root:
                source_path = Path(config.knowledge_data_root) / "documents"
                if source_path.exists():
                    bar.update(1)
                    output_dir = generator.generate_from_documents(source_path)
                    bar.update(2)
                else:
                    bar.update(1)
                    pages = generator.create_default_pages(config.infosite_title)
                    output_dir = generator.generate(pages)
                    bar.update(2)
            else:
                bar.update(1)
                pages = generator.create_default_pages(config.infosite_title)
                output_dir = generator.generate(pages)
                bar.update(2)

            bar.update(3)

        click.echo(f"\n✓ Infosite generated!")
        click.echo(f"  Location: {output_dir}")

        # List generated files
        md_files = list(output_dir.glob("**/*.md"))
        if md_files:
            click.echo(f"  Files: {len(md_files)} markdown files")

    except Exception as e:
        raise click.ClickException(f"Failed to generate infosite: {e}")


def list_projects():
    """List infosite projects."""
    InfoSiteProject = _get_django_project()

    if InfoSiteProject is None:
        click.echo("⚠️  Django integration not available (not configured)")
        click.echo("   Use 'generate' command to create infosites via CLI config")
        return

    click.echo("📋 Infosite Projects:\n")

    try:
        projects = InfoSiteProject.objects.all()

        if not projects.exists():
            click.echo("No projects yet.")
            return

        data = []
        for project in projects:
            doc_count = project.documents.count()
            imported = project.documents.filter(imported=True).count()
            data.append(
                [
                    project.title,
                    project.domain,
                    f"{imported}/{doc_count}",
                    "✓" if project.enabled else "✗",
                    project.last_generated or "-",
                ]
            )

        headers = ["Title", "Domain", "Docs", "Enabled", "Last Generated"]
        click.echo(tabulate(data, headers=headers, tablefmt="simple"))

    except Exception as e:
        raise click.ClickException(f"Failed to list projects: {e}")


def discover_documents():
    """Discover source documents."""
    click.echo("🔍 Discovering documents...\n")

    source_dir = click.prompt("Source directory")
    source_path = Path(source_dir)

    if not source_path.exists():
        raise click.ClickException(f"Directory not found: {source_path}")

    registry = DocumentImporterRegistry()
    documents = registry.import_directory(source_path)

    click.echo(f"\n✓ Found {len(documents)} document(s):\n")

    for file_path in sorted(documents.keys()):
        content = documents[file_path]
        size = len(content)
        click.echo(f"  • {file_path} ({size} bytes)")




def init_project():
    """Initialize a new infosite project."""
    click.echo("🚀 Initializing new infosite project...\n")

    title = click.prompt("Project title", default="My Knowledge Base")
    domain = click.prompt("Domain", default="default")
    source_dir = click.prompt("Source documents directory", default="", show_default=False)

    click.echo(f"\n✓ Project initialized:")
    click.echo(f"  Title: {title}")
    click.echo(f"  Domain: {domain}")
    if source_dir:
        click.echo(f"  Source: {source_dir}")

    click.echo("\nNext steps:")
    click.echo("  1. Configure infosite_output_base_dir in ki.yaml")
    click.echo("  2. Run: ki infosite generate")


def generate_infosite():
    """Generate infosite from source documents."""
    click.echo("📚 Generating infosite...\n")

    try:
        config = Config.from_yaml()

        if not config.infosite_output_base_dir:
            raise click.ClickException("infosite_output_base_dir not configured in ki.yaml")

        if not config.infosite_title:
            raise click.ClickException("infosite_title not configured in ki.yaml")

        click.echo(f"Title: {config.infosite_title}")
        click.echo(f"Domain: {config.infosite_domain}")
        click.echo(f"Output: {config.infosite_output_base_dir}")

        infosite_config = InfoSiteConfig(
            enabled=True,
            title=config.infosite_title,
            domain=config.infosite_domain,
            output_base_dir=config.infosite_output_base_dir,
        )

        generator = InfoSiteGenerator(infosite_config)

        with click.progressbar(
            length=3,
            label="Generating",
            show_eta=True,
        ) as bar:
            # Determine source
            if config.knowledge_data_root:
                source_path = Path(config.knowledge_data_root) / "documents"
                if source_path.exists():
                    bar.update(1)
                    output_dir = generator.generate_from_documents(source_path)
                    bar.update(2)
                else:
                    bar.update(1)
                    pages = generator.create_default_pages(config.infosite_title)
                    output_dir = generator.generate(pages)
                    bar.update(2)
            else:
                bar.update(1)
                pages = generator.create_default_pages(config.infosite_title)
                output_dir = generator.generate(pages)
                bar.update(2)

            bar.update(3)

        click.echo(f"\n✓ Infosite generated!")
        click.echo(f"  Location: {output_dir}")

        # List generated files
        md_files = list(output_dir.glob("**/*.md"))
        if md_files:
            click.echo(f"  Files: {len(md_files)} markdown files")

    except Exception as e:
        raise click.ClickException(f"Failed to generate infosite: {e}")


def list_projects():
    """List infosite projects."""
    if InfoSiteProject is None:
        raise click.ClickException("Django models not available")

    click.echo("📋 Infosite Projects:\n")

    try:
        projects = InfoSiteProject.objects.all()

        if not projects.exists():
            click.echo("No projects yet.")
            return

        data = []
        for project in projects:
            doc_count = project.documents.count()
            imported = project.documents.filter(imported=True).count()
            data.append(
                [
                    project.title,
                    project.domain,
                    f"{imported}/{doc_count}",
                    "✓" if project.enabled else "✗",
                    project.last_generated or "-",
                ]
            )

        headers = ["Title", "Domain", "Docs", "Enabled", "Last Generated"]
        click.echo(tabulate(data, headers=headers, tablefmt="simple"))

    except Exception as e:
        raise click.ClickException(f"Failed to list projects: {e}")


def discover_documents():
    """Discover source documents."""
    click.echo("🔍 Discovering documents...\n")

    source_dir = click.prompt("Source directory")
    source_path = Path(source_dir)

    if not source_path.exists():
        raise click.ClickException(f"Directory not found: {source_path}")

    registry = DocumentImporterRegistry()
    documents = registry.import_directory(source_path)

    click.echo(f"\n✓ Found {len(documents)} document(s):\n")

    for file_path in sorted(documents.keys()):
        content = documents[file_path]
        size = len(content)
        click.echo(f"  • {file_path} ({size} bytes)")
