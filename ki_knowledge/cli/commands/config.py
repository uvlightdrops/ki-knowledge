"""Config management commands for ki-knowledge (delegates to ki-core).

These commands provide config inspection and management by delegating
to ki_core.commands for consistency across the KI ecosystem.
"""

import click


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


def run_show():
    """Show config or specific key (delegates to ki-core)."""
    try:
        from ki_core.commands import run_show
        run_show(echo_fn=click.echo)
    except ImportError:
        click.echo("❌ ki-core not installed. Cannot show config.", err=True)
        raise click.Exit(code=1)


def run_verify():
    """Verify config against schema (delegates to ki-core)."""
    try:
        from ki_core.commands import run_verify
        run_verify(echo_fn=click.echo)
    except ImportError:
        click.echo("❌ ki-core not installed. Cannot verify config.", err=True)
        raise click.Exit(code=1)
