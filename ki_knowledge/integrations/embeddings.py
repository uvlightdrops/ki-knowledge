"""Embedding providers for semantic retrieval."""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from typing import Iterable

import requests


class OllamaEmbeddingProvider:
    """Embedding provider backed by local Ollama."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "nomic-embed-text",
        timeout: int = 120,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def embed(self, text: str) -> list[float]:
        # Try modern /api/embed endpoint first (Ollama >=0.1.26)
        try:
            response = requests.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": text},
                timeout=self.timeout,
            )
            if response.status_code == 404:
                # model not found — give clear install hint
                raise RuntimeError(
                    f"Embedding model '{self.model}' not found in Ollama. "
                    f"Install it with: ollama pull {self.model}\n"
                    f"Good alternatives: ollama pull nomic-embed-text"
                )
            response.raise_for_status()
            data = response.json()
            vectors = data.get("embeddings") or []
            if vectors:
                return vectors[0]
        except RuntimeError:
            raise
        except Exception:
            pass

        # Fallback to legacy /api/embeddings endpoint (Ollama <0.1.26)
        response = requests.post(
            f"{self.base_url}/api/embeddings",
            json={"model": self.model, "prompt": text},
            timeout=self.timeout,
        )
        if response.status_code == 404:
            raise RuntimeError(
                f"Embedding model '{self.model}' not found in Ollama. "
                f"Install it with: ollama pull {self.model}\n"
                f"Good alternatives: ollama pull nomic-embed-text"
            )
        response.raise_for_status()
        data = response.json()
        return data.get("embedding", [])


class TFIDFEmbeddingProvider:
    """
    Lightweight TF-IDF embedding provider — no GPU, no model download needed.

    Fits a vocabulary over a corpus of texts, then produces sparse-but-useful
    TF-IDF vectors for semantic similarity. Good enough for hundreds of issues
    and works entirely offline.
    """

    def __init__(self, min_df: int = 1, max_features: int = 2048):
        self.min_df = min_df
        self.max_features = max_features
        self._vocab: dict[str, int] = {}
        self._idf: list[float] = []
        self._fitted = False

    def fit(self, texts: Iterable[str]) -> "TFIDFEmbeddingProvider":
        corpus = [self._tokenize(t) for t in texts]
        df: Counter[str] = Counter()
        for tokens in corpus:
            df.update(set(tokens))

        n_docs = len(corpus)
        qualified = [
            term for term, count in df.most_common() if count >= self.min_df
        ][: self.max_features]

        self._vocab = {term: idx for idx, term in enumerate(qualified)}
        self._idf = [
            math.log((1 + n_docs) / (1 + df[term])) + 1.0
            for term in qualified
        ]
        self._fitted = True
        return self

    def embed(self, text: str) -> list[float]:
        if not self._fitted:
            raise RuntimeError("TFIDFEmbeddingProvider must be fit() before embed().")
        tokens = self._tokenize(text)
        tf: Counter[str] = Counter(tokens)
        total = max(len(tokens), 1)
        vec = [0.0] * len(self._vocab)
        for term, count in tf.items():
            idx = self._vocab.get(term)
            if idx is not None:
                vec[idx] = (count / total) * self._idf[idx]
        return vec

    def _tokenize(self, text: str) -> list[str]:
        normalized = (
            unicodedata.normalize("NFKD", text or "")
            .encode("ascii", "ignore")
            .decode("ascii")
            .lower()
        )
        return [tok for tok in re.findall(r"[a-z0-9]{3,}", normalized)]
