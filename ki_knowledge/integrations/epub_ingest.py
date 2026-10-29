"""Bounded, offline EPUB 2/3 ingestion, without ZIP extraction or Django.

``chapters[i]`` must be saved as ``{i + 1:04d}.md`` in one directory. Links
are rewritten against those filenames. Source XML IDs become inert HTML anchors
named ``epub-`` plus the UTF-8 hex encoding of the ID (also used in links).
These anchors are the only generated raw HTML. Consumers must allow inert
anchors if they want fragment navigation.

XHTML must be well-formed XML; internal DTD subsets/entities, DRM, unsupported spine media,
missing/empty reading-order documents and unsafe archives fail explicitly.
Recognized image-only covers and navigation-only manifest nav documents are
excluded with warnings before chapter numbering; an entirely non-text book fails.
Images are described, not extracted or embedded. CSS/layout and interactive
content are not reproduced. Tables use Markdown pipe-table syntax. Preformatted
code in lists is flattened to inline code for compatibility with Markdown engines.
Plain/external XHTML DOCTYPE declarations are accepted, but DTDs are never loaded.
"""

from __future__ import annotations

import html
import posixpath
import re
import stat
import zipfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
from xml.etree import ElementTree as ET
from xml.parsers import expat

__all__ = ["EpubBook", "EpubChapter", "EpubIngestError", "parse_epub"]

MAX_ARCHIVE_MEMBERS = 10_000
MAX_TOTAL_UNCOMPRESSED = 256 * 1024 * 1024
MAX_RESOURCE_BYTES = 16 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200
MAX_XML_NODES = 250_000
MAX_XML_DEPTH = 128

_DC = "http://purl.org/dc/elements/1.1/"
_EPUB_TYPE = "{http://www.idpf.org/2007/ops}type"
_XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
_XML_BASE = "{http://www.w3.org/XML/1998/namespace}base"
_XHTML_TYPES = {"application/xhtml+xml"}
_SKIP = {"head", "script", "style", "nav", "template"}
_MEDIA = {"iframe", "object", "embed", "audio", "video", "source", "form", "input", "button"}
_BLOCK = {
    "p", "div", "section", "article", "aside", "main", "header", "footer",
    "figure", "figcaption", "address", "dl", "dt", "dd", "li",
}


class EpubIngestError(ValueError):
    """The EPUB cannot be converted safely and completely."""


@dataclass
class EpubChapter:
    title: str
    href: str
    markdown: str


@dataclass
class EpubBook:
    title: str
    authors: list[str]
    language: str
    identifier: str
    chapters: list[EpubChapter]
    metadata: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(element: ET.Element) -> str:
    return " ".join("".join(element.itertext()).split())


def _warn(warnings: list[str], message: str) -> None:
    if message not in warnings:
        warnings.append(message)


def _xml(data: bytes, resource: str) -> ET.Element:
    # Expat callbacks work for every XML encoding, unlike scanning byte strings
    # for '<!DOCTYPE' (which misses UTF-16 and UTF-32 declarations).
    parser = expat.ParserCreate()
    depth = nodes = 0

    def forbidden(*args: object) -> None:
        raise EpubIngestError(f"{resource}: internal DTD subsets and entity references are forbidden")

    def doctype(name: str, system_id: str | None, public_id: str | None, internal_subset: int) -> None:
        if internal_subset:
            forbidden()
        if name != "html":
            raise EpubIngestError(f"{resource}: only XHTML DOCTYPE declarations are supported")

    def start(name: str, attributes: dict) -> None:
        nonlocal depth, nodes
        depth += 1
        nodes += 1
        if depth > MAX_XML_DEPTH or nodes > MAX_XML_NODES:
            raise EpubIngestError(f"{resource}: XML complexity limit exceeded")

    def end(name: str) -> None:
        nonlocal depth
        depth -= 1

    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    parser.StartDoctypeDeclHandler = doctype
    parser.EntityDeclHandler = forbidden
    parser.ExternalEntityRefHandler = forbidden
    parser.SkippedEntityHandler = forbidden
    parser.StartElementHandler = start
    parser.EndElementHandler = end
    try:
        parser.Parse(data, True)
        root = ET.fromstring(data)
    except (expat.ExpatError, ET.ParseError, ValueError) as exc:
        if isinstance(exc, EpubIngestError):
            raise
        raise EpubIngestError(f"{resource}: malformed XML ({exc})") from exc
    if any(_XML_BASE in element.attrib for element in root.iter()):
        raise EpubIngestError(f"{resource}: xml:base is unsupported")
    return root


