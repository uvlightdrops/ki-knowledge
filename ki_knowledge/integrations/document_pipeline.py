"""Per-document processing stages (book pipeline) with status, version and metrics.

Every document (currently: imported or failed PDFs of a domain) moves through a fixed
sequence of stages. Each stage writes one row per document into
``document_stage_status`` (status, stage version, metrics, error). Overviews read only
this table, so they stay fast; derived stages are recalculated by
:func:`sync_documents` and pipeline workers record their own results with
:meth:`DocumentStageStore.record`.

Stage versions make reprocessing explicit: a row whose ``version`` is lower than the
stage's current version counts as *stale* and needs to run again.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from ki_knowledge.integrations.sql_backend import StoreTarget, connect, json_text


@dataclass(frozen=True)
class Stage:
    key: str
    label: str
    version: int
    description: str
    measures_blocks: bool = False


STAGES: tuple[Stage, ...] = (
    Stage("ingest", "Text importiert", 1, "Text (PDF/TEI) extrahiert und als Blöcke gespeichert."),
    Stage("quality", "Textqualität", 1, "Zeichen pro Seite, leere Seiten, wiederkehrende Kopfzeilen; Hinweis auf OCR-Bedarf."),
    Stage("structure", "Gliederung", 1, "Inhaltsverzeichnis/Kapitelstruktur erkannt und mit Seiten verknüpft."),
    Stage("segments", "Abschnitte", 1, "Semantische Abschnitte statt Seitenblöcke."),
    Stage("embeddings", "Embeddings", 1, "Vektoren für die semantische Suche.", measures_blocks=True),
    Stage("terms", "Begriffe", 1, "Blöcke mit Begriffen des Semantic Layers verknüpft.", measures_blocks=True),
    Stage("review", "Geprüft", 1, "Redaktionelle Prüfung pro Buch (Stichprobe)."),
)
STAGE_KEYS = tuple(stage.key for stage in STAGES)
STAGE_BY_KEY = {stage.key: stage for stage in STAGES}

STATUS_LABELS: dict[str, str] = {
    "pending": "Offen",
    "partial": "Teilweise",
    "warning": "Mit Hinweisen",
    "done": "Erledigt",
    "failed": "Fehlgeschlagen",
    "stale": "Veraltet",
}
COMPLETE_STATUSES = frozenset({"done", "warning"})

FLAG_LABELS: dict[str, str] = {
    "needs_ocr": "OCR nötig",
    "many_empty_pages": "Viele leere Seiten",
    "boilerplate": "Viele Kopfzeilen",
}

# Thresholds of the quality stage (characters per page of a text layer, ratios 0..1).
MIN_CHARS_PER_PAGE = 300
MAX_EMPTY_PAGE_RATIO = 0.2
MAX_BOILERPLATE_RATIO = 0.5
_PREFIX_LENGTH = 40

_SQLITE_MAX_VARIABLES = 900


@dataclass
class StageState:
    status: str = "pending"
    version: int = 0
    metrics: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    updated_at: str = ""


@dataclass
class DocumentProgress:
    source_id: str
    domain: str
    stages: dict[str, StageState] = field(default_factory=dict)

    def state(self, stage_key: str) -> StageState:
        return self.stages.get(stage_key) or StageState()

    def effective_status(self, stage_key: str) -> str:
        state = self.state(stage_key)
        stage = STAGE_BY_KEY[stage_key]
        if state.status in COMPLETE_STATUSES and state.version < stage.version:
            return "stale"
        return state.status

    @property
    def completed_stages(self) -> int:
        return sum(1 for key in STAGE_KEYS if self.effective_status(key) in COMPLETE_STATUSES)

    @property
    def flags(self) -> list[str]:
        return list(self.state("quality").metrics.get("flags", []))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _chunked(items: list, size: int = _SQLITE_MAX_VARIABLES) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


class DocumentStageStore:
    """``document_stage_status`` table next to the knowledge store (same target/schema)."""

    def __init__(self, target: StoreTarget | str):
        self.target = target if isinstance(target, StoreTarget) else StoreTarget.parse(target, schema="knowledge")
        self._init_schema()

    def _init_schema(self) -> None:
        with connect(self.target) as conn:
            metrics_type = "jsonb" if conn.dialect == "postgres" else "TEXT"
            metrics_default = "'{}'::jsonb" if conn.dialect == "postgres" else "'{}'"
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS document_stage_status (
                    source_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    status TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 0,
                    metrics_json {metrics_type} NOT NULL DEFAULT {metrics_default},
                    error TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (source_id, stage)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_document_stage_status_domain "
                "ON document_stage_status(domain, stage, status)"
            )

    def record(
        self,
        source_id: str,
        stage: str,
        *,
        domain: str,
        status: str,
        version: int | None = None,
        metrics: Mapping[str, Any] | None = None,
        error: str = "",
    ) -> None:
        self.record_many([(source_id, stage, domain, status, version, metrics, error)])

    def record_many(self, rows: Iterable[tuple]) -> int:
        """Upsert ``(source_id, stage, domain, status, version, metrics, error)`` rows."""
        now = _now()
        payload = []
        for source_id, stage, domain, status, version, metrics, error in rows:
            if stage not in STAGE_BY_KEY:
                raise ValueError(f"unknown stage: {stage}")
            if status not in STATUS_LABELS or status == "stale":
                raise ValueError(f"invalid status: {status}")
            payload.append(
                (
                    source_id,
                    stage,
                    domain,
                    status,
                    STAGE_BY_KEY[stage].version if version is None else int(version),
                    json.dumps(dict(metrics or {}), ensure_ascii=False),
                    str(error or "")[:2000],
                    now,
                )
            )
        if not payload:
            return 0
        with connect(self.target) as conn:
            conn.executemany(
                """
                INSERT INTO document_stage_status
                    (source_id, stage, domain, status, version, metrics_json, error, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, stage) DO UPDATE SET
                    domain = excluded.domain,
                    status = excluded.status,
                    version = excluded.version,
                    metrics_json = excluded.metrics_json,
                    error = excluded.error,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return len(payload)

    def delete_missing(self, domain: str, keep_source_ids: Iterable[str]) -> int:
        """Remove rows of a domain whose document no longer exists."""
        keep = set(keep_source_ids)
        with connect(self.target) as conn:
            existing = [
                row[0]
                for row in conn.execute(
                    "SELECT DISTINCT source_id FROM document_stage_status WHERE domain = ?", (domain,)
                ).fetchall()
            ]
            stale = [source_id for source_id in existing if source_id not in keep]
            for chunk in _chunked(stale):
                placeholders = ",".join("?" for _ in chunk)
                conn.execute(
                    f"DELETE FROM document_stage_status WHERE domain = ? AND source_id IN ({placeholders})",
                    [domain, *chunk],
                )
        return len(stale)

    def documents(self, domain: str) -> list[DocumentProgress]:
        with connect(self.target) as conn:
            rows = conn.execute(
                "SELECT source_id, stage, status, version, metrics_json, error, updated_at "
                "FROM document_stage_status WHERE domain = ? ORDER BY source_id",
                (domain,),
            ).fetchall()
        documents: dict[str, DocumentProgress] = {}
        for row in rows:
            document = documents.setdefault(row[0], DocumentProgress(source_id=row[0], domain=domain))
            if row[1] not in STAGE_BY_KEY:
                continue
            metrics = row[4]
            if isinstance(metrics, str):
                metrics = json.loads(metrics or "{}")
            document.stages[row[1]] = StageState(
                status=row[2], version=int(row[3] or 0), metrics=dict(metrics or {}), error=row[5] or "", updated_at=row[6] or ""
            )
        return list(documents.values())

    def last_updated(self, domain: str) -> str:
        with connect(self.target) as conn:
            row = conn.execute(
                "SELECT MAX(updated_at) FROM document_stage_status WHERE domain = ?", (domain,)
            ).fetchone()
        return str(row[0] or "") if row else ""


