"""Local, read-only browser for Markdown documentation and block relations."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
from string import Template
from urllib.parse import parse_qs, quote, unquote, urlsplit

import markdown
import yaml

from ki_knowledge.wiki_assets import ASSETS, asset_text, valid_host


@dataclass(frozen=True)
class Block:
    title: str
    block_id: str | None
    content: str


@dataclass(frozen=True)
class Document:
    path: Path
    metadata: dict
    intro: str
    blocks: tuple[Block, ...]


class DocumentError(ValueError):
    """A document or its metadata cannot be read."""


def parse_document(path: Path, *, require_header: bool = True) -> Document:
    """Read YAML metadata and H2 sections without treating code as headings.

    Without ``require_header`` a file lacking front matter is read with empty metadata.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise DocumentError(f"{path}: Datei nicht lesbar: {exc}") from exc
    if not require_header and not text.startswith("---\n"):
        intro, blocks = split_blocks(text)
        return Document(path, {}, intro, tuple(blocks))
    if not text.startswith("---\n") or "\n---\n" not in text:
        raise DocumentError(f"{path}: YAML-Header fehlt oder ist nicht abgeschlossen")
    front, body = text[4:].split("\n---\n", 1)
    try:
        metadata = yaml.safe_load(front)
    except yaml.YAMLError as exc:
        raise DocumentError(f"{path}: YAML-Header ungültig: {exc}") from exc
    if not isinstance(metadata, dict):
        raise DocumentError(f"{path}: YAML-Header muss ein Objekt sein")
    relations = metadata.get("relations", [])
    if not isinstance(relations, list):
        raise DocumentError(f"{path}: relations muss eine Liste sein")
    for relation in relations:
        if not isinstance(relation, dict) or not all(
            isinstance(relation.get(key), str) and relation[key] for key in ("target", "type")
        ):
            raise DocumentError(f"{path}: Relation benötigt target und type als Text")
        if "source" in relation and not isinstance(relation["source"], str):
            raise DocumentError(f"{path}: source einer Relation muss Text sein")
    intro, blocks = split_blocks(body)
    return Document(path, metadata, intro, tuple(blocks))


def split_blocks(body: str) -> tuple[str, list[Block]]:
    """Split H2 sections while preserving fenced code and untagged sections."""
    sections: list[tuple[str | None, list[str]]] = [(None, [])]
    fence: str | None = None
    for line in body.splitlines():
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
        if fence is None and line.startswith("## "):
            sections.append((line[3:].strip(), []))
        else:
            sections[-1][1].append(line)
    blocks = []
    for heading, lines in sections[1:]:
        match = re.search(r"\s+\[([a-z0-9-]+)\]$", heading or "")
        title = (heading[:match.start()] if match else heading) or ""
        blocks.append(Block(title, match.group(1) if match else None, "\n".join(lines)))
    return "\n".join(sections[0][1]), blocks


def resolve_path(root: Path, relative: str, *, base: Path | None = None) -> Path:
    """Resolve an in-root Markdown path, rejecting traversal and symlink escapes."""
    root = root.resolve()
    path = ((base or root) / relative).resolve()
    if not path.is_relative_to(root) or path.suffix.lower() != ".md" or not path.is_file():
        raise DocumentError(f"Dokument nicht verfügbar: {relative}")
    return path


def document_url(root: Path, path: Path, fragment: str = "") -> str:
    query = quote(path.relative_to(root).as_posix(), safe="/")
    return f"/?file={query}" + (f"#{quote(fragment)}" if fragment else "")


