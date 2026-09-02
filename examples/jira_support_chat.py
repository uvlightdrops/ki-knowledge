"""Interactive support chat grounded on cached Jira CSV issues."""

from pathlib import Path
import os
import sys

# Allow direct execution via "python examples/jira_support_chat.py"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ki_core.adapters.ollama import OllamaClient
from ki_core.config import Config
from ki_core.core.models import ChatRequest, Message, Role
from ki_knowledge.integrations.embeddings import OllamaEmbeddingProvider, TFIDFEmbeddingProvider
from ki_knowledge.integrations.jira_assistant import JiraSupportAssistant
from ki_knowledge.integrations.jira_cache import JiraIssueCache
from ki_knowledge.integrations.jira_csv import JiraCSVImporter
from ki_knowledge.integrations.jira_graph import JiraKnowledgeGraph


def run_support_chat() -> None:
    config = Config.from_env()
    use_ollama = (
        os.getenv("USE_OLLAMA", "").lower() in ("1", "true", "yes")
        or not config.ki_api_key
        or not config.ki_base_url
        or config.ki_api_key in ("your-api-key-here", "dummy", "fake")
    )

    csv_path = os.getenv("JIRA_CSV_PATH", "").strip()
    csv_encoding = os.getenv("JIRA_CSV_ENCODING", "utf-8-sig").strip() or "utf-8-sig"
    csv_delimiter = os.getenv("JIRA_CSV_DELIMITER", "").strip() or None
    cache_db = os.getenv("JIRA_CACHE_DB", str(PROJECT_ROOT / ".jira_cache.sqlite")).strip()
    refresh_cache = os.getenv("JIRA_CACHE_REFRESH", "true").lower() in ("1", "true", "yes")
    embedding_model = os.getenv("JIRA_EMBED_MODEL", "nomic-embed-text").strip()
    use_hybrid = os.getenv("JIRA_USE_HYBRID_SEARCH", "true").lower() in ("1", "true", "yes")

    use_graph = os.getenv("JIRA_USE_GRAPH", "true").lower() in ("1", "true", "yes")
    graph_db = os.getenv("JIRA_GRAPH_DB", str(PROJECT_ROOT / ".jira_graph.sqlite")).strip()

    if not csv_path:
        print("CSV path missing in environment variables!")
        print("Set: JIRA_CSV_PATH=/path/to/jira-export.csv")
        return

    cache = JiraIssueCache(cache_db)
    if refresh_cache or cache.issue_count() == 0:
        issues = JiraCSVImporter.from_csv(
            csv_path,
            encoding=csv_encoding,
            delimiter=csv_delimiter,
        )
        ingested = cache.ingest_issues(issues)
        print(f"Cache updated: {ingested} issues")
    else:
        print(f"Using existing cache: {cache.issue_count()} issues")

    if use_ollama:
        backend = OllamaClient(
            base_url=config.ollama_base_url or "http://localhost:11434",
            model=config.ollama_model or "llama3.2",
        )
        print("Backend: Ollama")
    else:
        config.validate()
        raise RuntimeError("KI Server backend is not yet available in the extracted ki-knowledge project.")
        print("Backend: KI Server")

    embedding_backend = None
    if use_hybrid:
        try:
            ollama_embedder = OllamaEmbeddingProvider(
                base_url=config.ollama_base_url or "http://localhost:11434",
                model=embedding_model,
            )
            ollama_embedder.embed("probe")  # detect missing model early
            embedded = cache.build_embeddings(
                ollama_embedder,
                embedding_model=embedding_model,
            )
            embedding_backend = ollama_embedder
            print(f"Embeddings updated: {embedded} ({embedding_model})")
        except Exception as exc:
            print(f"⚠  Ollama embedding not available ({exc})")
            print("   Using local TF-IDF for hybrid search.")
            print("   For better quality: ollama pull nomic-embed-text")
            embedding_model = "tfidf"
            tfidf = TFIDFEmbeddingProvider()
            tfidf.fit(i.full_text for i in cache.list_issues(limit=5000))
            embedded = cache.build_embeddings(tfidf, embedding_model="tfidf")
            embedding_backend = tfidf
            print(f"TF-IDF embeddings built: {embedded}")

    graph = None
    if use_graph:
        graph = JiraKnowledgeGraph(graph_db)
        stats = graph.rebuild_from_cache(cache)
        print(f"Wissensgraph: {stats['nodes']} Knoten, {stats['edges']} Kanten")

    assistant = JiraSupportAssistant(
        backend=backend,
        cache=cache,
        embedding_backend=embedding_backend,
        embedding_model=embedding_model if embedding_backend else None,
        graph=graph,
    )
    print("Jira Support Chat aktiv. /ende zum Beenden.\n")

    while True:
        try:
            question = input("Du: ").strip()
        except EOFError:
            break
        if not question:
            continue
        if question == "/ende":
            break

        result = assistant.ask(question)
        print(f"\nAssistent: {result.answer}")
        if result.sources:
            print(f"Quellen: {', '.join(result.sources)}")
        else:
            print("Quellen: (keine Treffer)")
        if result.graph_expanded:
            print(f"Graph-ergänzt: {', '.join(result.graph_expanded)}")
        print()


if __name__ == "__main__":
    run_support_chat()
