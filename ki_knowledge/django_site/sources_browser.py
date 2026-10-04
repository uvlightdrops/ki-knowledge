"""Data for the sources browser (/data-sources/sources/).

Lists the knowledge-store sources of a domain with origin folder and counts,
finds files in the domain's source folders that are not imported yet, and runs
per-source / per-file actions. Client input is only ever a source id or a
folder key plus a path relative to that folder; absolute paths are resolved
on the server.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
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

from .domain_paths import domain_jira_dir, domain_source_dir, invalidate_domain_summary_cache


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

# Folders that are scanned for not-yet-imported files, with the file kinds they may contain.
_FOLDERS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("md", MARKDOWN, (MARKDOWN_KIND,)),
    ("pdf", PDF, (PDF_KIND,)),
    ("owl", ONTOLOGY, (ONTOLOGY_KIND,)),
    ("mix", MIX, (PDF_KIND, MARKDOWN_KIND, ONTOLOGY_KIND, TABLE_KIND, IMAGE_KIND)),
)
FOLDER_KEYS = tuple(key for key, _type, _kinds in _FOLDERS)
_FILE_KIND_ICON = {PDF_KIND: "📄", MARKDOWN_KIND: "📝", ONTOLOGY_KIND: "🕸️", TABLE_KIND: "📊", IMAGE_KIND: "🖼️"}
SORT_KEYS = ("updated", "title", "records", "kind")
PAGE_SIZE = 100


def source_kind(source_type: str) -> SourceKind:
    return _KIND_BY_TYPE.get(source_type, _OTHER_KIND)


def domain_folders(domain: str) -> dict[str, Path]:
    """Source folders of the domain by key (resolved once; path lookups re-read the config)."""
    folders = {key: domain_source_dir(source_type, domain) for key, source_type, _kinds in _FOLDERS}
    folders["jira"] = domain_jira_dir(domain)
    return folders


def _folder_roots(folders: dict[str, Path]) -> list[tuple[str, Path, bool]]:
    """(folder key, root as configured or resolved, is symlink) for every source folder incl. jira."""
    roots: list[tuple[str, Path, bool]] = []
    for key, directory in folders.items():
        directory = directory.expanduser()
        linked = directory.is_symlink()
        for candidate in (directory, directory.resolve(strict=False)):
            if all(candidate != root for _key, root, _linked in roots):
                roots.append((key, candidate, linked))
    # Longest roots first so e.g. md/<wt> never shadows a more specific folder.
    return sorted(roots, key=lambda item: len(item[1].parts), reverse=True)


def _origin(location: str, roots: list[tuple[str, Path, bool]]) -> tuple[str, str, bool]:
    path = Path(location).expanduser()
    for key, root, linked in roots:
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        return key, relative.as_posix(), linked
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


def kind_counts(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["kind"]] = counts.get(row["kind"], 0) + 1
    chips = [{"key": "", "label": "Alle", "icon": "", "count": sum(counts.values())}]
    for kind in SOURCE_KINDS + (_OTHER_KIND,):
        if kind is _OTHER_KIND and not counts.get(kind.key):
            continue
        chips.append({"key": kind.key, "label": kind.label, "icon": kind.icon, "count": counts.get(kind.key, 0)})
    return chips


def filter_rows(rows: list[dict[str, Any]], *, kind: str = "", query: str = "", sort: str = "updated") -> list[dict[str, Any]]:
    needle = query.strip().lower()
    selected = [
        row
        for row in rows
        if (not kind or row["kind"] == kind)
        and (not needle or needle in row["title"].lower() or needle in row["relative"].lower())
    ]
    if sort == "title":
        selected.sort(key=lambda row: row["title"].lower())
    elif sort == "records":
        selected.sort(key=lambda row: (-row["records"], row["title"].lower()))
    elif sort == "kind":
        selected.sort(key=lambda row: (KIND_KEYS.index(row["kind"]), row["title"].lower()))
    else:
        selected.sort(key=lambda row: row["updated_at"], reverse=True)
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
    from .services import get_pdf_batch_processor

    states: dict[str, tuple[str, str]] = {}
    try:
        jobs = get_pdf_batch_processor().list_jobs(domain=domain)
    except Exception:  # job DB unavailable must not break the page
        return states
    # list_jobs is newest first; keep the newest state per file.
    for job in jobs:
        for key in _path_keys(Path(job.pdf_path)):
            states.setdefault(key, (job.status, job.error_message or ""))
    return states


def unimported_files(domain: str, sources: Iterable[Any], folders: dict[str, Path] | None = None) -> dict[str, Any]:
    """Files in md/, pdf/, owl/ and mix/ without a matching source in the store."""
    folders = folders or domain_folders(domain)
    imported: set[str] = set()
    for source in sources:
        if source.location:
            imported |= _path_keys(Path(str(source.location)))
    job_states = _pdf_job_states(domain)
    groups = []
    total = 0
    for key, _source_type, kinds in _FOLDERS:
        root = folders[key]
        grouped = discover_mixed_files(root)
        files = []
        for kind in kinds:
            for path in grouped[kind]:
                keys = _path_keys(path)
                if keys & imported:
                    continue
                status, error = next((job_states[k] for k in keys if k in job_states), ("", ""))
                if status == "done":
                    continue
                files.append(
                    {
                        "folder": key,
                        "relative": _relative_to(path, root),
                        "name": path.name,
                        "kind": kind,
                        "icon": _FILE_KIND_ICON.get(kind, "📄"),
                        "status": {"pending": "queued", "processing": "queued", "failed": "failed"}.get(status, "new"),
                        "error": error,
                    }
                )
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
    "SOURCE_KINDS",
    "can_reimport",
    "delete_source",
    "domain_folders",
    "filter_rows",
    "import_all_unimported",
    "import_folder_file",
    "kind_counts",
    "reimport_source",
    "resolve_folder_file",
    "source_kind",
    "source_rows",
    "unimported_files",
]