# --- derived stages ---------------------------------------------------------------


def quality_metrics(pages_total: int, pages: Mapping[str, int], prefixes: Iterable[str]) -> dict[str, Any]:
    """Quality metrics of one document.

    ``pages`` maps a page label to the characters stored for it, ``prefixes`` are the
    opening characters of every block (to detect repeated running headers).
    """
    prefix_list = [" ".join(str(prefix).split()).lower() for prefix in prefixes]
    prefix_list = [prefix for prefix in prefix_list if prefix]
    chars = sum(int(value or 0) for value in pages.values())
    pages_with_text = sum(1 for value in pages.values() if int(value or 0) > 0)
    total = max(int(pages_total or 0), pages_with_text)
    chars_per_page = round(chars / total) if total else 0
    empty_ratio = round(1 - pages_with_text / total, 3) if total else 1.0
    top_count = Counter(prefix_list).most_common(1)[0][1] if prefix_list else 0
    boilerplate_ratio = round(top_count / len(prefix_list), 3) if len(prefix_list) >= 5 else 0.0
    flags = []
    if chars_per_page < MIN_CHARS_PER_PAGE:
        flags.append("needs_ocr")
    if empty_ratio > MAX_EMPTY_PAGE_RATIO:
        flags.append("many_empty_pages")
    if boilerplate_ratio > MAX_BOILERPLATE_RATIO:
        flags.append("boilerplate")
    return {
        "pages_total": total,
        "pages_with_text": pages_with_text,
        "chars": chars,
        "chars_per_page": chars_per_page,
        "empty_page_ratio": empty_ratio,
        "boilerplate_ratio": boilerplate_ratio,
        "flags": flags,
    }


