"""Extract domain terms and semantic signals from Jira CSV issues."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ki_core.config import Config
from ki_knowledge.integrations.embeddings import OllamaEmbeddingProvider, TFIDFEmbeddingProvider
from ki_knowledge.integrations.jira_cache import JiraIssueCache
from ki_knowledge.integrations.jira_csv import JiraCSVImporter


def _knowledge_root(config: Config) -> Path:
    if config.knowledge_data_root:
        return Path(config.knowledge_data_root).expanduser()
    legacy_root = os.getenv("KICLI_DATA_ROOT", "").strip()
    if legacy_root:
        return Path(legacy_root).expanduser()
    return Path.home() / "dev_data" / "ki-knowledge"


def _jira_csv_path(config: Config) -> str:
    return os.getenv("JIRA_CSV_PATH", str(_knowledge_root(config) / "jira" / "default" / "issues.csv")).strip()


def _jira_cache_db(config: Config) -> str:
    return os.getenv("JIRA_CACHE_DB", config.knowledge_cache_db or str(_knowledge_root(config) / ".jira_cache.sqlite")).strip()


def _build_embedder(cache: JiraIssueCache, ollama_url: str, embed_model: str):
    try:
        embedder = OllamaEmbeddingProvider(base_url=ollama_url, model=embed_model)
        embedder.embed("probe")
        return embedder, embed_model, f"Ollama:{embed_model}"
    except Exception:
        tfidf = TFIDFEmbeddingProvider()
        tfidf.fit(cache.semantic_text_corpus(issue_limit=5000))
        return tfidf, "tfidf-fields", "TF-IDF (local)"


def run(limit_terms: int, limit_hits: int, query: str) -> None:
    config = Config.from_env()
    csv_path = _jira_csv_path(config)
    if not csv_path:
        print("CSV path missing! Set JIRA_CSV_PATH in .env")
        sys.exit(1)

    csv_encoding = os.getenv("JIRA_CSV_ENCODING", "utf-8-sig").strip() or "utf-8-sig"
    csv_delimiter = os.getenv("JIRA_CSV_DELIMITER", "").strip() or None
    cache_db = _jira_cache_db(config)
    ollama_url = os.getenv("OLLAMA_BASE_URL", config.ollama_base_url or "http://localhost:11434").strip()
    embed_model = os.getenv("JIRA_EMBED_MODEL", config.knowledge_embed_model or "nomic-embed-text").strip()

    cache = JiraIssueCache(cache_db)
    issues = JiraCSVImporter.from_csv(csv_path, encoding=csv_encoding, delimiter=csv_delimiter)
    ingested = cache.ingest_issues(issues)
    print(f"Imported: {ingested} issues")

    terms = cache.extract_domain_terms(limit=limit_terms, min_count=2)
    print("\nTop domain terms (from labels + description/comments):")
    for idx, term in enumerate(terms, 1):
        print(
            f"{idx:>2}. {term.term:<22} "
            f"count={term.count:<3} issues={term.issue_count:<3} sources={','.join(term.sources)}"
        )

    embedder, embedding_model, backend_label = _build_embedder(cache, ollama_url, embed_model)
    built = cache.build_field_embeddings(embedder, embedding_model=embedding_model)
    print(f"\nField embeddings: {built} ({backend_label})")

    if query.strip():
        print(f"\nSemantic hits for query: {query!r}")
        hits = cache.semantic_field_search(
            query=query,
            backend=embedder,
            embedding_model=embedding_model,
            limit=limit_hits,
        )
        if not hits:
            print("  (no semantic matches)")
        for idx, hit in enumerate(hits, 1):
            print(
                f"{idx:>2}. [{hit.issue_key}] {hit.field_kind}/{hit.field_name} "
                f"score={hit.score:.3f} terms={','.join(hit.top_terms)}"
            )
            print(f"    {hit.excerpt}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Jira domain and semantic field analysis")
    parser.add_argument(
        "--terms",
        type=int,
        default=20,
        help="Maximum number of domain terms to print (default: 20)",
    )
    parser.add_argument(
        "--hits",
        type=int,
        default=8,
        help="Maximum number of semantic search hits (default: 8)",
    )
    parser.add_argument(
        "--query",
        default="auth login timeout",
        help="Semantic query over description/comment fields",
    )
    args = parser.parse_args()
    run(limit_terms=args.terms, limit_hits=args.hits, query=args.query)
