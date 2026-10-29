# Knowledge Graph Explorer

## Purpose

Build and inspect the knowledge graph from imported sources (CSV, Markdown, PDFs, Ontologies).

## Features

- Rebuild graph from cache
- Count nodes and edges
- Show neighbors of any entity
- Export Cypher queries (for Neo4j or learning)

## Environment Variables

- `KNOWLEDGE_DATA_ROOT` – Data directory
- `KNOWLEDGE_CACHE_DB` – SQLite cache path
- `KNOWLEDGE_GRAPH_DB` – Graph database path
- Optional: `KI_GRAPH_CYPHER_PATH` – Export location

## Usage

```bash
# Show graph statistics
python examples/jira_graph_explorer.py

# Find neighbors of an entity
python examples/jira_graph_explorer.py --entity-id "some-entity-key"

# Export Cypher queries
python examples/jira_graph_explorer.py --export-cypher
```

## Note

This tool was originally built for Jira CSV exports but now works with any imported knowledge source that creates graph relationships (Markdown blocks, PDFs, Ontologies).