def _safe_archive_path(value: str) -> str:
    if (
        not value or value.startswith("/") or "\\" in value
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
        or any(part in {"", ".", ".."} for part in value.split("/"))
        or re.match(r"^[A-Za-z]:", value)
    ):
        raise EpubIngestError(f"Unsafe archive/resource path: {value!r}")
    return value


def _resolve(base: str, href: str) -> tuple[str, str]:
    try:
        parts = urlsplit(href)
    except ValueError as exc:
        raise EpubIngestError(f"Invalid resource URL: {href!r}") from exc
    if parts.scheme or parts.netloc or parts.query:
        raise EpubIngestError(f"Non-local or ambiguous resource URL: {href!r}")
    path = unquote(parts.path, errors="strict")
    if "\\" in path or path.startswith("/") or any(ord(c) < 32 for c in path):
        raise EpubIngestError(f"Unsafe resource URL: {href!r}")
    result = posixpath.normpath(posixpath.join(posixpath.dirname(base), path)) if path else base
    return _safe_archive_path(result), unquote(parts.fragment, errors="strict")


class _Archive:
    def __init__(self, archive: zipfile.ZipFile):
        self.archive = archive
        self.members: dict[str, zipfile.ZipInfo] = {}
        entries = archive.infolist()
        if len(entries) > MAX_ARCHIVE_MEMBERS:
            raise EpubIngestError("Archive member limit exceeded")
        total = 0
        for info in entries:
            name = info.orig_filename
            _safe_archive_path(name[:-1] if info.is_dir() else name)
            if name in self.members:
                raise EpubIngestError(f"Duplicate ZIP member: {name}")
            self.members[name] = info
            if stat.S_ISLNK(info.external_attr >> 16):
                raise EpubIngestError(f"ZIP symlinks are unsupported: {name}")
            if info.flag_bits & 1:
                raise EpubIngestError(f"Encrypted ZIP member is unsupported: {name}")
            if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                raise EpubIngestError(f"Unsupported ZIP compression: {name}")
            total += info.file_size
            if info.file_size > MAX_RESOURCE_BYTES or total > MAX_TOTAL_UNCOMPRESSED:
                raise EpubIngestError(f"Archive uncompressed size limit exceeded: {name}")
            if info.file_size > 1024 * 1024 and info.file_size > max(1, info.compress_size) * MAX_COMPRESSION_RATIO:
                raise EpubIngestError(f"Archive compression ratio limit exceeded: {name}")

    def read(self, path: str) -> bytes:
        info = self.members.get(path)
        if info is None or info.is_dir():
            raise EpubIngestError(f"Missing EPUB resource: {path}")
        with self.archive.open(info) as handle:
            data = handle.read(MAX_RESOURCE_BYTES + 1)
        if len(data) > MAX_RESOURCE_BYTES or len(data) != info.file_size:
            raise EpubIngestError(f"Resource size limit/mismatch: {path}")
        return data

    def xml(self, path: str) -> ET.Element:
        return _xml(self.read(path), path)


def _anchor(identifier: str) -> str:
    return "epub-" + identifier.encode("utf-8").hex()


def _ids(element: ET.Element) -> list[str]:
    return list(dict.fromkeys(value for value in (element.get("id"), element.get(_XML_ID)) if value))


def _rendered_ids(element: ET.Element):
    if _local(element.tag).lower() in _SKIP:
        return
    yield from _ids(element)
    if _local(element.tag).lower() not in _MEDIA:
        for child in element:
            yield from _rendered_ids(child)


def _visible_nodes(element: ET.Element):
    if _local(element.tag).lower() in _SKIP | _MEDIA:
        return
    yield element
    for child in element:
        yield from _visible_nodes(child)


def _prose(element: ET.Element) -> str:
    if _local(element.tag).lower() in _SKIP | _MEDIA | {"img", "image"}:
        return ""
    return (element.text or "") + "".join(_prose(child) + (child.tail or "") for child in element)


def _escape(text: str | None) -> str:
    value = re.sub(r"\s+", " ", text or "")
    value = html.escape(value, quote=False)
    return re.sub(r"([\\`*_{}\[\]()#+.!|~\-])", r"\\\1", value)


