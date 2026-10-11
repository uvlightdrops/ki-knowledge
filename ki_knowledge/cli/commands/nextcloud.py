"""``kictl nextcloud ...``: list/download/import from and create-only upload to Nextcloud."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

import click

from ki_knowledge.data_layout import LayoutError
from ki_knowledge.integrations.nextcloud import NextcloudError


def _storage():
    from ki_knowledge.services.nextcloud_service import NextcloudStorage

    return NextcloudStorage.from_config()


def _emit(payload: Any) -> None:
    click.echo(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def _run(action):
    try:
        return action()
    except (NextcloudError, LayoutError) as exc:
        raise click.ClickException(f"{type(exc).__name__}: {exc}") from None


_domain = click.option("--domain", "-d", required=True, help="Configured domain (apps.ki_knowledge.nextcloud.domains)")


@click.command()
@_domain
@click.argument("path", default="", required=False)
def list_remote(domain: str, path: str) -> None:
    """List PATH below the domain's input root (non-recursive)."""
    _emit(_run(lambda: [asdict(record) for record in _storage().list(domain, path)]))


@click.command()
@_domain
@click.argument("path")
def download(domain: str, path: str) -> None:
    """Download PATH (relative to the input root) into the local input cache."""
    result = _run(lambda: _storage().download(domain, path))
    _emit({
        "path": result.entry.path,
        "remote_url": result.entry.url,
        "file_id": result.entry.file_id,
        "etag": result.etag,
        "sha256": result.sha256,
        "size": result.size,
        "not_modified": result.not_modified,
        "local_cache_path": str(result.local_path),
    })


@click.command(name="import")
@_domain
@click.argument("path", default="", required=False)
@click.option("--all", "import_all", is_flag=True, help="Import every Markdown file directly in PATH (folder)")
def import_remote(domain: str, path: str, import_all: bool) -> None:
    """Import a Markdown file (or with --all a folder) from the input root into the KnowledgeStore."""
    from ki_knowledge.services.nextcloud_service import open_store

    def action():
        storage = _storage()
        store = open_store()
        if import_all:
            return storage.import_folder(domain, path, store)
        if not path:
            raise click.UsageError("PATH is required unless --all is given")
        return asdict(storage.import_file(domain, path, store))

    result = _run(action)
    _emit(result)
    if import_all and result["errors"]:
        raise click.ClickException(f"{len(result['errors'])} file(s) failed")


@click.command()
@_domain
@click.argument("path")
@click.option("--mkdirs", is_flag=True, help="Create missing remote folders below the output root (MKCOL)")
def upload(domain: str, path: str, mkdirs: bool) -> None:
    """Upload a generated file from the domain's output tree; never overwrites (If-None-Match: *)."""
    _emit(asdict(_run(lambda: _storage().upload_output(domain, path, create_parents=mkdirs))))


@click.command()
def status() -> None:
    """Show the resolved Nextcloud settings (secrets masked, no network access)."""
    from ki_knowledge.integrations.nextcloud import NextcloudSettings

    settings = _run(NextcloudSettings.from_config)
    payload = settings.safe_summary()
    try:
        settings.require_ready()
        payload["ready"] = True
    except NextcloudError as exc:
        payload["ready"] = False
        payload["problem"] = str(exc)
    _emit(payload)