def relation_target(root: Path, document: Document, target: str) -> tuple[str, str | None]:
    """Resolve a relation target to its displayed title and optional viewer URL."""
    url = urlsplit(target)
    if url.scheme or url.netloc:
        return target, None
    try:
        path = resolve_path(root, unquote(url.path), base=document.path.parent) if url.path else document.path
        target_doc = document if path == document.path else parse_document(path)
    except DocumentError:
        return f"{target} (nicht verfügbar)", None
    if url.fragment:
        block = next((item for item in target_doc.blocks if item.block_id == unquote(url.fragment)), None)
        if block is None:
            return f"{target} (Block nicht gefunden)", None
        label = f"{block.title} ({path.relative_to(root)})"
    else:
        label = str(target_doc.metadata.get("title") or path.relative_to(root))
    return label, document_url(root, path, unquote(url.fragment))


class SafeHTML(HTMLParser):
    """Keep Markdown formatting while removing active markup and unsafe links."""

    tags = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "em", "strong", "code", "pre",
            "ul", "ol", "li", "blockquote", "table", "thead", "tbody", "tr", "th", "td",
            "hr", "br", "a", "del"}

    def __init__(self, root: Path, path: Path, block_ids: set[str]) -> None:
        super().__init__(convert_charrefs=True)
        self.root, self.path, self.block_ids, self.parts = root, path, block_ids, []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in self.tags:
            return
        if tag == "a":
            attributes = dict(attrs)
            anchor_id = attributes.get("id")
            anchor = (f' id="{escape(anchor_id, quote=True)}"'
                      if anchor_id and anchor_id not in self.block_ids else "")
            href = attributes.get("href")
            if href is None:
                self.parts.append(f"<a{anchor}>")
                return
            parsed = urlsplit(href)
            if parsed.scheme in {"http", "https"} and parsed.netloc:
                self.parts.append(f'<a{anchor} href="{escape(href, quote=True)}" rel="noreferrer">')
                return
            if not parsed.scheme and not parsed.netloc:
                try:
                    target = resolve_path(self.root, unquote(parsed.path), base=self.path.parent) if parsed.path else self.path
                    href = document_url(self.root, target, unquote(parsed.fragment))
                    self.parts.append(f'<a{anchor} href="{escape(href, quote=True)}">')
                    return
                except DocumentError:
                    pass
            self.parts.append(f"<a{anchor}>")
            return
        self.parts.append(f"<{tag}>")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.tags and tag not in {"hr", "br"}:
            self.parts.append(f"</{tag}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_data(self, data: str) -> None:
        self.parts.append(escape(data))


def render_markdown(root: Path, path: Path, text: str, block_ids: set[str]) -> str:
    """Render Markdown and limit output to safe tags and links."""
    rendered = markdown.markdown(text, extensions=["fenced_code", "tables"])
    parser = SafeHTML(root, path, block_ids)
    parser.feed(rendered)
    parser.close()
    return "".join(parser.parts)


def render_relations(root: Path, document: Document, source: str | None) -> str:
    rows = []
    for relation in document.metadata.get("relations", []):
        if relation.get("source") != source:
            continue
        label, href = relation_target(root, document, relation["target"])
        target = f'<a href="{escape(href, quote=True)}">{escape(label)}</a>' if href else escape(label)
        reason = escape(str(relation.get("reason", "")))
        rows.append(f'<li><strong>{escape(relation["type"])}</strong> → {target}'
                    f'{f"<div>{reason}</div>" if reason else ""}</li>')
    return '<h3>Beziehungen</h3><ul class="relations">' + "".join(rows) + "</ul>" if rows else ""


def format_metadata(value: object) -> str:
    if value is None:
        return "nicht angegeben"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def render_page(root: Path, document: Document, files: list[Path], *,
                django_url: str = "http://127.0.0.1:8000/", workspace_enabled: bool = False) -> str:
    """Render one document, its metadata and outgoing relations."""
    root = root.resolve()
    title = next((line[2:].strip() for line in document.intro.splitlines() if line.startswith("# ")),
                 document.path.relative_to(root).as_posix())
    navigation = "".join(
        f'<li><a href="{escape(document_url(root, path), quote=True)}">{escape(str(path.relative_to(root)))}</a></li>'
        for path in files
    )
    fields = ("project", "agent_project", "scope", "status", "created", "updated", "update_reason", "semantic_blocks")
    metadata = "".join(
        f"<dt>{escape(key)}</dt><dd>{escape(format_metadata(document.metadata[key]))}</dd>"
        for key in fields if key in document.metadata
    )
    sections = []
    block_ids = {block.block_id for block in document.blocks if block.block_id}
    known_sources = {"#" + block_id for block_id in block_ids}
    unknown_sources = sorted({relation["source"] for relation in document.metadata.get("relations", [])
                              if "source" in relation and relation["source"] not in known_sources})
    unresolved = "".join(
        f'<div><strong>Ausgangsblock nicht gefunden: {escape(source)}</strong>'
        f'{render_relations(root, document, source)}</div>' for source in unknown_sources
    )
    for block in document.blocks:
        anchor = f' id="{escape(block.block_id, quote=True)}"' if block.block_id else ""
        identifier = f'<span class="id">{escape(block.block_id)}</span>' if block.block_id else '<span class="id">ohne ID</span>'
        sections.append(f"<section{anchor}><h2>{escape(block.title)}</h2>{identifier}"
                        f"{render_markdown(root, document.path, block.content, block_ids)}"
                        f"{render_relations(root, document, '#' + block.block_id) if block.block_id else ''}</section>")
    intro = re.sub(r"(?m)^# .+\n?", "", document.intro, count=1)
    return Template(asset_text("viewer.html")).substitute(
        title=escape(title), navigation=navigation,
        django_url=escape(django_url, quote=True),
        workspace_link='<a href="/workspace/">Wissenswiki-Arbeitsraum</a>' if workspace_enabled else "",
        path=escape(str(document.path.relative_to(root))), metadata=metadata,
        document_relations=render_relations(root, document, None), unresolved=unresolved,
        intro=render_markdown(root, document.path, intro, block_ids), sections="".join(sections),
    )


def list_documents(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.md") if path.is_file() and path.resolve().is_relative_to(root))


def make_handler(root: Path, *, django_url: str | None = None,
                 workspace_enabled: bool = False) -> type[BaseHTTPRequestHandler]:
    root = root.resolve()

    class Handler(BaseHTTPRequestHandler):
        def django_link(self) -> str:
            host = urlsplit("http://" + self.headers["Host"]).hostname
            return django_url or f"http://{host}:8000/"

        def do_GET(self) -> None:
            parsed = urlsplit(self.path)
            if not valid_host(self):
                self.send_error(403, "Ungültiger Host")
                return
            if parsed.path in ASSETS:
                name, content_type = ASSETS[parsed.path]
                body = asset_text(name).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if parsed.path != "/":
                self.send_error(404)
                return
            files = list_documents(root)
            query = parse_qs(parsed.query)
            selected = query.get("file", [None])[0]
            try:
                if selected:
                    path = resolve_path(root, selected)
                elif files:
                    path = next((item for item in files if item.name == "KI-KNOWLEDGE-KONZEPT.md"), files[0])
                else:
                    raise DocumentError("Keine Markdown-Dokumente im ausgewählten Verzeichnis gefunden")
                body = render_page(root, parse_document(path), files, django_url=self.django_link(),
                                   workspace_enabled=workspace_enabled).encode("utf-8")
            except DocumentError as exc:
                self.send_error(400, explain=str(exc))
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'self'; base-uri 'none'")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Lokaler Markdown-Betrachter mit optionalem Arbeitsraum")
    parser.add_argument("directory", nargs="?", type=Path, default=Path("doc"))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="0.0.0.0", help="IPv4-Bindeadresse (Standard: alle Schnittstellen)")
    parser.add_argument("--workspace", type=Path, help="Separates bestehendes Verzeichnis für eigene Blöcke")
    parser.add_argument("--domain", action="append", nargs=3, metavar=("NAME", "QUELLE", "BEZIEHUNGEN"),
                        default=[], help="Benannte Dokumentdomäne mit separatem Beziehungsverzeichnis")
    parser.add_argument("--ki-domains", action="store_true",
                        help="Markdown-Domänen der Django-App lesend einbinden (temporäre Brücke)")
    parser.add_argument("--django-url", help="Abweichende URL der Django-App, z. B. http://192.168.1.2:8000/")
    args = parser.parse_args()
    root = args.directory.resolve()
    if not root.is_dir():
        parser.error(f"Dokumentationsverzeichnis existiert nicht: {root}")
    if args.django_url:
        parsed_url = urlsplit(args.django_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc or parsed_url.username or parsed_url.password:
            parser.error("--django-url muss eine HTTP(S)-URL ohne Zugangsdaten sein.")
    domains: dict = {}
    handler = make_handler(root, django_url=args.django_url, workspace_enabled=bool(args.workspace or args.domain or args.ki_domains))
    if args.workspace or args.domain or args.ki_domains:
        from ki_knowledge.wiki_web import make_workspace_handler
        from ki_knowledge.wiki_workspace import Workspace, WorkspaceError
        from ki_knowledge.wiki_documents import DocumentDomain

        try:
            workspace = Workspace(args.workspace) if args.workspace else None
            if workspace and (workspace.root.is_relative_to(root) or root.is_relative_to(workspace.root)):
                raise WorkspaceError("Der Arbeitsraum muss getrennt vom Dokumentationsverzeichnis liegen.")
            for name, source, relations in args.domain:
                if not name or name in domains:
                    raise WorkspaceError(f"Domänenname leer oder doppelt: {name}")
                domains[name] = DocumentDomain(Path(source), Path(relations))
            if args.ki_domains:
                from ki_knowledge.wiki_bridge import ki_domains

                served = [root, *(domain.source for domain in domains.values())]
                if workspace:
                    served.append(workspace.root)
                for name, source, relations in ki_domains(exclude=served):
                    domains[name] = DocumentDomain(source, relations, lenient=True)
            for domain in domains.values():
                if domain.storage.root.is_relative_to(root) or root.is_relative_to(domain.storage.root):
                    raise WorkspaceError("Beziehungsverzeichnisse müssen getrennt von der Dokumentation liegen.")
                if any(domain.storage.root.is_relative_to(other.source) or other.source.is_relative_to(domain.storage.root)
                       for other in domains.values()):
                    raise WorkspaceError("Beziehungsverzeichnisse müssen von allen Quellen getrennt liegen.")
            paths = [domain.storage.root for domain in domains.values()]
            if workspace:
                paths.append(workspace.root)
            if any(a.is_relative_to(b) or b.is_relative_to(a)
                   for index, a in enumerate(paths) for b in paths[index + 1:]):
                raise WorkspaceError("Arbeits- und Beziehungsverzeichnisse müssen voneinander getrennt sein.")
        except WorkspaceError as exc:
            parser.error(str(exc))
        handler = make_workspace_handler(handler, workspace, domains)
    with ThreadingHTTPServer((args.host, args.port), handler) as server:
        display_host = "127.0.0.1" if args.host == "0.0.0.0" else args.host
        print(f"Bindeadresse: {args.host}:{server.server_port}", flush=True)
        print(f"Lesende Ansicht: http://{display_host}:{server.server_port}/  ({root})", flush=True)
        if args.workspace:
            print(f"Arbeitsraum: http://{display_host}:{server.server_port}/workspace/  ({workspace.root})", flush=True)
        if domains:
            print(f"Domänen: http://{display_host}:{server.server_port}/workspace/graph/", flush=True)
        if (args.workspace or domains) and args.host != "127.0.0.1":
            print("Warnung: Arbeitsraum im Netzwerk ohne Passwort und ohne Verschlüsselung erreichbar.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nAnsicht beendet.")


if __name__ == "__main__":
    main()