def quality_status(metrics: Mapping[str, Any]) -> str:
    if not metrics.get("chars"):
        return "failed"
    return "warning" if metrics.get("flags") else "done"


def coverage_status(done: int, total: int) -> str:
    if total and done >= total:
        return "done"
    return "partial" if done else "pending"


@dataclass(frozen=True)
class DocumentInput:
    """A document known to the pipeline: imported source and/or its newest import job."""

    source_id: str
    title: str = ""
    path: str = ""
    imported: bool = False
    pages_total: int = 0
    job_status: str = ""
    job_error: str = ""
    extra: Mapping[str, Any] = field(default_factory=dict)


def _block_facts(target: StoreTarget, source_ids: list[str]) -> dict[str, dict[str, Any]]:
    facts: dict[str, dict[str, Any]] = {
        source_id: {"blocks": 0, "pages": {}, "prefixes": [], "block_ids": []} for source_id in source_ids
    }
    if not source_ids:
        return facts
    with connect(target) as conn:
        sid = json_text("metadata_json", "source_id", conn.dialect)
        title = json_text("metadata_json", "title", conn.dialect)
        for chunk in _chunked(source_ids):
            placeholders = ",".join("?" for _ in chunk)
            rows = conn.execute(
                f"SELECT {sid}, {title}, id, LENGTH(content), SUBSTR(content, 1, {_PREFIX_LENGTH}) "
                f"FROM knowledge_blocks WHERE {sid} IN ({placeholders})",
                chunk,
            ).fetchall()
            for row in rows:
                source_id, page, block_id, length, prefix = (row[index] for index in range(5))
                entry = facts[source_id]
                entry["blocks"] += 1
                entry["block_ids"].append(block_id)
                key = str(page or block_id)
                entry["pages"][key] = entry["pages"].get(key, 0) + int(length or 0)
                entry["prefixes"].append(prefix or "")
    return facts


def _embedded_block_ids(target: StoreTarget, block_ids: list[str]) -> set[str]:
    found: set[str] = set()
    with connect(target) as conn:
        for chunk in _chunked(block_ids):
            placeholders = ",".join("?" for _ in chunk)
            found.update(
                row[0]
                for row in conn.execute(
                    f"SELECT block_id FROM knowledge_embeddings WHERE block_id IN ({placeholders})", chunk
                ).fetchall()
            )
    return found


