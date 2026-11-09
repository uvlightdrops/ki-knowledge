"""File-backed local workspace for small, manually authored blocks."""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Iterator
from uuid import uuid4

import yaml

from ki_knowledge.wiki_relations import RELATION_TYPES


class WorkspaceError(ValueError):
    """A workspace operation could not be completed."""


class WorkspaceConflict(WorkspaceError):
    """The document has changed since it was opened."""


def _identifier(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{32}", value):
        raise WorkspaceError("Ungültige Block-ID.")
    return value


class Workspace:
    """Store each block as a Markdown file with YAML metadata."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        if not self.root.is_dir():
            raise WorkspaceError("Arbeitsverzeichnis existiert nicht.")

    @contextmanager
    def _locked(self) -> Iterator[None]:
        lock_path = self.root / ".wissenswiki.lock"
        flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(lock_path, flags, 0o600)
            with os.fdopen(fd, "r+") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                yield
        except OSError as exc:
            raise WorkspaceError(f"Arbeitsverzeichnis nicht zugänglich: {exc}") from exc

    def _path(self, block_id: object) -> Path:
        path = self.root / f"{_identifier(block_id)}.md"
        if path.is_symlink() or path.resolve().parent != self.root:
            raise WorkspaceError("Symbolische Links sind für Blöcke nicht erlaubt.")
        return path

    def _read(self, block_id: object) -> dict:
        path = self._path(block_id)
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            raise WorkspaceError(f"Block {block_id} kann nicht gelesen werden: {exc}") from exc
        if not text.startswith("---\n") or "\n---\n" not in text:
            raise WorkspaceError(f"Block {block_id}: YAML-Header fehlt.")
        header, body = text[4:].split("\n---\n", 1)
        try:
            metadata = yaml.safe_load(header)
        except yaml.YAMLError as exc:
            raise WorkspaceError(f"Block {block_id}: YAML-Header ungültig: {exc}") from exc
        if not isinstance(metadata, dict) or metadata.get("id") != block_id:
            raise WorkspaceError(f"Block {block_id}: ID im YAML-Header stimmt nicht.")
        if not isinstance(metadata.get("title"), str) or not isinstance(metadata.get("relations"), list) or not isinstance(metadata.get("parts"), list):
            raise WorkspaceError(f"Block {block_id}: title, relations oder parts ungültig.")
        for relation in metadata["relations"]:
            if not isinstance(relation, dict) or not isinstance(relation.get("type"), str):
                raise WorkspaceError(f"Block {block_id}: Relation ungültig.")
            _identifier(relation.get("target"))
        for part in metadata["parts"]:
            _identifier(part)
        return {"id": block_id, "title": metadata["title"], "text": body,
                "relations": metadata["relations"], "parts": metadata["parts"],
                "revision": hashlib.sha256(raw).hexdigest(), "_metadata": metadata}

    def _write(self, block: dict) -> dict:
        path = self._path(block["id"])
        metadata = dict(block["_metadata"])
        metadata.update(title=block["title"], relations=block["relations"], parts=block["parts"])
        data = "---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + "---\n" + block["text"]
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.root, delete=False) as file:
                tmp = Path(file.name)
                file.write(data)
                file.flush()
                os.fsync(file.fileno())
            os.replace(tmp, path)
        finally:
            if tmp is not None and tmp.exists():
                tmp.unlink()
        return self._public(self._read(block["id"]))

    @staticmethod
    def _public(block: dict) -> dict:
        result = {key: value for key, value in block.items() if key != "_metadata"}
        result["attributes"] = {"art": "Wiki-Block", "metadaten": json.loads(
            json.dumps(block["_metadata"], ensure_ascii=False, default=str))}
        return result

    def list_blocks(self) -> list[dict]:
        with self._locked():
            paths = sorted(self.root.glob("*.md"))
            return [self._public(self._read(path.stem)) for path in paths
                    if re.fullmatch(r"[a-f0-9]{32}", path.stem)]

    def create(self, title: object, text: object) -> dict:
        self._validate_text(title, text)
        with self._locked():
            block_id = uuid4().hex
            block = {"id": block_id, "title": title, "text": text, "relations": [], "parts": [],
                     "_metadata": {"id": block_id, "title": title, "formulation_origin": "human",
                                   "relations": [], "parts": []}}
            return self._write(block)

    @staticmethod
    def _validate_text(title: object, text: object) -> None:
        if not isinstance(title, str) or not isinstance(text, str) or not (title.strip() or text.strip()):
            raise WorkspaceError("Bitte einen Titel oder Text eingeben.")

    def update(self, block_id: object, revision: object, action: str, payload: dict) -> dict:
        with self._locked():
            block = self._read(block_id)
            if not isinstance(revision, str) or revision != block["revision"]:
                raise WorkspaceConflict("Der Block wurde zwischenzeitlich geändert. Bitte neu laden.")
            if action == "save":
                title, text = payload.get("title"), payload.get("text")
                self._validate_text(title, text)
                block.update(title=title, text=text)
            elif action in {"relate", "graph-relate"}:
                target = _identifier(payload.get("target"))
                relation_type = payload.get("type")
                if target == block_id or not isinstance(relation_type, str) or not relation_type.strip():
                    raise WorkspaceError("Bitte zwei verschiedene Blöcke und einen Beziehungstyp wählen.")
                if action == "graph-relate" and relation_type not in dict(RELATION_TYPES):
                    raise WorkspaceError("Unbekannter Beziehungstyp für die Netzansicht.")
                self._read(target)
                relation = {"target": target, "type": relation_type.strip()}
                if relation in block["relations"]:
                    raise WorkspaceError("Diese Beziehung besteht bereits.")
                block["relations"].append(relation)
            elif action == "unrelate":
                index = payload.get("index")
                if type(index) is not int or not 0 <= index < len(block["relations"]):
                    raise WorkspaceError("Beziehung nicht gefunden.")
                block["relations"].pop(index)
            elif action == "parts":
                parts = payload.get("parts")
                if not isinstance(parts, list):
                    raise WorkspaceError("Bestandteile müssen eine Liste sein.")
                for part in parts:
                    _identifier(part)
                    if part == block_id:
                        raise WorkspaceError("Ein Block kann nicht sein eigener Bestandteil sein.")
                    self._read(part)
                block["parts"] = parts
            else:
                raise WorkspaceError("Unbekannte Aktion.")
            return self._write(block)
