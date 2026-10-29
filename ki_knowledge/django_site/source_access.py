"""Workbench document access through the existing Data Sources inventory.

Selection IDs are deterministic opaque references, not encoded client paths or
a second registry. Every resolution rechecks the current domain inventory.
"""

import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode

from django.urls import reverse
from django.utils.crypto import salted_hmac


def selection_id(domain, row):
    reference = (
        ["registered", str(row["source_id"])] if row.get("source_id")
        else ["discovered", row.get("folder", ""), row.get("relative", "")]
    )
    payload = json.dumps([domain, reference], ensure_ascii=True, separators=(",", ":"))
    return "src_" + salted_hmac("workbench-source-selection-v1", payload, algorithm="sha256").hexdigest()


def controlled_location(domain, row):
    from .sources_browser import resolve_folder_file

    if row.get("kind") != "markdown":
        raise ValueError("Nur lokale Markdown-Dateien sind als Textsnapshot erfassbar.")
    if not row.get("folder"):
        raise ValueError("Keine Datei in einem konfigurierten Domain-Quellordner; entfernte Quellen werden nicht heruntergeladen.")
    candidate = resolve_folder_file(domain, row["folder"], row["relative"])
    if candidate is None:
        raise ValueError("Datei fehlt, Pfad ist ungültig oder Linkziel liegt außerhalb der vertrauenswürdigen Quellordner.")
    if candidate.suffix.lower() not in {".md", ".markdown"}:
        raise ValueError("Die Quelldatei hat keine unterstützte Markdown-Endung.")
    return candidate


def decorate_rows(domain, rows):
    """Keep every inventory row, with an explicit reason when capture is excluded."""
    for row in rows:
        row["selection_id"] = selection_id(domain, row)
        row["capture_exclusion"] = ""
        row["workbench_url"] = ""
        try:
            controlled_location(domain, row)
        except (OSError, ValueError, RuntimeError) as error:
            row["capture_exclusion"] = str(error)
        else:
            row["workbench_url"] = reverse("workbench") + "?" + urlencode({
                "domain": domain, "source_id": row["selection_id"],
            })
    return rows


def inventory(domain):
    from .knowledge_summary import _domain_scoped_sources
    from .sources_browser import source_inventory

    # Counts are immaterial to document selection; do not run the expensive
    # record/artifact aggregation or import anything just to open the editor.
    result = source_inventory(domain, _domain_scoped_sources(domain), {})
    return decorate_rows(domain, result["rows"])


def candidate_json(row):
    return {
        "id": row["selection_id"], "title": row["title"],
        "folder": row.get("folder", ""), "relative": row.get("relative", ""),
        "registered": bool(row.get("imported")),
        "source_id": row.get("source_id", ""),
    }


def capture_inventory(domain):
    available, excluded = [], []
    seen = {}
    for row in inventory(domain):
        item = candidate_json(row)
        if row["capture_exclusion"]:
            excluded.append({**item, "reason": row["capture_exclusion"]})
            continue
        try:
            path = controlled_location(domain, row).resolve(strict=True)
        except (OSError, ValueError, RuntimeError) as error:
            excluded.append({**item, "reason": str(error)})
            continue
        if path in seen:
            excluded.append({
                **item, "reason": "Dieselbe Datei ist bereits als andere Quelle auswählbar.",
                "canonical_id": seen[path],
            })
            continue
        seen[path] = item["id"]
        available.append(item)
    return {"sources": available, "excluded": excluded}


def resolve_selection(domain, identifier):
    for row in inventory(domain):
        if row["selection_id"] == identifier:
            path = controlled_location(domain, row)
            return row, path
    raise LookupError("Quelle ist nicht im aktuellen Domain-Inventar vorhanden.")


def snapshot_location(domain, row):
    from .sources_browser import domain_folders, linked_subdirectories

    path = controlled_location(domain, row).resolve(strict=True)
    roots = []
    for folder in domain_folders(domain).values():
        roots.append(folder.expanduser().resolve(strict=False))
        roots.extend(target for _link, target in linked_subdirectories(folder))
    for root in sorted(set(roots), key=lambda item: len(item.parts), reverse=True):
        if path.is_relative_to(root):
            return root, path.relative_to(root)
    raise ValueError("Quelle liegt außerhalb der vertrauenswürdigen Domain-Quellordner.")


def legacy_location(domain, locator):
    """Map a server-side legacy FK locator through the same controlled folders."""
    from .sources_browser import _folder_roots, _origin, domain_folders

    raw = Path(locator).expanduser()
    if ".." in raw.parts:
        raise ValueError("Traversal is not allowed.")
    folders = domain_folders(domain)
    if not raw.is_absolute():
        raw = folders["md"] / raw
    folder, relative, _linked = _origin(str(raw), _folder_roots(folders))
    return snapshot_location(domain, {"kind": "markdown", "folder": folder, "relative": relative})


def origin_metadata(row):
    return {
        "kind": "registered" if row.get("source_id") else "discovered",
        "source_id": row.get("source_id", ""),
        "folder": row.get("folder", ""), "relative": row.get("relative", ""),
    }


def identity_key(path):
    return hashlib.sha256(str(Path(path).resolve(strict=True)).encode("utf-8")).hexdigest()
