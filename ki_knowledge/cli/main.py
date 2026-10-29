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
    config_paths = [
        Path.cwd() / "cli.yaml",
        Path(__file__).parent / "cli.yaml",
    ]

    config_path = next((path for path in config_paths if path.exists()), None)
    if config_path is None:
        click.echo("Error: Could not find cli.yaml configuration", err=True)
        click.echo("\nSearched in:", err=True)
        for cp in config_paths:
            click.echo(f"  - {cp}", err=True)
        sys.exit(1)

    try:
        cli = CLIBuilder.from_yaml_file(config_path).build_cli()
    except Exception as e:
        click.echo(f"Error loading CLI configuration {config_path}: {e}", err=True)
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
