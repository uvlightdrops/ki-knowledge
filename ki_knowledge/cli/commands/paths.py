"""Display effective filesystem paths without creating directories."""

import click

from ki_knowledge.data_layout import LayoutError, SOURCE_TYPES, source_type_dir_name
from ki_knowledge.services.domain_paths import data_root, domain_source_dir


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
        if kind is not None:
            click.echo(str(domain_source_dir(kind, domain).resolve()))
            return
        click.echo(f"data_root: {data_root().resolve()}")
        found = False
        for source_type in SOURCE_TYPES:
            path = domain_source_dir(source_type, domain)
            if path.is_dir():
                click.echo(f"{source_type_dir_name(source_type)}: {path.resolve()}")
                found = True
        if not found:
            click.echo("No source directories exist for this domain.")
    except (LayoutError, OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
