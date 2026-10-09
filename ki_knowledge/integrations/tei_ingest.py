"""TEI-P5 (e.g. Deutsches Textarchiv) to page-wise text plus a reference outline.

A TEI file is turned into two independent views:

* ``pages``: the running text per printed page, as the pipeline would see a book scan.
  Headings are emitted as ordinary paragraphs, i.e. the structure is *hidden*.
* ``sections``: the editorial structure (``<div>``/``<head>``) with level, page and
  paragraph position. It is the ground truth for evaluating structure detection.

Footnotes, marginal notes and forme work (running headers, signatures, catchwords) are
left out of the running text.
"""

from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TEI_NS = "http://www.tei-c.org/ns/1.0"
_T = f"{{{TEI_NS}}}"

# Elements whose content is not part of the running text.
_SKIP = {f"{_T}{name}" for name in ("note", "fw", "figDesc", "teiHeader", "facsimile")}
# Elements that form one paragraph of running text.
_BLOCKS = {f"{_T}{name}" for name in ("p", "head", "l", "item", "quote", "byline", "dateline", "trailer", "argument", "closer", "opener", "salute", "signed", "docTitle", "titlePart", "docImprint", "docAuthor")}
# Section types that are not part of the book's outline.
_OUTLINE_SKIP_TYPES = {"titlepage", "contents", "imprimatur", "advertisement"}

_COMBINING_E = "\u0364"
_SNIFF_BYTES = 4096


@dataclass
class TeiSection:
    level: int
    title: str
    page: str
    page_index: int
    paragraph_index: int
    div_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "title": self.title,
            "page": self.page,
            "page_index": self.page_index,
            "paragraph_index": self.paragraph_index,
            "type": self.div_type,
        }


@dataclass
class TeiPage:
    label: str
    paragraphs: list[str] = field(default_factory=list)


@dataclass
class TeiDocument:
    title: str
    author: str
    year: str
    licence: str
    pages: list[TeiPage]
    sections: list[TeiSection]

    @property
    def paragraph_count(self) -> int:
        return sum(len(page.paragraphs) for page in self.pages)

    def to_markdown(self) -> str:
        """Page-wise markdown like the PDF import (``## Page N`` + paragraphs)."""
        chunks = []
        for index, page in enumerate(self.pages, start=1):
            if not page.paragraphs:
                continue
            chunks.append(f"## Page {index}")
            chunks.extend(_md_escape(paragraph) for paragraph in page.paragraphs)
        return "\n\n".join(chunks) + "\n"

    def outline_markdown(self) -> str:
        lines = [f"# Referenzgliederung: {self.title}", ""]
        for section in self.sections:
            indent = "  " * (section.level - 1)
            page = f"S. {section.page}, " if section.page else ""
            lines.append(f"{indent}- {section.title} ({page}Seite {section.page_index} im Import)")
        return "\n".join(lines) + "\n"


def is_tei_file(path: str | Path) -> bool:
    path = Path(path)
    if path.suffix.lower() not in {".xml", ".tei"}:
        return False
    try:
        with path.open("rb") as handle:
            head = handle.read(_SNIFF_BYTES)
    except OSError:
        return False
    return TEI_NS.encode() in head


def normalize_text(value: str) -> str:
    """Historic orthography to searchable text: long s, superscript e umlauts, spaces."""
    value = value.replace("ſ", "s").replace("ꝛ", "r")
    value = re.sub(rf"([aouAOU]){_COMBINING_E}", lambda m: unicodedata.normalize("NFC", m.group(1) + "\u0308"), value)
    value = value.replace(_COMBINING_E, "")
    return " ".join(value.split())


def _md_escape(text: str) -> str:
    # Paragraphs must never turn into markdown headings, lists or quotes.
    if re.match(r"^\s*(#|[-*+>]\s|\d+[.)]\s)", text):
        return "\\" + text
    return text


