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
from ki_knowledge.integrations.embeddings import OllamaEmbeddingProvider, TFIDFEmbeddingProvider
from ki_knowledge.integrations.jira_assistant import JiraSupportAssistant
from ki_knowledge.integrations.jira_cache import JiraIssueCache
from ki_knowledge.integrations.jira_csv import JiraCSVImporter
from ki_knowledge.integrations.jira_graph import JiraKnowledgeGraph


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


def _jira_graph_db(config: Config) -> str:
    return os.getenv("JIRA_GRAPH_DB", config.knowledge_graph_db or str(_knowledge_root(config) / ".jira_graph.sqlite")).strip()


def _jira_embed_model(config: Config) -> str:
    return os.getenv("JIRA_EMBED_MODEL", config.knowledge_embed_model or "nomic-embed-text").strip()


def run_support_chat() -> None:
    config = Config.from_env()
    use_ollama = (
        os.getenv("USE_OLLAMA", "").lower() in ("1", "true", "yes")
        or not config.ki_api_key
        or not config.ki_base_url
        or config.ki_api_key in ("your-api-key-here", "dummy", "fake")
    )

    csv_path = _jira_csv_path(config)
    csv_encoding = os.getenv("JIRA_CSV_ENCODING", "utf-8-sig").strip() or "utf-8-sig"
    csv_delimiter = os.getenv("JIRA_CSV_DELIMITER", "").strip() or None
    cache_db = _jira_cache_db(config)
    refresh_cache = os.getenv("JIRA_CACHE_REFRESH", "true").lower() in ("1", "true", "yes")
    embedding_model = _jira_embed_model(config)
    use_hybrid = os.getenv("JIRA_USE_HYBRID_SEARCH", "true").lower() in ("1", "true", "yes")

    use_graph = os.getenv("JIRA_USE_GRAPH", "true").lower() in ("1", "true", "yes")
    graph_db = _jira_graph_db(config)

    if not csv_path:
        print(f"CSV path missing or not found: {csv_path}")
        print("Set JIRA_CSV_PATH or configure knowledge_data_root with jira/default/issues.csv")
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
