"""Nextcloud storage backend: list / download / import (input) and create-only upload (output).

Input and output are separated per domain (``apps.ki_knowledge.nextcloud.domains``):

* ``input_root``: remote folder that is listed, downloaded and imported. Paths
  given by callers are relative to it and can never leave it.
* ``output_root``: remote folder that receives generated files from the local
  DataLayout output tree of the same domain. Uploads never overwrite.

Downloads land in a dedicated cache (``DataLayout.remote_input_cache_dir``),
never in local source folders. Imported knowledge keeps the *remote* identity
(URL, ETag, Nextcloud file id) as provenance; the local cache path is only
recorded as secondary information. Only Markdown is importable for now; other
types raise :class:`NextcloudUnsupportedTypeError` before any download.

This is plain file transport. It does not synchronise knowledge records or
relations (that is the separate node contribution mechanism).
"""

from __future__ import annotations

import json
import mimetypes
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit

from ki_knowledge.data_layout import DataLayout, LayoutError
from ki_knowledge.integrations.markdown_blocks import KnowledgeBlock, MarkdownBlockParser
from ki_knowledge.integrations.nextcloud import (
    DomainRoots,
    DownloadResult,
    NextcloudConfigError,
    NextcloudError,
    NextcloudPathError,
    NextcloudResponseError,
    NextcloudSettings,
    NextcloudSizeError,
    NextcloudUnsupportedTypeError,
    NextcloudWebDAVClient,
    RemoteEntry,
    UploadResult,
    is_within,
    join_remote,
    split_remote_path,
)
from ki_knowledge.knowledge.models import DataSourceDescriptor, KnowledgeSource, SourceDocumentRecord

PROVIDER = "nextcloud"
SOURCE_TYPE = "nextcloud_markdown"
IMPORTABLE_SUFFIXES = {".md": "markdown", ".markdown": "markdown"}
_FILES_DIR = "files"
_META_DIR = "meta"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def import_kind(path: str) -> str:
    """Importer for a remote file name, or raise for unsupported types."""
    suffix = Path(path).suffix.lower()
    kind = IMPORTABLE_SUFFIXES.get(suffix)
    if kind is None:
        supported = ", ".join(sorted(IMPORTABLE_SUFFIXES))
        raise NextcloudUnsupportedTypeError(f"{path}: file type {suffix or '(none)'} is not importable (supported: {supported})")
    return kind


@dataclass(frozen=True)
class ImportResult:
    source_id: str
    path: str
    remote_url: str
    etag: Optional[str]
    file_id: Optional[str]
    records: int
    not_modified: bool
    local_cache_path: str


class _ProvenanceParser(MarkdownBlockParser):
    """Markdown parser that stamps the remote provenance onto every block."""

    def __init__(self, provenance: dict[str, Any]):
        super().__init__()
        self._provenance = provenance

    def parse_markdown(self, text: str, source_path: str) -> list[KnowledgeBlock]:
        blocks = super().parse_markdown(text, source_path)
        for block in blocks:
            block.metadata["remote"] = dict(self._provenance)
        return blocks