class _Renderer:
    def __init__(self, paths: dict[str, str], ids: dict[str, set[str]], warnings: list[str]):
        self.paths = paths
        self.ids = ids
        self.warnings = warnings
        self.path = ""
        self.list_depth = 0

    def link(self, href: str, base: str) -> str | None:
        if not href or any(ord(char) < 32 or ord(char) == 127 for char in href):
            _warn(self.warnings, f"{base}: empty/unsafe link omitted")
            return None
        try:
            parsed = urlsplit(href)
            if parsed.scheme.lower() in {"http", "https", "mailto"}:
                return quote(href, safe="/:#?@!$&'+,;=%~-._")
            path, fragment = _resolve(base, href)
        except (EpubIngestError, ValueError, UnicodeError):
            _warn(self.warnings, f"{base}: unsafe/unsupported link omitted: {href!r}")
            return None
        if path not in self.paths or (fragment and fragment not in self.ids[path]):
            _warn(self.warnings, f"{base}: unresolved book link omitted: {href!r}")
            return None
        return "./" + self.paths[path] + ("#" + _anchor(fragment) if fragment else "")

    def content(self, element: ET.Element) -> str:
        return _escape(element.text) + "".join(self.node(child) + _escape(child.tail) for child in element)

    def anchors(self, element: ET.Element) -> str:
        return "".join(f'<a id="{_anchor(value)}"></a>' for value in _ids(element))

    def node(self, element: ET.Element) -> str:
        tag = _local(element.tag).lower()
        if tag in _SKIP:
            return ""
        anchor = self.anchors(element)
        if tag in {"img", "image"}:
            _warn(self.warnings, f"{self.path}: images are not extracted or embedded")
            return anchor + ("[Image: " + _escape(element.get("alt", "image")) + "]")
        if tag in _MEDIA:
            _warn(self.warnings, f"{self.path}: unsupported interactive/media element omitted: {tag}")
            return anchor
        if tag in {"svg", "math"}:
            _warn(self.warnings, f"{self.path}: {tag} simplified to text")
            return "".join(f'<a id="{_anchor(value)}"></a>' for value in _rendered_ids(element)) + _escape(_text(element))
        if tag == "pre" and not self.list_depth:
            value = "".join(element.itertext()).replace("\r\n", "\n").replace("\r", "\n")
            longest = max((len(run) for run in re.findall(r"`+", value)), default=0)
            fence = "`" * max(3, longest + 1)
            anchors = "".join(f'<a id="{_anchor(value)}"></a>' for value in _rendered_ids(element))
            return f"\n\n{anchors}\n{fence}\n{value.rstrip()}\n{fence}\n\n"
        if tag == "code" or tag == "pre":
            if tag == "pre":
                # Common Markdown engines do not support fenced blocks in lists;
                # flatten to an inline code span rather than risk active HTML.
                _warn(self.warnings, f"{self.path}: preformatted code inside a list flattened")
            value = re.sub(r"\s+", " ", "".join(element.itertext()))
            longest = max((len(run) for run in re.findall(r"`+", value)), default=0)
            fence = "`" * (longest + 1)
            anchors = "".join(f'<a id="{_anchor(value)}"></a>' for value in _rendered_ids(element))
            return anchors + fence + " " + value + " " + fence
        if tag in {"ol", "ul"}:
            lines = []
            try:
                number = int(element.get("start", "1"))
            except ValueError:
                number = 1
            for child in element:
                if _local(child.tag) != "li":
                    lines.append(self.node(child))
                    continue
                marker = f"{number}. " if tag == "ol" else "- "
                self.list_depth += 1
                try:
                    value = (self.anchors(child) + self.content(child)).strip()
                finally:
                    self.list_depth -= 1
                lines.append(marker + value.replace("\n", "\n" + " " * max(4, len(marker))))
                number += 1
            return "\n\n" + anchor + "\n".join(lines) + "\n\n"
        if tag == "table":
            return "\n\n" + anchor + self.table(element) + "\n\n"
        value = self.content(element)
        if re.fullmatch(r"h[1-6]", tag):
            return f"\n\n{anchor}\n{'#' * int(tag[1])} {value.strip()}\n\n"
        if tag == "blockquote":
            return "\n\n" + anchor + "\n".join("> " + line for line in value.strip().splitlines()) + "\n\n"
        if tag in {"em", "i"}:
            return anchor + "*" + value + "*"
        if tag in {"strong", "b"}:
            return anchor + "**" + value + "**"
        if tag == "a":
            target = self.link(element.get("href", ""), self.path) if "href" in element.attrib else None
            return anchor + (f"[{value}]({target})" if target else value)
        if tag == "br":
            return anchor + "  \n"
        if tag == "hr":
            return "\n\n" + anchor + "\n---\n\n"
        if tag in _BLOCK:
            return "\n\n" + anchor + value.strip() + "\n\n"
        return anchor + value

    def table(self, element: ET.Element) -> str:
        rows: list[list[str]] = []
        extra: list[str] = []
        for child in element:
            if _local(child.tag) == "caption":
                extra.append(self.node(child))
        def table_rows(parent: ET.Element):
            for child in parent:
                if _local(child.tag) == "tr":
                    yield child
                elif _local(child.tag) in {"thead", "tbody", "tfoot"}:
                    extra.append(self.anchors(child))
                    yield from table_rows(child)
                elif _local(child.tag) in {"col", "colgroup"}:
                    extra.extend(self.anchors(node) for node in child.iter())

        source_rows = list(table_rows(element))
        for row in source_rows:
            cells = []
            extra.append(self.anchors(row))
            for cell in row:
                if _local(cell.tag) not in {"th", "td"}:
                    continue
                if cell.get("colspan", "1") != "1" or cell.get("rowspan", "1") != "1":
                    _warn(self.warnings, f"{self.path}: table cell spans flattened")
                # Numeric entities keep literal pipes safe in code and link URLs.
                value = (self.anchors(cell) + self.content(cell)).strip().replace("\\|", "&#124;").replace("|", "&#124;")
                cells.append(re.sub(r"\s*\n\s*", " ", value))
            if cells:
                rows.append(cells)
        if not rows:
            return "".join(extra) + self.content(element)
        width = max(map(len, rows))
        rows = [row + [""] * (width - len(row)) for row in rows]
        # A headerless table gets an empty header, rather than losing its first row.
        first_row = source_rows[0] if source_rows else None
        has_header = first_row is not None and any(_local(cell.tag) == "th" for cell in first_row)
        if not has_header:
            rows.insert(0, [""] * width)
        lines = ["| " + " | ".join(row) + " |" for row in rows]
        lines.insert(1, "| " + " | ".join(["---"] * width) + " |")
        return "".join(extra) + "\n" + "\n".join(lines)

    def render(self, path: str, root: ET.Element) -> str:
        self.path = path
        # Do not normalize blank lines after rendering: that changes code blocks,
        # and inserting protected code later would lose list/blockquote indentation.
        return self.node(root).strip() + "\n"


