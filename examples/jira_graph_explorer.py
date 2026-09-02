"""Build and inspect Jira knowledge graph from cached CSV issues."""

import argparse
from pathlib import Path
import os
import sys

# Allow direct execution via "python examples/jira_graph_explorer.py"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ki_core.config import Config
from ki_knowledge.integrations.jira_cache import JiraIssueCache
from ki_knowledge.integrations.jira_csv import JiraCSVImporter
from ki_knowledge.integrations.jira_graph import JiraKnowledgeGraph


def run_graph_explorer(sample_issue_key: str | None = None) -> None:
    Config.from_env()  # load .env

    csv_path = os.getenv("JIRA_CSV_PATH", "").strip()
    csv_encoding = os.getenv("JIRA_CSV_ENCODING", "utf-8-sig").strip() or "utf-8-sig"
    csv_delimiter = os.getenv("JIRA_CSV_DELIMITER", "").strip() or None
    cache_db = os.getenv("JIRA_CACHE_DB", str(PROJECT_ROOT / ".jira_cache.sqlite")).strip()
    refresh_cache = os.getenv("JIRA_CACHE_REFRESH", "true").lower() in ("1", "true", "yes")
    export_cypher_path = os.getenv("JIRA_GRAPH_CYPHER_PATH", "").strip()
    sample_issue_key = (sample_issue_key or os.getenv("JIRA_GRAPH_ISSUE_KEY", "")).strip()

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

    graph = JiraKnowledgeGraph(cache_db)
    stats = graph.rebuild_from_cache(cache)
    print(f"Graph rebuilt: {stats['nodes']} nodes, {stats['edges']} edges")

    if export_cypher_path:
        cypher = graph.export_cypher()
        Path(export_cypher_path).write_text(cypher, encoding="utf-8")
        print(f"Cypher export written: {export_cypher_path}")

    if not sample_issue_key:
        issues = cache.list_issues(limit=1)
        sample_issue_key = issues[0].key if issues else ""

    if not sample_issue_key:
        print("No issue available for traversal sample.")
        return

    neighbors = graph.issue_neighbors(sample_issue_key, limit=20)
    print(f"\nNeighbors for {sample_issue_key}:")
    for nb in neighbors:
        print(f"- {nb.relation} -> {nb.neighbor_id} (type={nb.neighbor_type}, w={nb.weight})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build and inspect the Jira knowledge graph")
    parser.add_argument(
        "issue_key",
        nargs="?",
        help="Issue key to inspect (fallback: JIRA_GRAPH_ISSUE_KEY, then first issue in cache)",
    )
    args = parser.parse_args()
    run_graph_explorer(args.issue_key)
