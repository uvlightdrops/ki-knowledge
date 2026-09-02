"""Embedding helpers for knowledge blocks."""

from __future__ import annotations

import re
from collections import Counter
from typing import Protocol

from ki_knowledge.integrations.knowledge_store import KnowledgeStore


class EmbeddingBackend(Protocol):
    """Simple embedding backend interface."""

    def fit(self, texts: list[str]) -> None:
        ...

    def embed(self, text: str) -> list[float]:
        ...


class SimpleBagOfWordsEmbeddingBackend:
    """A lightweight local embedding implementation using bag-of-words."""

    def __init__(self) -> None:
        self.vocabulary: list[str] = []

    def fit(self, texts: list[str]) -> None:
        tokens = set()
        for text in texts:
            tokens.update(self._tokenize(text))
        self.vocabulary = sorted(tokens)

    def embed(self, text: str) -> list[float]:
        if not self.vocabulary:
            self.fit([text])

        counts = Counter(self._tokenize(text))
        total = sum(counts.values()) or 1
        return [counts.get(token, 0) / total for token in self.vocabulary]

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"[a-zA-Z0-9_]+", text.lower())


class BlockEmbeddingService:
    """Build and persist embeddings for knowledge blocks."""

    def __init__(self, backend: EmbeddingBackend):
        self.backend = backend

    def build_embeddings(self, store: KnowledgeStore, model_name: str = "bag_of_words") -> int:
        blocks = store.list_blocks()
        if not blocks:
            return 0
        texts = [block.content for block in blocks]
        self.backend.fit(texts)
        for block in blocks:
            store.add_embedding(block.id, model_name, self.backend.embed(block.content))
        return len(blocks)
