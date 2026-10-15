"""Profile management commands for ki-knowledge (delegates to ki-core).

These commands provide profile management by delegating
to ki_core.commands for consistency across the KI ecosystem.
"""

import click


def run_list():
    """List available profiles (delegates to ki-core)."""
    try:
        from ki_core.commands import run_profile_list
        run_profile_list(echo_fn=click.echo, profiles_dir="config/profiles")
    except ImportError:
        click.echo("❌ ki-core not installed. Cannot list profiles.", err=True)
        raise click.Exit(code=1)


def run_set():
    """Set active profile (delegates to ki-core)."""
    try:
        from ki_core.commands import run_profile_set
        # Would need CLI args here - for now just show message
        click.echo("Use: ki profile set <name>")
        click.echo("❌ CLI argument passing not yet implemented.", err=True)
        raise click.Exit(code=1)
    except ImportError:
        click.echo("❌ ki-core not installed. Cannot set profile.", err=True)
        raise click.Exit(code=1)


def run_active():
    """Show active profile (delegates to ki-core)."""
    try:
        from ki_core.commands import run_profile_active
        run_profile_active(echo_fn=click.echo, profiles_dir="config/profiles")
    except ImportError:
        click.echo("❌ ki-core not installed. Cannot show active profile.", err=True)
        raise click.Exit(code=1)