class _Walker:
    def __init__(self) -> None:
        self.pages: list[TeiPage] = [TeiPage(label="")]
        self.sections: list[TeiSection] = []
        self._buffer: list[str] = []
        self._block_depth = 0
        self._pending_hyphen = False
        self._seen_page_break = False

    @property
    def page(self) -> TeiPage:
        return self.pages[-1]

    def _paragraph_index(self) -> int:
        return sum(len(page.paragraphs) for page in self.pages)

    def text(self, value: str | None) -> None:
        if not value or not self._block_depth:
            return
        if self._pending_hyphen:
            value = value.lstrip()
            self._pending_hyphen = False
        self._buffer.append(value)

    def line_break(self) -> None:
        if not self._buffer:
            return
        last = self._buffer[-1].rstrip()
        if last.endswith(("¬", "-")) and not last.endswith(" -"):
            self._buffer[-1] = last[:-1]
            self._pending_hyphen = True
        else:
            self._buffer.append(" ")

    def flush(self) -> None:
        text = normalize_text("".join(self._buffer))
        self._buffer = []
        self._pending_hyphen = False
        if text:
            self.page.paragraphs.append(text)

    def page_break(self, label: str) -> None:
        # A paragraph running across the break is split, as a scan would show it.
        self.flush()
        if self._seen_page_break or self.page.paragraphs:
            self.pages.append(TeiPage(label=label))
        else:
            self.page.label = label
        self._seen_page_break = True

    def walk(self, element: ET.Element, level: int) -> None:
        tag = element.tag
        if tag in _SKIP:
            return
        if tag == f"{_T}pb":
            self.page_break(element.get("n", ""))
            return
        if tag == f"{_T}lb":
            self.line_break()
            self.text(element.tail)
            return
        is_div = tag == f"{_T}div"
        is_block = tag in _BLOCKS
        if is_div:
            self.flush()
            head = element.find(f"{_T}head")
            div_type = element.get("type", "")
            if head is not None and div_type not in _OUTLINE_SKIP_TYPES:
                title = normalize_text(" ".join(_running_text(head)))
                if title:
                    self.sections.append(
                        TeiSection(
                            level=level + 1,
                            title=title,
                            page=self.page.label,
                            page_index=len(self.pages),
                            paragraph_index=self._paragraph_index(),
                            div_type=div_type,
                        )
                    )
        if is_block:
            self.flush()
            self._block_depth += 1
        self.text(element.text)
        for child in element:
            self.walk(child, level + 1 if is_div else level)
            if child.tag not in (f"{_T}lb",):
                self.text(child.tail)
        if is_block:
            self._block_depth -= 1
            self.flush()


def _running_text(element: ET.Element) -> list[str]:
    parts: list[str] = []

    def visit(node: ET.Element) -> None:
        if node.tag in _SKIP:
            return
        if node.tag == f"{_T}lb":
            parts.append(" ")
        parts.append(node.text or "")
        for child in node:
            visit(child)
            parts.append(child.tail or "")

    visit(element)
    text = "".join(parts)
    return [re.sub(r"[¬-]\s+(?=[a-zäöüß])", "", text)]


def _header_text(root: ET.Element, path: str) -> str:
    node = root.find(path)
    return normalize_text("".join(node.itertext())) if node is not None else ""


def parse_tei(path: str | Path) -> TeiDocument:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise ValueError(f"invalid TEI XML: {exc}") from exc
    text = root.find(f"{_T}text")
    if text is None:
        raise ValueError("TEI file has no <text> element")
    walker = _Walker()
    for part in text:
        if part.tag in (f"{_T}front", f"{_T}body", f"{_T}back"):
            walker.walk(part, 0)
    walker.flush()
    pages = [page for page in walker.pages if page.paragraphs]
    # Page indices of sections must refer to the non-empty pages that get imported.
    index_map: dict[int, int] = {}
    kept = 0
    for original, page in enumerate(walker.pages, start=1):
        if page.paragraphs:
            kept += 1
        index_map[original] = max(1, kept if page.paragraphs else kept + 1)
    for section in walker.sections:
        section.page_index = min(index_map.get(section.page_index, section.page_index), max(1, len(pages)))
    licence = root.find(f".//{_T}availability/{_T}licence")
    return TeiDocument(
        title=_header_text(root, f".//{_T}titleStmt/{_T}title[@type='main']") or Path(path).stem,
        author=_header_text(root, f".//{_T}titleStmt/{_T}author//{_T}surname"),
        year=_header_text(root, f".//{_T}sourceDesc//{_T}publicationStmt/{_T}date"),
        licence=(licence.get("target", "") if licence is not None else ""),
        pages=pages,
        sections=walker.sections,
    )


__all__ = ["TEI_NS", "TeiDocument", "TeiPage", "TeiSection", "is_tei_file", "normalize_text", "parse_tei"]
