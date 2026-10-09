"""Detect the outline of every book of a domain and check it against reference outlines.

Results go to the ``detected_structure`` artifact of each source and to the
``structure`` stage of the book pipeline.  Books with a ``reference_structure``
artifact (TEI imports) get precision/recall metrics; others are marked as
unverified.
"""

from __future__ import annotations

import hashlib
from typing import Any, Iterable

from django.conf import settings

from ki_knowledge.integrations import structure_eval
from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.knowledge.models import KnowledgeArtifact

from .book_pipeline import BOOK_SOURCE_TYPES, stage_store
from .domain_paths import normalize_semantic_domain
from .source_workflow import REFERENCE_STRUCTURE_ARTIFACT

DETECTED_STRUCTURE_ARTIFACT = "detected_structure"
DEFAULT_METHOD = "combined"
# Thresholds for the stage status of books with a reference outline.
DONE_TITLED_RECALL = 0.8
DONE_PRECISION = 0.7
WARNING_TITLED_RECALL = 0.5


def _artifact_id(source_id: str, artifact_type: str) -> str:
    return hashlib.sha256(f"{source_id}:{artifact_type}".encode("utf-8")).hexdigest()[:24]


def stage_status(evaluation: dict[str, Any] | None, sections: int) -> str:
    if evaluation is None:
        return "warning" if sections >= 3 else "partial"
    if evaluation["titled_recall"] >= DONE_TITLED_RECALL and evaluation["precision"] >= DONE_PRECISION:
        return "done"
    if evaluation["titled_recall"] >= WARNING_TITLED_RECALL:
        return "warning"
    return "partial"


def analyze_source(
    store: KnowledgeStore,
    source: Any,
    *,
    method: str = DEFAULT_METHOD,
    reference: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Detect, evaluate (if a reference exists) and also evaluate the flattened PDF-like variant."""
    records, _total = store.query_records([source.source_id])
    pages = structure_eval.pages_from_records(records)
    headings = structure_eval.detect(pages, method)
    result: dict[str, Any] = {
        "source_id": source.source_id,
        "title": source.title,
        "method": method,
        "sections": len(headings),
        "headings": headings,
        "evaluation": None,
        "evaluation_flat": None,
    }
    if reference:
        result["evaluation"] = structure_eval.evaluate(headings, reference, method=method).to_dict()
        flat_pages = structure_eval.pages_from_records(records, flat=True)
        flat = structure_eval.detect(flat_pages, method)
        result["evaluation_flat"] = structure_eval.evaluate(flat, reference, method=method).to_dict()
    return result


def analyze_domain(
    domain: str,
    *,
    method: str = DEFAULT_METHOD,
    source_ids: Iterable[str] | None = None,
    write: bool = True,
) -> list[dict[str, Any]]:
    from .knowledge_summary import _domain_scoped_sources

    resolved = normalize_semantic_domain(domain)
    store = KnowledgeStore(settings.KNOWLEDGE_STORE_TARGET)
    wanted = set(source_ids or [])
    references = {
        artifact.source_id: list(artifact.metadata.get("sections", []))
        for artifact in store.list_artifacts(artifact_type=REFERENCE_STRUCTURE_ARTIFACT)
    }
    stages = stage_store()
    results = []
    for source in _domain_scoped_sources(resolved):
        if source.source_type not in BOOK_SOURCE_TYPES or (wanted and source.source_id not in wanted):
            continue
        result = analyze_source(store, source, method=method, reference=references.get(source.source_id))
        results.append(result)
        if not write:
            continue
        headings = result["headings"]
        store.upsert_artifact(
            KnowledgeArtifact(
                artifact_id=_artifact_id(source.source_id, DETECTED_STRUCTURE_ARTIFACT),
                artifact_type=DETECTED_STRUCTURE_ARTIFACT,
                source_id=source.source_id,
                source_block_ids=[],
                content=structure_eval.outline_markdown(source.title, headings),
                metadata={
                    "method": method,
                    "headings": [heading.to_dict() for heading in headings],
                    "evaluation": result["evaluation"],
                    "evaluation_flat": result["evaluation_flat"],
                },
            )
        )
        evaluation = result["evaluation"]
        metrics: dict[str, Any] = {"method": method, "sections": len(headings), "verified": evaluation is not None}
        if evaluation is not None:
            metrics.update({key: evaluation[key] for key in ("reference", "precision", "recall", "f1", "titled_recall")})
            metrics["titled_recall_flat"] = result["evaluation_flat"]["titled_recall"]
        stages.record(
            source.source_id,
            "structure",
            domain=resolved,
            status=stage_status(evaluation, len(headings)),
            metrics=metrics,
            error="" if headings else "Keine Gliederung erkannt",
        )
    return results
