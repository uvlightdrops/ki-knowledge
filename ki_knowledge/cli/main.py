#!/usr/bin/env python
"""Ki-Knowledge CLI - Main entry point.

Usage:
    python -m ki_knowledge.cli.main infosite generate
    python -m ki_knowledge.cli.main infosite list
    python -m ki_knowledge.cli.main knowledge import
    python -m ki_knowledge.cli.main --help
"""

import sys
from pathlib import Path

import click

from ki_knowledge.cli.framework import CLIBuilder


def main():
    """Main CLI entry point."""
    # Try to find cli.yaml config
    config_paths = [
        Path.cwd() / "cli.yaml",
        Path(__file__).parent.parent.parent / "cli.yaml",  # From ki_knowledge/cli/main.py -> project root
        Path(__file__).parent / "cli.yaml",  # From module
    ]

    cli = None
    for config_path in config_paths:
        try:
            if config_path.exists():
                builder = CLIBuilder.from_yaml_file(config_path)
                cli = builder.build_cli()
                break
        except Exception as e:
            pass

    if cli is None:
        click.echo("Error: Could not find cli.yaml configuration", err=True)
        click.echo("\nSearched in:", err=True)
        for cp in config_paths:
            click.echo(f"  - {cp}", err=True)
        sys.exit(1)

    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\nInterrupted.", err=True)
        sys.exit(130)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
