"""Hybrid semantic+lexical retrieval over Jira cache."""

from pathlib import Path
import argparse
import os
import sys

# Allow direct execution via "python examples/jira_hybrid_search.py"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ki_core.config import Config
from ki_knowledge.integrations.embeddings import OllamaEmbeddingProvider, TFIDFEmbeddingProvider
from ki_knowledge.integrations.jira_cache import JiraIssueCache
from ki_knowledge.integrations.jira_csv import JiraCSVImporter


def build_embedder(cache: JiraIssueCache, ollama_url: str, embed_model: str):
    """Build embedding backend; fall back to TF-IDF if Ollama model missing."""
    try:
        embedder = OllamaEmbeddingProvider(base_url=ollama_url, model=embed_model)
        embedder.embed("probe")
        return embedder, embed_model, f"Ollama:{embed_model}"
    except Exception as e:
        print(f"⚠  Ollama embedding not available ({e})")
        print("   Falling back to local TF-IDF embeddings.")
        print("   For better quality: ollama pull nomic-embed-text")
        tfidf = TFIDFEmbeddingProvider()
        tfidf.fit(i.full_text for i in cache.list_issues(limit=5000))
        return tfidf, "tfidf", "TF-IDF (local)"


def run_queries(queries: list[str], limit: int) -> None:
    Config.from_env()

    csv_path = os.getenv("JIRA_CSV_PATH", "").strip()
    csv_encoding = os.getenv("JIRA_CSV_ENCODING", "utf-8-sig").strip() or "utf-8-sig"
    csv_delimiter = os.getenv("JIRA_CSV_DELIMITER", "").strip() or None
    cache_db = os.getenv("JIRA_CACHE_DB", str(PROJECT_ROOT / ".jira_cache.sqlite")).strip()
    refresh_cache = os.getenv("JIRA_CACHE_REFRESH", "false").lower() in ("1", "true", "yes")
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    embed_model = os.getenv("JIRA_EMBED_MODEL", "nomic-embed-text").strip()

    if not csv_path:
        print("CSV path missing! Set JIRA_CSV_PATH in .env")
        sys.exit(1)

    cache = JiraIssueCache(cache_db)
    if refresh_cache or cache.issue_count() == 0:
        issues = JiraCSVImporter.from_csv(csv_path, encoding=csv_encoding, delimiter=csv_delimiter)
        ingested = cache.ingest_issues(issues)
        print(f"Cache updated: {ingested} issues")

    embedder, embed_model, embed_label = build_embedder(cache, ollama_url, embed_model)
    embedded = cache.build_embeddings(embedder, embedding_model=embed_model)
    print(f"Embeddings ready: {embedded} ({embed_label})\n")

    for query in queries:
        hits = cache.hybrid_search(query, backend=embedder, embedding_model=embed_model, limit=limit)
        print(f"Query: {query!r}")
        if not hits:
            print("  (keine Treffer)\n")
            continue
        for idx, hit in enumerate(hits, 1):
            print(
                f"  {idx}. [{hit.issue.key}] {hit.issue.summary}"
                f"  (score={hit.combined_score:.3f} lex={hit.lexical_score:.3f} sem={hit.semantic_score:.3f})"
            )
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hybrid Jira issue search")
    parser.add_argument("query", nargs="+", help="One or more search queries")
    parser.add_argument(
        "-n", "--limit", type=int, default=8, metavar="N", help="Results per query (default: 8)"
    )
    args = parser.parse_args()
    run_queries(args.query, args.limit)
