"""Display effective filesystem paths without creating directories."""

import click

from ki_knowledge.data_layout import LayoutError, SOURCE_TYPES, source_type_dir_name
from ki_knowledge.services import domain_paths


@click.command()
@click.argument("domain")
@click.argument(
    "kind",
    type=click.Choice(["md", "pdf", "epub", "jira", "owl", "mix"]),
    required=False,
)
def paths(domain: str, kind: str | None) -> None:
    """Show existing source folders for DOMAIN, or the resolved path for KIND."""
    if not domain.strip():
        raise click.UsageError("DOMAIN must not be empty.")
    try:
        domain_paths.validate_domain_name(domain_paths.normalize_semantic_domain(domain))
        if kind is not None:
            click.echo(str(domain_paths.domain_source_dir(kind, domain).resolve()))
            return
        layout = domain_paths.data_layout()
        click.echo(f"data_root: {layout.root.resolve()}")
        click.echo(f"layout_version: {layout.version}")
        found = False
        for source_type in SOURCE_TYPES:
            path = domain_paths.domain_source_dir(source_type, domain)
            if path.is_dir():
                click.echo(f"{source_type_dir_name(source_type)}: {path.resolve()}")
                found = True
        if not found:
            click.echo("No source directories exist for this domain.")
    except (LayoutError, OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
