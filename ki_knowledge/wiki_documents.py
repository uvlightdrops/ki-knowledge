"""Read documentation as graph nodes and keep extra relations separately."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
import tempfile
from urllib.parse import quote, unquote, urlsplit

from ki_knowledge.doc_viewer import DocumentError, list_documents, parse_document
from ki_knowledge.wiki_relations import RELATION_TYPES
from ki_knowledge.wiki_workspace import Workspace, WorkspaceConflict, WorkspaceError

_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


class DocumentDomain:
    def __init__(self, source: Path, relations: Path, *, lenient: bool = False) -> None:
        """``lenient`` reads files without front matter and derives IDs for untagged sections."""
        self.source = source.resolve()
        self.lenient = lenient
        if not self.source.is_dir():
            raise WorkspaceError(f"Quelldomäne existiert nicht: {self.source}")
        self.storage = Workspace(relations)
        if self.storage.root.is_relative_to(self.source) or self.source.is_relative_to(self.storage.root):
            raise WorkspaceError("Quellen und Beziehungsverzeichnis müssen getrennt sein.")

    def _node_id(self, path: Path, fragment: str = "") -> str:
        name = path.relative_to(self.source).as_posix()
        return "doc:" + quote(name, safe="/") + ("#" + quote(fragment, safe="") if fragment else "")

    def _target(self, source: Path, target: str) -> str:
        url = urlsplit(target)
        if url.scheme or url.netloc:
            return target
        path = (source.parent / unquote(url.path)).resolve() if url.path else source
        if not path.is_relative_to(self.source):
            return target
        return self._node_id(path, unquote(url.fragment))

    def _read_sources(self) -> tuple[list[dict], list[str]]:
        nodes, errors = [], []
        for path in list_documents(self.source):
            try:
                document = parse_document(path, require_header=not self.lenient)
            except DocumentError as exc:
                errors.append(str(exc))
                continue
            doc_id = self._node_id(path)
            relative = path.relative_to(self.source)
            metadata = json.loads(json.dumps(document.metadata, ensure_ascii=False, default=str))
            title = next((line[2:].strip() for line in document.intro.splitlines()
                          if line.startswith("# ")), relative.as_posix())
            doc = {"id": doc_id, "title": title, "text": document.intro, "relations": [],
                   "path": relative.as_posix(), "linkable": True,
                   "attributes": {"art": "Dokument", "datei": relative.as_posix(),
                                  "ordner": relative.parent.as_posix(), "dokument_metadaten": metadata}}
            nodes.append(doc)
            indexed = {}
            derived: set[str] = set()
            for index, block in enumerate(document.blocks):
                fragment = block.block_id or (self._derived_id(block.title, derived) if self.lenient else None)
                block_id = self._node_id(path, fragment) if fragment else f"{doc_id}#!unstable-{index}"
                if block_id in indexed:
                    errors.append(f"{path}: doppelte Block-ID {block.block_id}")
                    continue
                node = {"id": block_id, "title": block.title, "text": block.content, "relations": [],
                        "path": doc["path"], "linkable": bool(fragment),
                        "attributes": {"art": "Abschnitt", "block_id": block.block_id,
                                       "datei": doc["path"], "ordner": relative.parent.as_posix(),
                                       "dokument_metadaten": metadata}}
                indexed[block_id] = node
                nodes.append(node)
            for relation in document.metadata.get("relations", []):
                source_id = self._target(path, relation["source"]) if "source" in relation else doc_id
                source_node = doc if source_id == doc_id else indexed.get(source_id)
                if source_node is None:
                    errors.append(f"{path}: Ausgangsblock {relation['source']} nicht gefunden")
                    continue
                source_node["relations"].append({"target": self._target(path, relation["target"]),
                                                 "type": relation["type"]})
        return nodes, errors

    @staticmethod
    def _derived_id(title: str, taken: set[str]) -> str:
        """``auto-<slug>`` for an untagged section; stable only while its title stays."""
        slug = re.sub(r"[^a-z0-9]+", "-", title.casefold().translate(_UMLAUTS)).strip("-")[:40] or "abschnitt"
        candidate, number = f"auto-{slug}", 2
        while candidate in taken:
            candidate, number = f"auto-{slug}-{number}", number + 1
        taken.add(candidate)
        return candidate

    def _read_relations(self) -> tuple[list[dict], str]:
        path = self.storage.root / "dokument-beziehungen.json"
        if path.is_symlink():
            raise WorkspaceError("Beziehungsdatei darf kein symbolischer Link sein.")
        if not path.exists():
            return [], hashlib.sha256(b"").hexdigest()
        try:
            raw = path.read_bytes()
            result = json.loads(raw)
        except (OSError, UnicodeError, ValueError) as exc:
            raise WorkspaceError(f"Beziehungsdatei nicht lesbar: {exc}") from exc
        if not isinstance(result, list) or any(
            not isinstance(item, dict) or not all(isinstance(item.get(key), str) for key in ("source", "target", "type"))
            for item in result
        ):
            raise WorkspaceError("Beziehungsdatei hat ein ungültiges Format.")
        return result, hashlib.sha256(raw).hexdigest()

    def _snapshot(self) -> dict:
        nodes, errors = self._read_sources()
        relations, revision = self._read_relations()
        lookup = {item["id"]: item for item in nodes}
        for relation in relations:
            source = lookup.get(relation["source"])
            if source:
                source["relations"].append({"target": relation["target"], "type": relation["type"]})
            else:
                errors.append(f"Gespeicherte Beziehung: Ausgang nicht gefunden: {relation['source']}")
        return {"blocks": nodes, "errors": errors, "revision": revision}

    def snapshot(self) -> dict:
        with self.storage._locked():
            return self._snapshot()

    def relate(self, payload: dict) -> dict:
        with self.storage._locked():
            snapshot = self._snapshot()
            if payload.get("revision") != snapshot["revision"]:
                raise WorkspaceConflict("Beziehungen wurden geändert. Bitte neu laden.")
            source, target, kind = payload.get("id"), payload.get("target"), payload.get("type")
            lookup = {node["id"]: node for node in snapshot["blocks"]}
            if (not isinstance(source, str) or not isinstance(target, str)
                    or source not in lookup or target not in lookup or source == target
                    or not lookup[source]["linkable"] or not lookup[target]["linkable"]):
                raise WorkspaceError("Zwei verschiedene Dokumente oder Blöcke mit stabiler ID auswählen.")
            if not isinstance(kind, str) or kind not in dict(RELATION_TYPES):
                raise WorkspaceError("Unbekannter Beziehungstyp.")
            if {"target": target, "type": kind} in lookup[source]["relations"]:
                raise WorkspaceError("Diese Beziehung besteht bereits.")
            relations, _ = self._read_relations()
            relations.append({"source": source, "target": target, "type": kind})
            path = self.storage.root / "dokument-beziehungen.json"
            tmp = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.storage.root, delete=False) as file:
                    tmp = Path(file.name)
                    json.dump(relations, file, ensure_ascii=False, indent=2)
                    file.write("\n")
                    file.flush()
                    os.fsync(file.fileno())
                os.replace(tmp, path)
            finally:
                if tmp is not None and tmp.exists():
                    tmp.unlink()
            return self._snapshot()
