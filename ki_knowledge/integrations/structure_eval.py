"""Detect a book's outline from imported blocks and evaluate it against a reference.

Two detectors are compared:

``heading``
    Short stand-alone paragraphs that look like headings (``§. 3.``, ``Erster
    Abschnitt``, roman numerals, ``Einleitung`` …).  Needs paragraph
    boundaries, i.e. works on TEI/Markdown and paragraph-wise PDF imports, not on flattened pages.
``toc``
    Parses the printed table of contents (entries ending with a page number)
    and locates every entry title in the page text.  Works on flattened page
    text as well, so it is the candidate for the PDF books.

Every text is also evaluated in a *flat* variant where all paragraphs of a
page are joined, which simulates the former one-block-per-page PDF import.
"""

from __future__ import annotations

import re
import statistics
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Iterable, Mapping, Sequence

METHODS = ("heading", "toc", "combined")
TITLE_SIMILARITY = 0.8
PAGE_TOLERANCE = 1

_ORDINALS = (
    "erst|zweit|dritt|viert|fünft|funft|sechst|siebent|siebt|acht|neunt|zehnt|elft|zwölft|zwolft"
)
_UNITS = "buch|theil|teil|abschnitt|abtheilung|abteilung|kapitel|capitel|vorlesung|rede|stück|stuck|band|periode|epoche"
_STRONG_HEADING = re.compile(
    rf"""^(?:
        §\.?\s*\d+                                    # §. 12.
      | (?:{_ORDINALS})(?:e[rsn]?|es)\s+(?:{_UNITS})\b  # Erster Abschnitt
      | (?:{_UNITS})\s+(?:\d+|[ivxlc]+)\b              # Kapitel 3 / Buch IV
      | [ivxlc]{{1,6}}\.\s                             # IV. Bildung des Kelches
      | [ivxlc]{{1,6}}\.?$                             # IV.
      | \d{{1,3}}\.\s+[A-ZÄÖÜ]                         # 3. Titel
      | [A-ZÄÖÜ]\)\s                                   # A) Titel
      | (?:einleitung|vorrede|vorbericht|vorwort|nachwort|nachschrift|schluss|schluß|beschluss|beschluß|
           zueignung|anhang|zusatz|anmerkung|allgemeine\s+anmerkung|inhalt|register|übersicht|einführung)\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)
_TOC_NUMBER = re.compile(
    r"\b(?:pag|seite|s)\.?\s*(\d{1,4})\.?(?=\s|$)"  # "S. 22." / "Pag. 1"
    r"|(?<![\w§.,])(\d{1,4})(?=\s|$)",               # bare trailing number
    re.IGNORECASE,
)
_MAX_TOC_TITLE = 160
_TOC_MARKER = re.compile(r"^\s*(?:inhalt|inhaltsverzeichnis|inhaltsverzeichniß|inhalts-?anzeige|übersicht)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Heading:
    title: str
    page: int
    level: int = 1
    method: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"title": self.title, "page": self.page, "level": self.level, "method": self.method}


@dataclass
class Evaluation:
    method: str
    predicted: int
    reference: int
    matched: int
    level_recall: dict[int, float] = field(default_factory=dict)
    titled_reference: int = 0
    titled_matched: int = 0
    misses: list[str] = field(default_factory=list)
    false_hits: list[str] = field(default_factory=list)

    @property
    def precision(self) -> float:
        return self.matched / self.predicted if self.predicted else 0.0

    @property
    def recall(self) -> float:
        return self.matched / self.reference if self.reference else 0.0

    @property
    def titled_recall(self) -> float:
        """Recall over sections with a worded title (chapters), ignoring bare numbers like ``§. 12.``."""
        return self.titled_matched / self.titled_reference if self.titled_reference else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "predicted": self.predicted,
            "reference": self.reference,
            "matched": self.matched,
            "precision": round(self.precision, 3),
            "recall": round(self.recall, 3),
            "f1": round(self.f1, 3),
            "titled_reference": self.titled_reference,
            "titled_recall": round(self.titled_recall, 3),
            "level_recall": {str(level): round(value, 3) for level, value in sorted(self.level_recall.items())},
            "misses": self.misses[:10],
            "false_hits": self.false_hits[:10],
        }


# --- text helpers ---------------------------------------------------------------------


def normalize_title(value: str) -> str:
    value = unicodedata.normalize("NFC", value).lower().replace("ſ", "s").replace("ß", "ss")
    value = re.sub(r"\bpag\.?\s*\d+$", "", value)
    value = re.sub(r"[^\w§]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def is_titled(title: str) -> bool:
    """A title with at least one word of three letters (not just ``§. 4.`` or ``IV.``)."""
    return any(len(word) >= 3 and word.isalpha() and not re.fullmatch(r"[ivxlc]+", word)
               for word in normalize_title(title).split())


def _leading_number(normalized: str) -> str:
    """Section number at the start (``§ 12``, ``iv``, ``3``) – different numbers never match."""
    match = re.match(r"^(?:§\s*)?(\d+|[ivxlc]{1,6})\b", normalized)
    return match.group(1) if match else ""


def similarity(left: str, right: str) -> float:
    a, b = normalize_title(left), normalize_title(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if _leading_number(a) != _leading_number(b):
        return 0.0
    shorter, longer = sorted((a, b), key=len)
    # A heading paragraph may carry the first words of the text ("§. 1. Ein jeder …").
    if len(shorter) >= 4 and longer.startswith(shorter + " ") and (" " in shorter or len(shorter) / len(longer) >= 0.3):
        return 0.9
    return SequenceMatcher(None, a, b).ratio()


def pages_from_records(records: Iterable[Any], *, flat: bool = False) -> list[tuple[int, list[str]]]:
    """``(page, paragraphs)`` in reading order from knowledge records (``metadata.page`` or ``Page N`` title)."""
    grouped: dict[int, list[tuple[int, str]]] = defaultdict(list)
    for record in records:
        if getattr(record, "block_type", "") == "heading":
            continue
        metadata = getattr(record, "metadata", None) or {}
        page = metadata.get("page")
        if page is None:
            match = re.match(r"page\s+(\d+)", str(getattr(record, "title", "") or ""), re.IGNORECASE)
            page = int(match.group(1)) if match else 0
        text = str(getattr(record, "content", "") or "").strip()
        if text:
            grouped[int(page)].append((int(getattr(record, "order_index", 0) or 0), text))
    pages = []
    for page in sorted(grouped):
        paragraphs = [text for _order, text in sorted(grouped[page])]
        pages.append((page, [" ".join(paragraphs)] if flat else paragraphs))
    return pages


# --- detectors -------------------------------------------------------------------------


def _looks_like_heading(text: str) -> tuple[bool, int]:
    words = text.split()
    if not words or len(text) > 120 or len(words) > 14:
        return False, 0
    if _STRONG_HEADING.match(text):
        level = 2 if text.lstrip().startswith("§") else 1
        return True, level
    # Weak signal: very short paragraph starting with a capital, no sentence punctuation inside.
    if len(words) <= 6 and text[0].isupper() and not re.search(r"[,;:]\s|\s[a-zäöü]+[.!?]\s", text):
        return not text.rstrip().endswith((",", ";", ":", "-")), 1
    return False, 0


def detect_headings(pages: Sequence[tuple[int, list[str]]]) -> list[Heading]:
    toc_pages = {page for page, _ in _toc_entries(pages)}
    headings: list[Heading] = []
    for page, paragraphs in pages:
        if page in toc_pages:
            continue
        for text in paragraphs:
            ok, level = _looks_like_heading(text.strip())
            if ok:
                headings.append(Heading(text.strip(), page, level, "heading"))
    return headings


def _parse_toc_text(text: str) -> list[tuple[str, int]]:
    """Split ``Title 12 Next title 17`` at stand-alone numbers (linear, no backtracking)."""
    entries = []
    last = 0
    for match in _TOC_NUMBER.finditer(text):
        title = re.sub(r"[\s.·…_—–§-]+$", "", text[last : match.start()])
        title = re.sub(r"^[\s.·…_—–-]+", "", title).strip()
        # Leftover end of a page range ("S. 22–100. I. Titel") in front of the next title.
        title = re.sub(r"^\d{1,4}\.\s+(?=\S)", "", title)
        last = match.end()
        if len(title) <= _MAX_TOC_TITLE and re.search(r"[A-Za-zÄÖÜäöü]{3}", title):
            entries.append((title, int(match.group(1) or match.group(2))))
    return entries


def _toc_entries(pages: Sequence[tuple[int, list[str]]]) -> list[tuple[int, list[tuple[str, int]]]]:
    """Pages that look like a printed table of contents with their ``(title, printed page)`` entries."""
    found = []
    in_toc = False
    for page, paragraphs in pages:
        text = " ".join(paragraphs)
        entries = _parse_toc_text(_TOC_MARKER.sub("", text))
        numbers = [number for _title, number in entries]
        ascending = sum(1 for a, b in zip(numbers, numbers[1:]) if b >= a)
        dense = len(entries) >= 4 and ascending >= 0.7 * (len(numbers) - 1)
        starts_toc = bool(_TOC_MARKER.match(paragraphs[0] if paragraphs else ""))
        if dense and (starts_toc or in_toc or len(entries) >= 8):
            found.append((page, entries))
            in_toc = True
        else:
            in_toc = starts_toc
    return found


def _find_title(title: str, pages: Sequence[tuple[int, str]], skip: set[int]) -> list[int]:
    """Pages containing the title's first words (6, then 3 words for spelling variants of subtitles)."""
    words = normalize_title(title).split()
    for count in (6, 3):
        if len(words) < min(count, 2) and count == 3:
            break
        needle = " ".join(words[:count])
        if not needle:
            return []
        hits = [page for page, text in pages if page not in skip and needle in text]
        if hits:
            return hits
    return []


def detect_from_toc(pages: Sequence[tuple[int, list[str]]]) -> list[Heading]:
    """Locate the printed TOC entries in reading order.

    Printed page numbers are only a hint (plates, blank pages and section
    numbers in place of pages are common), so each entry takes the first hit
    after the previous entry; the printed number only decides between hits if
    the page offset is stable across the book.
    """
    toc = _toc_entries(pages)
    if not toc:
        return []
    skip = {page for page, _ in toc}
    normalized_pages = [(page, normalize_title(" ".join(paragraphs))) for page, paragraphs in pages]
    entries = [entry for _page, page_entries in toc for entry in page_entries]
    candidates = [(title, printed, _find_title(title, normalized_pages, skip)) for title, printed in entries]
    offsets = [hits[0] - printed for _title, printed, hits in candidates if len(hits) == 1]
    stable = len(offsets) >= 3 and statistics.pstdev(offsets) <= 3
    offset = int(statistics.median(offsets)) if offsets else 0
    headings = []
    previous = 0
    for title, printed, hits in candidates:
        later = [hit for hit in hits if hit >= previous]
        if stable:
            expected = printed + offset
            pool = later or hits
            page = min(pool, key=lambda hit: abs(hit - expected)) if pool else expected
            if pool and abs(page - expected) > 3:
                page = expected
        elif later:
            page = later[0]
        else:
            continue
        previous = page
        headings.append(Heading(title, page, 1, "toc"))
    return headings


def detect_combined(pages: Sequence[tuple[int, list[str]]]) -> list[Heading]:
    """TOC entries plus heading paragraphs that no TOC entry already covers (same page ±1)."""
    toc = detect_from_toc(pages)
    extra = [
        heading for heading in detect_headings(pages)
        if not any(abs(entry.page - heading.page) <= PAGE_TOLERANCE and similarity(entry.title, heading.title) >= TITLE_SIMILARITY
                   for entry in toc)
    ]
    for heading in extra:
        heading_level = heading.level + 1 if toc and heading.level == 1 else heading.level
        toc.append(Heading(heading.title, heading.page, heading_level, "combined"))
    return sorted(toc, key=lambda heading: heading.page)


def drop_boilerplate(headings: Sequence[Heading], pages: Sequence[tuple[int, list[str]]]) -> list[Heading]:
    """Remove "headings" that recur on many pages (running heads, copyright footers)."""
    if len(pages) < 10:
        return list(headings)
    normalized = [normalize_title(" ".join(paragraphs)) for _page, paragraphs in pages]
    limit = max(5, 0.2 * len(pages))
    counts: dict[str, int] = {}
    kept = []
    for heading in headings:
        needle = " ".join(normalize_title(heading.title).split()[:6])
        if needle not in counts:
            counts[needle] = sum(1 for text in normalized if needle and needle in text)
        if counts[needle] <= limit:
            kept.append(heading)
    return kept


def detect(pages: Sequence[tuple[int, list[str]]], method: str) -> list[Heading]:
    if method == "heading":
        found = detect_headings(pages)
    elif method == "toc":
        found = detect_from_toc(pages)
    elif method == "combined":
        found = detect_combined(pages)
    else:
        raise ValueError(f"unknown structure method: {method}")
    return drop_boilerplate(found, pages)


# --- evaluation ------------------------------------------------------------------------


def evaluate(
    predicted: Sequence[Heading],
    reference: Sequence[Mapping[str, Any]],
    *,
    method: str = "",
    title_similarity: float = TITLE_SIMILARITY,
    page_tolerance: int = PAGE_TOLERANCE,
) -> Evaluation:
    """Greedy one-to-one matching: similar title and page within the tolerance."""
    by_page: dict[int, list[int]] = defaultdict(list)
    for pred_index, pred in enumerate(predicted):
        by_page[pred.page].append(pred_index)
    pairs = []
    for ref_index, ref in enumerate(reference):
        ref_page = int(ref.get("page_index", 0))
        nearby = [
            index for page in range(ref_page - page_tolerance, ref_page + page_tolerance + 1) for index in by_page.get(page, [])
        ]
        for pred_index in nearby:
            pred = predicted[pred_index]
            score = similarity(str(ref.get("title", "")), pred.title)
            if score >= title_similarity:
                pairs.append((score, -abs(int(ref.get("page_index", 0)) - pred.page), ref_index, pred_index))
    pairs.sort(reverse=True)
    used_ref: set[int] = set()
    used_pred: set[int] = set()
    for _score, _distance, ref_index, pred_index in pairs:
        if ref_index in used_ref or pred_index in used_pred:
            continue
        used_ref.add(ref_index)
        used_pred.add(pred_index)
    per_level: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for index, ref in enumerate(reference):
        level = int(ref.get("level", 1) or 1)
        per_level[level][1] += 1
        per_level[level][0] += index in used_ref
    titled = [index for index, ref in enumerate(reference) if is_titled(str(ref.get("title", "")))]
    return Evaluation(
        method=method,
        titled_reference=len(titled),
        titled_matched=sum(1 for index in titled if index in used_ref),
        predicted=len(predicted),
        reference=len(reference),
        matched=len(used_ref),
        level_recall={level: hits / total for level, (hits, total) in per_level.items() if total},
        misses=[f"S.{ref.get('page_index')} {ref.get('title')}" for i, ref in enumerate(reference) if i not in used_ref],
        false_hits=[f"S.{pred.page} {pred.title}" for i, pred in enumerate(predicted) if i not in used_pred],
    )


def outline_markdown(title: str, headings: Sequence[Heading]) -> str:
    lines = [f"# Erkannte Gliederung: {title}", ""]
    for heading in headings:
        lines.append(f"{'  ' * max(0, heading.level - 1)}- {heading.title} (Seite {heading.page})")
    return "\n".join(lines) + "\n"