def _toc(root: ET.Element, path: str, renderer: _Renderer, ncx: bool = False) -> list[dict]:
    if ncx:
        parent = next((node for node in root.iter() if _local(node.tag) == "navMap"), None)
    else:
        parent = next((node for node in root.iter() if _local(node.tag) == "nav" and "toc" in node.get(_EPUB_TYPE, "").split()), None)
        if parent is not None:
            parent = next((node for node in parent if _local(node.tag) == "ol"), None)
    if parent is None:
        return []

    def entries(node: ET.Element) -> list[dict]:
        result = []
        for child in node:
            if _local(child.tag) != ("navPoint" if ncx else "li"):
                continue
            label_tags = {"navLabel"} if ncx else {"a", "span"}
            label = next((item for item in child if _local(item.tag) in label_tags), None)
            target = next((item for item in child if _local(item.tag) == "content"), None) if ncx else label
            nested = child if ncx else next((item for item in child if _local(item.tag) == "ol"), child)
            href = target.get("src" if ncx else "href", "") if target is not None else ""
            result.append({
                "title": _text(label) if label is not None else "",
                "href": href,
                "target": renderer.link(href, path) if href else None,
                "children": entries(nested) if nested is not child or ncx else [],
            })
        return result

    return entries(parent)


def _parse(archive: _Archive, warnings: list[str]) -> EpubBook:
    if "mimetype" in archive.members:
        if archive.read("mimetype").strip() != b"application/epub+zip":
            raise EpubIngestError("Invalid EPUB mimetype")
    else:
        _warn(warnings, "EPUB mimetype member is missing")
    if "META-INF/encryption.xml" in archive.members:
        encryption = archive.xml("META-INF/encryption.xml")
        if any(_local(node.tag) == "EncryptedData" for node in encryption.iter()):
            raise EpubIngestError("EPUB encryption/DRM (including font obfuscation) is unsupported")
    container = archive.xml("META-INF/container.xml")
    if _local(container.tag) != "container":
        raise EpubIngestError("Invalid EPUB container.xml root")
    roots = [node for node in container.iter() if _local(node.tag) == "rootfile" and node.get("media-type") == "application/oebps-package+xml"]
    if not roots:
        raise EpubIngestError("EPUB container has no OPF rootfile")
    if len(roots) > 1:
        _warn(warnings, "Multiple EPUB renditions: using the first OPF rootfile")
    opf_path = _safe_archive_path(roots[0].get("full-path", ""))
    package = archive.xml(opf_path)
    if _local(package.tag) != "package":
        raise EpubIngestError(f"{opf_path}: invalid OPF package root")
    meta = next((node for node in package if _local(node.tag) == "metadata"), None)
    manifest = next((node for node in package if _local(node.tag) == "manifest"), None)
    spine = next((node for node in package if _local(node.tag) == "spine"), None)
    if meta is None or manifest is None or spine is None:
        raise EpubIngestError("OPF requires metadata, manifest and spine")
    dc: dict[str, list[str]] = {}
    metadata_items = []
    for node in meta:
        if node.tag.startswith("{" + _DC + "}"):
            dc.setdefault(_local(node.tag), []).append(_text(node))
        elif _local(node.tag) == "meta":
            metadata_items.append({**node.attrib, "value": _text(node)})
    identifiers = [node for node in meta if node.tag == f"{{{_DC}}}identifier"]
    selected_identifier = next((node for node in identifiers if node.get("id") == package.get("unique-identifier")), None)
    identifier = _text(selected_identifier) if selected_identifier is not None else next(iter(dc.get("identifier", [])), "")
    title = next(iter(dc.get("title", [])), "").strip()
    if not title:
        title = Path(opf_path).stem
        _warn(warnings, "Missing book title; using OPF filename")
    items: dict[str, dict] = {}
    for node in manifest:
        if _local(node.tag) != "item":
            continue
        item_id, href = node.get("id", ""), node.get("href", "")
        if not item_id or not href or item_id in items:
            raise EpubIngestError("Invalid/duplicate OPF manifest item ID or missing href")
        try:
            parsed = urlsplit(href)
        except ValueError as exc:
            raise EpubIngestError(f"Invalid manifest href: {href!r}") from exc
        remote = bool(parsed.scheme or parsed.netloc)
        path, fragment = ("", "") if remote else _resolve(opf_path, href)
        if fragment:
            raise EpubIngestError(f"Manifest resource has a fragment: {href}")
        items[item_id] = {**node.attrib, "path": path, "remote": remote}
        if remote:
            _warn(warnings, f"Remote manifest resource not fetched: {href}")
        media_type = node.get("media-type", "")
        if (
            media_type not in _XHTML_TYPES | {
                "application/x-dtbncx+xml", "text/css", "application/font-woff",
                "application/vnd.ms-opentype", "application/x-font-ttf",
                "application/x-font-opentype", "application/font-sfnt",
            }
            and not media_type.startswith(("image/", "font/"))
        ):
            _warn(warnings, f"Unsupported manifest resource not converted: {href} ({media_type})")
    cover_paths: set[str] = set()
    for guide in package:
        if _local(guide.tag) == "guide":
            for reference in guide:
                if reference.get("type", "").lower() == "cover" and reference.get("href"):
                    cover_path, _ = _resolve(opf_path, reference.get("href"))
                    cover_paths.add(cover_path)
    documents: list[tuple[str, ET.Element]] = []
    skipped_chapters: list[dict[str, str]] = []
    seen = set()
    for itemref in spine:
        if _local(itemref.tag) != "itemref":
            continue
        item = items.get(itemref.get("idref", ""))
        if item is None:
            raise EpubIngestError("Spine refers to a missing manifest item")
        if itemref.get("linear", "yes").lower() == "no":
            _warn(warnings, f"Nonlinear spine item excluded: {item['href']}")
            continue
        path = item["path"]
        if item["remote"] or item.get("media-type") not in _XHTML_TYPES:
            raise EpubIngestError(f"Unsupported reading-order resource: {item['href']}")
        if path in seen:
            raise EpubIngestError(f"Duplicate spine resource: {path}")
        seen.add(path)
        root = archive.xml(path)
        if _local(root.tag) != "html" or not any(_local(node.tag) == "body" for node in root):
            raise EpubIngestError(f"{path}: reading-order resource is not XHTML with a body")
        body = next(node for node in root if _local(node.tag) == "body")
        if not _prose(body).strip():
            visible = list(_visible_nodes(body))
            has_images = any(_local(node.tag) in {"img", "image"} for node in visible)
            has_navigation = any(_local(node.tag) == "nav" for node in body.iter())
            if "nav" in item.get("properties", "").split() and has_navigation and not has_images:
                _warn(warnings, f"{path}: navigation-only spine document excluded; navigation is retained in metadata")
                skipped_chapters.append({"href": path, "reason": "navigation-only document"})
                continue
            html_title = next((node for node in root.iter() if _local(node.tag) == "title"), None)
            cover_names = {"cover", "frontcover", "front-cover", "front_cover"}
            recognized_cover = (
                path in cover_paths
                or "cover" in item.get("properties", "").split()
                or Path(path).stem.lower() in cover_names
                or (html_title is not None and _text(html_title).lower() in cover_names)
                or any("cover" in node.get(_EPUB_TYPE, "").split() for node in visible)
            )
            if has_images and recognized_cover:
                _warn(warnings, f"{path}: image-only cover excluded; image content is not converted or extracted")
                skipped_chapters.append({"href": path, "reason": "image-only cover"})
                continue
            raise EpubIngestError(f"{path}: empty/non-text chapter cannot be converted")
        documents.append((path, root))
    if not documents:
        raise EpubIngestError("EPUB has no linear textual reading-order chapters")
    paths = {path: f"{index:04d}.md" for index, (path, _) in enumerate(documents, 1)}
    ids: dict[str, set[str]] = {}
    for path, root in documents:
        found: set[str] = set()
        for node in root.iter():
            for value in _ids(node):
                if value in found:
                    raise EpubIngestError(f"{path}: duplicate XML ID: {value!r}")
                found.add(value)
        ids[path] = set(_rendered_ids(root))
    renderer = _Renderer(paths, ids, warnings)
    chapters = []
    for path, root in documents:
        body = next(node for node in root if _local(node.tag) == "body")
        visible = list(_visible_nodes(body))
        heading = next((node for node in visible if re.fullmatch(r"h[1-6]", _local(node.tag))), None)
        html_title = next((node for node in root.iter() if _local(node.tag) == "title"), None)
        chapter_title = _text(heading) if heading is not None else (_text(html_title) if html_title is not None else "")
        chapters.append(EpubChapter(chapter_title or Path(path).stem, path, renderer.render(path, root)))
    toc = []
    for item in items.values():
        if "nav" in item.get("properties", "").split():
            if item["remote"]:
                raise EpubIngestError("Remote EPUB navigation document is unsupported")
            toc = _toc(archive.xml(item["path"]), item["path"], renderer)
            if toc:
                break
    if not toc and spine.get("toc"):
        ncx = items.get(spine.get("toc"))
        if not ncx or ncx["remote"]:
            raise EpubIngestError("Missing or remote NCX navigation resource")
        toc = _toc(archive.xml(ncx["path"]), ncx["path"], renderer, ncx=True)
    return EpubBook(
        title=title, authors=dc.get("creator", []),
        language=next(iter(dc.get("language", [])), ""), identifier=identifier,
        chapters=chapters, metadata={
            "opf_path": opf_path, "version": package.get("version", ""),
            "dc": dc, "meta": metadata_items, "toc": toc,
            "chapter_files": paths, "skipped_chapters": skipped_chapters,
        }, warnings=warnings,
    )


def parse_epub(path: Path) -> EpubBook:
    """Read an EPUB without extraction/network access; raise EpubIngestError.

    Chapter ``href`` values are archive-root-relative, decoded resource paths,
    not output filenames. ``metadata["chapter_files"]`` maps them to the
    numbered Markdown files. ``metadata["toc"]`` is a nested list of dictionaries
    with ``title``, original ``href``, rewritten ``target`` and ``children``.
    """
    try:
        with zipfile.ZipFile(path) as archive:
            return _parse(_Archive(archive), [])
    except EpubIngestError:
        raise
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError, ValueError, UnicodeError, NotImplementedError, expat.ExpatError, zlib.error, EOFError) as exc:
        raise EpubIngestError(f"Cannot ingest EPUB {path}: {exc}") from exc
