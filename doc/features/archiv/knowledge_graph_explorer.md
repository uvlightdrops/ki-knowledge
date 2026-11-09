---
project: ki-knowledge
agent_project: ki-knowledge
scope: features
created: "2026-09-02 07"
updated: "2026-11-08 01"
update_reason: "Jira-spezifisches Beispiel und überholte Quellenbehauptung archiviert"
status: archived
semantic_blocks:
  - purpose
  - features
  - environment
  - usage
  - note
relations:
  - target: README.md
    type: parent
    reason: "Archiv der Fachfunktionen"
  - target: graph_explorer.md
    type: reference
    reason: "Bereits geprüfte Beschreibung desselben Jira-Graphpfads"
---

# Knowledge Graph Explorer

> **Legacy:** Das angeführte Skript verwendet Jira-CSV, Jira-Cache und
> Jira-Graph; die unten behauptete allgemeine Quellenabdeckung ist falsch.
> Auch die unten aufgeführten Optionen und Variablennamen stimmen nicht mit
> dem Skript überein. Für die geprüfte historische Einordnung siehe
> [Graph Explorer](graph_explorer.md). Allgemeine Graphfunktionen bleiben
> davon unberührt.

<a id="purpose"></a>
## Purpose [purpose]

Build and inspect the knowledge graph from imported sources (CSV, Markdown, PDFs, Ontologies).

<a id="features"></a>
## Features [features]

- Rebuild graph from cache
- Count nodes and edges
- Show neighbors of any entity
- Export Cypher queries (for Neo4j or learning)

<a id="environment"></a>
## Environment Variables [environment]

- `KNOWLEDGE_DATA_ROOT` – Data directory
- `KNOWLEDGE_CACHE_DB` – SQLite cache path
- `KNOWLEDGE_GRAPH_DB` – Graph database path
- Optional: `KI_GRAPH_CYPHER_PATH` – Export location

<a id="usage"></a>
## Usage [usage]

```bash
# Show graph statistics
python examples/jira_graph_explorer.py

# Find neighbors of an entity
python examples/jira_graph_explorer.py --entity-id "some-entity-key"

# Export Cypher queries
python examples/jira_graph_explorer.py --export-cypher
```

<a id="note"></a>
## Note [note]

This tool was originally built for Jira CSV exports but now works with any imported knowledge source that creates graph relationships (Markdown blocks, PDFs, Ontologies).
