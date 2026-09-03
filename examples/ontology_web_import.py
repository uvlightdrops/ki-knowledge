"""Fetch and parse ontology files from the web into the knowledge store."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ki_core.config import Config
from ki_knowledge.config_runtime import knowledge_db_path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.knowledge.ontology_ingest import (
    fetch_ontology_url,
    import_ontology_to_store,
)


def default_knowledge_db_path() -> str:
    return str(knowledge_db_path(Config.from_env()))


def main() -> None:
    parser = argparse.ArgumentParser(description="Import ontology file from web URL")
    parser.add_argument("url", help="Ontology URL (RDF/XML, Turtle, or JSON-LD)")
    parser.add_argument("--top", type=int, default=60, help="Top concepts to persist")
    parser.add_argument("--db", default=default_knowledge_db_path())
    args = parser.parse_args()

    print(f"Fetching ontology from {args.url}")
    text, content_type = fetch_ontology_url(args.url)

    store = KnowledgeStore(args.db)
    record_count, source_id = import_ontology_to_store(
        text,
        source_url=args.url,
        content_type=content_type,
        store=store,
        top_n=args.top,
    )
    print(f"Knowledge records imported: {record_count}")
    print(f"Source ID: {source_id}")


if __name__ == "__main__":
    main()
