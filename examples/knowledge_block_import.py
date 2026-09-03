"""Import markdown into reusable knowledge blocks."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ki_core.config import Config
from ki_knowledge.config_runtime import knowledge_db_path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ki_knowledge.integrations.block_embeddings import BlockEmbeddingService, SimpleBagOfWordsEmbeddingBackend
from ki_knowledge.integrations.knowledge_graph import KnowledgeGraph
from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.knowledge.generate import KnowledgeArtifactGenerator
from ki_knowledge.knowledge.ingest import KnowledgeIngestService


def default_knowledge_db_path() -> str:
    return str(knowledge_db_path(Config.from_env()))


def main() -> None:
    parser = argparse.ArgumentParser(description="Import markdown or iasem quiz sources into the knowledge store")
    parser.add_argument("path", help="Source file or directory to import")
    parser.add_argument(
        "--format",
        default="markdown",
        choices=["markdown", "iasem_quiz"],
        help="Source format to import",
    )
    parser.add_argument("--db", default=default_knowledge_db_path())
    parser.add_argument("--source-name", default=None)
    parser.add_argument("--embed", action="store_true", help="Build lightweight bag-of-words embeddings")
    parser.add_argument("--graph", action="store_true", help="Rebuild the graph from stored relations")
    parser.add_argument(
        "--generate",
        choices=["generated_quiz_module", "flashcard_set", "summary_note", "glossary", "study_guide"],
        action="append",
        default=[],
        help="Generate learning artifacts for each imported source",
    )
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"Path not found: {path}")
        sys.exit(1)

    store = KnowledgeStore(args.db)
    imported = 0
    imported_source_ids: list[str] = []
    if args.format == "markdown":
        if path.is_file():
            files = [path]
        else:
            files = sorted(path.glob("**/*.md"))

        if not files:
            print("No markdown files found.")
            sys.exit(1)

        for file_path in files:
            source_name = args.source_name or (file_path.relative_to(path).as_posix() if path.is_dir() else file_path.name)
            blocks = store.import_markdown_file(file_path, source_name=source_name)
            imported += len(blocks)
            imported_source_ids.append(f"markdown:{file_path.resolve()}")
        print(f"Imported {imported} blocks from {len(files)} markdown file(s)")
    else:
        if path.is_dir():
            files = sorted(path.glob("**/*.y*ml"))
        else:
            files = [path]
        if not files:
            print("No quiz YAML files found.")
            sys.exit(1)
        ingest = KnowledgeIngestService(store)
        for file_path in files:
            result = ingest.import_iasem_quiz_file(file_path)
            imported += int(result["blocks"])
            imported_source_ids.append(result["source_id"])
        print(f"Imported {imported} records from {len(files)} iasem quiz file(s)")

    if args.generate:
        generator = KnowledgeArtifactGenerator(store)
        for source_id in imported_source_ids:
            for artifact_type in args.generate:
                if artifact_type == "generated_quiz_module":
                    artifact = generator.generate_quiz_module(source_id)
                elif artifact_type == "flashcard_set":
                    artifact = generator.generate_flashcards(source_id)
                elif artifact_type == "summary_note":
                    artifact = generator.generate_summary_note(source_id)
                elif artifact_type == "glossary":
                    artifact = generator.generate_glossary(source_id)
                else:
                    artifact = generator.generate_study_guide(source_id)
                print(f"Generated {artifact.artifact_type}: {artifact.artifact_id}")

    if args.embed:
        count = BlockEmbeddingService(SimpleBagOfWordsEmbeddingBackend()).build_embeddings(store)
        print(f"Embeddings built for {count} blocks")

    if args.graph:
        graph = KnowledgeGraph(args.db)
        stats = graph.rebuild_from_store(store)
        print(f"Graph rebuilt: {stats['nodes']} nodes, {stats['edges']} edges")


if __name__ == "__main__":
    main()