def sync_documents(
    stage_store: DocumentStageStore,
    knowledge_target: StoreTarget,
    domain: str,
    documents: Iterable[DocumentInput],
    *,
    linked_record_ids: set[str] | None = None,
    prune: bool = True,
) -> dict[str, int]:
    """Recalculate the derived stages (ingest, quality, embeddings, terms) of documents.

    Stages produced by dedicated workers (structure, segments, review) are only
    initialised as ``pending`` if they have no row yet; existing results are kept.
    With ``prune`` the given documents are the complete set of the domain and rows of
    other documents are removed.
    """
    docs = {doc.source_id: doc for doc in documents}
    imported_ids = sorted(source_id for source_id, doc in docs.items() if doc.imported)
    facts = _block_facts(knowledge_target, imported_ids)
    embedded = _embedded_block_ids(
        knowledge_target, [block_id for fact in facts.values() for block_id in fact["block_ids"]]
    )
    linked = linked_record_ids or set()
    existing = {doc.source_id: doc for doc in stage_store.documents(domain)}

    rows: list[tuple] = []
    counts = Counter()
    for source_id, doc in docs.items():
        fact = facts.get(source_id, {"blocks": 0, "pages": {}, "prefixes": [], "block_ids": []})
        base = {"title": doc.title, "path": doc.path}
        if doc.imported and fact["blocks"]:
            ingest_status, ingest_error = "done", ""
        elif doc.job_status in {"failed", "done"}:
            ingest_status, ingest_error = "failed", doc.job_error or "Keine Blöcke importiert"
        else:
            ingest_status, ingest_error = "pending", ""
        rows.append(
            (source_id, "ingest", domain, ingest_status, None,
             {**base, **doc.extra, "blocks": fact["blocks"], "pages_total": doc.pages_total, "job_status": doc.job_status},
             ingest_error)
        )
        counts[f"ingest:{ingest_status}"] += 1
        if ingest_status != "done":
            for key in ("quality", "embeddings", "terms"):
                rows.append((source_id, key, domain, "pending", 0, {}, ""))
        else:
            metrics = quality_metrics(doc.pages_total, fact["pages"], fact["prefixes"])
            rows.append((source_id, "quality", domain, quality_status(metrics), None, metrics, ""))
            block_ids = fact["block_ids"]
            done_embeddings = sum(1 for block_id in block_ids if block_id in embedded)
            done_terms = sum(1 for block_id in block_ids if block_id in linked)
            rows.append((source_id, "embeddings", domain, coverage_status(done_embeddings, len(block_ids)), None,
                         {"blocks": len(block_ids), "blocks_done": done_embeddings}, ""))
            rows.append((source_id, "terms", domain, coverage_status(done_terms, len(block_ids)), None,
                         {"blocks": len(block_ids), "blocks_done": done_terms}, ""))
        previous = existing.get(source_id)
        for key in ("structure", "segments", "review"):
            if previous is None or key not in previous.stages:
                rows.append((source_id, key, domain, "pending", 0, {}, ""))
    stage_store.record_many(rows)
    removed = stage_store.delete_missing(domain, docs.keys()) if prune else 0
    return {"documents": len(docs), "rows": len(rows), "removed": removed, **dict(counts)}


# --- overview -----------------------------------------------------------------------


def funnel(documents: list[DocumentProgress]) -> list[dict[str, Any]]:
    """Per stage: completed documents (and blocks for block-measured stages) in percent."""
    total = len(documents)
    result = []
    for stage in STAGES:
        statuses = Counter(document.effective_status(stage.key) for document in documents)
        done = statuses["done"] + statuses["warning"]
        entry: dict[str, Any] = {
            "key": stage.key,
            "label": stage.label,
            "description": stage.description,
            "version": stage.version,
            "total": total,
            "done": done,
            "percent": round(100 * done / total, 1) if total else 0.0,
            "statuses": {key: statuses.get(key, 0) for key in STATUS_LABELS},
        }
        if stage.measures_blocks:
            blocks = sum(int(document.state(stage.key).metrics.get("blocks", 0)) for document in documents)
            blocks_done = sum(int(document.state(stage.key).metrics.get("blocks_done", 0)) for document in documents)
            entry["blocks"] = blocks
            entry["blocks_done"] = blocks_done
            entry["blocks_percent"] = round(100 * blocks_done / blocks, 1) if blocks else 0.0
        result.append(entry)
    return result


def record_document(knowledge_target: StoreTarget, domain: str, document: DocumentInput) -> None:
    """Update the stages of a single document, e.g. right after its import job finished."""
    sync_documents(DocumentStageStore(knowledge_target), knowledge_target, domain, [document], prune=False)
