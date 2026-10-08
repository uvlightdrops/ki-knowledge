"""Data for the sources browser (/data-sources/sources/).

Lists the domain's files together with knowledge-store sources and their counts,
finds files in the domain's source folders that are not imported yet, and runs
per-source / per-file actions. Client input is only ever a source id or a
folder key plus a path relative to that folder; absolute paths are resolved
on the server.
"""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
import sqlite3
from typing import Any, Iterable

from ki_knowledge.data_layout import MARKDOWN, MIX, ONTOLOGY, PDF
from ki_knowledge.integrations.mixed_ingest import (
    IMAGE_KIND,
    MARKDOWN_KIND,
    ONTOLOGY_KIND,
    PDF_KIND,
    TABLE_KIND,
    UNSUPPORTED_KIND,
    classify_file,
    discover_mixed_files,
)

from .domain_paths import (
    domain_jira_dir,
    domain_source_dir,
    invalidate_domain_summary_cache,
    linked_subdirectories,
)


@dataclass(frozen=True)
class SourceKind:
    key: str
    label: str
    icon: str
    source_types: tuple[str, ...]


SOURCE_KINDS: tuple[SourceKind, ...] = (
    SourceKind("markdown", "Markdown", "📝", ("markdown",)),
    SourceKind("pdf", "PDF", "📄", ("pdf",)),
    SourceKind("owl", "Ontologie", "🕸️", ("owl",)),
    SourceKind("table", "Tabelle", "📊", (TABLE_KIND,)),
    SourceKind("image", "Bild", "🖼️", (IMAGE_KIND,)),
)
_OTHER_KIND = SourceKind("other", "Sonstige", "📦", ())
_KIND_BY_TYPE = {source_type: kind for kind in SOURCE_KINDS for source_type in kind.source_types}
KIND_KEYS = tuple(kind.key for kind in SOURCE_KINDS) + (_OTHER_KIND.key,)

# Folder names describe their usual content, not a restriction on file formats.
_SUPPORTED_FILE_KINDS = (PDF_KIND, MARKDOWN_KIND, ONTOLOGY_KIND, TABLE_KIND, IMAGE_KIND)
_FOLDERS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("md", MARKDOWN, _SUPPORTED_FILE_KINDS),
    ("pdf", PDF, _SUPPORTED_FILE_KINDS),
    ("owl", ONTOLOGY, _SUPPORTED_FILE_KINDS),
    ("mix", MIX, _SUPPORTED_FILE_KINDS),
)
FOLDER_KEYS = tuple(key for key, _type, _kinds in _FOLDERS)
_FILE_KIND_ICON = {PDF_KIND: "📄", MARKDOWN_KIND: "📝", ONTOLOGY_KIND: "🕸️", TABLE_KIND: "📊", IMAGE_KIND: "🖼️"}
STATUS_KEYS = ("imported", "new", "queued", "failed", "unsupported")
SORT_KEYS = ("updated", "title", "records", "kind", "path", "status")
PAGE_SIZE = 100


def source_kind(source_type: str) -> SourceKind:
    return _KIND_BY_TYPE.get(source_type, _OTHER_KIND)


def domain_folders(domain: str) -> dict[str, Path]:
    """Source folders of the domain by key (resolved once; path lookups re-read the config)."""
    folders = {key: domain_source_dir(source_type, domain) for key, source_type, _kinds in _FOLDERS}
    folders["jira"] = domain_jira_dir(domain)
    return folders


_FolderRoot = tuple[str, Path, bool, str]


def _folder_roots(folders: dict[str, Path]) -> list[_FolderRoot]:
    """(folder key, root, is symlink, relative prefix) for every source folder incl. jira.

    Roots are the folder as configured, its resolved path and the resolved targets of
    symlinked subfolders (prefix = the link path relative to the folder).
    """
    roots: list[_FolderRoot] = []

    def add(key: str, candidate: Path, linked: bool, prefix: str) -> None:
        if all(candidate != root for _key, root, _linked, _prefix in roots):
            roots.append((key, candidate, linked, prefix))

    for key, directory in folders.items():
        directory = directory.expanduser()
        linked = directory.is_symlink()
        for candidate in (directory, directory.resolve(strict=False)):
            add(key, candidate, linked, "")
        for link_path, target in linked_subdirectories(directory):
            add(key, target, True, link_path.relative_to(directory).as_posix())
    # Longest roots first so e.g. md/<wt> never shadows a more specific folder.
    return sorted(roots, key=lambda item: len(item[1].parts), reverse=True)