class NextcloudStorage:
    """Domain-bound facade over :class:`NextcloudWebDAVClient`."""

    def __init__(
        self,
        settings: NextcloudSettings,
        layout: DataLayout,
        *,
        client: Optional[NextcloudWebDAVClient] = None,
    ):
        settings.require_ready()
        self.settings = settings
        self.layout = layout
        self.client = client or NextcloudWebDAVClient(settings)

    @classmethod
    def from_config(cls, cfg: Any = None) -> "NextcloudStorage":
        if cfg is None:
            from ki_knowledge.app_config import AppConfig

            cfg = AppConfig.from_env()
        return cls(NextcloudSettings.from_config(cfg), DataLayout.from_config(cfg))

    # --- path mapping -------------------------------------------------------------

    def roots(self, domain: str) -> DomainRoots:
        return self.settings.roots_for(domain)

    def input_path(self, domain: str, relative: str = "") -> tuple[str, ...]:
        root = self.roots(domain).input_root
        segments = root + split_remote_path(relative)
        if not is_within(segments, root):  # pragma: no cover - split_remote_path rejects ".."
            raise NextcloudPathError(f"{relative!r} escapes the input root of domain {domain!r}")
        return segments

    def output_path(self, domain: str, relative: Path) -> tuple[str, ...]:
        root = self.roots(domain).output_root
        segments = root + split_remote_path(relative.as_posix(), allow_empty=False)
        if not is_within(segments, root):  # pragma: no cover
            raise NextcloudPathError(f"{relative} escapes the output root of domain {domain!r}")
        return segments

    def _input_relative(self, domain: str, entry: RemoteEntry) -> str:
        root = self.roots(domain).input_root
        segments = split_remote_path(entry.path)
        if not is_within(segments, root) or segments == root:
            raise NextcloudPathError(f"{entry.path} is outside the input root of domain {domain!r}")
        return join_remote(segments[len(root):])

    # --- descriptors -------------------------------------------------------------

    def source_id(self, entry: RemoteEntry) -> str:
        """Stable id: Nextcloud file id (survives renames/moves); remote URL as fallback."""
        host = urlsplit(self.settings.base_url).netloc.lower()
        if entry.file_id:
            return f"{PROVIDER}:{host}:{self.settings.effective_user_id}:fileid:{entry.file_id}"
        return f"{PROVIDER}:{entry.url}"

    def describe_domain(self, domain: str) -> DataSourceDescriptor:
        roots = self.roots(domain)
        return DataSourceDescriptor(
            source_id=f"{PROVIDER}:{urlsplit(self.settings.base_url).netloc.lower()}:{self.settings.effective_user_id}:{domain}",
            source_type="remote_storage",
            title=f"Nextcloud {domain}",
            uri=self.client.url_for(roots.input_root),
            provider=PROVIDER,
            status="configured",
            metadata={
                "domain": domain,
                "transport": "webdav",
                "input_root": join_remote(roots.input_root),
                "output_root": join_remote(roots.output_root),
                "output_uri": self.client.url_for(roots.output_root),
            },
        )

    def describe_entry(self, domain: str, entry: RemoteEntry) -> SourceDocumentRecord:
        relative = self._input_relative(domain, entry)
        try:
            importable = import_kind(entry.path) if not entry.is_dir else None
        except NextcloudUnsupportedTypeError:
            importable = None
        return SourceDocumentRecord(
            document_id=self.source_id(entry),
            source_id=self.describe_domain(domain).source_id,
            document_type="folder" if entry.is_dir else (importable or "unsupported"),
            title=entry.name,
            uri=entry.url,
            version=entry.etag or "",
            status="remote",
            checksum=entry.etag,
            metadata={
                "domain": domain,
                "path": relative,
                "remote_path": entry.path,
                "file_id": entry.file_id,
                "size": entry.size,
                "last_modified": entry.last_modified,
                "content_type": entry.content_type,
                "importable": importable is not None,
            },
        )

    # --- list --------------------------------------------------------------------

    def list(self, domain: str, relative: str = "") -> list[SourceDocumentRecord]:
        """Direct children of ``<input_root>/<relative>`` (non-recursive)."""
        entries = self.client.list(self.input_path(domain, relative))
        return [self.describe_entry(domain, entry) for entry in entries]

    # --- download ------------------------------------------------------------------

    def _cache_paths(self, domain: str, relative: str) -> tuple[Path, Path, Path]:
        base = self.layout.remote_input_cache_dir(domain, PROVIDER)
        segments = split_remote_path(relative, allow_empty=False)
        files_root = base / _FILES_DIR
        meta_root = base / _META_DIR
        target = files_root.joinpath(*segments)
        meta = meta_root.joinpath(*segments[:-1], segments[-1] + ".json")
        for root, path in ((files_root, target), (meta_root, meta)):
            root.mkdir(parents=True, exist_ok=True)
            resolved_root = root.resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.parent.resolve().is_relative_to(resolved_root) or path.is_symlink():
                raise LayoutError(f"cache path escapes the Nextcloud cache: {path}")
        return target, meta, base

    @staticmethod
    def _read_meta(meta: Path) -> dict[str, Any]:
        try:
            return json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    @staticmethod
    def _write_meta(meta: Path, payload: dict[str, Any]) -> None:
        fd, tmp_name = tempfile.mkstemp(prefix=f".{meta.name}.", suffix=".part", dir=meta.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            os.replace(tmp_name, meta)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise

    def download(self, domain: str, relative: str) -> DownloadResult:
        """Fetch one file of the input root into the local input cache (conditional on the ETag)."""
        segments = self.input_path(domain, relative)
        if segments == self.roots(domain).input_root:
            raise NextcloudPathError("a file path below the input root is required")
        entry = self.client.stat(segments)
        if entry.is_dir:
            raise NextcloudResponseError(f"{join_remote(segments)} is a folder, not a file")
        if entry.size is not None and entry.size > self.settings.max_download_bytes:
            raise NextcloudSizeError(f"{entry.path}: {entry.size} bytes exceeds limit {self.settings.max_download_bytes}")
        rel = self._input_relative(domain, entry)
        target, meta_path, _ = self._cache_paths(domain, rel)
        meta = self._read_meta(meta_path)
        known_etag = meta.get("etag") if meta.get("remote_url") == entry.url else None
        not_modified, etag, sha256, size = self.client.download(segments, target, if_none_match=known_etag)
        if not_modified:
            etag, sha256 = known_etag, meta.get("sha256")
        else:
            etag = etag or entry.etag
            meta = {
                "provider": PROVIDER,
                "domain": domain,
                "path": rel,
                "remote_path": entry.path,
                "remote_url": entry.url,
                "etag": etag,
                "file_id": entry.file_id,
                "size": size,
                "last_modified": entry.last_modified,
                "content_type": entry.content_type,
                "sha256": sha256,
                "fetched_at": _now(),
                "imported_etag": meta.get("imported_etag"),
            }
            self._write_meta(meta_path, meta)
        return DownloadResult(entry, target, etag, sha256, size, not_modified)

    # --- import --------------------------------------------------------------------

    def import_file(self, domain: str, relative: str, store: Any) -> ImportResult:
        """Download (conditionally) and import one Markdown file into ``store``."""
        import_kind(relative)
        result = self.download(domain, relative)
        entry = result.entry
        import_kind(entry.path)
        try:
            text = result.local_path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            raise NextcloudUnsupportedTypeError(f"{entry.path}: content is not valid UTF-8 Markdown") from None
        rel = self._input_relative(domain, entry)
        source_id = self.source_id(entry)
        provenance = {
            "provider": PROVIDER,
            "transport": "webdav",
            "instance": self.settings.base_url.rstrip("/"),
            "user_id": self.settings.effective_user_id,
            "domain": domain,
            "remote_url": entry.url,
            "remote_path": entry.path,
            "path": rel,
            "etag": result.etag,
            "file_id": entry.file_id,
            "size": result.size,
            "last_modified": entry.last_modified,
            "content_type": entry.content_type,
            "sha256": result.sha256,
        }
        store.import_markdown_text(
            text,
            source_path=entry.url,
            source_name=rel,
            parser=_ProvenanceParser({k: provenance[k] for k in ("provider", "remote_url", "etag", "file_id")}),
            source_id=source_id,
            source_type=SOURCE_TYPE,
            replace=True,
        )
        store.upsert_source(KnowledgeSource(
            source_id=source_id,
            source_type=SOURCE_TYPE,
            title=rel,
            location=entry.url,
            metadata={
                "source_name": rel,
                "domain": domain,
                "provenance": {**provenance, "imported_at": _now(), "local_cache_path": str(result.local_path)},
            },
        ))
        records = len(store.list_records(source_id=source_id))
        _, meta_path, _ = self._cache_paths(domain, rel)
        meta = self._read_meta(meta_path)
        meta.update({"imported_etag": result.etag, "imported_at": _now(), "source_id": source_id})
        self._write_meta(meta_path, meta)
        return ImportResult(
            source_id, rel, entry.url, result.etag, entry.file_id, records, result.not_modified, str(result.local_path)
        )

    def import_folder(self, domain: str, relative: str, store: Any) -> dict[str, Any]:
        """Import every Markdown file directly in ``<input_root>/<relative>`` (non-recursive).

        Unsupported files and sub folders are reported as skipped, never as imported.
        """
        imported: list[dict[str, Any]] = []
        skipped: list[dict[str, str]] = []
        errors: list[dict[str, str]] = []
        for record in self.list(domain, relative):
            path = record.metadata["path"]
            if record.document_type == "folder":
                skipped.append({"path": path, "reason": "folder (not recursive)"})
                continue
            if not record.metadata["importable"]:
                skipped.append({"path": path, "reason": "unsupported file type"})
                continue
            try:
                imported.append(asdict(self.import_file(domain, path, store)))
            except NextcloudError as exc:
                errors.append({"path": path, "error": str(exc)})
        return {"imported": imported, "skipped": skipped, "errors": errors}

    # --- upload --------------------------------------------------------------------

    def upload_output(self, domain: str, local_path: str | Path, *, create_parents: bool = False) -> UploadResult:
        """Upload one generated file of the domain's output tree to the output root.

        The remote path mirrors the path below ``DataLayout.output_dir(domain)``.
        The upload is create-only; an existing remote file raises
        :class:`NextcloudConflictError` and stays untouched.
        """
        self.roots(domain)
        resolved, relative = self.layout.require_output_file(domain, local_path)
        target = self.output_path(domain, relative)
        if create_parents:
            root = self.roots(domain).output_root
            for depth in range(len(root) + 1, len(target)):
                self.client.mkcol(target[:depth])
        content_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        return self.client.upload_new(target, resolved, content_type=content_type)


def open_store(cfg: Any = None):
    """KnowledgeStore of the configured target (same selection as Django)."""
    from ki_knowledge.config_runtime import knowledge_store_target
    from ki_knowledge.integrations.knowledge_store import KnowledgeStore

    return KnowledgeStore(knowledge_store_target(cfg))


__all__ = [
    "IMPORTABLE_SUFFIXES",
    "ImportResult",
    "NextcloudConfigError",
    "NextcloudStorage",
    "PROVIDER",
    "SOURCE_TYPE",
    "import_kind",
    "open_store",
]
