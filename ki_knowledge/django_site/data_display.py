"""Display-only path labels and artifact previews."""

from __future__ import annotations

from pathlib import Path
import json

from ki_knowledge.data_layout import DataLayout
from ki_knowledge.services.domain_paths import data_root


def display_data_path(value: str | Path | None) -> str:
    if value is None:
        return "-"
    raw = str(value).strip()
    if not raw:
        return "-"
    path = Path(raw).expanduser()
    root = data_root().expanduser()
    layout = DataLayout(root)
    home = Path.home().expanduser()

    # Try first without following symlinks: if a domain directory (e.g. md/anthro)
    # is itself a symlink into some other location, we still want to display it
    # by its location under data_root rather than leaking the symlink target.
    try:
        absolute = path if path.is_absolute() else (root / path)
        relative = absolute.relative_to(root)
        if not relative.parts:
            return "."
        relative = layout.display_relative(relative)
        return "." if not relative.parts else relative.as_posix()
    except (OSError, RuntimeError, ValueError):
        pass

    try:
        resolved = path.resolve(strict=False)
    except (OSError, RuntimeError):
        resolved = path

    try:
        relative = resolved.relative_to(root.resolve())
        if not relative.parts:
            return "."
        relative = layout.display_relative(relative)
        return "." if not relative.parts else relative.as_posix()
    except (OSError, RuntimeError, ValueError):
        pass

    try:
        relative = resolved.relative_to(home.resolve())
        if not relative.parts:
            return "."
        return relative.as_posix()
    except (OSError, RuntimeError, ValueError):
        pass

    normalized = resolved.as_posix().replace("\\", "/")
    if normalized.startswith("/"):
        normalized = normalized.lstrip("/")
    return normalized or "."


def display_source_ref(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return "-"
    if ":" not in text:
        return display_data_path(text)
    prefix, remainder = text.split(":", 1)
    remainder = remainder.strip()
    if not remainder:
        return f"{prefix}:"
    return f"{prefix}:{display_data_path(remainder)}"


def artifact_content_preview(artifact_type: str, content: str, *, limit: int = 240) -> str:
    text = (content or "").strip()
    if not text:
        return ""
    if artifact_type == "summary_note":
        try:
            payload = json.loads(text)
        except ValueError:
            payload = {}
        sections = payload.get("sections") if isinstance(payload, dict) else []
        if isinstance(sections, list) and sections:
            first = sections[0] if isinstance(sections[0], dict) else {}
            title = str(first.get("title", "")).strip()
            summary = str(first.get("summary", "")).strip()
            snippet = f"{title}: {summary}" if title else summary
            if snippet:
                return snippet[:limit]
        if isinstance(payload, dict):
            raw = payload.get("title") or payload.get("content") or ""
            if raw:
                return str(raw)[:limit]
    normalized = " ".join(text.split())
    return normalized[:limit]