def _origin(location: str, roots: list[_FolderRoot]) -> tuple[str, str, bool]:
    path = Path(location).expanduser()
    for key, root, linked, prefix in roots:
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        relative_text = relative.as_posix()
        if prefix:
            relative_text = prefix if relative_text == "." else f"{prefix}/{relative_text}"
        return key, relative_text, linked
    return "", location, False


def _short_timestamp(value: str) -> str:
    return value.replace("T", " ")[:16] if value else ""


def source_rows(
    domain: str,
    sources: Iterable[Any],
    stats: dict[str, dict[str, Any]],
    folders: dict[str, Path] | None = None,
) -> list[dict[str, Any]]:
    roots = _folder_roots(folders or domain_folders(domain))
    rows = []
    for source in sources:
        kind = source_kind(source.source_type)
        folder, relative, linked = _origin(str(source.location or ""), roots)
        stat = stats.get(source.source_id, {})
        location = Path(str(source.location or "")).expanduser()
        rows.append(
            {
                "source_id": source.source_id,
                "imported": True,
                "status": "imported",
                "error": "",
                "title": source.title or relative,
                "source_type": source.source_type,
                "kind": kind.key,
                "kind_label": kind.label,
                "icon": kind.icon,
                "folder": folder,
                "relative": relative,
                "linked": linked,
                "records": int(stat.get("records", 0) or 0),
                "artifacts": int(stat.get("artifacts", 0) or 0),
                "updated_at": _short_timestamp(str(stat.get("updated_at", "") or "")),
                "missing": bool(folder) and not location.exists(),
                "can_reimport": can_reimport(source),
                "image_processing": str((getattr(source, "metadata", None) or {}).get("image_processing", "ocr")),
            }
        )
    return rows


def _counts(rows: Iterable[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key, "") or "")
        counts[value] = counts.get(value, 0) + 1
    return counts


