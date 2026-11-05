"""Config management commands for ki-knowledge (delegates to ki-core).

Config inspection uses the app's canonical ki-core-backed accessor.
Other commands delegate to ki_core.commands.
"""

from typing import Any

import click
import yaml


def run_config():
    """Resolve and display full config (delegates to ki-core)."""
    try:
        from ki_core.commands import run_resolve
        run_resolve(echo_fn=click.echo)
    except ImportError:
        click.echo("❌ ki-core not installed. Cannot resolve config.", err=True)
        raise click.Exit(code=1)


def run_skeleton():
    """Generate config skeleton (delegates to ki-core)."""
    try:
        from ki_core.commands import run_skeleton
        run_skeleton(echo_fn=click.echo, output_file="ki.yaml")
    except ImportError:
        click.echo("❌ ki-core not installed. Cannot generate skeleton.", err=True)
        raise click.Exit(code=1)


@click.command()
@click.argument("key", required=False)
def run_show(key: str | None = None):
    """Show resolved app config or a dotted KEY, including runtime overrides."""
    from ki_knowledge.app_config import AppConfig

    value: Any = dict(AppConfig.from_env().raw)
    if key is not None:
        for part in key.split("."):
            if not isinstance(value, dict) or part not in value:
                raise click.ClickException(f"Configuration key not found: {key}")
            value = value[part]
    if isinstance(value, str):
        click.echo(value)
    else:
        click.echo(yaml.safe_dump(value, sort_keys=False).removesuffix("...\n").rstrip("\n"))


def run_verify():
    """Verify config against schema (delegates to ki-core)."""
    try:
        from ki_core.commands import run_verify
        run_verify(echo_fn=click.echo)
    except ImportError:
        click.echo("❌ ki-core not installed. Cannot verify config.", err=True)
        raise click.Exit(code=1)
