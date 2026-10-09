"""Embed knowledge blocks with a local Ollama model, resumable and in batches.

Only blocks without an up-to-date vector of the model are processed, so the job
can be interrupted and restarted at any time.  ``nomic-embed-text`` expects task
prefixes: documents are embedded as ``search_document: …`` and queries as
``search_query: …``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Iterable, Protocol

from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.knowledge.models import KnowledgeBlockRecord

DEFAULT_EMBED_MODEL = "nomic-embed-text"
# nomic-embed-text has a 2048-token context in Ollama; ~6000 chars of German prose stay below it.
MAX_INPUT_CHARS = 6000

_PREFIXES: dict[str, tuple[str, str]] = {
    "nomic-embed-text": ("search_document: ", "search_query: "),
}


class BatchEmbedder(Protocol):
    def embed_many(self, texts: list[str]) -> list[list[float]]:
        ...


def model_key(model: str) -> str:
    """Model name without the ``:latest`` tag, used as the stored model id."""
    return model.split(":", 1)[0] if model.endswith(":latest") else model


def document_text(record: KnowledgeBlockRecord, model: str) -> str:
    prefix = _PREFIXES.get(model_key(model), ("", ""))[0]
    title = (record.title or "").strip()
    body = (record.content or "").strip()
    text = f"{title}\n{body}" if title and not title.lower().startswith("page ") else body
    return prefix + text[:MAX_INPUT_CHARS]


def query_text(query: str, model: str) -> str:
    return _PREFIXES.get(model_key(model), ("", ""))[1] + query.strip()


@dataclass
class EmbeddingRun:
    model: str
    embedded: int = 0
    failed: int = 0
    batches: int = 0
    seconds: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def rate(self) -> float:
        return self.embedded / self.seconds if self.seconds else 0.0


def _note(run: EmbeddingRun, message: str, keep: int = 20) -> None:
    if len(run.errors) < keep:
        run.errors.append(message)


def embed_pending_blocks(
    store: KnowledgeStore,
    embedder: BatchEmbedder,
    source_ids: Iterable[str],
    *,
    model: str = DEFAULT_EMBED_MODEL,
    batch_size: int = 32,
    limit: int | None = None,
    progress: Callable[[EmbeddingRun], None] | None = None,
) -> EmbeddingRun:
    """Embed missing/outdated blocks of ``source_ids`` until done or ``limit`` is reached."""
    ids = list(source_ids)
    key = model_key(model)
    run = EmbeddingRun(model=key)
    started = time.monotonic()
    skipped: set[str] = set()
    while limit is None or run.embedded + run.failed < limit:
        size = batch_size if limit is None else min(batch_size, limit - run.embedded - run.failed)
        candidates = store.blocks_needing_embeddings(ids, key, limit=size + len(skipped))
        batch = [record for record in candidates if record.block_id not in skipped][:size]
        if not batch:
            break
        try:
            vectors = embedder.embed_many([document_text(record, key) for record in batch])
        except Exception as exc:  # One bad batch: retry block by block to isolate the culprit.
            _note(run, f"batch error: {exc}")
            vectors = []
            for record in batch:
                try:
                    vectors.extend(embedder.embed_many([document_text(record, key)]))
                except Exception as single_exc:
                    skipped.add(record.block_id)
                    run.failed += 1
                    _note(run, f"{record.block_id}: {single_exc}")
                    vectors.append([])
        pairs = [(record.block_id, vector) for record, vector in zip(batch, vectors) if vector]
        run.embedded += store.add_embeddings(key, pairs)
        run.batches += 1
        run.seconds = time.monotonic() - started
        if progress is not None:
            progress(run)
    run.seconds = time.monotonic() - started
    return run
