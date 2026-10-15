"""Stage management commands for ki-knowledge (delegates to ki-core).

These commands provide stage management by delegating
to ki_core.commands for consistency across the KI ecosystem.
"""

import click


def run_list():
    """List available stages (delegates to ki-core)."""
    try:
        from ki_core.commands import run_stage_list
        run_stage_list(echo_fn=click.echo, stages_dir="config/stages")
    except ImportError:
        click.echo("❌ ki-core not installed. Cannot list stages.", err=True)
        raise click.Exit(code=1)


def run_set():
    """Set active stage (delegates to ki-core)."""
    try:
        from ki_core.commands import run_stage_set
        # Would need CLI args here - for now just show message
        click.echo("Use: ki stage set <name>")
        click.echo("❌ CLI argument passing not yet implemented.", err=True)
        raise click.Exit(code=1)
    except ImportError:
        click.echo("❌ ki-core not installed. Cannot set stage.", err=True)
        raise click.Exit(code=1)


def run_active():
    """Show active stage (delegates to ki-core)."""
    try:
        from ki_core.commands import run_stage_active
        run_stage_active(echo_fn=click.echo, stages_dir="config/stages")
    except ImportError:
        click.echo("❌ ki-core not installed. Cannot show active stage.", err=True)
        raise click.Exit(code=1)