def kind_counts(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = _counts(rows, "kind")
    chips = [{"key": "", "label": "Alle", "icon": "", "count": sum(counts.values())}]
    for kind in SOURCE_KINDS + (_OTHER_KIND,):
        if kind is _OTHER_KIND and not counts.get(kind.key):
            continue
        chips.append({"key": kind.key, "label": kind.label, "icon": kind.icon, "count": counts.get(kind.key, 0)})
    return chips


def status_counts(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    return _counts(rows, "status")


def folder_counts(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    return _counts(rows, "folder")


def _safe_path_prefix(path: str) -> str:
    cleaned = str(path or "").strip().strip("/")[:200]
    if not cleaned:
        return ""
    rel = PurePosixPath(cleaned)
    if rel.is_absolute() or any(part in {"", ".", ".."} for part in rel.parts):
        return ""
    return rel.as_posix()


def filter_rows(
    rows: list[dict[str, Any]],
    *,
    kind: str = "",
    query: str = "",
    sort: str = "updated",
    status: str = "",
    folder: str = "",
    path: str = "",
) -> list[dict[str, Any]]:
    needle = query.strip().lower()
    path_prefix = _safe_path_prefix(path).lower()
    selected = [
        row
        for row in rows
        if (not kind or row.get("kind") == kind)
        and (not status or row.get("status") == status)
        and (not folder or row.get("folder") == folder)
        and (not path_prefix or str(row.get("relative", "")).lower().startswith(path_prefix))
        and (
            not needle
            or needle in str(row.get("title", "")).lower()
            or needle in str(row.get("relative", "")).lower()
            or needle in str(row.get("folder", "")).lower()
        )
    ]
    if sort == "title":
        selected.sort(key=lambda row: str(row.get("title", "")).lower())
    elif sort == "records":
        selected.sort(key=lambda row: (-int(row.get("records", 0) or 0), str(row.get("title", "")).lower()))
    elif sort == "kind":
        selected.sort(key=lambda row: (KIND_KEYS.index(row.get("kind")) if row.get("kind") in KIND_KEYS else 999, str(row.get("title", "")).lower()))
    elif sort == "path":
        selected.sort(key=lambda row: (str(row.get("folder", "")), str(row.get("relative", "")).lower()))
    elif sort == "status":
        selected.sort(key=lambda row: (STATUS_KEYS.index(row.get("status")) if row.get("status") in STATUS_KEYS else 999, str(row.get("title", "")).lower()))
    else:
        selected.sort(key=lambda row: str(row.get("updated_at", "")), reverse=True)
    return selected


# --- not yet imported --------------------------------------------------------------


def _path_keys(path: Path) -> set[str]:
    keys = {str(path.expanduser())}
    try:
        keys.add(str(path.expanduser().resolve(strict=False)))
    except (OSError, RuntimeError):
        pass
    return keys


def _pdf_job_states(domain: str) -> dict[str, tuple[str, str]]:
    from .services import pdf_batch_db_path

    states: dict[str, tuple[str, str]] = {}
    try:
        path = Path(pdf_batch_db_path())
        if not path.is_file():
            return states
        # Reading the browser must not create a queue or run schema migrations.
        with closing(sqlite3.connect(path.absolute().as_uri() + "?mode=ro", uri=True)) as connection:
            jobs = connection.execute(
                "SELECT pdf_path, status, error_message FROM pdf_import_jobs "
                "WHERE domain = ? ORDER BY created_at DESC",
                (domain,),
            ).fetchall()
    except (OSError, sqlite3.Error):  # An unavailable queue must not break file discovery.
        return states
    # Keep the newest state per file, matching the job queue's list ordering.
    for pdf_path, status, error in jobs:
        for key in _path_keys(Path(pdf_path)):
            states.setdefault(key, (status, error or ""))
    return states


def discover_domain_files(domain: str, folders: dict[str, Path] | None = None) -> list[dict[str, Any]]:
    """Read-only inventory: classify filenames, without importing or reading their contents."""
    folders = folders or domain_folders(domain)
    job_states = _pdf_job_states(domain)
    discovered = []
    seen: set[str] = set()
    # Prefer the dedicated Jira workflow if a mixed folder also links to Jira files.
    for key in ("jira", *FOLDER_KEYS):
        if key not in folders:
            continue
        root = folders[key]
        for file_kind, paths in discover_mixed_files(root).items():
            for path in paths:
                keys = _path_keys(path)
                if keys & seen:
                    continue
                seen |= keys
                job_status, error = next(
                    (job_states[k] for k in sorted(keys) if k in job_states), ("", "")
                ) if file_kind == PDF_KIND else ("", "")
                jira = key == "jira" and path.suffix.lower() == ".csv"
                supported = file_kind != UNSUPPORTED_KIND and (key != "jira" or jira)
                try:
                    updated_at = datetime.fromtimestamp(path.stat().st_mtime).isoformat()
                except OSError:
                    updated_at = ""
                discovered.append({
                    "folder": key,
                    "relative": _relative_to(path, root),
                    "name": path.name,
                    "kind": file_kind,
                    "icon": _FILE_KIND_ICON.get(file_kind, "📦"),
                    "status": (
                        {"pending": "queued", "processing": "queued", "failed": "failed"}.get(job_status, "new")
                        if supported else "unsupported"
                    ),
                    "job_status": job_status,
                    "error": error,
                    "workflow": "jira" if jira else "",
                    "can_import": supported and not jira and job_status not in {"pending", "processing"},
                    "linked": root.is_symlink() or path.is_symlink(),
                    "updated_at": _short_timestamp(updated_at),
                    "path_keys": keys,
                })
    return discovered


def source_inventory(
    domain: str,
    sources: Iterable[Any],
    stats: dict[str, dict[str, Any]],
    folders: dict[str, Path] | None = None,
) -> dict[str, Any]:
    """Merge registered sources and one filesystem scan, retaining store IDs and counts."""
    folders = folders or domain_folders(domain)
    sources = list(sources)
    discovered = discover_domain_files(domain, folders)
    imported = set().union(*(_path_keys(Path(str(source.location))) for source in sources if source.location))
    rows = source_rows(domain, sources, stats, folders)
    for item in discovered:
        if item["path_keys"] & imported:
            continue
        kind = source_kind("owl" if item["kind"] == ONTOLOGY_KIND else item["kind"])
        rows.append({
            **{key: value for key, value in item.items() if key not in {"path_keys", "job_status", "name"}},
            "source_id": "",
            "source_type": item["kind"],
            "title": item["name"],
            "imported": False,
            "kind": kind.key,
            "kind_label": kind.label,
            "records": 0,
            "artifacts": 0,
            "missing": False,
            "can_reimport": False,
            "image_processing": "ocr",
        })
    return {"rows": rows, "pending": unimported_files(domain, sources, folders, discovered=discovered)}


def unimported_files(
    domain: str,
    sources: Iterable[Any],
    folders: dict[str, Path] | None = None,
    *,
    discovered: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Files in md/, pdf/, owl/ and mix/ without a matching source in the store."""
    folders = folders or domain_folders(domain)
    imported: set[str] = set()
    for source in sources:
        if source.location:
            imported |= _path_keys(Path(str(source.location)))
    if discovered is None:
        discovered = discover_domain_files(domain, folders)
    groups = []
    total = 0
    for key, _source_type, kinds in _FOLDERS:
        files = []
        for item in discovered:
            if item["folder"] != key or item["kind"] not in kinds:
                continue
            if item["path_keys"] & imported or item["job_status"] == "done":
                continue
            files.append({field: item[field] for field in ("folder", "relative", "name", "kind", "icon", "status", "error")})
        files.sort(key=lambda item: item["relative"].lower())
        total += len(files)
        if files:
            groups.append({"key": key, "files": files, "new": sum(1 for f in files if f["status"] == "new")})
    return {
        "folders": groups,
        "total": total,
        "new": sum(folder["new"] for folder in groups),
    }


def _relative_to(path: Path, root: Path) -> str:
    for base in (root, root.resolve(strict=False)):
        for candidate in (path, path.resolve(strict=False)):
            try:
                return candidate.relative_to(base).as_posix()
            except ValueError:
                continue
    return path.name


def resolve_folder_file(domain: str, folder: str, relative: str) -> Path | None:
    """Map (folder key, relative path) back to a file inside that folder; None if invalid."""
    source_type = next((source_type for key, source_type, _kinds in _FOLDERS if key == folder), None)
    if source_type is None or not relative:
        return None
    rel = PurePosixPath(relative)
    if rel.is_absolute() or any(part in {"", ".", ".."} for part in rel.parts):
        return None
    root = domain_source_dir(source_type, domain)
    candidate = root.joinpath(*rel.parts)
    if not candidate.is_file():
        return None
    # Symlinks inside the folder are allowed (that's how mix/ works), but the
    # joined path must stay lexically inside the folder.
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


# --- actions -----------------------------------------------------------------------


def _queue_pdf(path: Path, domain: str) -> str:
    from .services import create_pdf_import_job

    return create_pdf_import_job(str(path), domain=domain)


def import_folder_file(
    domain: str,
    folder: str,
    relative: str,
    image_processing: str = "ocr",
) -> dict[str, Any]:
    from .source_workflow import import_markdown_file, import_mixed_file

    path = resolve_folder_file(domain, folder, relative)
    if path is None:
        return {"ok": False, "message": f"Datei nicht gefunden: {folder}/{relative}"}
    kind = classify_file(path)
    if kind == UNSUPPORTED_KIND:
        return {"ok": False, "message": f"{path.name}: Format nicht unterstützt"}
    try:
        if kind == PDF_KIND:
            _queue_pdf(path, domain)
            result = {"ok": True, "message": f"{path.name}: PDF-Job eingereiht"}
        elif kind == MARKDOWN_KIND and folder == "md":
            imported = import_markdown_file(path, source_name=relative)
            result = {"ok": True, "message": f"{path.name}: {imported['imported']} Blöcke"}
        else:
            imported = import_mixed_file(path, domain=domain, image_processing=image_processing)
            if imported.get("error"):
                result = {"ok": False, "message": f"{path.name}: {imported['error']}"}
            else:
                message = f"{path.name}: {imported.get('imported', 0)} Wissensobjekte"
                if imported.get("warnings"):
                    message += f" ({'; '.join(imported['warnings'])})"
                result = {"ok": True, "message": message}
    except (OSError, ValueError) as exc:
        result = {"ok": False, "message": f"{path.name}: {exc}"}
    invalidate_domain_summary_cache(domain)
    return result


def import_all_unimported(
    domain: str,
    sources: Iterable[Any],
    folder: str = "",
    image_processing: str = "ocr",
) -> list[dict[str, Any]]:
    pending = unimported_files(domain, sources)
    results = []
    for group in pending["folders"]:
        if folder and group["key"] != folder:
            continue
        for item in group["files"]:
            if item["status"] == "new":
                results.append(
                    import_folder_file(domain, item["folder"], item["relative"], image_processing=image_processing)
                )
    return results


def can_reimport(source: Any) -> bool:
    location = str(getattr(source, "location", "") or "")
    if source.source_type == "owl" and location.startswith(("http://", "https://")):
        return True
    return source.source_type in {"markdown", "pdf", "owl", TABLE_KIND, IMAGE_KIND} and Path(location).expanduser().is_file()


def reimport_source(
    domain: str,
    source: Any,
    image_processing: str | None = None,
) -> dict[str, Any]:
    from .source_workflow import import_markdown_file, import_mixed_file, import_ontology_file, import_ontology_url

    if not can_reimport(source):
        return {"ok": False, "message": f"{source.title}: Datei fehlt oder Typ nicht unterstützt"}
    location = str(source.location)
    try:
        if source.source_type == "pdf":
            from .services import create_pdf_import_job

            create_pdf_import_job(location, domain=domain, force=True)
            return {"ok": True, "message": f"{source.title}: PDF-Job eingereiht"}
        if source.source_type == "markdown":
            result = import_markdown_file(Path(location), source_name=source.title)
        elif source.source_type == "owl":
            result = import_ontology_url(location) if location.startswith(("http://", "https://")) else import_ontology_file(Path(location))
        else:
            selected_image_processing = image_processing or str(source.metadata.get("image_processing", "ocr"))
            result = import_mixed_file(
                Path(location),
                domain=domain,
                image_processing=selected_image_processing,
            )
    except (OSError, ValueError) as exc:
        return {"ok": False, "message": f"{source.title}: {exc}"}
    finally:
        invalidate_domain_summary_cache(domain)
    if result.get("error"):
        return {"ok": False, "message": f"{source.title}: {result['error']}"}
    message = f"{source.title}: {result.get('imported', 0)} Wissensobjekte neu importiert"
    if result.get("warnings"):
        message += f" ({'; '.join(result['warnings'])})"
    return {"ok": True, "message": message}


def delete_source(domain: str, store_obj: Any, source: Any) -> dict[str, Any]:
    removed = store_obj.delete_source(source.source_id)
    invalidate_domain_summary_cache(domain)
    return {
        "ok": bool(removed["sources"]),
        "message": f"{source.title}: aus dem Store entfernt ({removed['records']} Einträge, {removed['artifacts']} Artefakte). Die Datei bleibt erhalten.",
    }


__all__ = [
    "FOLDER_KEYS",
    "KIND_KEYS",
    "PAGE_SIZE",
    "SORT_KEYS",
    "STATUS_KEYS",
    "SOURCE_KINDS",
    "can_reimport",
    "delete_source",
    "discover_domain_files",
    "domain_folders",
    "filter_rows",
    "folder_counts",
    "import_all_unimported",
    "import_folder_file",
    "kind_counts",
    "status_counts",
    "reimport_source",
    "resolve_folder_file",
    "source_kind",
    "source_inventory",
    "source_rows",
    "unimported_files",
]
