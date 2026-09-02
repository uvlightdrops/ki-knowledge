"""Workspace helpers for the Streamlit knowledge explorer."""

from __future__ import annotations

import hashlib
import json
import difflib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ki_knowledge.ui.knowledge_api_client import discover_markdown_files


@dataclass
class MarkdownTreeNode:
    """A directory node with nested files and child directories."""

    path: Path
    children: dict[str, "MarkdownTreeNode"] = field(default_factory=dict)
    files: list[Path] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.path.name or self.path.as_posix()

    def iter_children(self) -> list["MarkdownTreeNode"]:
        return [self.children[key] for key in sorted(self.children)]

    def iter_files(self) -> list[Path]:
        """Return all markdown files below this directory node."""
        collected: list[Path] = list(self.files)
        for child in self.iter_children():
            collected.extend(child.iter_files())
        return collected


@dataclass
class WorkspaceState:
    """Persistent UI state for recents, favorites, and version snapshots."""

    recent_files: list[str] = field(default_factory=list)
    favorite_files: list[str] = field(default_factory=list)
    snapshots: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


def workspace_state_path(markdown_directory: str | Path) -> Path:
    """Return the JSON file used to persist UI state."""
    return Path(markdown_directory).expanduser() / ".kicli_workspace.json"


def load_workspace_state(markdown_directory: str | Path) -> WorkspaceState:
    """Load persisted UI state if present."""
    path = workspace_state_path(markdown_directory)
    if not path.exists():
        return WorkspaceState()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return WorkspaceState()
    return WorkspaceState(
        recent_files=list(payload.get("recent_files", [])),
        favorite_files=list(payload.get("favorite_files", [])),
        snapshots={key: list(value) for key, value in (payload.get("snapshots", {}) or {}).items()},
    )


def save_workspace_state(markdown_directory: str | Path, state: WorkspaceState) -> None:
    """Persist UI state to disk."""
    path = workspace_state_path(markdown_directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8")


def mark_recent_file(state: WorkspaceState, file_path: str, *, limit: int = 12) -> None:
    """Move a file to the top of the recent list."""
    normalized = str(Path(file_path).expanduser())
    state.recent_files = [normalized, *[item for item in state.recent_files if item != normalized]][:limit]


def set_favorite_file(state: WorkspaceState, file_path: str, favorite: bool) -> None:
    """Add or remove a file from favorites."""
    normalized = str(Path(file_path).expanduser())
    favorites = [item for item in state.favorite_files if item != normalized]
    if favorite:
        favorites.insert(0, normalized)
    state.favorite_files = favorites


def is_favorite_file(state: WorkspaceState, file_path: str) -> bool:
    """Return whether a file is marked as favorite."""
    normalized = str(Path(file_path).expanduser())
    return normalized in state.favorite_files


def add_snapshot(
    state: WorkspaceState,
    file_path: str,
    content: str,
    *,
    label: str,
    max_versions: int = 8,
) -> None:
    """Store a content snapshot if it differs from the latest entry."""
    normalized = str(Path(file_path).expanduser())
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "label": label,
        "digest": digest,
        "content": content,
    }
    snapshots = state.snapshots.setdefault(normalized, [])
    if snapshots and snapshots[0].get("digest") == digest:
        snapshots[0] = entry
    else:
        snapshots.insert(0, entry)
    del snapshots[max_versions:]


def snapshots_for_file(state: WorkspaceState, file_path: str) -> list[dict[str, Any]]:
    """Return the stored versions for one file."""
    normalized = str(Path(file_path).expanduser())
    return list(state.snapshots.get(normalized, []))


def file_digest(content: str) -> str:
    """Return a stable digest for markdown content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def restore_snapshot(state: WorkspaceState, file_path: str, index: int = 0) -> str | None:
    """Return a stored snapshot content so callers can write it back."""
    normalized = str(Path(file_path).expanduser())
    snapshots = state.snapshots.get(normalized, [])
    if index < 0 or index >= len(snapshots):
        return None
    return snapshots[index].get("content", "")


def diff_snapshot(state: WorkspaceState, file_path: str, index: int = 0, *, current_content: str) -> str:
    """Return a unified diff between a snapshot and the current content."""
    normalized = str(Path(file_path).expanduser())
    snapshots = state.snapshots.get(normalized, [])
    if index < 0 or index >= len(snapshots):
        return ""
    previous = snapshots[index].get("content", "").splitlines(keepends=True)
    current = current_content.splitlines(keepends=True)
    return "".join(difflib.unified_diff(previous, current, fromfile="snapshot", tofile="current"))


def build_markdown_tree(markdown_directory: str | Path, *, query: str = "") -> MarkdownTreeNode | None:
    """Build a directory tree from markdown files for sidebar browsing."""
    root = Path(markdown_directory).expanduser()
    if not root.exists():
        return None

    files = discover_markdown_files(root)
    normalized_query = query.strip().lower()
    if normalized_query:
        files = [
            path
            for path in files
            if normalized_query in path.name.lower() or normalized_query in path.as_posix().lower()
        ]
    if not files:
        return MarkdownTreeNode(path=root)

    root_node = MarkdownTreeNode(path=root)
    for file_path in files:
        relative = file_path.relative_to(root)
        node = root_node
        current_path = root
        for part in relative.parts[:-1]:
            current_path = current_path / part
            node = node.children.setdefault(part, MarkdownTreeNode(path=current_path))
        node.files.append(file_path)

    def _sort_node(node: MarkdownTreeNode) -> None:
        node.files.sort(key=lambda path: path.name.lower())
        for child in node.children.values():
            _sort_node(child)

    _sort_node(root_node)
    return root_node
