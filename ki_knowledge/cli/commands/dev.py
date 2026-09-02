"""Development commands for Django and testing."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click


def _get_project_root() -> Path:
    """Get project root directory."""
    return Path(__file__).resolve().parents[3]


@click.command()
@click.option("--host", default="127.0.0.1", help="Server host (default: 127.0.0.1)")
@click.option("--port", default=8000, type=int, help="Server port (default: 8000)")
@click.option(
    "--no-migrate",
    is_flag=True,
    help="Skip database migrations before starting",
)
def django_start(host: str, port: int, no_migrate: bool) -> None:
    """Start Django development server.

    Examples:
        kictl dev django start
        kictl dev django start --port 8001
        kictl dev django start --host 0.0.0.0
    """
    project_root = _get_project_root()

    click.echo("🚀 Starting Django development server...", err=True)

    if not no_migrate:
        click.echo("📦 Running migrations...", err=True)
        result = subprocess.run(
            [sys.executable, "manage.py", "migrate"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            click.echo(f"❌ Migration failed: {result.stderr}", err=True)
            raise click.ClickException("Migrations failed")
        click.echo("✓ Migrations complete", err=True)

    click.echo(f"📍 Server starting at http://{host}:{port}/", err=True)
    click.echo("Press Ctrl+C to stop", err=True)
    click.echo("", err=True)

    result = subprocess.run(
        [sys.executable, "manage.py", "runserver", f"{host}:{port}"],
        cwd=project_root,
    )
    sys.exit(result.returncode)


@click.command()
def django_migrate() -> None:
    """Run Django database migrations.

    Examples:
        kictl dev django migrate
    """
    project_root = _get_project_root()

    click.echo("📦 Running migrations...", err=True)
    result = subprocess.run(
        [sys.executable, "manage.py", "migrate"],
        cwd=project_root,
    )

    if result.returncode == 0:
        click.echo("✓ Migrations complete", err=True)
    else:
        raise click.ClickException("Migrations failed")

    sys.exit(result.returncode)


@click.command()
def django_shell() -> None:
    """Open Django interactive shell.

    Examples:
        kictl dev django shell
    """
    project_root = _get_project_root()

    click.echo("🐚 Opening Django shell...", err=True)
    result = subprocess.run(
        [sys.executable, "manage.py", "shell"],
        cwd=project_root,
    )
    sys.exit(result.returncode)


@click.command()
def django_createsuperuser() -> None:
    """Create Django admin superuser.

    Examples:
        kictl dev django createsuperuser
    """
    project_root = _get_project_root()

    click.echo("👤 Creating superuser...", err=True)
    result = subprocess.run(
        [sys.executable, "manage.py", "createsuperuser"],
        cwd=project_root,
    )
    sys.exit(result.returncode)


@click.command()
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Verbose output",
)
@click.option(
    "--coverage",
    is_flag=True,
    help="Run with coverage report",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Quiet output",
)
@click.argument("test_path", default="tests/", required=False)
def run_tests(verbose: bool, coverage: bool, quiet: bool, test_path: str) -> None:
    """Run tests with pytest.

    Examples:
        kictl dev test
        kictl dev test tests/test_cli.py
        kictl dev test --verbose
        kictl dev test --coverage
    """
    project_root = _get_project_root()

    cmd = [sys.executable, "-m", "pytest"]

    if verbose:
        cmd.append("-v")
    
    if quiet:
        cmd.append("-q")

    if coverage:
        cmd.extend(["--cov=ki_knowledge", "--cov-report=html"])

    cmd.append(test_path)

    click.echo(f"🧪 Running tests: {' '.join(cmd)}", err=True)
    result = subprocess.run(cmd, cwd=project_root)
    sys.exit(result.returncode)


@click.command()
@click.option(
    "--select",
    default="",
    help="Select specific rules (e.g., E,W)",
)
def run_lint(select: str) -> None:
    """Run linter (ruff/flake8).

    Examples:
        kictl dev lint
        kictl dev lint --select E,W
    """
    project_root = _get_project_root()

    # Try ruff first, fall back to flake8
    for linter_cmd in [
        [sys.executable, "-m", "ruff", "check", "ki_knowledge", "tests"],
        [sys.executable, "-m", "flake8", "ki_knowledge", "tests"],
    ]:
        try:
            click.echo(f"📝 Running linter: {' '.join(linter_cmd)}", err=True)
            result = subprocess.run(linter_cmd, cwd=project_root)
            sys.exit(result.returncode)
        except FileNotFoundError:
            continue

    click.echo("❌ No linter found (ruff or flake8)", err=True)
    click.echo("Install with: pip install ruff", err=True)
    sys.exit(1)
